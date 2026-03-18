/* Artist nav — force clean navigation (defeats bfcache which causes stale/frozen tabs) */
(function () {
  // Disable bfcache: pages with unload handlers are not cached
  window.addEventListener("unload", function () {});

  // Intercept nav link clicks to force full page loads
  document.addEventListener("click", function (e) {
    var link = e.target.closest(".artist-nav a");
    if (!link) return;
    e.preventDefault();
    window.location.href = link.href;
  });
})();
