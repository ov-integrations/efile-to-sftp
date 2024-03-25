# efile-to-sftp2

Module transfers files from an efile field in OneVizio and delivers to SFTP.

1.  Queries OneVizion to get a list of files to transferred based on a checkbox.
2.  Downloads files one at a file from OneVizion and sends to SFTP.
3.  When successful, clears the checkbox


Example of settings.json

```json
{
	"OV": {
		"UserName" : "AccessKey",
		"Password" : "SecretKey",
		"Url" : "xxx.onevizion.com"
	},
	"SFTP": {
		"Host" : "ftp.onevizion.com",
		"UserName" : "",
		"Password" : "",
		"InboundDirectory" : "/home/xxx/xxx/Inbound",
		"OutboundDirectory" : "/home/xxx/xxx/Outbound"
	},
	"Config": {
		"TrackorType" : "Document",
		"CheckboxField" : "DOC_TRIGGER_SFTP",
		"EFileField" : "DOC_EFILE"
	}
}```
