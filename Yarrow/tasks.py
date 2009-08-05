"Tasks that the web front end may carry out"

# Copyright (c) 2002-9 Thomas Thurman
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

################################################################

import cgi
import re
import string
import rgtp
import cache
import common
import time
import user
import config
import random
import os

################################################################

# METHODS WHICH SHOULD PROBABLY GO IN THE SUPERCLASS OR IN YARROW

def mailto(address, linking=0):
	"""Returns an HTML snippet containing a mailto link for
the given address. Correctly handles the GROGGS-specific special
cases of spqr1@cam and spqr@foo. (We assume that all RGTP servers
other than GROGGS use only the full network domain.)"""

	# _Just_ in case we have any addresses with &s in...
	address = cgi.escape(address)

	if not linking:
		return address # that was easy...

	atpos = address.find('@')

	if atpos==-1:
		# no @-sign!
		return address # only sensible answer, really

	domain = address[atpos+1:]
	suffix = ''

	if domain=='cam':
		# Generic Cambridge address
		suffix = '.ac.uk'
	elif domain.find('.')==-1:
		# Cambridge department or college or similar
		suffix = '.cam.ac.uk'

	# mild spam-trap:
	address = address.replace('@','&#64;').replace('.','&#46;')

	return '<a class="uid" href="mailto:%s%s">%s</a>' % (address,
							     suffix,
							     address)

def html_print(message, grogname, author, time, y, seq=None):
	"""Prints one of the sections of an item which contains
	one reply and the banner across the top."""

	# First: the banner across the top...

	if grogname:
		print '<table class="reply" width="100%"><tr>'

		print '<th rowspan="2">' + linkify(y, grogname) + '</th>'
		print '<td>' + mailto(author, y.uidlink)
		if seq:
			print '<a href="#'+ seq +'" class="seq">' +\
			      '(#'+seq+')</a>'
		print '</td></tr>'
		print '<tr><td>' + time + '</td></tr></table>'

	# Get rid of useless whitespace...
	while len(message)!=0 and message[0]=='': message = message[1:]
	while len(message)!=0 and message[-1]=='': message = message[:-1]

	# And now for some real content.

	print '<p>'
	for line in message:
		print linkify(y, line)
		if y.reformat:
			if line=='':
				print '</p><p>'
		else:
			# We're not reformatting, so just
			# break at the ends of lines.
			print '<br>'
	print '</p>'

def linkify(y, text):
	"""Adds hyperlinks to |text|. Automatically calls cgi.escape()
	on the text for you."""

	temp = cgi.escape(text)
	temp = re.sub(r'\b([A-Za-z]\d{7})\b',
		      y.html_for_matched_itemid,
		      temp)
	temp = re.sub('(http:([A-Za-z0-9_+~#/?=%.,-]|&amp;)*)(?!<)',
		      r'<a href="\1">\1</a>',
		      temp)
	temp = re.sub('(ftp:([A-Za-z0-9_+~#/?=%.,-]|&amp;)*)(?!<)',
		      r'<a href="\1">\1</a>',
		      temp)
	temp = re.sub('(gopher:([A-Za-z0-9_+~#/?=%.,-]|&amp;)*)(?!<)',
		      r'<a href="\1">\1</a>',
		      temp)
	temp = re.sub('([A-Za-z0-9._+-]*@[A-Za-z0-9._+]+)',
		      r'<a href="mailto:\1">\1</a>',
		      temp)
	# I was considering allowing www.anything to be an http link,
	# but that starts interfering with the text when it's already
	# in a link. Odd that links can't nest, isn't it?

	return temp

def http_status_from_exception(e):
	"""Returns a properly-formatted Status: line for return
	in the CGI headers. The line will contain a HTTP status
	code as defined in RFC2616 section 10. It will no longer
	contain the actual text "Status: ", though."""
	n = '404'
	ec = e.__class__

	if ec is rgtp.RGTPTimeoutException:
		# 503: Service Unavailable
		# Note that this isn't 504 (Gateway Timeout)
		# since this is returned when the RGTP server
		# times US out, not when we time THEM out.
		n = '503'
	elif ec is rgtp.RGTPUpstreamException:
		# 502: Bad Gateway
		n = '502'
	elif ec is rgtp.RGTPServerException:
		# 500: Internal Server Error; our bad
		n = '500'
	elif ec is rgtp.RGTPAuthException:
		# You'd think this would be 403: Forbidden...
		# but actually it makes more sense for it
		# to be 200: OK, because people need to see the
		# "visitor" button, and the error code can make
		# intermediate agents hide the http body.
		# (In particular, it means you can't set any browse
		# page as a Freshmeat demo site.)
		n = '200'
	else:
		# no idea about this one.
		# Make it something generic.
		n = '500'

	return '%s %s' % (n, str(e))

################################################################

