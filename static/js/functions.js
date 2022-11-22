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

  var signout = document.getElementById("sign-out");
  signout.style.display = "block";
  var signin = document.getElementById("sign-in");
  signin.style.display = "none";

  const emailRecord = ""
  const emailDoc = db.collection("users").where("email", "==", email);
  emailDoc.get().then(function(doc) {
      if (doc.empty) {
        var d = new Date(Date.now());
        db.collection("users").add({
            email: email,
            time: d
        }) 
      }
      
  }).catch(function(error) {
      console.log("Error getting document:", error);
  });

  var signout = document.getElementById("sign-out");
  var signin = document.getElementById("sign-in");
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

  var signout = document.getElementById("sign-out");
  signout.style.display = "none";
  var signin = document.getElementById("sign-in");
  signin.style.display = "block";
  var emailform = document.getElementById("email");
  emailform.value = ""
}

function testingSignIn(){
  try {
    var floatingsignon = document.getElementById("floating-sign-in");
    floatingsignon.style.display = 'none';
    var inputdiv = document.getElementById("input-div");
    inputdiv.className = 'unblur';
    var inputform = document.getElementById("input-form");
    inputform.disabled = false;

    var signout = document.getElementById("sign-out");
    signout.style.display = "block";
    var signin = document.getElementById("sign-in");
    signin.style.display = "none";
  } catch (error) {
    console.error(error);
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  let searchParams = new URLSearchParams(window.location.search);
  if (searchParams.has('session_id')) {
    const session_id = searchParams.get('session_id');
    console.log('This is session id');
    console.log(session_id);
    document.getElementById('session-id').setAttribute('value', session_id);
  }
});

window.onload=function(){

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

  $('#file-upload').bind('change', function() { 
    var fileName = ''; fileName = $(this).val(); $('#file-selected').html(fileName);
    var urlinput = document.getElementById("url");
    urlinput.required=false;
  })

    $('#url').bind('change', function() { 
    var fileinput = document.getElementById("file-upload");
    fileinput.required=false;
  })

  // UNCOMMENT WHEN DONE WITH TESTING
  var loggedin = gapi.auth2.getAuthInstance().isSignedIn.get();
  if (loggedin === true) {
    onSignIn();
  } else if (loggedin === false) {
    signOut();
  }
  // testingSignIn();
  // UNCOMMENT WHEN DONE WITH TESTING

}