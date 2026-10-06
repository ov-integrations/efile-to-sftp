# efile-to-sftp

Module sends files from an EFile field in OneVizion to SFTP.

1. Finds Trackors of the selected Trackor Type where the checkbox field is checked (up to 1000 per run, the rest are sent on the next run)
2. Downloads the file from the EFile field of each Trackor and uploads it to the SFTP directory. A file with the same name in the SFTP directory is replaced
3. When the file is sent, clears the checkbox. If a file fails, the checkbox stays checked, so the file is sent again on the next run, and the process is marked as failed


* sftpUrl* - SFTP host name
* sftpPort - SFTP port. Default is 22
* sftpUserName* - SFTP user name
* sftpPassword - SFTP password. Used when sftpPrivateKey is not filled in
* sftpPrivateKey - full text of the private key (RSA, ECDSA or Ed25519), including the `-----BEGIN ...-----` and `-----END ...-----` lines. Line breaks must be written as `\n`. When filled in, the key is used instead of the password
* sftpPrivateKeyPassphrase - passphrase of the private key. Only needed if the key is protected with a passphrase
* sftpFingerprint - if not filled in, you may be vulnerable to Man-in-the-Middle attacks. If filled in, the fingerprint will be checked for compliance when connecting to SFTP. The fingerprint should only be passed as a key without the padding symbol (=) and in SHA256 format.
* sftpDirectory* - SFTP directory the files are uploaded to
* sftpOutboundDirectory - SFTP outbound directory. Kept from the previous settings, the module does not use it currently
* ovUrl* - OneVizion URL
* ovAccessKey*, ovSecretKey* - OneVizion API user token. The user needs RE access to the Trackor Type, the tab with the checkbox and EFile fields, and R access to WEB_SERVICES
* ovTrackorType* - Trackor Type name
* ovCheckboxFieldName* - checkbox field name that marks the files to be sent
* ovEfileFieldName* - EFile field name with the file to be sent

\* - required. Either sftpPassword or sftpPrivateKey must be filled in. Optional settings that are not used must be removed, not left empty.


Example of settings.json with password

```json
{
    "sftpUrl": "ftp.onevizion.com",
    "sftpPort": 22,
    "sftpUserName": "******",
    "sftpPassword": "************",
    "sftpDirectory": "/home/xxx/xxx/Inbound",
    "sftpOutboundDirectory": "/home/xxx/xxx/Outbound",

    "ovUrl": "https://***.onevizion.com/",
    "ovAccessKey": "******",
    "ovSecretKey": "************",

    "ovTrackorType": "Document",
    "ovCheckboxFieldName": "DOC_TRIGGER_SFTP",
    "ovEfileFieldName": "DOC_EFILE"
}
```

Example of settings.json with private key

```json
{
    "sftpUrl": "ftp.onevizion.com",
    "sftpUserName": "******",
    "sftpPrivateKey": "-----BEGIN OPENSSH PRIVATE KEY-----\n************\n-----END OPENSSH PRIVATE KEY-----\n",
    "sftpPrivateKeyPassphrase": "************",
    "sftpFingerprint": "1gaCiV/saoKIajnkD9y6TRKT4O+0mKJt4+VpIsfxsvg",
    "sftpDirectory": "/home/xxx/xxx/Inbound",

    "ovUrl": "https://***.onevizion.com/",
    "ovAccessKey": "******",
    "ovSecretKey": "************",

    "ovTrackorType": "Document",
    "ovCheckboxFieldName": "DOC_TRIGGER_SFTP",
    "ovEfileFieldName": "DOC_EFILE"
}
```


## Upgrading from the previous version

The settings file format has changed. Move the values from the old settings to settings.json:

| Old setting | New setting |
|---|---|
| OV.Url | ovUrl (add `https://`) |
| OV.UserName | ovAccessKey |
| OV.Password | ovSecretKey |
| SFTP.Host | sftpUrl |
| SFTP.UserName | sftpUserName |
| SFTP.Password | sftpPassword |
| SFTP.InboundDirectory | sftpDirectory |
| SFTP.OutboundDirectory | sftpOutboundDirectory |
| Config.TrackorType | ovTrackorType |
| Config.CheckboxField | ovCheckboxFieldName |
| Config.EFileField | ovEfileFieldName |