class handler_ancestor:
    def print_login_form(self, y):
	    print '<h1>Log in to '+y.server+'</h1>'+\
		'<p>Please enter your '+y.server+' email address and '+\
		'password (sometimes called a "shared secret").</p>'+\
		'<form action="' +\
		y.uri('login') +\
		'" method="post">' +\
		'<table>' +\
		'<tr><td>Email address (looks like "spqr1@cam.ac.uk"):</td> '+\
		'<td><INPUT TYPE="text" NAME="userid"></td>'+\
		'</tr>' +\
		'<tr><td>Password (looks like "E12AB567CD"):</td> '+\
		'<td><INPUT TYPE="text" '+\
		'NAME="secret"></td>'+\
		'</tr>' +\
		'<tr><td>Remember my login ' +\
		'on this computer.</td>' +\
		'<td><INPUT TYPE="checkbox" ' +\
		'CHECKED NAME="remember"><br>'+\
		'(You probably want to leave this turned on, ' +\
		'unless you\'re using a public workstation.) ' +\
		'</td></tr><tr><td colspan="2" align="right">' +\
		'<input type="submit" value=" OK "></td></tr>' +\
		'</table></form>'+\
		'<p>If you don\'t have an account on '+y.server+\
		', you may <a href="'+y.uri('newbie')+'">get one '+\
		'here</a>.</p>'+\
		'<p>If you have an account on '+y.server+\
		', but have forgotten your password, please <a href="'+y.uri('motd')+\
		'">contact the Editors</a>, who will be happy to '+\
		'assist you.</p>'+\
		'<p>You will need cookies ' +\
		'enabled from here on in.</p>'

    def you_should_be_logged_in(self, y):
	"""Prints appropriate warnings if y requires you to be logged in
	and you're not. Returns whether we recommend they should be
	prevented from continuing.  This is called from the body()
	methods of various task classes; it should possibly be
	replaced by a general check of the privilege() method."""

	result = 0

	if y.user:
		# They're logged into yarrow.

		who_they_are = y.user.state(y.server, 'userid', '')

		if not who_they_are:
			# ... but we have no details for them on this
			# server.

			if y.connection.access_level==0:
				print """<p>Sorry, this server doesn't
permit guest users. You'll have to <a href="%s">apply for
an account</a> if you want to use it.</p>""" % (
	y.uri('newbie', None, 1))

			if y.user.username!='Visitor':
				print """
<p><b>Already have a %s ID?</b>
<a href="%s">Set it up</a> in order to post.<br>
<b>Don't have a %s ID?</b>
<a href="%s">Apply for one!</a></p>""" % (
			    y.server,
			    y.uri('config'),
			    y.server,
			    y.uri('newbie', None, 1),
			    )

			if y.connection.access_level==0:
				# Can't go any further, then.
				result = 1
	else:
		# They're not logged in to yarrow.
		# Can we give them satisfaction anyway?
		if y.connection.access_level==0:
			# No. But at least we can point them
			# in the right direction.
			print """
<p>You're trying to view a page from %s, which
doesn't permit anonymous browsing.</p>""" % (y.server)
			self.print_login_form(y)
			result = 1

		# Otherwise they have guest access anyway,
		# which is just about as good.

	if not y.is_real_user() and y.connection.access_level==1:
	        print '<p>To post or reply, you\'ll need to '+\
		'<a href="%s">log ' % (y.uri('login', None, 1)) +\
		'in</a>. Even if '+\
		'you don\'t want to post, it\'s worth logging in, '+\
		'because then Yarrow can highlight any unread '+\
		'gossip for you.</p>'

	return result

    def title(self):
        """Returns the name displayed in the sidebar for this task.
	Returns None if the task should not be displayed in the
	sidebar."""
        name = self.__class__.__name__
        if not name.endswith('_handler'):
            return ''
        else:
            return '_'+name[:-8]

    def sortkey(self):
        """Returns a key to sort the task by in the sidebar."""
	# default is alphabetical order
        return self.__class__.__name__

    def privilege(self):
        """Returns the minimum privilege needed to use the task:
        3 = only usable by Editors
	2 = only usable by people with write access
        1 = usable by people with read access
        0 = usable at all times, even when logged out
        -1 = usable only when logged out
	-2 = usable by all users, but needs login; always shown
	in sidebar, though, even if logged out (so they know what
	would be possible if they logged in).

	XXX FIXME
	Change this:
	This does not stop the task being called; it's only used
	to decide what to display in the sidebar.  For the actual
	access control, see the you_should_be_logged_in() method,
	amongst others."""
	# the default is by far the most common case
        return 1

################################################################

class read_handler(handler_ancestor):

	def head(self, y):

		try:
			# fixme: This stat is wasteful. We can pick all this
			# up from a[0].

			self.status = y.connection.stat(y.item)
			y.title = self.status['subject']
			self.item = y.connection.item(y.item)
		except rgtp.RGTPException, r:
			print http_status_from_exception(r)
			y.title = str(r)
			self.status = None
			self.item = None

	def print_item(self, y):
		for i in self.item[1:]:

			seq = "%x" % (i['sequence'])
			
			print '<hr class="invisible"><a name="'+seq+'"></a>'
			html_print(i['message'], i['grogname'],
				   i['author'],
				   time.strftime("%a %d %b %Y %I:%M:%S%P",
						 time.localtime(i['timestamp'])),
				   y,
				   seq)
			print '<a name="after-'+seq+'"></a>'

	def possibly_link(self, y, title, key, anchor):
		"""If we have a continuation in direction 'key',
		prints a link to it."""
		target = self.status[key]
		if target:
			try:
				name = y.connection.stat(target)['subject']
				print '<p><i>(%s <a href="%s">%s</a>)</i></p>' % (
					title,
					y.uri(target + anchor),
					name)

			except rgtp.RGTPException:
				print '<p><i>(%s item %s, which is no longer available.)</i></p>' % (title, target)

	def body(self, y):

		print '<h1>%s</h1>' % (linkify(y, y.title))

		if self.you_should_be_logged_in(y):
			return

		if y.user and not y.user.last_sequences.has_key(y.server):
			y.user.last_sequences[y.server] = {} # Stop errors below...

		if self.item:
			self.possibly_link(y,
				      'Continued from', 'from', '#end')

			self.print_item(y)
			
			self.possibly_link(y, 'Continued in', 'to', '')

			print '<a name="end"></a>'

			# It's possible that we'll have to include some
			# text in the posting box. If the user previously
			# supplied some gossip but there was a collision,
			# we're required to show again it here.

			if y.user:
				collision_debris = y.user.state(y.server,
								y.item+'-collision',
								None)
			else:
				collision_debris = ''

			if y.connection.access_level > 1:
				# They do at least have the capability to post.

				if self.status['to']==None:
					# This item has no continuation, so...
					print '<hr>'

					if collision_debris:
						print '<p><b>Collision:</b> '+\
						      'You previously posted '+\
						      'some gossip, which '+\
						      'didn\'t appear '+\
						      'because of a '+\
						      'collision. Read '+\
						      'what\'s new above, '+\
						      'and change your '+\
						      'gossip below '+\
						      'as necessary.</p>'
						
					y.show_posting_box(self.status['replied'],
							   None,
							   collision_debris)
				else:
					if collision_debris:
						print '<p><b>Collision:</b> '+\
						      'You previously posted '+\
						      'some gossip, which '+\
						      'didn\'t appear '+\
						      'because of a '+\
						      'collision. However, '+\
						      'this item has been '+\
						      'continued since '+\
						      'then. If you carry on '+\
						      'to the next item, '+\
						      'your text will appear '+\
						      'in the posting box.</p>'

						y.user.set_state(y.server,
								 self.status['to']+'-collision',
								 collision_debris)

			if collision_debris:
				y.user.clear_state(y.server,
						   y.item+'-collision')
				y.user.save()

		if y.user and \
			self.status and \
			(not y.user.last_sequences[y.server].has_key(y.item) or \
				y.user.last_sequences[y.server][y.item] != self.status['replied']):

			# When they last read this entry, there was a
			# different number of replies. Update their record
			# with the new number they've seen.

			y.user.last_sequences[y.server][y.item] = self.status['replied']
			y.user.save()

	      	y.print_hop_list()

		# List some other places they might be interested in going.
		
		print '<ul class="others">'

		if self.status and (self.status['from'] or self.status['to']):
			print '<li>Read <a href="%s">this ' % (
				y.uri(y.item + '/thread')) +\
				'whole thread</a> in a printer-friendly format.</li>'

		print '<li>Return to <a href="%s">the %s index</a>.</li>' % (
                    y.uri(''),
                    y.server.title())

		print '</ul>'

        def title(self):
            return None

