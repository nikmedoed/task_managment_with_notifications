document.addEventListener("DOMContentLoaded", () => {
  handleHashChange();
  initializeTabs();
  setupSidebarToggle();
  setupSearchBarToggle();
  handleNavbarLinksActiveStateOnScroll();
  handleHeaderScroll();
  setupBackToTopButton();
  initiateTooltips();
  initiateValidationCheck();
  autoresizeEchartCharts();
});

function handleHashChange() {
  const hash = window.location.hash;
  if (hash) {
    const activeTab = document.querySelector(`a[href="${hash}"]`);
    if (activeTab) {
      const tab = new bootstrap.Tab(activeTab);
      tab.show();
    }
  }
}

function initializeTabs() {
  document.querySelectorAll("#myTab a").forEach(tabLink => {
    tabLink.addEventListener("shown.bs.tab", event => {
      history.replaceState(null, null, event.target.getAttribute("href"));
    });
  });
}

function setupSidebarToggle() {
  const sidebarToggleBtn = select(".toggle-sidebar-btn");
  if (sidebarToggleBtn) {
    sidebarToggleBtn.addEventListener("click", () => {
      document.body.classList.toggle("toggle-sidebar");
    });
  }
}

function setupSearchBarToggle() {
  const searchBarToggleBtn = select(".search-bar-toggle");
  if (searchBarToggleBtn) {
    searchBarToggleBtn.addEventListener("click", () => {
      select(".search-bar").classList.toggle("search-bar-show");
    });
  }
}

function handleNavbarLinksActiveStateOnScroll() {
  const navbarLinks = select("#navbar .scrollto", true);
  const updateNavbarLinksActiveState = () => {
    const position = window.scrollY + 200;
    navbarLinks.forEach(navbarLink => {
      if (!navbarLink.hash) return;
      const section = select(navbarLink.hash);
      if (!section) return;
      if (position >= section.offsetTop && position <= section.offsetTop + section.offsetHeight) {
        navbarLink.classList.add("active");
      } else {
        navbarLink.classList.remove("active");
      }
    });
  };
  window.addEventListener("load", updateNavbarLinksActiveState);
  document.addEventListener("scroll", updateNavbarLinksActiveState);
}

function handleHeaderScroll() {
  const header = select("#header");
  if (header) {
    const toggleHeaderScrolledClass = () => {
      if (window.scrollY > 100) {
        header.classList.add("header-scrolled");
      } else {
        header.classList.remove("header-scrolled");
      }
    };
    window.addEventListener("load", toggleHeaderScrolledClass);
    document.addEventListener("scroll", toggleHeaderScrolledClass);
  }
}

function setupBackToTopButton() {
  const backToTopBtn = select(".back-to-top");
  if (backToTopBtn) {
    const toggleBackToTopBtn = () => {
      if (window.scrollY > 100) {
        backToTopBtn.classList.add("active");
      } else {
        backToTopBtn.classList.remove("active");
      }
    };
    window.addEventListener("load", toggleBackToTopBtn);
    document.addEventListener("scroll", toggleBackToTopBtn);
  }
}

function initiateTooltips() {
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
}

function initiateValidationCheck() {
  const forms = document.querySelectorAll(".needs-validation");
  Array.prototype.slice.call(forms).forEach(form => {
    form.addEventListener("submit", event => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    }, false);
  });
}

function autoresizeEchartCharts() {
  const mainContainer = select("#main");
  if (mainContainer) {
    setTimeout(() => {
      new ResizeObserver(() => {
        select(".echart", true).forEach(echart => {
          echarts.getInstanceByDom(echart).resize();
        });
      }).observe(mainContainer);
    }, 200);
  }
}

function select(el, all = false) {
  el = el.trim();
  if (all) {
    return [...document.querySelectorAll(el)];
  } else {
    return document.querySelector(el);
  }
}
