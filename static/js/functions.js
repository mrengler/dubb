// import firebase from "firebase/app";
// import "firebase/auth";

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


function isUserEqual(googleUser, firebaseUser) {
  if (firebaseUser) {
    var providerData = firebaseUser.providerData;
    for (var i = 0; i < providerData.length; i++) {
      if (providerData[i].providerId === firebase.auth.GoogleAuthProvider.PROVIDER_ID &&
          providerData[i].uid === googleUser.getBasicProfile().getId()) {
        // We don't need to reauth the Firebase connection.
        return true;
      }
    }
  }
  return false;
}

function onSignIn(googleUser) {

  console.log('Google Auth Response', googleUser);
  // We need to register an Observer on Firebase Auth to make sure auth is initialized.
  var unsubscribe = firebase.auth().onAuthStateChanged((firebaseUser) => {
    unsubscribe();
    // Check if we are already signed-in Firebase with the correct user.
    if (!isUserEqual(googleUser, firebaseUser)) {
      // Build Firebase credential with the Google ID token.
      var credential = firebase.auth.GoogleAuthProvider.credential(
          googleUser.getAuthResponse().id_token);

      console.log(credential);
  
      // Sign in with credential from the Google user.
      // [START auth_google_signin_credential]
      firebase.auth().signInWithCredential(credential).catch((error) => {
        // Handle Errors here.
        var errorCode = error.code;
        console.log(errorCode);
        var errorMessage = error.message;
        console.log(errorMessage);
        // The email of the user's account used.
        var email = error.email;
        console.log(email);
        // The firebase.auth.AuthCredential type that was used.
        var credential = error.credential;
        console.log(credential);
        // ...
      });
      // [END auth_google_signin_credential]
    } else {
      console.log('User already signed-in Firebase.');
    }
  });
  var profile = googleUser.getBasicProfile();
  email = profile.getEmail();
  try {
    var emailform = document.getElementById("email");
    emailform.value = email;
  } catch (error) {
    console.error(error);
  }


  var floatingsignon = document.getElementById("floating-sign-in");
  var floatingupgrade = document.getElementById("floating-upgrade");
  var inputdiv = document.getElementById("input-div");
  var inputform = document.getElementById("input-form");
  var signout = document.getElementById("sign-out");
  var signin = document.getElementById("sign-in");
  var upgrade = document.getElementById("checkout");
  var manage = document.getElementById("manage");
  var contact = document.getElementById("contact");

  var userstatus;
  var userfreecredits;

  const emailDoc = db.collection("users_info").doc(email);
  emailDoc.get().then((doc) => {
      if (doc.exists) {
          console.log("Document data:", doc.data());
          data = doc.data();
          userstatus = data.status;
          userfreecredits = data.free_credits;
          console.log('these are userstatus and freecredits');
          console.log(userstatus);
          console.log(userfreecredits);

          if ((userstatus == 'trial') && (userfreecredits > 0)) {
            floatingsignon.style.display = 'none';
            floatingupgrade.style.display = 'none';
            inputdiv.className = 'unblur';
            inputform.disabled = false;
            upgrade.style.display = 'block';
            manage.style.display = 'none';
            contact.style.display = 'none';
          } else if (userstatus == 'premium') {
            floatingsignon.style.display = 'none';
            floatingupgrade.style.display = 'none';
            inputdiv.className = 'unblur';
            inputform.disabled = false;
            upgrade.style.display = 'none';
            manage.style.display = 'block';
            contact.style.display = 'block';
          } else {
            floatingsignon.style.display = 'none';
            floatingupgrade.style.display = 'block';
            inputdiv.className = 'blur';
            inputform.disabled = true;
            upgrade.style.display = 'block';
            manage.style.display = 'none';
            contact.style.display = 'none';
          }


      } else {
          // doc.data() will be undefined in this case
          console.log("No such document!");
          var d = new Date(Date.now());
          userstatus = 'trial';
          userfreecredits = 3;
          var usersubmissions = 0
          db.collection("users_info").doc(email).set({
              time: d,
              status: userstatus,
              free_credits: userfreecredits,
              submissions: usersubmissions
          })
          floatingsignon.style.display = 'none';
          floatingupgrade.style.display = 'none';
          inputdiv.className = 'unblur';
          inputform.disabled = false;
          upgrade.style.display = 'block';
          manage.style.display = 'none';
          contact.style.display = 'none';
      }
  }).catch((error) => {
      console.log("Error getting document:", error);
  });

  //applies to all

  signout.style.display = "block";
  signin.style.display = "none";
  upgrade.style.display = "block";

  $.ajax({
      type: "POST",
      url: "/log_email",
      contentType: "application/json",
      data: JSON.stringify({user: email}),
      dataType: "json",
      success: function(response) {
          console.log(response);
      },
      error: function(err) {
          console.log(err);
      }
  });
}

function signOut() {
  console.log('sign out called')
  var auth2 = gapi.auth2.getAuthInstance();
  auth2.signOut().then(function () {
    console.log('User signed out.');
  });
  try {
    var floatingsignon = document.getElementById("floating-sign-in");
    floatingsignon.style.display = 'block';
    var floatingupgrade = document.getElementById("floating-upgrade");
    floatingupgrade.style.display = 'none';
    var inputdiv = document.getElementById("input-div");
    inputdiv.className = 'blur';
    var inputform = document.getElementById("input-form");
    inputform.disabled = true;
    var manage = document.getElementById("manage");
    manage.style.display = 'none';
    var contact = document.getElementById("contact");
    contact.style.display = 'none';
    
    auth2.attachClickHandler(
      floatingsignon, {}, 
      onSignIn, 
      function(error) {
      console.log(JSON.stringify(error, undefined, 2));
    });
  } catch (error) {
    console.error(error);
  }

  var signout = document.getElementById("sign-out");
  signout.style.display = "none";
  var signin = document.getElementById("sign-in");
  signin.style.display = "block";
  var upgrade = document.getElementById("checkout");
  upgrade.style.display = "none";
  var emailform = document.getElementById("email");
  emailform.value = ""

  $.ajax({
      type: "POST",
      url: "/log_email",
      contentType: "application/json",
      data: JSON.stringify({user: ''}),
      dataType: "json",
      success: function(response) {
          console.log(response);
      },
      error: function(err) {
          console.log(err);
      }
  });
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
  console.log('google auth object');
  console.log(gapi.auth2.getAuthInstance());
  console.log(gapi.auth2.getAuthInstance().currentUser.get());
  var loggedin = gapi.auth2.getAuthInstance().isSignedIn.get();
  if (loggedin === true) {
    var googleUser = gapi.auth2.getAuthInstance().currentUser.get();
    onSignIn(googleUser);
  } 
  // else if (loggedin === false) {
  //   signOut();
  // }
  // testingSignIn();
  // UNCOMMENT WHEN DONE WITH TESTING

}