################################################################

class thread_handler(read_handler):

	def head(self, y):

		try:
			self.collated = cache.index(y.server, y.connection).items()

			corrected = None

			# FIXME: Eh? Isn't this back to front? Fix!
			if self.collated[y.item].has_key('child'):

				while self.collated[y.item].has_key('child'):
					y.item = self.collated[y.item]['child']

				corrected = '%s%s/%s/%s/thread' % (
					os.environ['SERVER_NAME'],
					os.environ['SCRIPT_NAME'],
					y.server,
					y.item)

			if not self.collated[y.item].has_key('child') \
			   and not self.collated[y.item].has_key('parent'):

				# No parents or children, so no threading.

				corrected = '%s%s/%s/%s' % (
					os.environ['SERVER_NAME'],
					os.environ['SCRIPT_NAME'],
					y.server,
					y.item)

			if corrected:
				y.fly.set_header('Status',
						 '301 A long, long time ago.')
				y.fly.set_header('Location',
						    'http://'+corrected)
				y.fly.send_only_headers()

			self.status = y.connection.stat(y.item)
			y.title = self.status['subject'] + ' (and following)'
			self.item = y.connection.item(y.item)
		except rgtp.RGTPException, r:
			y.title = str(r)

	def body(self, y):

		if self.you_should_be_logged_in(y):
			return

		if y.user and not y.user.last_sequences.has_key(y.server):
			y.user.last_sequences[y.server] = {} # Stop errors below...

		while y.item:
			print '<a name="item-'+y.item+'"></a>'
			print '<h1>'+ linkify(y, y.connection.stat(y.item)['subject'])
			print '(<a href="#item-'+y.item+'">'+y.item+'</a>)</h1>'
			print '<ul class="others"><li>'
			print '<a href="'+y.uri(y.item)+'">'
			print 'See just this item</a></li></ul>'

			self.print_item(y)

			if self.collated[y.item].has_key('parent'):
				y.item = self.collated[y.item]['parent']
				self.item = y.connection.item(y.item)
			else:
				y.item = 0
			
			# We don't count this as reading for the purposes of
			# determining read-ness of an item, so we don't update
			# the item's status.

		print '<a name="end"></a>'
		# You can't post from here, so we don't add the posting box.
	      	y.print_hop_list()

################################################################

class motd_handler(handler_ancestor):
        "Show the system status, and how to get in contact with the Editors."
	def head(self, y):
		y.title = y.server + ' message of the day'

	def body(self, y):
		print '<h1>'+y.server+' message of the day</h1>'
		if y.form.has_key('data') and y.is_post_request() and y.connection.access_level > 2:
			self.set_it(y)
		else:
			self.get_it(y)

	def set_it(self, y):
		y.connection.send_data('yarrow', # discarded
				       string.split(y.form['data'].value, '\r\n'))
		y.connection.set_motd()
		print '<p>Okay, the message of the day is now changed.</p>'

	def get_it(self, y):
		# FIXME: a thought. yarrow could have its own motd method,
		# which updated the sequence number for when the user last
		# saw the motd as a side-effect, and did the [1:]
		# automatically.
		# (maybe also have a param "return None if the sequence
		# is <= N")

		motd = y.connection.motd()[1:]
		
		html_print(motd, None, None, None, y)

		# Editors get extra stuff:
		if y.connection.access_level > 2:
			print """
<hr>
<p>If you'd like to modify the message of the day,
please enter the new text into the box below.</p>
<form action="%s" method="post">
<textarea style="width: 99%%" cols="50"
class="textbox" rows="10" name="data">""" % (
				y.uri('motd'))
			for line in motd:
				print line
			print '</textarea>'
			print '<input type="submit" value=" Modify "></form>'

        def title(self):
            return '_status'

        def privilege(self):
            return 0

################################################################

