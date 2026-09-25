function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (uri.length > 1 && uri.charAt(uri.length - 1) === "/") {
    uri = uri.slice(0, -1);
  }
  if (uri.indexOf(".") !== -1) {
    return request;
  }
  var parts = uri.split("/");
  if (parts.length >= 3 && parts[1] === "incidents" && parts[2] && parts[2] !== "_") {
    request.uri = "/incidents/_/index.html";
    return request;
  }
  if (uri === "" || uri === "/") {
    request.uri = "/index.html";
    return request;
  }
  request.uri = uri + "/index.html";
  return request;
}
