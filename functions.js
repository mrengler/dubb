function onSignIn(googleUser) {
  var inputform = document.getElementById("input-form");
  inputform.disabled = false;
  var urlform = document.getElementById("url");
  urlform.value = "url of file (can be youeube, spotify)"
}