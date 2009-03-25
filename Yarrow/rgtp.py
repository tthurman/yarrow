"RGTP client library."

# Copyright (c) 2002 Thomas Thurman
# thomas@thurman.org.uk
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have be able to view the GNU General Public License at 
# http://www.gnu.org/copyleft/gpl.html ; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

import socket
import string
import md5
import binascii
import wrapping
import common

###########################################################

class RGTPException (Exception):
	"Houston, we have a problem."

	def __init__(self, name=''):
		self.name = name

	def __str__(self):
		return self.name

# And all the subclasses:

class RGTPTimeoutException(RGTPException):
	"Problem due to timeouts somewhere along the line."
	pass

class RGTPUpstreamException(RGTPException):
	"Problem with the RGTP server, as judged by us."
	pass

class RGTPServerException(RGTPException):
	"Problem with us, possibly as judged by the RGTP server."
	pass

class RGTPAuthException(RGTPException):
	"Authentication problems."
	pass

class AlreadyEditedError (RGTPException):
	"""Thrown after an attempt to modify an item
	which had been modified by someone else."""
	pass

class FullItemError (RGTPException):
	"Thrown after an attempt to add to a full item."
	pass

class UnacceptableContentError (RGTPException):
	"""Thrown if the server isn't happy with the text
we send. There are two public member fields: |problem| is
one of ['text','subject','grogname'], and |text| is the text
the server sent to complain."""

	def __init__(self, code, text):
		if code==423:
			self.problem = 'text'
		elif code==424:
			self.problem = 'subject'
		elif code==425:
			self.problem = 'grogname'
		else:
			raise 'unknown unacceptable content code: ' + code
			
		self.code = code
		self.text = text

###########################################################

class response:
	"One message from the server."

	def __init__(self, text, code=None):
		"Creates a response from a line of text received from the server."

		if code==None:
			try:
				self.numeric = int(text[0:3])
				self.textual = text[4:]
			except:
				self.numeric = -999
				self.textual = '(Weird bug finding:) ' +text
		else:
			self.numeric = code
			self.textual = text
		self.maybe_panic()

	def maybe_panic(self):
		if self.numeric==481:
			raise RGTPTimeoutException("Timeout: "+self.textual)
		elif self.numeric in (
			484,  # general rgtp server panic
			-999, # the panic code that yarrow assigns when
			#       the response is so malformed we can't get a
			#       code out of it
			):
			raise RGTPUpstreamException("Server internal error: "+self.textual)
		elif self.numeric in (
			500, # General mess-up
			510, # Unknown command
			511, # Wrong parameters
			512, # Line length problems
			582, # Dot-doubling problems
			):
			raise RGTPServerException("Broken client: "+self.textual)
		elif self.numeric in (530, 531):
			raise RGTPAuthException("Permission denied. (Try logging in with a privileged account?): "+self.textual)

	def code(self):
		return self.numeric

	def text(self):
		return self.textual

	def __str__(self):
		return str(self.numeric) + " " + self.textual

###########################################################

class callback:
	"The 'base' class gives RGTP messages to callbacks of this form."

	def __call__(self, message):
		"""Deals with an incoming RGTP message.
|message| is of type Message."""
		pass

	def done(self):
		"""Returns 1 iff 'base' can throw this callback away now.
This will not be checked until __call__() has been called at least once."""
		return 1

###########################################################

class expect(callback):
	"""Callback that expects a message with a certain RGTP code number;
the callback finishes quietly if the first message has that number, and
throws an exception if it does not."""
	def __init__(self, expectation):
		self.desideratum = expectation

	def __call__(self, message):
		if message.code() != self.desideratum:
			raise "Expected %s, but got %s." % (
				str(self.desideratum),
				message,
				)

###########################################################

class multiline(callback):

	def __init__(self):
		self.finished = 0

	def complete(self):
		self.finished = 1

	def done(self):
		return self.finished

###########################################################

class stomach(multiline):
	def __init__(self):
		multiline.__init__(self)
		self.stuff = []

	def __call__(self,message):
		self.eat(message)

	def eat(self,message):
		if message.code()==250:
			pass # data coming up-- good
		elif message.code()==-1:
			self.stuff.append(message.text())
		elif message.code()==0:
			self.complete()
		else:
			raise RGTPException("Wasn't expecting " + str(message))

