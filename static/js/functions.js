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
  var inputform = document.getElementById("input-form");
  inputform.disabled = false;
  var urlform = document.getElementById("url");
  urlform.value = "url of file";
  var speakersform = document.getElementById("speakers");
  speakersform.value = "The names of the speakers in order of appearance, with commas separating each name, ex. 'Jane Doe, John Smith'";
  var signout = document.getElementById("sign-out");
  signout.style.display = "block";
  var signin = document.getElementById("sign-in");
  signin.style.display = "none";
  var emailform = document.getElementById("email");
  emailform.value = email;
  // emailform.disabled = true;
}

function signOut() {
  var auth2 = gapi.auth2.getAuthInstance();
  auth2.signOut().then(function () {
    console.log('User signed out.');
  });

  var inputform = document.getElementById("input-form");
  inputform.disabled = true;
  var urlform = document.getElementById("url");
  urlform.value = "Sign in to use Dubb";
  var speakersform = document.getElementById("speakers");
  speakersform.value = ""
  var signout = document.getElementById("sign-out");
  signout.style.display = "none";
  var signin = document.getElementById("sign-in");
  signin.style.display = "block";
  var emailform = document.getElementByID("email");
  emailform.value = ""
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
}