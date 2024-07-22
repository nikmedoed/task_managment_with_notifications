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

  document.querySelectorAll(".utc-time").forEach(function(element) {
        const utcTime = element.getAttribute("data-utc-time");
        const date = new Date(utcTime + 'Z');

        const options = {
            year: '2-digit',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        };

        const formatter = new Intl.DateTimeFormat('ru-RU', options);
        const formattedTime = formatter.format(date);

        element.textContent = formattedTime.replace(',', '');
    });

});
