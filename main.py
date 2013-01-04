#!/usr/bin/env python

# Copyright 2012 Evernote Corporation
# All rights reserved.

import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import thrift.transport.THttpClient as THttpClient
import evernote.edam.userstore.UserStore as UserStore
import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.notestore.NoteStore as NoteStore
import evernote.edam.type.ttypes as Types
import evernote.edam.error.ttypes as Errors

import hashlib
import binascii
import mimetypes
import os.path

EN_HOST = "sandbox.evernote.com"
EN_URL = "https://%s" % EN_HOST
TEST_NOTE_GUID = "36dd7123-12c0-457a-a6d0-75555fcc7770"


def getUserStoreInstance(authToken):
	userStoreUri = "%s/edam/user" % EN_URL
	userStoreHttpClient = THttpClient.THttpClient(userStoreUri)
	userStoreProtocol = TBinaryProtocol.TBinaryProtocol(userStoreHttpClient)
	userStore = UserStore.Client(userStoreProtocol)
	print "Created UserStore.Client instance"
	return userStore

def getNoteStoreInstance(authToken, userStore):
	try:
		noteStoreUrl = userStore.getNoteStoreUrl(authToken)
	except Errors.EDAMUserException, ue:
		print "Error: your dev token is probably wrong; double-check it."
		print ue
		return None

	noteStoreHttpClient = THttpClient.THttpClient(noteStoreUrl)
	noteStoreProtocol = TBinaryProtocol.TBinaryProtocol(noteStoreHttpClient)
	noteStore = NoteStore.Client(noteStoreProtocol)
	print "Created NoteStore.Client instance"
	return noteStore

def getNonEmptyUserInput(prompt):
	"""
	Prompt the user for input, disallowing empty responses
	"""
	uinput = raw_input(prompt)
	if uinput:
		return uinput
	print "This can't be empty. Try again."
	return getNonEmptyUserInput(prompt)

def makeResourceFromFiles(fpaths):
	"""
	Create a Resource object from the passed file(s) and return it
	"""
	for fpath in fpaths:
		if not os.path.exists(fpath):
			print "Path doesn't exist: %s" % fpath
			continue

		# try to determine the MIME type of the file
		mt = mimetypes.guess_type(fpath)
		typestr = mt[0]
		if typestr.split('/')[0] == "text":
			rmode = 'r'
		else:
			rmode = 'rb'

		fdata = open(fpath, rmode).read()
		md5 = hashlib.md5()
		md5.update(fdata)
		hashs = md5.digest()

		data = Types.Data()
		data.size = len(fdata)
		data.bodyHash = hashs
		data.body = fdata

		resource = Types.Resource()
		resource.mime = typestr
		resource.data = data

		attrs = Types.ResourceAttributes()
		attrs.fileName = os.path.basename(fpath)

		resource.attributes = attrs

		yield resource

def createNote(authToken, noteStore, noteTitle, noteBody, resources=[], parentNotebook=None):
	"""
	Create a Note instance with title and body 
	Send Note object to user's account
	"""

	ourNote = Types.Note()
	ourNote.title = noteTitle

	## Build body of note

	nBody = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
	nBody += "<!DOCTYPE en-note SYSTEM \"http://xml.evernote.com/pub/enml2.dtd\">"
	nBody += "<en-note>%s" % noteBody
	if resources:
		### Add Resource objects to note body
		nBody += "<br />" * 2
		ourNote.resources = resources
		for resource in resources:
			hexhash = binascii.hexlify(resource.data.bodyHash)
			nBody += "Attachment with hash %s: <br /><en-media type=\"%s\" hash=\"%s\" /><br />" % \
				(hexhash, resource.mime, hexhash)
	nBody += "</en-note>"

	ourNote.content = nBody

	## parentNotebook is optional; if omitted, default notebook is used
	if parentNotebook and hasattr(parentNotebook, 'guid'):
		ourNote.notebookGuid = parentNotebook.guid

	## Attempt to create note in Evernote account
	try:
		note = noteStore.createNote(authToken, ourNote)
	except Errors.EDAMUserException, edue:
		## Something was wrong with the note data
		## See EDAMErrorCode enumeration for error code explanation
		## http://dev.evernote.com/documentation/reference/Errors.html#Enum_EDAMErrorCode
		print "EDAMUserException:", edue
		return None
	except Errors.EDAMNotFoundException, ednfe:
		## Parent Notebook GUID doesn't correspond to an actual notebook
		print "EDAMNotFoundException: Invalid parent notebook GUID"
		return None
	## Return created note object
	return note