class browse_handler(handler_ancestor):
        "An overview of the gossip on this server."
	def head(self, y):
		try:
			y.collater = cache.index(y.server, y.connection)
			y.title = y.server + ' index'
		except rgtp.RGTPException, r:
			print http_status_from_exception(r)
			y.title = str(r)			

	def body(self, y):

		def we_should_show_motd(y, sequences):
			"Whether we should show the MOTD this time."

			if not y.user:
				return 1
			
			whether = y.user.state(y.server, 'motd', 0)

			if whether=='always':
				return 1
			elif whether=='never':
				return 0
			else:
				# So we only show it if it's changed.

				if y.user.last_sequences[y.server].get('motd')==sequences.get('motd'):
					return 0
				elif not sequences.has_key('motd'):
					# Weird, but possible
					return 0
				else:
					y.user.last_sequences[y.server]['motd']=sequences['motd']
					y.user.save()
					return 1
		
		if self.you_should_be_logged_in(y):
			return

		if not y.collater:
			print '<p>%s</p><p>(Try' % (
				y.title)
			print '<a href="%s">reconfiguring</a>?)</p>' % (
				y.uri('config'))
			return

		index = y.collater.items()
		sequences = y.collater.sequences()
		keys = y.collater.keys()

		if y.user and not y.user.last_sequences.has_key(y.server):
			# Stop errors below...
			y.user.last_sequences[y.server] = {}

		if we_should_show_motd(y, sequences):
			html_print(y.connection.motd()[1:],
				   None,
				   '',
				   '',
				   y)

		################################################################
		# Work out slice sizes.

		sliceStart = 0
		sliceSize = 20
		if y.form.has_key('unsliced'):
			sliceSize = len(keys)

		if y.form.has_key('slice'):
			try:
				sliceSize = int(y.form['slice'].value)
			except:
				pass
				
		if y.form.has_key('skip'):
			try:
				sliceStart = int(y.form['skip'].value)
			except:
				pass
		
		keys = keys[sliceStart:sliceSize+sliceStart]

		################################################################
		# The JavaScript parent/child highlighting.
		#
		# Work out family relationships.
		
		js_family = []
		scanned = {}

		for n in keys:
			if not n in scanned.keys():

				# Find the oldest ancestor.
				cursor = n
				while index[cursor].has_key('parent'):
					cursor = index[cursor]['parent']

				# OK, now find all its kids (that are on screen)

				family = [cursor]
				while index[cursor].has_key('child'):
					cursor = index[cursor]['child']
					family.append(cursor)
					scanned[cursor] = 1

				family = [x for x in family if x in keys]

				if len(family)!=1:
					js_family.append("'%s'" % (string.join(family,' ')))
		del scanned
		
		print '<script><!--'
		print "var m = [%s];" % (string.join(js_family,",\n"))
		print 'function b(i, c) { document.getElementById(i).setAttribute("class",c); }'
		print 'function g(f, i, c) { for (var k in f) { if (f[k]!=i) b(f[k], c); } }'
		print 'function s(i, c) { for (var j in m) { if (m[j].indexOf(i)!=-1) g(m[j].split(" "), i, c); } }'
		print 'function r(i) { s(i.getAttribute("id"), "related"); }'
		print 'function u(i) { s(i.getAttribute("id"), ""); }'
		print '//-->'
		print '</script>'

		print '<table width="100%" class="browse">'
		print '<tr><th>On</th><th>#</th><th>Most recently by</th>'

		if y.accesskeys & 2:
			print '<th>Alt</th>'

		print '<th>About</th></tr>'

		################################################################
		# Print the list.

		accesskeycount = 0

		for k in keys:
			line = index[k]

			jumps_are_to_end = 0

			if y.is_real_user():
				if y.user.last_sequences[y.server].get(k)>=sequences.get(k):
					highlight = 0
					jumps_are_to_end = 1
				else:
					highlight = 1
			else:
				# No user information, so don't bother highlighting.
				highlight = 0

			if highlight and y.user.last_sequences[y.server].has_key(k):
				anchor = '#after-%x' % (
					y.user.last_sequences[y.server][k])
			elif jumps_are_to_end:
				anchor = '#end'
			else:
				anchor = ''

			if line['live']:
				most_recently_from = mailto(line['from'], y.uidlink)
			else:
				# Don't show "most recently by" on
				# posts that have been continued.
				most_recently_from = '-- continued above'

			# Any access key?
			accesskey_html = ''
			accesskey_display = ''

			if highlight and y.accesskeys & 2:
				# If the item is HLd, but it has a parent
				# which is also HLd, there is no access key
				# and we display a downward-pointing arrow.

				highlight_parent = 0

				if line.has_key('child'):
					parent = line['child'] # FIXME

					if y.user.last_sequences[y.server].get(parent)<sequences.get(parent):
						highlight_parent = 1

				if highlight_parent:
					accesskey_display = '&darr;'
				else:
					if accesskeycount<10:
						accesskeycount += 1
						n = accesskeycount
						if n==10:
							n = 0
						accesskey_html = ' accesskey="%d" ' % (n)
						accesskey_display = '<b><kbd>%d</kbd></b>' % (n)
					else:
						accesskey_display = '&gt;'

			print '<tr><td>%s</td>' % (
				common.neat_date(line['date']) )
			print '<td><i>%d</i></td>' % (
				line['count'])
			print '<td class="uid">%s</td>' % (
				most_recently_from)
			if y.accesskeys & 2:
				print '<td>%s</td>' % (
					accesskey_display)
			print '<td class="subject"><a id="%s"%s' % (
				k,
				accesskey_html) +\
			'onmouseover="r(this)" onmouseout="u(this)" '+\
			'href="%s">' % (y.uri(k + anchor))

			print ('<i>', '')[line['live']] +\
			      ('', '<b>')[highlight] +\
			      cgi.escape(line['subject']) +\
			      ('', '</b>')[highlight] +\
			      ('</i>', '')[line['live']]

			print '</a></td></tr>'

		################################################################
		# Print footers.

		colcount = 4
		if (y.accesskeys & 2): colcount = 5

		print '<tr><td colspan="%d" align="center">' % (colcount)

		if sliceStart+sliceSize < len(index):
			print '<a href="%s?skip=%d">&lt;&lt; Earliest</a> |' % (
				y.uri(),
				len(index)-sliceSize)
			
			print '<a href="%s?skip=%d">&lt; Previous</a> |' % (
				y.uri(),
				sliceStart+sliceSize)
		
		print 'Items %d-%d of %d' % (sliceStart+1,
					      sliceStart+len(keys),
					      len(index))

		if y.form.has_key('unsliced'):
			 print '| <a href="%s">Most recent</a>' % (y.uri())
		else:
			 print '| <a href="%s?unsliced=1">All</a>' % (y.uri())

		if sliceStart - sliceSize >= 0:
			if sliceStart==sliceSize:
				print '| <a href="%s">Next &gt;</a>' % (
					y.uri())
			else:
				print '| <a href="%s?skip=%d">Next &gt;</a>' % (
					y.uri(),
					sliceStart-sliceSize)
	
			print '| <a href="%s">Newest &gt;&gt;</a>' % (
				y.uri())
		
		print '</td></tr>' +\
		      '<tr><td colspan="%d" align="center">' % (colcount) +\
		      '( <a href="' + y.uri('post') +\
		      '">Post a new message</a> )</td></tr></table>'

################################################################

class wombat_handler(handler_ancestor):
	def head(self, y):
		y.title = 'The wombat'

	def body(self, y):
		print """<h1>The wombat</h1>
<p>Mary had a little lamb.<br>They met in unarmed combat,<br>
and (for the sake of rhyming verse)<br>it turned into a wombat.</p>"""

        def title(self):
            return None

        def privilege(self):
            return 0

################################################################

class random_handler(handler_ancestor):
        "Jump to a random piece of gossip."
	def head(self, y):
		itemids = cache.index(y.server, y.connection).items().keys()
		if itemids:
			target = random.choice(itemids)
			y.fly.set_header('Status', '301 Random')
			y.fly.set_header('Location', y.uri(target))
			y.fly.send_only_headers()

	def body(self, y):
		# if you got here...
		print "There are no items, so you cannot go to one."

        def sortkey(self):
            return 'catchzzz' # after "catch up"

################################################################

