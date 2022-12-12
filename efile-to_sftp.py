#!/usr/bin/env python3

import json
import os
import onevizion
import shutil
import pysftp

# Read settings
with open('settings','r') as p:
	params = json.loads(p.read())

try:
	OvUserName = params['OV']['UserName']
	OvPassword = params['OV']['Password']
	OvUrl      = params['OV']['Url']
	SftpHost   = params['SFTP']['Host']
	SftpUN     = params['SFTP']['UserName']
	SftpPWD    = params['SFTP']['Password']
	SftpInDir  = params['SFTP']['InboundDirectory']
	TrackorType = params['Config']['TrackorType']
	CheckboxField = params['Config']['CheckboxField']
	EFileField    = params['Config']['EFileField']
except Exception as e:
	raise "Please check settings"

class MyCnOpts:  #used by sftp connection
	pass

# connect to SFTP
try:
	#not best practice, but avoids needing entry in .ssh/known_hosts
	#from Joe Cool near end of https://bitbucket.org/dundeemt/pysftp/issues/109/hostkeysexception-no-host-keys-found-even
	cnopts = MyCnOpts()
	cnopts.log = False
	cnopts.compression = False
	cnopts.ciphers = None
	cnopts.hostkeys = None

	sftp = pysftp.Connection(SftpHost,
		username=SftpUN,
		password=SftpPWD,
		cnopts = cnopts
		)
except:
	Message('could not connect')
	Message(sys.exc_info())
	quit(1)

# make sure api user has RE on the tab with checkbox and the field list of blobs and RE for the trackor type(sometimes Checklist) and R for WEB_SERVICES 
Req = onevizion.Trackor(trackorType = TrackorType, URL = OvUrl, userName=OvUserName, password=OvPassword, isTokenAuth=True)
Req.read(filters = {CheckboxField : 1}, 
		fields = ['TRACKOR_KEY',CheckboxField], 
		sort = {'TRACKOR_KEY':'ASC'}, page = 1, perPage = 1000)

if len(Req.errors)>0:
	# If can not read list of efiles then must be upgrade or something.  Quit and try again later.
	print(Req.errors)
	quit(1)

hasErrors = False
# send files to Inbound directory
for f in Req.jsonData:
	FileReq = onevizion.Trackor(trackorType = TrackorType, URL = OvUrl, userName=OvUserName, password=OvPassword, isTokenAuth=True)
	fname = FileReq.GetFile(trackorId=f['TRACKOR_ID'], fieldName = EFileField)
	if len(FileReq.errors)>0:
		hasErrors = True
		print(FileReq.errors)
		continue
	try:
		with sftp.cd(SftpOutDir) :
			sftp.put(fname)
		Req.update(filters = {'TRACKOR_ID': f['TRACKOR_ID']}, fields = {CheckboxField: 0})
	except:
		hasErrors = True
		print(FileReq.errors)
		continue

if hasErrors:
	quit(1) # quit with positive number makes the process have status of failed

