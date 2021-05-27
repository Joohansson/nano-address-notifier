# using SendGrid's Python Library
# https://github.com/sendgrid/sendgrid-python
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import *
import logging
import json
import simplejson
import websockets
import datetime
import asyncio
import time
from pathlib import Path

# CONFIG THESE
enableEmail = False # if False, it will only log to file
fromEmail = 'send@example.com' # approved sender in sendgrid 'send@example.com'
toEmails = ['get1@example.com'] # comma separated list ['get1@example.com','get2@example.com']
sendgridAPIKey = 'xxx' # sendgrid account API key
ws_host = 'wss://socket.nanos.cc'

# New transaction will be emailed directly if this many seconds has passed since last email
# Transactions will be bulk sent in one email if they arrive faster
emailBufferLength = 3600

# Nano amount below this will not be tracked
minAmount = 0.0000001

# Set to True if tracking thousands of accounts, or subscription will fail. Subscribing to all will still work
# but increases the web traffic for both client and server
subscribeAll = False

# INPUT AND OUTPUT
accountFile = 'accounts.json' # input accounts to track
logFile = 'events.log'

# CODE - Don't touch
filename = Path(logFile)
filename.touch(exist_ok=True)
logging.basicConfig(level=logging.INFO,filename=logFile, filemode='a+', format='%(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

statData = []
accounts = {'account':{}}
accountsIds = []
emailBuffer = []
lastEmail = 0
nano = 1000000000000000000000000000000

def timeLog(msg):
    return str(datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')) + ": " + msg

emails = []
for address in toEmails:
    emails.append(To(address))

def sendMail(body):
    message = Mail(
    from_email=fromEmail,
    to_emails=emails,
    subject='Nano Address Notifier: Transaction events',
    html_content='<strong>Transactions occured:</strong><br><br>'+body)

    try:
        sg = SendGridAPIClient(sendgridAPIKey)
        response = sg.send(message)
        if response.status_code != 202:
            log.error(timeLog('Failed to send email. Status code: ' + response.status_code))
            log.error(timeLog(response.body))

        #print(response.status_code)
        #print(response.body)
        #print(response.headers)
    except Exception as e:
        log.error(e)

def trackAccounts():
    global accounts

    # read account file
    try:
        with open(accountFile) as json_file:
            inputJson = json.load(json_file)
            # only keep stats from past week
            for a in inputJson:
                if 'account' in a:
                    alias = 'N/A'
                    if 'alias' in a:
                        alias = str(a['alias'])
                    accounts[a['account']] = {'alias': alias}
                    accountsIds.append(a['account'])

    except Exception as e:
        log.error(timeLog('Could not read account data. Error: %r' %e))

async def connectWebsocket(init = True):
    global accounts
    global accountsIds
    global emailBuffer

    if init:
      trackAccounts()

    # Predefined subscription message
    msg = {
        "action": "subscribe",
        "topic": "confirmation",
        "ack": "true",
        "id": "12345"
    }
    if not subscribeAll:
        msg['options'] = {
            "accounts": accountsIds
        }
    try:
        async with websockets.connect(ws_host) as websocket:
            log.info(timeLog('Subscribing to websocket and waiting for acknowledge..'))
            await websocket.send(json.dumps(msg))
            while 1:
                try:
                    rec = json.loads(await websocket.recv())
                    if 'ack' in rec:
                      log.info(timeLog('Subscription acknowledged! Waiting for transactions..'))
                    if 'topic' in rec and rec['topic'] == 'confirmation':
                        message = rec['message']
                        text = 'Unknown block'
                        
                        amount = '0'
                        okAmount = False
                        okBlock = False
                        if int(message['amount']) > 0:
                            amount = str(int(message['amount']) / nano)
                            if float(amount) >= minAmount:
                                okAmount = True

                        ## send, receive or change block
                        if message['block']['account'] in accountsIds:
                            account = message['account']
                            text = 'Account ' + accounts[account]['alias'] + ' (' + account + ')'
                            # send block
                            if message['block']['subtype'] == 'send':
                                text = text + ' sent ' + amount + ' NANO to ' + message['block']['link_as_account']
                                okBlock = True
                            # receive block
                            elif message['block']['subtype'] == 'receive':
                                text = text + ' received ' + amount + ' NANO'
                                okBlock = True
                            # change block
                            elif message['block']['subtype'] == 'change':
                                text = text + ' changed rep to ' + message['block']['representative']
                                okAmount = True
                                okBlock = True

                        ## incoming block
                        elif message['block']['link_as_account'] in accounts:
                            account = message['block']['link_as_account']
                            text = 'Account ' + accounts[account]['alias'] + ' (' + account + ')'
                            # incoming block
                            if message['block']['subtype'] == 'send':
                                text = text + ' got incoming ' + amount + ' NANO from ' + message['block']['account']
                                okBlock = True

                        if okBlock and okAmount:
                            log.info(timeLog(text))
                            emailBuffer.append(text)

                except Exception as e:
                    log.error(timeLog('Error: %r' %e))
                    await asyncio.sleep(5)

    except Exception as e:
        log.error(timeLog('Websocket connection error. Error: %r' %e))
        # wait 5sec and reconnect
        await asyncio.sleep(5)
        await connectWebsocket(False)

async def emailer():
    global emailBuffer
    global lastEmail

    if not enableEmail:
        return

    while 1:
        try:
            await asyncio.sleep(1)
            if len(emailBuffer) > 0 and int(time.time()) > lastEmail + emailBufferLength:
                body = ''
                for text in emailBuffer:
                    body = body + text + '<br>'
                emailBuffer = [] # reset buffer
                log.info(timeLog('Sending email'))
                sendMail(body)
                lastEmail = int(time.time())
        
        except Exception as e:
            log.error(timeLog('Failed to send email'))
            log.error(timeLog('Error: %r' %e))

try:
    loop = asyncio.get_event_loop()
    futures = [connectWebsocket(), emailer()]
    loop.run_until_complete(asyncio.wait(futures))
except KeyboardInterrupt:
    pass