class post_handler(handler_ancestor):
	"Create new gossip." # Also handles replying to existing gossip.

	def head(self, y):
		y.title = 'Post to %s' % (y.server)

	def body(self, y):

		if y.connection.access_level < 2:
			print '<h1>You don\'t have permission to post.</h1>'

			if not y.is_real_user():
				print '<p>Maybe you should try '+\
				'<a href="%s">logging ' % (
					y.uri('login', None, 1),
					) +\
				'in</a>.</p>'

			print '<p>You might want to '+\
			      '<a href="%s">return ' % (
				y.uri(),
				) +\
			      'to the index</a>.</p>'

			return
		
		if y.form.has_key('data'):
			self.submit(y)
		else:
			self.form(y)

	def submit(self, y):
		if y.form.has_key('from'):
			name = y.form['from'].value
		else:
			name = '' # just use a blank

		if y.form.has_key('subject'):
			subject = y.form['subject'].value
		else:
			subject = None

		if y.item!='':
			item = y.item
		else:
			item = None

		if (not subject) and (not item):
			print '<h1>You must give a subject</h1>'
			print '<p>You cannot post an item without a subject.'
			print 'Please try again.</p>'
			y.show_posting_box(None,
					   '',
					   y.form['data'].value)
			return

		try:
			if y.form.has_key('sequence'):
				# They've requested some sanity checks:
				# the item hasn't been continued, and
				# its reply number matches a certain sequence number.
				currently = y.connection.stat(y.item)
				if currently['to'] or \
				   (int(y.form['sequence'].value,16) !=
				    currently['replied']):
					# Then it's been edited.
					raise rgtp.AlreadyEditedError()

			y.connection.send_data(name,
					       string.split(y.form['data'].value,
							    '\r\n'))
			details = y.connection.post(item, subject)

			# Success! Work out the URL of the new posting.
			print '<h1>Added gossip</h1>'
			print 'Your gossip was added. You can view it ' +\
			      '<a href="%s#%x">here</a>.' % (
				y.uri(details['itemid']),
				details['sequence'])

			if y.readmyown:
				# We've read our own comments; update the
				# "most recent sequence" number of this item
				# to show so.

				y.user.last_sequences[y.server][details['itemid']]=details['sequence']
				y.user.save()

			y.print_hop_list()

		except rgtp.AlreadyEditedError:
			# Nope, someone's been there before us.

			y.user.set_state(y.server,
					 item+'-collision',
					 y.form['data'].value)
			y.user.save()
			
			print '<h1>Collision</h1>'
			print '<p>Sorry, someone posted a reply in the time'
			print 'between when you read the item and when you'
			print 'submitted your reply. Carry on and'
			print '<a href="'+y.uri(item)+'">read what\'s new</a>;'
			print 'you\'ll see your reply already filled in there,'
			print 'and you can modify it as necessary and post it'
			print 'if you still want to.</p>'

		except rgtp.FullItemError:
			print '<h1>That item\'s full</h1>'
			print '<p>You need to start a new item. Edit your text'
			print 'if needs be, and think of an appropriate new subject'
			print 'line.</p>'
			y.show_posting_box(None, '', y.form['data'].value)

		except rgtp.UnacceptableContentError, uce:
			print """
<h1>%s</h1>
<p>The server isn't happy with %s. It says:</p><blockquote>%s</blockquote>
<p>Please fix the problem and try again.</p>""" % (
				uce.text,
				{
				'text': 'the text of your posting',
				'subject': 'the subject of your posting',
				'grogname': 'your grogname',
				} [uce.problem],
				uce.text);

			y.show_posting_box(None,
					   subject,
					   y.form['data'].value)

	def form(self, y):
		print '<h1>Post a new item</h1>'
		y.show_posting_box()

        def sortkey(self):
            return 'browsezzz' # immediately after "browse"

	def privilege(self):
            return 2

################################################################

class editlog_handler(handler_ancestor):
        "View all edits made by the Editors."

	def head(self, y):
		y.title = y.server + ' edit log'

	def body(self, y):
		if self.you_should_be_logged_in(y):
			return

		print """
<h1>Edit log</h1>
<p>Only editors have the power to change the entries that
other users have made on an RGTP server. When they do edit
something, it shows up here so that everyone can know that
a change has been made. Editors usually also add a note to
the item itself, to explain.</p>
<table width="100%">
<tr>
<th>Item</th>
<th>Date</th>
<th>Action</th>
<th>Editor</th>
<th>Reason</th>
</tr>"""

		edits = y.connection.edit_log()
		edits.reverse()

		for thing in edits:
			print '<tr>'
			if thing.has_key('item'):
				print '<td>'
				if thing['action']=='withdrawn':
					print thing['item']
				else:
					print linkify(y, thing['item'])
				print '</td>'
			else:
				print '<td><a href="%s">' % (
					y.uri())
				print '<i>index</i></a></td>'
			print '<td>'+thing['date']+'</td>'
			print '<td>'+thing['action']+'</td>'
			print '<td>'+thing['editor']+'</td>'
			print '<td>'+linkify(y, thing['reason'])+'</td>'
			print '</tr>'
		print '</table>'

        def title(self):
            return 'show&nbsp;_edits'

################################################################

class user_validator(handler_ancestor):
	def validate_user(self, y):
		"""Grabs the userid and shared-secret from the form, and
		runs some basic checks on them. May print error messages.
		Does not check that they're real on the server, just
		that they're formatted correctly."""

		if y.form.has_key('userid'):
			userid = y.form['userid'].value
		else:
			userid = None

		# Remove spaces. (Maybe an RE would have been prettier.)
		if y.form.has_key('secret'):
			secret = string.join(string.split(y.form['secret'].value),'')
		else:
			secret = ''

		# Check for its not being a hex number.
		if not re.search('^[0-9A-Fa-f]*$', secret):
			print '<h1>Invalid secret</h1>'
			print '<p>Sorry, the shared-secret you gave wasn\'t valid.'
			print 'Secrets may contain only the digits 0 to 9,'
			print 'the letters A to F, and spaces. Case doesn\'t matter.'
			print 'If you copied the secret from an email, double-check'
			print 'that it was copied correctly.'
			y.try_again()
			return None

		if len(secret)%2==1:
			print '<h1>Invalid secret</h1>'
			print '<p>Sorry, the shared-secret you gave wasn\'t valid.'
			print 'Secrets must contain an even number of letters or numbers;'
			print 'yours had %d, which is very odd.' % (len(secret))
			y.try_again()
			return None

		return (userid, secret)

	def is_real_account(self, host, port, userid, secret):
		"""Tests that the userid and secret are valid accounts
		on the remote system, with at least read-only access.
		Returns the access level, or 0 if they are not valid"""
		test_connection = rgtp.fancy(host, port, 1)
		try:
			# We need at least a 1.
			test_connection.raise_access_level(1, userid, secret)

			result = test_connection.access_level
			test_connection.logout()
			return result
		except rgtp.RGTPException:
			return 0

	def show_congratulations(self, y):
		print '<h1>Success!</h1>'
		print '<p>Thank you. You now have'
		print ['no','read-only','normal read and append','full editor'][y.connection.access_level]
		print 'access to %s.</p>' % (y.server)

