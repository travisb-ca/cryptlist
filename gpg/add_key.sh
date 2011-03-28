#!/bin/bash
# Copyright Travis Brown travisb@travisbrown.ca $Date$ $Rev$
# Add the given public key to the list keylist such that it can receive encrypted messages.
# Must be run from the directory with the list keyring in it.

if [ -z $1 ]; then
	echo "Usage: add_key.sh public_keyfile keynumber"
	exit
fi

key=`gpg --homedir . --import $1 2>&1 | head -n 1|awk '{print $3}'| sed 's/://'`
gpg --homedir . --edit-key ${key} lsign quit
