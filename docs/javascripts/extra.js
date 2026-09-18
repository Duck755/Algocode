document.addEventListener('DOMContentLoaded', function () {
  var palette = document.querySelector('.md-header__option[data-md-component="palette"]');
  if (!palette) return;

  var path = window.location.pathname;
  var docsIndex = path.indexOf('/docs');
  var homepage = docsIndex >= 0
    ? path.slice(0, docsIndex) + '/'
    : 'http://127.0.0.1:8001/';

  var link = document.createElement('a');
  link.href = homepage;
  link.className = 'md-header__button md-icon';
  link.title = '返回官网';
  link.setAttribute('aria-label', '返回官网');
  link.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z"/></svg>';

  palette.parentNode.insertBefore(link, palette);
});