################################################################

class config_handler(user_validator):
        "Configure how Yarrow behaves for you."

	def head(self, y):
		y.title = 'Options for %s' % (y.server)

	def body(self, y):
		if not y.is_real_user():
			print '<p>Sorry, you can\'t set the options for'
			print 'a server unless you'
			print '<a href="%s">log in to' % (
				y.uri('login', None, 1))
			print 'it</a>.</p>'
			return

		if y.form.has_key("yes"):
			self.submit(y)
		else:
			self.form(y)

	def form(self, y):
		def meta_field(y, field):
			result = y.user.state(y.server, field, '')
			if result==None:
				return ''
			else:
				return result

		print '<h1>How to access '+y.server+'</h1>'

		print '<h2>Logging in</h2>'
		print '<form action="'+y.uri('config')+'" method="post">'
		print '<p>Firstly, please give a user-ID and shared-secret to use'
		print 'on this server.  You use these to log into Yarrow.'
		print 'You should have received an email'
		print 'from the '+y.server+' editors telling you what your'
		print 'shared-secret is.</p>'
		print '<table>'
		print '<tr><td>User-ID:</td>'
		print '<td><INPUT TYPE="text" NAME="userid" value="%s"></td></tr>' % (meta_field(y, 'userid'))
		print '<tr><td>Shared-secret:</td>'
		print '<td><INPUT TYPE="text" NAME="secret" value="%s"></td></tr>' % (meta_field(y, 'secret'))
		print '</table>'

		print '<h2>Grogname</h2>'
		print '<p>Your grogname is a short piece of text which identifies you. It\'s'
		print 'similar to a nameline on <a href="http://mono.org">Monochrome</a> or'
		print 'a title on <a href="http://ewtoo.org">talkers</a>. You always have'
		print 'the chance to set a grogname wherever you can use one, but here you'
		print 'get the chance to set a default one.</p>'
		print '<p>If you list more than one (on separate lines), yarrow will'
		print 'pick a random one for you each time.</p>'
		print '<textarea cols="75" rows="5" name="grogname">'

		grognames = y.user.state(y.server, 'grogname', '')
		if grognames:
			for name in grognames:
				print '%s' % (name)
		else:
			print 'The Wombat'
		print '</textarea>'

		print '<h2>Reformatting</h2>'
		print '<p>If you like, yarrow can attempt to reformat the text received'
		print 'from the server so that it fills the width of your screen.'
		print 'Otherwise, the text will be displayed just as the server'
		print 'sends it.</p>'

		if meta_field(y, 'reformat')==1:
			reformatting_checked = ' checked'
		else:
			reformatting_checked = ''

		print '<p><input type="checkbox" name="reformat"%s> Reformat text.</p>' % (
			reformatting_checked)

		always_checked = updated_checked = never_checked = ''
		motd_status = meta_field(y, 'motd')
		if motd_status=='always':
			always_checked = ' checked'
		elif motd_status=='never':
			never_checked = ' checked'
		else:
			updated_checked = ' checked'

		print """<h2>Message of the Day</h2>
<p>Should yarrow show the message of the day on the index page?
(You can always see it by clicking the "status" link in the sidebar, too.)</p>

<p><input type="radio" name="motd" value="always"%s>Always show the MOTD.<br>
<input type="radio" name="motd" value="updated"%s>Only show the MOTD when
it's been updated.<br>
<input type="radio" name="motd" value="never"%s>Never show
the MOTD.</p>""" % (
	always_checked,
	updated_checked,
	never_checked,
	)
                print '<h2>Logging</h2>'
		if meta_field(y, 'log')==1:
			logging_checked = ' checked'
		else:
			logging_checked = ''

		print """<p>Show what messages were passed between us and the RGTP server
to generate each page. Unless you're hugely interested in
<a href="http://www.groggs.group.cam.ac.uk/groggs/protocol.txt">RGTP
nargery</a>, you probably don't want this turned on.</p>

<p><input type="checkbox" name="log"%s> Show RGTP logs.</p>
""" % (
	logging_checked)


		checked = ''
	        if meta_field(y, 'uidlink')!=0:
			checked = ' checked'

		print '<h2>Linking userids</h2>'
		print '<p>Yarrow can turn userids into hyperlinks; this is mostly useful,'
		print 'but with some kinds of browser it just gets annoying.</p>'
		print '<p><input type="checkbox" name="uidlink"%s>' % (checked)
		print 'Linkify userids.</p>'
		
		checked = ''
	        if meta_field(y, 'readmyown')!=0:
			checked = ' checked'

		print '<h2>Marking your own gossip as unread</h2>'
		print '<p>When you post to this server, do you want your own contributions'
		print 'to be marked as read as soon as you post them? If you leave this'
		print 'turned off, they will stay unread until you actually read them,'
		print 'just like contributions from anyone else.</p>'
		print '<p><input type="checkbox" name="readmyown"%s>' % (checked)
		print 'Mark that I\'ve read anything I post.</p>'

		print '<h2>Access keys</h2>'
		print '<p>If you like, some of the links in Yarrow can be accessed'
		print 'from the keyboard. Sometimes this gets in the way, though,'
		print 'so it can be turned off. On PCs, you usually press Alt and'
		print 'the access key together; the Mac uses Ctrl instead.</p>'

		accesskeys = meta_field(y, 'accesskeys')
		if accesskeys=='':
			accesskeys = 3

		checked = ''
		if accesskeys & 1: checked = ' checked'
		
		print '<p><input type="checkbox" name="accessaction"%s>' % (checked)
		print 'Use access keys for common actions (<u>b</u>rowse, <u>p</u>ost,'
		print 'etc.).<br> The access key will be shown underlined in the sidebar'
		print 'on the right.<br>'

		checked = ''
		if accesskeys & 2: checked = ' checked'

		print '<input type="checkbox" name="accesshop"%s>' % (checked)
		print 'Use access keys for the unread-item list at the end of'
		print 'each item.<br>The list will be numbered, and the access key'
		print 'will be the number shown. (For example, the access key'
		print 'of the first entry is 1.)<br>This also adds a column'
		print 'giving access keys for the unread items on'
		print 'the index page.</p>'
		
                print '<input type="submit" value=" OK ">'
		print '<input type="hidden" name="yes" value="y">'
		print '</form>'

	def submit(self, y):
		def put_meta_field(y, field, value):
			y.user.set_state(y.server, field, value)

		(userid, secret) = self.validate_user()

		# Right. Before we can treat this as valid, we must attempt to log in
		# using it, and see what happens. (Since this is separate from the
		# main RGTP session, we don't log it.) [FIXME: If we did, would it
		# work anyway? Should it? Find out.]

		if userid:
			level = self.is_real_account(host, port, userid, secret)

			if level:
				put_meta_field(y, 'userid', userid)
				put_meta_field(y, 'secret', secret)

				y.connection.access_level = result
				self.show_congratulations(y)
			else:
				print '<h1>Authentication failure</h1>'
				print '<p>That doesn\'t appear to be a registered shared-secret'
				print 'on %s.' % (y.server)
				y.try_again()
				print '</p>'
				return
		else:
			put_meta_field(y, 'userid', userid)
			put_meta_field(y, 'secret', secret)
		
		grognames = []
		# [] is also what they get if they've specified no grognames.

		if y.form.has_key('grogname'):
			original = string.split(y.form['grogname'].value,
						'\r\n')

			# Now weed out the bad ones: too long, say, or blank.
			for name in original:
				if len(name)>75:
					print '<p>'+name
					print ' is too long to be a grogname. Ignored.</p>'
				elif name!='':
					grognames.append(name)

		put_meta_field(y, 'grogname', grognames)

		# FIXME generalise this and put it into a loop
		if y.form.has_key('reformat') and y.form['reformat'].value=='on':
			put_meta_field(y, 'reformat', 1)
		else:
			put_meta_field(y, 'reformat', 0)

		if y.form.has_key('motd') and y.form['motd'].value in ('always','never'):
			put_meta_field(y, 'motd', y.form['motd'].value)
		else:
			put_meta_field(y, 'motd', 'updated')

		if y.form.has_key('log') and y.form['log'].value=='on':
			put_meta_field(y, 'log', 1)
		else:
			put_meta_field(y, 'log', 0)

		if y.form.has_key('uidlink') and y.form['uidlink'].value=='on':
			put_meta_field(y, 'uidlink', 1)
		else:
			put_meta_field(y, 'uidlink', 0)

		if y.form.has_key('readmyown') and y.form['readmyown'].value=='on':
			put_meta_field(y, 'readmyown', 1)
		else:
			put_meta_field(y, 'readmyown', 0)

		accesskeys = 0
		if y.form.has_key('accessaction') and y.form['accessaction'].value=='on':
			accesskeys += 1
		if y.form.has_key('accesshop') and y.form['accesshop'].value=='on':
			accesskeys += 2
		put_meta_field(y, 'accesskeys', accesskeys)
		y.accesskeys = accesskeys # so it affects the success message too
			
		y.user.save()

		print """
<p>You probably want to go and <a href="%s">read
some gossip</a> now.</p>""" % (y.uri())

	def privilege(self):
		return -2

