// Applies the color theme before first paint — loaded synchronously in <head>.
// Priority: ?theme= query override (not persisted) > saved choice > OS preference.
// Sets data-theme (our tokens) and data-bs-theme (Bootstrap's form/modal palette).
(function () {
  var theme = null;
  try {
    var param = new URLSearchParams(window.location.search).get('theme');
    if (param === 'light' || param === 'dark') theme = param;
    if (!theme) {
      var stored = window.localStorage.getItem('mt-theme');
      if (stored === 'light' || stored === 'dark') theme = stored;
    }
  } catch (e) { /* blocked storage — fall through to the OS preference */ }
  if (!theme) {
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    theme = prefersDark ? 'dark' : 'light';
  }
  document.documentElement.setAttribute('data-theme', theme);
  document.documentElement.setAttribute('data-bs-theme', theme);
})();
