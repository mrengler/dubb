function onSignIn(googleUser) {
  var inputform = document.getElementById("input-form");
  inputform.disabled = false;
  var urlform = document.getElementById("url");
  urlform.value = "url of file"
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