###########################################################

class base:
	"Basic RGTP handling."

	def __init__(self, host, port, cback, logging):
		self.logging=logging
		self.log=''
		self.state = 0
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.connect((host, port))
		self.incoming = sock.makefile("r")
		self.outgoing = sock.makefile("w")
		self.cback = cback
		self.get_line()

	def get_line(self):
		looping = 1

		while looping:
			temp = ''

			# Read from the client until we get a response.
			while len(temp)==0:
				temp = self.receive()
				message = response(temp)
				self.cback(message)

			if message.code()==250: # Magic value for continuations
				while temp!='.':
					temp = self.receive()
					if temp!='.':
						self.cback(response(temp, -1))
				self.cback(response('', 0))

			# okay. Ask whether we should go round again.
			looping = not self.cback.done()

	def receive(self):
		temp = string.rstrip(self.incoming.readline())
		if self.logging: self.log = self.log + "\n<" +temp
		return temp

	def raw_send(self, message):
		"Simply sends one line to the server."
		self.outgoing.write(message + "\r\n")
		self.outgoing.flush()
		if self.logging:
			self.log = self.log + "\n>"+message

	def send(self, message, cback):
		"Sends one line to the server, and waits for a response."
		self.cback = cback
		self.raw_send(message)
		self.get_line()

###########################################################

