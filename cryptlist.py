#!/usr/bin/python
# Copyright Travis Brown travisb@travisbrown.ca $Date$ $Rev$

# This is a small script which handles simple encrypted mailing lists. It is meant to be run from
# a regular user account. Perhaps by filtering mailing list traffic via procmail or straight from
# a dedicated account usind fetchmail.

import fileinput
import sys
import email.parser
import email.message as message
import smtplib
import subprocess
import copy
import time

# Where do we keep our simple file logs?
sys.stdout = open("/tmp/crytplist_output", "a")
sys.stderr = open("/tmp/crytplist_error", "a")
smtp = smtplib.SMTP('localhost')

class list:
	name = "List Name to be prependet to subjects. List gives [List]"
	address = "list@example.org"
	address_bounces = "list-bounce@example.org"
	desc = "Awesome things being dicussed"
	encrypted_message = "This is an encrypted message. Install GPG and notify the\n"\
	                    "list maintainer (list-admin@example.org) about your public\n"\
			    "key to join in the fun."
	# Don't send encryted warning messages to those who don't have an key in the list keyring
	# True will cause anybody without a public key in the keyring to receive the above message
	# instead of the reencrypted original.
	send_on_encrypt_failure = False
	admin = "list-admin@example.org"
	bounce_message = "Message rejected. Only members of the list may post to the list.\n"\
			 "Original message below.\n\n----------\n\n"

class config:
	dir = '/path/to/cryptlist/directory'

# Each user is an email address. This will be matched if it is a subset of the From address.
# If you want to have encrypted message sent encrypted to any particular member you will have
# use the add_key script to add their public key to the list keyring.
Users = [
	'user1@example.com',
	'user2@example.org',
	'travisb@travisbrown.ca',
]

# End of configuration options

# Parse the email message
parser = email.parser.FeedParser()
for line in fileinput.input():
	parser.feed(line)

email = parser.close()

# Prevent loops by ignoring messages we have already seen
for line in email.get_all('X-Loop', []):
	if line == list.address:
		print "Found X-Loop, quiting"
		sys.exit(0)
email['X-Loop'] = list.address

if not email.has_key('From'):
	print "Dropping message without from"
	sys.exit(0)

from_member = False
for user in Users:
	if user in email['From']:
		from_member = True

if not from_member:
	# Save stuff for later
	new_subject = "Bounce: " + email['Subject']
	new_body = list.bounce_message + email.as_string(False)
	old_from = email['From']

	# Bounce to the admin for further processing
	print "Bouncing message from %s at %f" % (email['From'], time.time())
	del email['To']

	try:
		del email['X-Original-To']
	except:
		pass

	email['To'] = list.admin
	smtp.sendmail(email['From'], list.admin, email.as_string(False))

	# Bounce to the sender
	bounce_email = message.Message()
	bounce_email['Subject'] = new_subject
	bounce_email['From'] = list.address_bounces
	bounce_email['To'] = old_from
	bounce_email.set_payload(new_body)
	bounce_email.set_type('text/plain')

	smtp.sendmail(list.address_bounces, old_from, bounce_email.as_string(False))

	sys.exit(0)

# Set some important list headers
if email.has_key('Subject'):
	subject = email['Subject']
	del email['Subject']
elif email.has_key('Subject'):
	subject = email['subject']
	del email['subject']
else:
	subject = ""
 
if '[' + list.name + ']' not in subject:
	email['Subject'] = '[' + list.name + '] ' + subject
else:
	email['Subject'] = subject

email['Sender'] = list.address
email['Precendence'] = "List"
email['List-Id'] = list.desc + " <" + list.address + ">"
email['X-List'] = list.address
email['List-Post'] = '<mailto:' + list.address + '>'

del email['Return-Path']
email['Return-Path'] = "<bounces-" + list.address + ">"

# Find any parts which need to be re-encrypted
encrypted_parts = []
original_text = {}
payload = email.get_payload()
if not isinstance(payload, str):
	for part in payload:
		if 'BEGIN PGP MESSAGE' in part.get_payload():
			decryptor = subprocess.Popen('/usr/bin/gpg --homedir %s/gpg --batch --no-tty --status-fd 2 --decrypt -' % config.dir,
					stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell = True)
			out, err = decryptor.communicate(part.get_payload())
			if 'DECRYPTION_OKAY' in err:
				original_text[part] = out
				encrypted_parts.append(part)

for user in Users:

	email_valid = True
	for part in encrypted_parts:
		encryptor = subprocess.Popen('/usr/bin/gpg --homedir %s/gpg --always-trust --batch --no-tty --status-fd 2 -r %s -a --encrypt -' % (config.dir, user),
				stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell = True)
		out, err = encryptor.communicate(original_text[part])
		if 'INV_RECP' in err:
			#print 'Sorry, I can\'t encrypt to you'
			if list.send_on_encrypt_failure:
				error_email = copy.deepcopy(email)
				error_email.set_payload(list.encrypted_message)
				error_email.set_type('text/plain')
				smtp.sendmail(list.address, user, error_email.as_string(False))
			email_valid = False
			break
		else:
			#print out
			#print '----------------------------------'
			#print err
			#print encryptor.returncode
			part.set_payload(out)

	if email_valid:
		smtp.sendmail(list.address, user, email.as_string(False))

smtp.quit()

