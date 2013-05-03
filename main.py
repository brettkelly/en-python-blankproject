#!/usr/bin/env python

# Copyright 2013 Brett Kelly
# All rights reserved.

import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.type.ttypes as Types
from evernote.api.client import EvernoteClient

def getNonEmptyUserInput(prompt):
	"Prompt the user for input, disallowing empty responses"
	uinput = raw_input(prompt)
	if uinput:
		return uinput
	print "This can't be empty. Try again."
	return getNonEmptyUserInput(prompt)

auth_token = "" # set this to your dev token to avoid being prompted

if not auth_token:
    auth_token = getNonEmptyUserInput("Enter your developer token: ")

client = EvernoteClient(token=auth_token, sandbox=True)

user_store = client.get_user_store()

note_store = client.get_note_store()

##
# You now have a ready-to-use Evernote client. Kaboom.
##

nbs = note_store.listNotebooks()

print len(nbs)