def getUserShardId(authToken, userStore):
	"""
	Get the User from userStore and return the user's shard ID
	"""
	try:
		user = userStore.getUser(authToken)
	except (Errors.EDAMUserException, Errors.EDAMSystemException), e:
		print "Exception while getting user's shardID:"
		print type(e), e
		return None
	
	if hasattr(user, 'shardId'):
		return user.shardId
	return None


def shareSingleNote(authToken, noteStore, userStore, noteGuid, shardId=None):
	"""
	Share a single note and return the public URL for the note
	"""
	if not shardId:
		shardId = getUserShardId(authToken, userStore)
		if not shardId:
			raise SystemExit

	try:
		shareKey = noteStore.shareNote(authToken, noteGuid)
	except (EDAMNotFoundException, EDAMSystemException, EDAMUserException), e:
		print "Error sharing note:"
		print type(e), e
		return None

	return "%s/shard/%s/sh/%s/%s" % \
		(EN_URL, shardId, noteGuid, shareKey)

def stopSharingSingleNote(authToken, noteStore, noteGuid):
	try:
		noteStore.stopSharingNote(authToken, noteGuid)
	except (EDAMNotFoundException, EDAMSystemException, EDAMUserException), e:
		print "Error stopping sharing note:"
		print type(e), e
		return None
	return noteGuid	

def getAllSharedNotes(authToken, noteStore, maxCount=None):
	"""
	Get a list of all of the shared notes in a user's account
	"""
	noteFilter = NoteStore.NoteFilter()
	noteFilter.words = "sharedate:*"
	sharedNotes = []
	offset = 0
	if not maxCount:
		maxCount = 500
	while len(sharedNotes) < maxCount:
		try:
			noteList = noteStore.findNotes(authToken, noteFilter, offset, 50)
			sharedNotes += noteList.notes
		except (EDAMNotFoundException, EDAMSystemException, EDAMUserException), e:
			print "Error getting shared notes:"
			print type(e), e
			return None

		if len(sharedNotes) % 50 != 0:
			## We've retrieved all of the notes 
			break
		else:
			offset += 50
	return sharedNotes[:maxCount]


def getAllTags(authToken, noteStore):
	try:
		print "in getAllTags"
		tags = noteStore.listTags(authToken)
		return tags
	except Exception, e:
		print e
		print "broken"

def isTagInUse(authToken, noteStore, tagGuid):
	nfilter = NoteStore.NoteFilter()
	nfilter.tagGuids = [tagGuid]
	notes = noteStore.findNotes(authToken, nfilter, 0, 1)
	return len(notes.notes)

def markTagName(authToken, noteStore, tag):
	tag.name = "DELETEME %s" % tag.name
	try:
		seq = noteStore.updateTag(authToken, tag)
	except Exception, e:
		print "updateTag broke:"
		print e

authToken = "" # bypass the dev token prompt by populating this variable.

if not authToken:
	authToken = getNonEmptyUserInput("Enter your dev token: ")

userStore = getUserStoreInstance(authToken)
noteStore = getNoteStoreInstance(authToken, userStore)

print "getting tags"

tags = getAllTags(authToken, noteStore)

print type(tags)
print dir(tags)
print tags

unusedTags = []

c = 1
for tag in tags:
	c += 1
	print "Checking tag: %s" % tag.name
	if not isTagInUse(authToken, noteStore, tag.guid):
		markTagName(authToken, noteStore, tag)
	if c == 10: break



# sharedNotes = getAllSharedNotes(authToken, noteStore, 1)

# print "All shared notes (%d, total):" % len(sharedNotes)
# for n in sharedNotes:
# 	print n.title

# sharedUrl = shareSingleNote(authToken, noteStore, userStore)

# print sharedUrl

# nTitle = "This is a test note!"
# nBody = "This is the body of a test note!"

# resObjs = []
# resources = ['enlogo.png', 'main.py']
# for res in makeResourceFromFiles(resources):
# 	resObjs.append(res)

# createdNote = createNote(authToken, noteStore, nTitle, nBody, resObjs)

# if createdNote:
# 	print "Note created with GUID: %s" % createdNote.guid
# else:
# 	print "createNote failed and returned None"