class fancy:
	"Encapsulated RGTP."

	base = 0
	access_level = 0

	def __init__(self, host, port, logging):
		class first_connect(callback):
			access_level = 0
			def __call__(self, message):
				self.access_level = message.code()-230

		towel = first_connect()
		self.base = base(host, port, towel, logging)
		self.access_level = towel.access_level

	def login(self, email, sharedsecret = None):

		class authorise(multiline):

			def __init__(self, base, email, sharedsecret):
				multiline.__init__(self)
				self.clientnonce = common.random_hex_string()
				self.hash = md5.new()
				self.base = base
				self.email = email[0:16]
				while len(self.email)<16:
					# pad with nuls if it's <16 bytes
					self.email += '\0'
				self.sharedsecret = sharedsecret

			def __call__(self, message):
				if message.code()==333:
					def inverted_bitstring(x):
						result = ""
						for i in range(len(x)):
							result = result + chr(255-ord(x[i]))
						return result
					self.hash.update(binascii.unhexlify(self.clientnonce))
					self.hash.update(binascii.unhexlify(message.text()))
					self.hash.update(self.email)
					self.hash.update(inverted_bitstring(binascii.unhexlify(self.sharedsecret)))
					self.base.send("AUTH "+self.hash.hexdigest()+" "+self.clientnonce, self)
				elif message.code()==133:
					pass # ummm...
				elif message.code()==483:
					raise RGTPException("Authentication failed ("+message.text()+")")
				elif message.code()==130:
					pass # ignore this
				elif message.code()>=230 and message.code()<=233:
					self.access_level = message.code()-230
					self.complete()
				elif message.code()==482 or message.code()==483 or message.code()==432 or message.code()==433:
					raise RGTPException("Failed to log you in - " + message.text())
				else:
					raise RGTPException("Wasn't expecting " + str(message))

		towel = authorise(self.base, email, sharedsecret)
		self.base.send("USER "+email, towel)
		self.access_level = towel.access_level

	def request_account(self, email):
		class regu_handler(stomach):

			def __init__(self):
				stomach.__init__(self)

			def __call__(self, message):
				if message.code()==100:
					pass # probably best to ignore this
				elif message.code()==482 or message.code()==280:
					successful = message.code()==280
					self.answer = (successful, message.text())
				elif message.code()==250:
					pass # good, that's what we want
				elif message.text()=='' or message.text()[0]==' ':
					self.eat(response(message.text()[1:], message.code()))

		towel = regu_handler()
		self.base.send("REGU", towel)
		if email!=None:
			self.base.send("USER "+email, towel)
			return towel.answer
		else:
			return towel.stuff

	def motd(self):
		towel = stomach()
		self.base.send("MOTD", towel)
		return towel.stuff

	def index(self, since=None, since_is_date=0):
		class index_reader(multiline):
			def __init__(self):
				multiline.__init__(self)
				self.result = []

			def __call__(self, message):
				if message.code()==-1:
					b = message.text()
					self.result.append((string.strip(b[0:8]), string.strip(b[9:17]),
						string.strip(b[18:26]), string.strip(b[27:102]),
						b[103], string.strip(b[105:])))
				elif message.code()==0:
					self.complete()

		towel = index_reader()
		if since:
			if since_is_date:
				request = 'INDX %08x' % (since)
			else:
				request = 'INDX #%08x' % (since)
		else:
			request = 'INDX'

		self.base.send(request, towel)
		return towel.result

	def logout(self):
		if self.access_level != 0:
			self.base.send("QUIT", expect(280))
			self.access_level = 0

	def __del__(self):
		self.logout()

	def item(self, id):
		class item_reader(multiline):
			def __init__(self):
				multiline.__init__(self)
				self.result = []
				self.firstline = 0
				self.buffer = ''
				self.subject = ''

			def put_buffer(self):
				if self.buffer!='':
					lines = string.split(self.buffer, '\n')
					grogname = ''
					author = ''
					date = ''

					# Firstly, there'll be "item" or "reply" lines.
					# (Perhaps we should complain if there aren't.)
					if lines[0][0:5]=='Item ':
						date = lines[0][19:]
						lines = lines[1:]
					elif lines[0][0:11]=='Reply from ':
						date = lines[0][11:]
 						lines = lines[1:]

					atpos = string.rfind(date, ' at ')
					if atpos != -1:
						author = date[:atpos]
						date = date[atpos+4:]

					# "From" introduces an explicit grogname.
					if lines[0][0:5]=='From ':
						grogname = lines[0][5:]
						lines = lines[1:]

					# If the server tells us a subject, ignore it;
					# we'll have other ways of finding that out.
					if lines[0][0:9]=='Subject: ':
						lines = lines[1:]

					# Right. If we don't know the grogname by now,
					# it might have been short enough to go into the
					# author field.
					if grogname=='':
						openbracket = string.rfind(author, '(')
						if openbracket!=-1 and author[-1]==')':
							# Ah, so it was.
							grogname = author[:openbracket-1]
							author = author[openbracket+1:-1]
						else:
							# Well, just give them the address again.
							grogname = author

					self.result.append({'grogname': grogname,
						'date': date,
						'author': author,
						'message': lines,
						'sequence': self.sequence,
						'timestamp': self.timestamp})
					self.buffer=''

			def __call__(self, message):
				if message.code()==-1:
					text = message.text()
					if self.firstline:
						self.firstline = 0
						# should parse it, but...
						self.result.append(text)

					elif text!='' and text[0]=='^' and text[1]!='^':
						self.put_buffer()
						if len(text)==18:
							self.sequence = int(text[1:9], 16)
							self.timestamp = int(text[10:18], 16)
					else:
						if text!='' and text[0] in ['^', '.']:
							text = text[1:]
						self.buffer=self.buffer+text+"\n"
				elif message.code()==0:
					self.put_buffer()
					self.complete()
				elif message.code()==410:
					raise "No such item"
				elif message.code()==250:
					self.firstline = 1

		towel = item_reader()
		self.base.send("ITEM "+id, towel)
		return towel.result

        def raise_access_level(self, target=None, user=None, password=None, tryGuest=0):
		# Set target==None to get as high as we can with current
		# credentials.
                if target==None or target > self.access_level:
			# If they want more than they already have...
                        if user!=None and user!='':
				# They have a username. Fine: use it.
                                self.login(user, password)
		                if target!=None and target > self.access_level:
					raise RGTPException(user + " doesn't have a high enough access level.")
                        else:
				# No username. Hmm, maybe we can try the "guest" trick.
                                if tryGuest and (target==None or target==1) and self.access_level==0:
                                        self.login("guest", 0)
                                else:
					if target!=None:
	                                        raise RGTPException("You need to log in for that.")

		# So, did it work?
                if target > self.access_level:
			raise RGTPException("Sorry: try logging in with a more privileged account.");

	def stat(self, id):
		class status_reader(callback):
			def __call__(self, message):
				if message.code()==211:
					self.result = message.text()
				elif message.code()==410:
					raise RGTPException("Not available: "+message.text())
				else:
					raise RGTPException("Wasn't expecting " + str(message))

		def maybe_blank(thing):
			if thing=='        ':
				return None
			else:
				return thing

		def maybe_hex(thing):
			if thing==None:
				return None
			else:
				return int(thing, 16)

		towel = status_reader()
		self.base.send("STAT "+id, towel)
		r = towel.result
		return {'from': maybe_blank(r[0:8]),
			'to': maybe_blank(r[9:17]),
			'edited': maybe_hex(maybe_blank(r[18:26])),
			'replied': maybe_hex(maybe_blank(r[27:35])),
			'subject': r[36:] }

	def send_data(self, grogname, message):
		class dumper(multiline):

			def __init__(self, name, data, base):
                                multiline.__init__(self)
				self.name = name
				self.data = data
				self.base = base

			def __call__(self, message):
				def dot_doubled(line):
					if line!='' and line[0]=='.':
						# Dot-doubling: if it already
						# begins with a dot, it needs
						# another.
						return '.' + line
					else:
						return line

				if message.code()==150:
					# The server says "go ahead".
					# So here goes!
					self.base.raw_send(
						dot_doubled(self.name))
					for paragraph in self.data:
						for line in wrapping.wrap(paragraph):
							self.base.raw_send(dot_doubled(line))
					# All done!
					self.base.raw_send('.')
				elif message.code() in [423, 424, 425]:
					# server's not happy with
					# something we said
					raise UnacceptableContentError(
						message.code(),
						message.text())
				elif message.code()==350:
					self.complete()
				else:
					raise("Wasn't expecting " + str(message))

		self.base.send('DATA', dumper(grogname, message, self.base))

	def post(self, item, subject):
		"""
If item is None, this is a NEWI.
If item is not None and subject is None, this is a REPL.
If item is not None and subject is not None, this is a CONT.

On success, returns a dictionary with keys "itemid" and "sequence".

Failure cases:
 Throws AlreadyEditedError if this item has been edited.
   (You should check for the item having been edited already
    yourself, as well; there are cases this function won't
    pick up (such as editing which doesn't cause continuation).
 Throws FullItemError if this item is full (so you must CONT).
 Throws UnacceptableContentError if the content is unacceptable
    (it could be a bad subject or grogname, or something to
    do with the text).
"""

		class item_generator(multiline):
			"Callback for post()."

			def __init__(self, itemid):
                                multiline.__init__(self)
				self.itemid = itemid
				self.sequence = None

			def __call__(self, message):
				if message.code()==120:
					# A new itemid for us.
					self.itemid = message.text()

				elif message.code()==122:
					# continuation information
					# (it'll go to 422, below)

					# Because we're so stateless
					# around here, we can throw
					# this information away. If anyone
					# wants to use this library for more
					# general purposes, I'll add code to
					# capture it.

					pass

				elif message.code()==220:
					# Success code, and sequence number.
					self.sequence = int(
						message.text()[:8],16)
					
					# woohoo! all done
					self.complete()
					
				elif message.code()==421:
					# it's overflowing!
					raise FullItemError()

				elif message.code()==422:
					# it's overflowed!
					raise AlreadyEditedError()

				elif message.code() in [423, 424, 425]:
					# server's not happy with
					# something we said
					raise UnacceptableContentError(
						message.code(),
						message.text())

				else:
					raise("Wasn't expecting " +
					      str(message))

		towel = item_generator(item)
		if item==None:
			self.base.send('NEWI '+subject, towel)
		else:
			try:
				self.base.send('REPL '+item, towel)
			except FullItemError, fie:
				if subject!=None:
					# ah, we don't need to return an error:
					# we were given a subject in case
					# this happened. Use it.
					towel = item_generator(item)
					self.base.send('CONT '+subject, towel)
				else:
					# So we don't know what to do about
					# full items. Let's hope the
					# caller does.
					raise fie

		# Looks like it all worked.
		return {"itemid": towel.itemid,
			"sequence": towel.sequence}

	def edit_log(self):
		class edit_log_reader(multiline):
			def __init__(self):
				multiline.__init__(self)
				self.state = 0
				self.result = []

			def __call__(self, message):
				if message.code()==-1:
					if self.state==0:
						b = string.split(message.text())
						self.change = {}

						if b[0]=="Item":
							self.change['item'] = b[1]
							b=b[2:]
						elif b[0]=="Index":
							b=b[1:]
						else:
							raise RGTPException('Unexpected stuff in edit log')

						self.change['action'] = b[0]
						self.change['editor'] = b[2]
						self.change['date'] = string.join(b[4:9])
