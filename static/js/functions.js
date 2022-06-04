// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: "AIzaSyBAYSpW1JYsG3dI3JbxEp6_KZSoGlys3Rg",
  authDomain: "dubb-3ed06.firebaseapp.com",
  projectId: "dubb-3ed06",
  storageBucket: "dubb-3ed06.appspot.com",
  messagingSenderId: "254099317950",
  appId: "1:254099317950:web:69d42c0e4ea52888a06aef",
  measurementId: "G-55CFDNV8T4"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
var db = firebase.firestore();
var email;

function onSignIn(googleUser) {
  var profile = googleUser.getBasicProfile();
  email = profile.getEmail();
  var emailform = document.getElementById("email");
  emailform.value = email;

  var floatingsignon = document.getElementById("floating-sign-in");
  floatingsignon.style.display = 'none';
  var inputdiv = document.getElementById("input-div");
  inputdiv.className = 'unblur';
  var inputform = document.getElementById("input-form");
  inputform.disabled = false;
  // var uploadinstruct = document.getElementById("upload-instruct")
  // uploadinstruct.hidden = false;
  // var fileupload = document.getElementById("file-upload");
  // fileupload.type = 'file';
  // var uploadfile = document.getElementById("upload-file");
  // uploadfile.style.display = 'inline-block';     
  // var urlform = document.getElementById("url");
  // urlform.value = "https://open.spotify.com/episode/yourgreatpodcast";
  // var namesinstruct = document.getElementById("names-instruct")
  // namesinstruct.hidden = false;
  // var speakersform = document.getElementById("speakers");
  // speakersform.type = 'text';
  // var gobutton = document.getElementById("submit");
  // gobutton.type = 'submit';  

  var signout = document.getElementById("sign-out");
  signout.style.display = "block";
  var signin = document.getElementById("sign-in");
  signin.style.display = "none";
  // var topnavright = document.getElementById("topnav-right");
  // topnavright.innerHTML = '<div class="g-signin2" id="sign-in" data-onsuccess="onSignIn"></div>'
  
  var d = new Date(Date.now()).toString();
  db.collection("users").add({
      email: email,
      time: d
  })
  .then((docRef) => {
      console.log("Document written with ID: ", docRef.id);
  })
  .catch((error) => {
      console.error("Error adding document: ", error);
  });
  var signout = document.getElementById("sign-out");
  console.log(signout);
  var signin = document.getElementById("sign-in");
  console.log(signin);
}

function signOut() {
  console.log('sign out called')
  var auth2 = gapi.auth2.getAuthInstance();
  auth2.signOut().then(function () {
    console.log('User signed out.');
  });

  var floatingsignon = document.getElementById("floating-sign-in");
  floatingsignon.style.display = 'block';
  var inputdiv = document.getElementById("input-div");
  inputdiv.className = 'blur';
  var inputform = document.getElementById("input-form");
  inputform.disabled = true;
  // var uploadinstruct = document.getElementById("upload-instruct")
  // uploadinstruct.hidden = true;
  // var fileupload = document.getElementById("file-upload");
  // fileupload.type = 'hidden';
  // var uploadfile = document.getElementById("upload-file");
  // uploadfile.style.display = 'none';    
  // var urlform = document.getElementById("url");
  // urlform.value = "Sign in to use Dubb";
  // var namesinstruct = document.getElementById("names-instruct")
  // namesinstruct.hidden = true;
  // var speakersform = document.getElementById("speakers");
  // speakersform.type = 'hidden';
  // var gobutton = document.getElementById("submit");
  // gobutton.type = 'hidden';  

  // var topnavright = document.getElementById("topnav-right");
  // topnavright.innerHTML = '<a href="#" id="sign-out" onclick="signOut();">Sign out</a>'



  var signout = document.getElementById("sign-out");
  console.log(signout);
  signout.style.display = "none";
  console.log(signout);
  var signin = document.getElementById("sign-in");
  console.log(signin);
  signin.style.display = "block";
  console.log(signin);
  var emailform = document.getElementById("email");
  emailform.value = ""
  console.log(signout.style.display);
}

function onSubmit() {
  var urlform = document.getElementById("url");
  var urlinput = urlform.value;
  var d = new Date(Date.now()).toString();
  console.log(urlinput);
  $.ajax({
    type: "POST",
    url: "/",
    // contentType: "application/json",
    data: { url: urlinput},
    // dataType: 'json'
  }).done(function( o ) {
     // do something
  });
  // db.collection("requests").add({
  //     email: email,
  //     url: urlinput,
  //     time: d
  // })
  // .then((docRef) => {
  //     console.log("Document written with ID: ", docRef.id);
  // })
  // .catch((error) => {
  //     console.error("Error adding document: ", error);
  // });
}

function testSetup() {
  var inputform = document.getElementById("input-form");
  inputform.disabled = false;
  var uploadinstruct = document.getElementById("upload-instruct")
  uploadinstruct.hidden = false;
  var uploadfile = document.getElementById("upload-file");
  uploadfile.type = 'file';  
  var urlform = document.getElementById("url");
  urlform.value = "https://open.spotify.com/episode/yourgreatpodcast";
  var namesinstruct = document.getElementById("names-instruct")
  namesinstruct.hidden = false;
  var speakersform = document.getElementById("speakers");
  speakersform.type = 'text';
  var gobutton = document.getElementById("submit");
  gobutton.type = 'submit';  
  var signout = document.getElementById("sign-out");
  signout.style.display = "block";
  var signin = document.getElementById("sign-in");
  signin.style.display = "none";
}

window.onload=function(){
  var loggedin = gapi.auth2.getAuthInstance().isSignedIn.get();
  console.log(loggedin);
  if (loggedin === true) {
    console.log('on load is signed in');
    onSignIn();
  } else if (loggedin === false) {
    console.log('on load not signed in');
    signOut();
  }

  var coll = document.getElementsByClassName("collapsible");
  var i;

  for (i = 0; i < coll.length; i++) {
    coll[i].addEventListener("click", function() {
      this.classList.toggle("active");
      var content = this.nextElementSibling;
      if (content.style.maxHeight){
        content.style.maxHeight = null;
      } else {
        content.style.maxHeight = content.scrollHeight + "px";
      } 
    });
  }

  $('#file-upload').bind('change', function() { var fileName = ''; fileName = $(this).val(); $('#file-selected').html(fileName); })


  // TO BE DELETED. FOR TESTING
  testSetup();
}