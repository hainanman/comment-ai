(function () {
  const root = document.getElementById('sentimentRoot');
  if (!root) return;

  const apiUrl = root.dataset.url;
  const rangeEl = document.getElementById('sentimentRange');
  const targetEl = document.getElementById('sentimentTarget');
  const refreshBtn = document.getElementById('sentimentRefresh');
  const errorEl = document.getElementById('sentimentError');
  const alertEl = document.getElementById('sentimentAlert');
  const charts = {};
  let resizeTimer = null;

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function pct(value) {
    return `${((Number(value) || 0) * 100).toFixed(1)}%`;
  }

  function pp(value) {
    const number = Number(value) || 0;
    const sign = number > 0 ? '+' : '';
    return `${sign}${(number * 100).toFixed(1)}pp`;
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[ch]));
  }

  function showError(message) {
    if (!errorEl) return;
    errorEl.style.display = message ? 'block' : 'none';
    errorEl.textContent = message || '';
  }

  function fetchData() {
    showError('');
    const params = new URLSearchParams({ range: rangeEl.value });
    const target = targetEl.value.trim();
    if (target) params.set('target', target);

    fetch(`${apiUrl}?${params.toString()}`, { headers: { Accept: 'application/json' } })
      .then((resp) => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
      })
      .then((body) => {
        if (!body.ok) throw new Error(body.error?.message || '数据加载失败');
        renderKpi(body.data);
        renderAlert(body.data.alert);
        renderCharts(body.data);
        renderTable(body.data.products || []);
        renderRecent(body.data.recent_negative || []);
        setText('sentimentUpdated', new Date().toLocaleString());
      })
      .catch((err) => {
        showError(`数据加载失败：${err.message}`);
      });
  }

  function renderKpi(data) {
    const overall = data.overall || {};
    setText('s-total', overall.total ?? 0);
    setText('s-positive-rate', pct(overall.positive_rate));
    setText('s-negative-rate', pct(overall.negative_rate));
    setText('s-negative-count', overall.negative ?? 0);
    setText('s-average', overall.total ? Number(overall.average || 0).toFixed(1) : '—');
    setText('s-delta', pp(data.delta?.negative_rate));
  }

  function renderAlert(alert) {
    if (!alertEl || !alert) return;
    const level = alert.level === 'warning' ? 'warning' : (alert.level === 'ok' ? 'success' : 'info');
    alertEl.className = `alert alert-${level}`;
    alertEl.textContent = alert.message || '';
  }

  function renderCharts(data) {
    const trend = data.trend || [];
    const products = data.products || [];
    const keywords = data.negative_keywords || [];

    if (!window.echarts) {
      renderFallback('chart-sentiment-trend', trend.map((item) => [item.day, item.negative]));
      renderFallback('chart-sentiment-product', products.map((item) => [item.name, Math.round(item.negative_rate * 100)]));
      renderFallback('chart-sentiment-keywords', keywords.map((item) => [item.word, item.count]));
      return;
    }

    const trendChart = ensureChart('chart-sentiment-trend');
    trendChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { top: 0, data: ['好评', '中评', '差评', '差评率'] },
      grid: { left: 45, right: 50, top: 40, bottom: 35 },
      xAxis: { type: 'category', data: trend.map((item) => item.day) },
      yAxis: [
        { type: 'value', name: '评论数' },
        { type: 'value', name: '差评率', max: 1, axisLabel: { formatter: (v) => `${(v * 100).toFixed(0)}%` } }
      ],
      series: [
        { name: '好评', type: 'bar', stack: 'sentiment', data: trend.map((item) => item.positive), itemStyle: { color: '#16a34a' } },
        { name: '中评', type: 'bar', stack: 'sentiment', data: trend.map((item) => item.neutral), itemStyle: { color: '#94a3b8' } },
        { name: '差评', type: 'bar', stack: 'sentiment', data: trend.map((item) => item.negative), itemStyle: { color: '#dc2626' } },
        { name: '差评率', type: 'line', yAxisIndex: 1, smooth: true, data: trend.map((item) => item.negative_rate), itemStyle: { color: '#7f1d1d' } }
      ]
    });

    const productChart = ensureChart('chart-sentiment-product');
    productChart.setOption({
      tooltip: { trigger: 'axis', valueFormatter: (v) => `${v}%` },
      grid: { left: 90, right: 30, top: 15, bottom: 25 },
      xAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
      yAxis: { type: 'category', data: products.map((item) => item.name) },
      series: [{
        type: 'bar',
        data: products.map((item) => Math.round(item.negative_rate * 1000) / 10),
        itemStyle: { color: '#dc2626', borderRadius: [0, 4, 4, 0] }
      }]
    });

    const keywordChart = ensureChart('chart-sentiment-keywords');
    keywordChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 80, right: 25, top: 15, bottom: 25 },
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: keywords.map((item) => item.word).reverse() },
      series: [{
        type: 'bar',
        data: keywords.map((item) => item.count).reverse(),
        itemStyle: { color: '#f59e0b', borderRadius: [0, 4, 4, 0] }
      }]
    });
  }

  function renderTable(products) {
    const body = document.getElementById('sentiment-product-body');
    if (!body) return;
    if (!products.length) {
      body.innerHTML = '<tr><td colspan="5" class="text-muted">暂无已发布评论</td></tr>';
      return;
    }
    body.innerHTML = products.map((item) => {
      const name = item.slug
        ? `<a href="/products/${encodeURIComponent(item.slug)}">${escapeHtml(item.name)}</a>`
        : escapeHtml(item.name);
      const rateClass = item.negative_rate >= 0.3 ? 'text-danger' : '';
      return `<tr>
        <td>${name}</td>
        <td>${item.total}</td>
        <td>${pct(item.positive_rate)}</td>
        <td class="${rateClass}">${pct(item.negative_rate)}</td>
        <td>${Number(item.average || 0).toFixed(1)}</td>
      </tr>`;
    }).join('');
  }

  function renderRecent(items) {
    const list = document.getElementById('recent-negative-list');
    if (!list) return;
    if (!items.length) {
      list.innerHTML = '<p class="text-muted mb-0">当前范围没有差评评论。</p>';
      return;
    }
    list.innerHTML = items.map((item) => {
      const name = item.slug
        ? `<a href="/products/${encodeURIComponent(item.slug)}">${escapeHtml(item.target_name)}</a>`
        : escapeHtml(item.target_name);
      const keywords = (item.keywords || []).map((word) => `<span class="keyword">${escapeHtml(word)}</span>`).join('');
      return `<article class="sentiment-recent-item">
        <div class="d-flex justify-content-between align-items-start gap-2">
          <strong>${name}</strong>
          <span class="meta">${escapeHtml(item.created_at)}</span>
        </div>
        <p class="comment-content mt-1 mb-1">${escapeHtml(item.content)}</p>
        <div>${keywords}</div>
      </article>`;
    }).join('');
  }

  function ensureChart(id) {
    if (!charts[id]) {
      charts[id] = window.echarts.init(document.getElementById(id));
    }
    return charts[id];
  }

  function renderFallback(id, rows) {
    const el = document.getElementById(id);
    if (!el) return;
    const usable = (rows || []).filter((row) => Number(row[1]) > 0);
    if (!usable.length) {
      el.innerHTML = '<div class="empty">暂无数据</div>';
      return;
    }
    const max = Math.max(...usable.map((row) => Number(row[1])));
    el.innerHTML = usable.map((row) => {
      const width = max ? Math.max(4, Math.round((Number(row[1]) / max) * 100)) : 0;
      return `<div class="fallback-row"><span>${escapeHtml(row[0])}</span><span class="fallback-bar" style="width:${width}%"></span><b>${row[1]}</b></div>`;
    }).join('');
  }

  refreshBtn?.addEventListener('click', fetchData);
  rangeEl?.addEventListener('change', fetchData);
  targetEl?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') fetchData();
  });
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      Object.values(charts).forEach((chart) => chart.resize());
    }, 150);
  });

  fetchData();
})();