#						self.change['sequence'] = b[9][2:10]
						if len(b)>9:
							self.change['sequence'] = b[9]
						else:
							# Very old versions of IWJ's rgtp didn't
							# supply this.
							self.change['sequence'] = ''
					elif self.state==1:
						self.change['reason'] = message.text()
						self.result.append(self.change)

					self.state = (self.state+1)%3

				elif message.code()==0:
					self.complete()

		towel = edit_log_reader()
		self.base.send("ELOG", towel)
		return towel.result

	def diff(self, itemid):
		"""
Returns the changes made by an editor to an item.
|itemid| may be None, in which case the index is diffed."""
		class diff_reader(multiline):
			def __init__(self):
				multiline.__init__(self)
				self.state = 0
				self.result = []

			def __call__(self, message):
				if message.code()==-1:
					self.result.append(message.text())
				elif message.code()==0:
					self.complete()

		towel = diff_reader()
		if itemid:
			self.base.send("DIFF "+itemid, towel)
		else:
			self.base.send("DIFF", towel)
		return towel.result

	def literal(self, strings):
		"Sends a series of literal commands to the server. Ignores the results."

		dummy = callback()

		for thing in strings:
                        if thing!='':
				self.base.send(thing, dummy)

	def udbm(self, command=''):
		towel = stomach()
		command = ('UDBM '+command).strip()
		self.base.send(command, towel)
		return towel.stuff

	def set_motd(self):
		"Sets the MOTD to the data you most recently sent."
		# FIXME: should maybe return the new sequence number.
		# not much use for it at present, though.
		self.base.send('MOTS', expect(220))

