// Click on header return us to the package page
function setLink() {
  document.getElementsByTagName("h2")[0].onclick = function() {
    location.href = location.pathname.replace(/\/browse\/.*/, "");
  }
}
document.addEventListener("DOMContentLoaded", setLink);
