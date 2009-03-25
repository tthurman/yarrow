#!/usr/bin/python
#
#  yarrow - (yet another retro reverse-ordered website?)
#  v0.40
#
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

import shelve
import md5
import common
import smtplib
import config

users_file = '/var/lib/yarrow/users'
sessions_file = '/var/lib/yarrow/sessions'

class AlreadyExistsException(Exception):
	"Thrown when you attempt to create a user that already exists."
	pass

def hash_of(password):
	temp = md5.new()
	temp.update(password)
	return temp.hexdigest()

class user:
	def __init__(self, username):
		self.username = username
		self.metadata = {}
		self.last_sequences = {}
		self.version = 1

	def __str__(self):
		return self.username

	def set_state(self, server, field, value):
		if not self.metadata.has_key(server):
			self.metadata[server] = {}

		self.metadata[server][field] = value

	def state(self, server, field, default):
		if self.metadata.has_key(server) and \
		  self.metadata[server].has_key(field):
			return self.metadata[server][field]
		else:
			return default

	def session_key(self):
		"Returns a session key that can later be passed to from_session_key() to retrieve this user."
		key = common.random_hex_string()
		mutex = common.mutex('sessions.lock')
		mutex.get()
		sessions = shelve.open(sessions_file)
		sessions[key] = self.username
		sessions.close()
		mutex.drop()
		return key

	def password_matches(self, another):
		"Returns true if the password that's set matches |password|."
		return hash_of(another) == self.password

	def save(self, must_not_exist=0):
		mutex = common.mutex('users.lock')
		mutex.get()
		store = shelve.open(users_file)

		if must_not_exist and store.has_key(self.username):
			store.close()
			raise AlreadyExistsException()

		store[self.username] = self
		store.close()
		mutex.drop()

	def set_password(self, new_password):
		self.password = hash_of(new_password)

	def invent_new_password(self):
		"Sets the password to something random, and notifies the user. (Be sure to save after calling this, or the user will get confused."

		the_password = common.random_hex_string(8) # not the MD5 hash!
		self.set_password(the_password)

		sent_to = self.username
		message = ("From: %s\r\nTo: %s\r\n\
Subject: yarrow password\r\n\
Delivered-By-The-Graces-Of: yarrow\r\n\r\n\
You have requested a new password on the yarrow server. \
It has been reset to %s.\r\n\r\n\
Thank you for using yarrow.\r\n" % \
			(config.mail_source_address,
			sent_to,
			the_password))

		mail = smtplib.SMTP('localhost')
		mail.sendmail(config.mail_source_address,sent_to, message)
		mail.quit()

def from_name(username):
	"Returns a user with the given username. If none exists, returns None."
	users = shelve.open(users_file)
	if users.has_key(username):
		result = users[username]
	else:
		result = None
	users.close()
	return result

def from_session_key(key):
	sessions = shelve.open(sessions_file)
	if sessions.has_key(key):
		username = sessions[key]
	else:
		username = None
	sessions.close()

	if username:
		return from_name(username)
	else:
		return None

def create(username):
	"Creates a new user with username |username| and a random password. It must not already exist. Writes it out to persistant storage, notifies the user by email, and returns the newly-created user."

	result = user(username)
	result.save(1) # so we're sure we can actually save
	# (hmm, is it worth saving twice just to check this, when
	# we have to get mutex and everything?) 
	result.invent_new_password()
	result.save()

	return result