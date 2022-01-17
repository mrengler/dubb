var db = firebase.firestore();
var email;

function onSignIn(googleUser) {
  var profile = googleUser.getBasicProfile();
  email = profile.getEmail();
  var inputform = document.getElementById("input-form");
  inputform.disabled = false;
  var urlform = document.getElementById("url");
  urlform.value = "url of file";
  db.collection("users").add({
      email: email
  })
  .then((docRef) => {
      console.log("Document written with ID: ", docRef.id);
  })
  .catch((error) => {
      console.error("Error adding document: ", error);
  });

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
  db.collection("requests").add({
      email: email,
      url: urlinput
  })
  .then((docRef) => {
      console.log("Document written with ID: ", docRef.id);
  })
  .catch((error) => {
      console.error("Error adding document: ", error);
  });
}