#!/usr/bin/env python3

import sys
import subprocess

installed_dependencies = subprocess.run(
    [sys.executable, '-m', 'pip', 'install', '-r', 'python_dependencies.ini'],
    check=True, stdout=subprocess.PIPE).stdout.decode().strip()
if 'Successfully installed' in installed_dependencies:
    raise Exception('Some required dependent libraries were installed. ' \
        'Module execution has to be terminated now to use installed libraries on the next scheduled launch.')

import json
import os
import onevizion
import pysftp
import urllib.parse

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
	print('could not connect')
	print(sys.exc_info())
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
	fnameDecoded = urllib.parse.unquote(fname) #turn %20 into spaces
	print(f'{fname}   {fnameDecoded}')
	if len(FileReq.errors)>0:
		hasErrors = True
		print(FileReq.errors)
		continue
	try:
		with sftp.cd(SftpInDir) :
			sftp.remove(fnameDecoded)
	except:
		pass # removing the file if it exists before put.  if it is not there, ignore the error

	try:
		with sftp.cd(SftpInDir) :
			sftp.put(fname,fnameDecoded)
		Req.update(filters = {'TRACKOR_ID': f['TRACKOR_ID']}, fields = {CheckboxField: 0})
		os.remove(fname)
	except:
		hasErrors = True
		print(sys.exc_info)
		continue

if hasErrors:
	quit(1) # quit with positive number makes the process have status of failed

