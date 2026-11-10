(function () {
  const reviews = document.getElementById('reviews');
  if (!reviews) return;

  const selector = [
    '#reviews .sentiment-filter',
    '#reviews .keyword-chip',
    '#reviews .keyword-filter-note a',
    '#reviews .pagination a',
    '#reviews .empty a'
  ].join(',');

  let loading = false;

  document.addEventListener('click', (event) => {
    if (loading || event.defaultPrevented) return;
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    const link = event.target.closest(selector);
    if (!link) return;
    if (!link.href) return;

    const url = new URL(link.href, window.location.href);
    if (url.pathname !== window.location.pathname || !url.search) return;

    event.preventDefault();
    loadReviews(url, true);
  });

  async function loadReviews(url, pushState) {
    if (loading) return;
    loading = true;
    const scrollY = window.scrollY;
    reviews.classList.add('review-loading');
    reviews.setAttribute('aria-busy', 'true');

    try {
      const response = await fetch(url.pathname + url.search, {
        headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'text/html' },
        credentials: 'same-origin'
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const html = await response.text();
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const next = doc.getElementById('reviews');
      if (!next) throw new Error('reviews block missing');

      reviews.innerHTML = next.innerHTML;
      if (pushState) {
        history.pushState({ reviewUrl: url.pathname + url.search + url.hash }, '', url.pathname + url.search + url.hash);
      }
      // 保持点击前的滚动位置，只替换评论内容
      window.scrollTo(0, scrollY);
    } catch (error) {
      window.location.href = url.href;
    } finally {
      loading = false;
      reviews.classList.remove('review-loading');
      reviews.removeAttribute('aria-busy');
    }
  }

  window.addEventListener('popstate', () => {
    const url = new URL(window.location.href);
    if (url.pathname === window.location.pathname) {
      loadReviews(url, false);
    }
  });
})();
