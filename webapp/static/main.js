document.addEventListener("DOMContentLoaded", function () {
  var hash = window.location.hash;

  if (hash) {
    var activeTab = document.querySelector('a[href="' + hash + '"]');
    if (activeTab) {
      var tab = new bootstrap.Tab(activeTab);
      tab.show();
    }
  }

  var tabLinks = document.querySelectorAll("#myTab a");
  tabLinks.forEach(function (tabLink) {
    tabLink.addEventListener("shown.bs.tab", function (event) {
      history.replaceState(null, null, event.target.getAttribute("href"));
    });
  });
});