################################################################

# need to add fields for:
# datestamp of last eat()
class interpreted_index:
	"bah. explain this. i don't feel like explaining it atm."

	def __init__(self):
		self.index = {}
		self.last_sequences = { 'all': 0 }
		self.version = 1
		self.c_line = None

	def eat(self, lines):
		for line in lines:

			sequence = int(line[0], 16)
			if sequence>self.last_sequences['all']:
				self.last_sequences['all'] = sequence

			if line[4] in ['I','R','C','F']:
				if not self.index.has_key(line[2]):
					self.index[line[2]] = {'date': 0,
							       'count': 0,
							       'subject': 'Unknown',
							       'live': 1 }
					self.last_sequences[line[2]] = 0

				if line[4]!='F' and sequence > self.last_sequences[line[2]]:
					self.last_sequences[line[2]] = sequence

				if line[4] in ['I','C']:
					self.index[line[2]]['subject'] = line[5]

				if self.index[line[2]]['date'] < int(line[1],16):
					self.index[line[2]]['date'] = int(line[1],16)
					self.index[line[2]]['from'] = line[3]



				if line[4]!='F' and sequence > self.last_sequences[line[2]]:
					self.last_sequences[line[2]] = sequence

				if line[4] in ['I','C']:
					self.index[line[2]]['subject'] = line[5]

				if line[4]=='C':
				    self.c_line = line

				if self.index[line[2]]['date'] < int(line[1],16):
					self.index[line[2]]['date'] = int(line[1],16)
					self.index[line[2]]['from'] = line[3]

				if line[4]=='F':
					self.index[line[2]]['live'] = 0
					self.index[line[2]]['parent'] = self.c_line[2]
					self.index[self.c_line[2]]['child'] = line[2]

				self.index[line[2]]['count'] = self.index[line[2]]['count'] + 1

			elif line[4]=='M':
				self.last_sequences['motd'] = sequence

	def items(self):
		# throw if version!=1?
		return self.index

	def sequences(self):
		return self.last_sequences