################################################################

class unknown_command:
	def head(self, y):
		y.title = "Unknown command - " + y.verb
		# This is quite legitimately 404-- since pages are
		# named after commands, you've specified a page which
		# doesn't exist.
		y.fly.set_header('Status','404 Unknown command')

	def body(self, y):
		print '<h1>Unknown command</h1>'
		print '<p>I don\'t know how to %s.' % (y.verb)
		print 'Try starting from <a href="%s">the top</a>.</p>' % (
			y.uri(None, ''))

################################################################

class unknown_server_login:
	def __init__(self, server_name):
		self.server_name = server_name

	def head(self, y):
		y.title = "Unknown server - " + self.server_name
		y.fly.set_header('Status','404 Unknown server')

	def body(self, y):
		print '<h1>Unknown server</h1>'
		print '<p>I don\'t know a server named '+self.server_name+'.'
		print '(Here\'s <a href="%s">the servers I do know</a>.)</p>' % (
			y.uri(None, ''))

################################################################

class failed_login:
	def head(self, y):
		y.title = "Login failed!"

	def body(self, y):
		print '<h1>Password failure</h1>'
		print '<p>That\'s not your password!</p>'

################################################################

class rgtp_error_login:
	def head(self, y):
		y.title = y.logging_in_details

	def body(self, y):
		print '<h1>RGTP error</h1>'
		print '<p>Sorry; I couldn\'t do what you asked, because:</p>'
		print '<blockquote>%s</blockquote>' % (
			y.logging_in_details)
		if y.server:
			print '<p>Perhaps you could try <a href="%s">reconfiguring</a>.</p>' % (
				y.uri('config'))

################################################################

class login_handler(user_validator):
        "Log into this server."

	def head(self, y):
		y.title = "Log in to "+y.server
		self.status = self.handle_potential_logging_in(y)

	def handle_potential_logging_in(self, y):
		"""Returns
		'accepted' if the user was logged in successfully,
		'failed' if they weren't,
		and 'not' if the user wasn't attempting to log in."""

		(username, secret) = self.validate_user(y)

		if not secret:
			return 'not'

		if y.form.has_key('remember') and y.form['remember'].value:
			# Ten years or so
			expiry = 60*60*24*365*10
		else:
			# As soon as you close the browser
			expiry = 0

		# So they have entered a username/secret.
		# Find whether it's real, and what the privileges are.
		y.connection.access_level = self.is_real_account(y.server_details['host'],
								 y.server_details['port'],
								 username, secret)
		if y.connection.access_level==0:
			return 'failed'

		# OK, so they're logging in.
		possible = user.from_userid_and_secret(username, secret, y.server)

		if possible:
			y.accept_user(possible, 1, expiry)
			return 'accepted'

		# So it must be a real account that we don't yet know.
		# Create a Yarrow account so we can track them.
		y.accept_user(user.create(username, secret, y.server),
			      1, expiry)
		return 'accepted'

	def body(self, y):
		if self.status=='accepted':
			# Since all they asked for was to log in,
			# we needn't take them straight to any
			# particular page.
			self.show_congratulations(y)

			ret = y.return_target()

			if ret:
				print '<a href="' +\
				      y.uri(None, '') +\
				      cgi.escape(ret) +\
				      '">Carry on from where you left off.</a>'
			else:
				print 'You probably ' +\
				      'want to go and look for <a href="' +\
				      y.uri(None, None) +\
				      '">some gossip</a> to read.</p>'

		elif self.status=='failed':
			print '<h1>Login failed</h1>'+\
			    '<p>You can either <a href="'+y.uri('login')+\
			    '">try again</a>, '+\
			    'or <a href="'+y.uri('motd')+'">ask the Editors '+\
			    'for help</a>.</p>';
		else:
			# not trying to log in; invite them to try
			self.print_login_form(y)

        def title(self):
            return 'log&nbsp;_in'

        def privilege(self):
            return -1

