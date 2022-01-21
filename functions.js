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
}

function signOut() {
  var auth2 = gapi.auth2.getAuthInstance();
  auth2.signOut().then(function () {
    console.log('User signed out.');
  });

  var inputform = document.getElementById("input-form");
  inputform.disabled = true;
  var urlform = document.getElementById("url");
  urlform.value = "Sign in to use Dubb"
}

function onSubmit() {
  var urlform = document.getElementById("url");
  var urlinput = urlform.value;
  var d = new Date(Date.now()).toString();
  db.collection("requests").add({
      email: email,
      url: urlinput,
      time: d
  })
  .then((docRef) => {
      console.log("Document written with ID: ", docRef.id);
  })
  .catch((error) => {
      console.error("Error adding document: ", error);
  });
}