(function () {
  "use strict";

  const config = window.SOURCING_APP || {
    pwaUrl: "https://sourcing-production-8102.up.railway.app/user",
  };

  function goToPwa() {
    window.location.href = config.pwaUrl;
  }

  document.querySelectorAll("[data-go-pwa]").forEach((el) => {
    el.addEventListener("click", (event) => {
      event.preventDefault();
      goToPwa();
    });
  });

  /* In-page anchors on static landing */
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", (event) => {
      const id = anchor.getAttribute("href");
      if (!id || id === "#") return;
      const target = document.querySelector(id);
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
})();