################################################################

class logout_handler(handler_ancestor):
        "Log out of this server."
	def head(self, y):
		y.title = "Log out of yarrow"
		y.clear_session()
		y.user = None

	def body(self, y):
		# force no privileges
		# (FIXME: this is wrong, because
		# they might have level=1 when logged out)
		y.connection.access_level = 0
		print """
<h1>Logged out</h1>
<p>You're now logged out.</p>"""

        def title(self):
            return 'log&nbsp;_out'

        def sortkey(self):
            return 'zzz' # last of all.

################################################################

class serverlist_handler(handler_ancestor):
	def head(self, y):
		y.title = 'Choose an RGTP server'

	def body(self, y):
		print '<h1>First off, choose yourself a server.</h1><dl>'

		servers = config.all_known_servers()
		server_names = servers.keys()
		server_names.sort()

		for server in server_names:
			print '<dt><a href="%s">%s</a></dt><dd>%s</dd>' % (
				y.uri(None, server),
				server,
				servers[server]['description'])

		print '</dl>'
	
		print '<h1>Interested in adding to these?</h1>'
		print '<p>You can'
		print '<a href="https://launchpad.net/spurge">download</a>'
		print 'and run your own RGTP server.'
		print 'If you know of any servers not listed above,'
		print 'please <a href="mailto:thomas@thurman.org.uk">'
		print 'let us know</a>.</p>'

        def title(self):
            return None

        def privilege(self):
            return 0

################################################################

class newbie_handler(handler_ancestor):
        "Creates an account on this server."
	def head(self, y):
		y.title = 'Request a %s account' % (y.server)

	def body(self, y):
		print '<h1>New %s account</h1>' % (y.server)

		if y.form.has_key('newbie'):
			# We have a name. Try to create an account with that name.
			result = y.connection.request_account(y.form['newbie'].value)

			if result[0]:
				print '<h2>Success!</h2>'
			else:
				print '<h2>Account creation failed</h2>'
				
			print '<p><i>%s</i></p>' % (result[1])

			if result[0]:
				print '<p>Check your email for a message '+\
				      'from the %s server.</p>' % (y.server)
			else:
				# Didn't work. Print helpful messages if we
				# can shed any light on what's going wrong.
				
				if result[1].find('contains non-alphanums')!=-1:
					print '<p><b>Note:</b> This may be '+\
					      'caused by a problem with the '+\
					      'RGTP protocol. Addresses which'+\
					      ' contain dots before the "@" '+\
					      'may not be allowed by '+\
					      'pedantic servers. If this is '+\
					      'indeed the problem, try '+\
					      'getting a redirect or webmail '+\
					      'address which doesn\'t have '+\
					      'the same problem (for '+\
					      'example, from one of the many'+\
					      ' <a href="http://dmoz.org/'+\
					      'Computers/Internet/'+\
					      'E-mail/Free/">free '+\
					      'email providers</a>).</p>'


			print '<p>If you\'d like to contact a human to '+\
			      'discuss this, the Editors\' email addresses '+\
			      'are usually listed in <a href="'+\
			      y.uri('motd') +\
			      '">the server\'s message of the day</a>.</p>'

			ret = y.return_target()

			if ret:
				print '<a href="' +\
				      y.uri(None, '') +\
				      cgi.escape(ret) +\
				      '">Carry on from where you left off.</a>'
		else:
			# They haven't given us a username. So we give them a form
			# to fill in. Firstly, get the warning text, by doing an
			# account request and then bailing before we give them a
			# name.
			
			warning = y.connection.request_account(None)
			
			print '<p><b>Please read this before ' +\
			      'continuing:</b></p><p>'
			
			for line in warning:
				print cgi.escape(line) + '<br>'
				
			print '</p>' +\
			      '<form action="' + y.uri('newbie') + '" ' +\
			      'method="post">' +\
			      '<input type="text" name="newbie">' +\
			      '<input type="submit" value=" Apply "></form>'
        def title(self):
            return None # no need to show this in the list

        def privilege(self):
            return -1

################################################################

class users_handler(handler_ancestor):
        "Edit the users database."
	def head(self, y):
		y.title = 'Modify user settings on '+y.server

	def body(self, y):
		print '<h1>%s user database manager</h1>' % (
			y.server)
		
		if y.connection.access_level < 3:
			# Errrr nope. You need to be an editor to do this.
			print 'You need to be an editor to use the database manager.'
			return
		
		command = ''
		if y.form.has_key('command'):
			command = y.form['command'].value

		response = y.connection.udbm(command)
		print """
<form action="%s" method="post">
<input type="text" name="command">
<input type="submit" value=" OK "></form>
<pre>%s</pre>""" % (
			y.uri('users'),
			cgi.escape(string.join(response,'\n')))

                if response == []:
			# GROGGS's udbm often returns a success code
			# but no text on success.
			print '<i>(Looks like that was successful.)</i>'

        def title(self):
            return '_accounts'

        def privilege(self):
            return 3

################################################################

class catchup_handler(handler_ancestor):
        "Mark all gossip on this server as read."

	def head(self, y):
		y.title = 'Catch up with %s' % (y.server)

	def body(self, y):
		print '<h1>Catch up with %s</h1>' % (y.server)

		if y.form.has_key('yes') and y.is_post_request():
			# Note that this catches us up to *now*, rather than
			# wherever we were when the user read the index last.
			# The difference is a few seconds, usually, but might
			# be significant occasionally. I'm not sure what we
			# should do about it, though.

			y.user.last_sequences[y.server] = \
				cache.index(y.server, y.connection).sequences()
			y.user.save()

			print '<p>OK, done. Now, you probably want to'
		else:
			print '<p>If you press this button, all gossip '+\
			      'on %s will be marked as "read".</p>' % (y.server) +\
			      '<form action="%s" method="post">' % (y.uri('catchup')) +\
			      '<input type="hidden" name="yes" value="y">' +\
			      '<input type="submit" value=" I mean it! "></form>' +\
			      '<p>Or you could just'

		print 'go back to <a href="%s">the %s index</a>.</p>' % (
			y.uri(), y.server)

        def title(self):
            return 'catch&nbsp;_up'