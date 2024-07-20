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

/**
 * Initiate Datatables
 */
document.addEventListener("DOMContentLoaded", function () {
  const datatables = document.querySelectorAll(".datatable");
  datatables.forEach((datatable) => {
    new simpleDatatables.DataTable(datatable, {
      perPage: 100,
      perPageSelect: [10, 50, 100, ["All", -1]],
      columns: [
        {
          select: 5,
          searchable: false,
          filter: ["Да", "Нет"],
        },
        {
          select: 6,
          searchable: false,
          filter: ["Да", "Нет"],
        },
        {
          select: 7,
          sortable: false,
          searchable: false,
        },
      ],
    });
  });
});
