#!/usr/bin/env python

# Copyright 2013 Brett Kelly
# All rights reserved.

import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import thrift.transport.THttpClient as THttpClient
import evernote.edam.userstore.UserStore as UserStore
import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.notestore.NoteStore as NoteStore
import evernote.edam.type.ttypes as Types
import evernote.edam.error.ttypes as Errors

import time
import hashlib
import os
import os.path
import binascii

EN_HOST = "sandbox.evernote.com"
EN_URL = "https://%s" % EN_HOST

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
	"Prompt the user for input, disallowing empty responses"
	uinput = raw_input(prompt)
	if uinput:
		return uinput
	print "This can't be empty. Try again."
	return getNonEmptyUserInput(prompt)

def buildSharedNoteUrl(username, noteGuid, shareKey):
    "Create a public URL for a shared note and return it"
    try:
        userInfo = userStore.getPublicUserInfo(username)
    except Exception, e:
        print "Error getting User from UserStore"
        print type(e)
        print e
        raise SystemExit
    return "%ssh/%s/%s" % (userInfo.webApiUrlPrefix, noteGuid, shareKey)
    

authToken = "" # bypass the dev token prompt by populating this variable.

if not authToken:
	authToken = getNonEmptyUserInput("Enter your dev token: ")

userStore = getUserStoreInstance(authToken)
noteStore = getNoteStoreInstance(authToken, userStore)
user = userStore.getUser(authToken)

print "UserStore and NoteStore instances are created!"
raw_input("Hit enter to create a notebook...")

##
# You now have a ready-to-use Evernote client. Kaboom.
##
name = "Fancy Notebook! %s" % str(time.time())
print "Creating a new notebook called '%s'" % name

## Create a notebook
notebook = Types.Notebook()
notebook.name = name 
notebook = noteStore.createNotebook(authToken, notebook)
print "New notebook GUID: %s" % notebook.guid
raw_input("Hit enter to create a new note in our notebook...")

## Create a note in the notebook 
note = Types.Note()
note.title = "My Spiffy Note!"
content = '<?xml version="1.0" encoding="UTF-8"?>'
content += '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">'
content += "<en-note>Hello World!</en-note>"
note.content = content
note.notebookGuid = notebook.guid
note = noteStore.createNote(authToken, note)
print "New note GUID: %s" % note.guid
print
print "Hit enter to add an image to our note AND share it..."
raw_input("Create a file called ~/temp/image.png, then hit enter...")

## Add an image to the note

# Find and read the image file
imgFileName = 'image.png'
imageFile = os.path.join(os.path.expanduser('~'), 'temp', imgFileName)

imageData = file(imageFile,'rb').read()

# Get the MD5 of the image
md5 = hashlib.md5()
md5.update(imageData)
hashVal = md5.digest()
hashHex = binascii.hexlify(hashVal)

# Create the Data member for our resource
data = Types.Data()
data.size = len(imageData)
data.bodyHash = hashVal
data.body = imageData

# Create our resource
resource = Types.Resource()
resource.type = 'image/png'
resource.data = data
note.resources = [resource]

# Define ResourceAttributes so we can name our file
resAttrs = Types.ResourceAttributes()
resAttrs.name = os.path.basename(imageFile)
resource.attributes = resAttrs

# Build our note contents
newContent = '<?xml version="1.0" encoding="UTF-8"?>'
newContent += '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">'
newContent += '<en-note>'
newContent += 'This image is called: %s' % imgFileName
newContent += '<br />'
newContent += 'The image hash value is %s' % hashHex
newContent += '<br />'
newContent += '<en-media type="%s" hash="%s"></en-media>' % (resource.type, hashHex)
newContent += '<br />Have a nice day!'
newContent += '</en-note>'

note.content = newContent 

# Update the note on the server
note = noteStore.updateNote(authToken, note)

## Share the note
shareKey = noteStore.shareNote(authToken, note.guid)
shareUrl = buildSharedNoteUrl(user.username, note.guid, shareKey)
print "View the note in the browser at:"
print shareUrl
print
print "If that's not magic, I don't know what is!"
print
raw_input("Hit enter to see all of your notebooks...")

### Get all notebooks
notebooks = noteStore.listNotebooks(authToken)
print "Here be ye notebooks!"
print
for nb in notebooks:
    print "%s - %s" % (nb.name, nb.guid)
print
raw_input("Hit enter to share the notebook we created earlier...")

print
email = raw_input("Enter a valid email address (make sure it's actually valid): ")

### Share the notebook with somebody
sharedNotebook = Types.SharedNotebook()
sharedNotebook.privilege = Types.SharedNotebookPrivilegeLevel.READ_NOTEBOOK
sharedNotebook.email = email 
sharedNotebook.notebookGuid = notebook.guid
sharedNotebook = noteStore.createSharedNotebook(authToken, sharedNotebook)

print "Check your email, dummy!"

raw_input("We're done here. Hit enter to exit.")
