document.addEventListener("DOMContentLoaded", function () {
    // Get the hash from the URL
    var hash = window.location.hash;

    if (hash) {
        var activeTab = document.querySelector('a[href="' + hash + '"]');
        if (activeTab) {
            // Activate the tab based on the URL hash
            var tab = new bootstrap.Tab(activeTab);
            tab.show();
        }
    }

    // Update URL when a tab is clicked
    var tabLinks = document.querySelectorAll('#myTab a');
    tabLinks.forEach(function (tabLink) {
        tabLink.addEventListener('shown.bs.tab', function (event) {
            history.replaceState(null, null, event.target.getAttribute('href'));
        });
    });
});