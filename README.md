# nano-address-notifier
Track accounts and notify via log file or email

## Required python libs

    pip3 install sendgrid
    pip3 install simplejson
    pip3 install websockets
    pip3 install asyncio
    pip3 install numpy

## Config

* Copy accounts.json.default to accounts.json and edit the file
* Open the notify python file in an editor
* Enable email if you have a [sendgrid](https://sendgrid.com/) account and enter your from/to email and sendgrid API key.
* Set email interval and min amount to track
* If thousands of accounts being tracked, the websocket could fail. In that case set subscribeAll = True.

## Run

    python3 notify.py

Or set up a service

## Set up sendgrid

* Go to [sendgrid.com](https://sendgrid.com/) and set up a free account
* Verify a single send address or domain from settings => Sender Authentication. Set as sender address in the python file
* Generate an API key from settings => API Keys. Paste that into the python file
* That's it!