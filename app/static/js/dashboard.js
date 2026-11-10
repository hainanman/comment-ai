(function () {
  const root = document.getElementById('dashboardRoot');
  if (!root) return;

  const apiUrl = root.dataset.url;
  const rangeEl = document.getElementById('range');
  const targetEl = document.getElementById('target');
  const refreshBtn = document.getElementById('refreshBtn');
  const errorEl = document.getElementById('dashboardError');
  const charts = {};
  let resizeTimer = null;

  const violationLabels = {
    ad: '广告引流',
    fraud: '刷单返利',
    abuse: '辱骂攻击',
    false_promo: '虚假宣传',
    irrelevant: '无关内容',
    other: '其他违规'
  };
  const statusLabels = { published: '已发布', reviewing: '待复核', rejected: '已驳回' };

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function pct(value) {
    return `${((Number(value) || 0) * 100).toFixed(1)}%`;
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
        renderKpi(body.data.kpi);
        renderCharts(body.data);
        setText('lastUpdated', new Date().toLocaleString());
      })
      .catch((err) => {
        showError(`数据加载失败：${err.message}`);
      });
  }

  function renderKpi(kpi) {
    setText('kpi-total', kpi.total ?? 0);
    setText('kpi-today', kpi.today ?? 0);
    setText('kpi-reviewing', kpi.reviewing ?? 0);
    setText('kpi-appeals', kpi.appeals ?? 0);
    setText('kpi-reject-rate', pct(kpi.reject_rate));
    setText('kpi-ai-coverage', pct(kpi.ai_coverage));
    setText('kpi-avg-ms', `${kpi.avg_analysis_ms ?? 0} ms`);
    setText('kpi-cost', `¥${Number(kpi.estimated_cost || 0).toFixed(2)}`);
  }

  function renderCharts(data) {
    if (!window.echarts) {
      renderFallback('chart-sentiment', [
        ['好评', data.sentiment.positive],
        ['中评', data.sentiment.neutral],
        ['差评', data.sentiment.negative]
      ]);
      renderFallback('chart-violation', (data.violations || []).map((v) => [violationLabels[v.type] || v.type, v.count]));
      renderFallback('chart-trend', (data.trend || []).map((t) => [t.day, t.total]));
      renderFallback('chart-status', [
        ['已发布', data.status.published],
        ['待复核', data.status.reviewing],
        ['已驳回', data.status.rejected]
      ]);
      return;
    }

    const sentimentChart = ensureChart('chart-sentiment');
    sentimentChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      color: ['#16a34a', '#6b7280', '#dc2626'],
      series: [{
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b}: {c} ({d}%)' },
        data: [
          { name: '好评', value: data.sentiment.positive },
          { name: '中评', value: data.sentiment.neutral },
          { name: '差评', value: data.sentiment.negative }
        ]
      }]
    });

    const violationChart = ensureChart('chart-violation');
    const violations = data.violations || [];
    violationChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 90, right: 20, top: 20, bottom: 20 },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: violations.map((v) => violationLabels[v.type] || v.type)
      },
      series: [{
        type: 'bar',
        data: violations.map((v) => v.count),
        itemStyle: { color: '#2563eb', borderRadius: [0, 4, 4, 0] }
      }]
    });

    const trendChart = ensureChart('chart-trend');
    const trend = data.trend || [];
    trendChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { top: 0 },
      grid: { left: 45, right: 45, top: 35, bottom: 30 },
      xAxis: { type: 'category', data: trend.map((t) => t.day) },
      yAxis: [
        { type: 'value', name: '评论数' },
        { type: 'value', name: '比例', axisLabel: { formatter: (v) => `${(v * 100).toFixed(0)}%` } }
      ],
      series: [
        { name: '评论数', type: 'bar', data: trend.map((t) => t.total), itemStyle: { color: '#93c5fd' } },
        { name: '差评率', type: 'line', yAxisIndex: 1, data: trend.map((t) => t.negative_rate), smooth: true },
        { name: '驳回率', type: 'line', yAxisIndex: 1, data: trend.map((t) => t.reject_rate), smooth: true }
      ]
    });

    const statusChart = ensureChart('chart-status');
    statusChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0 },
      grid: { left: 30, right: 20, top: 20, bottom: 45 },
      xAxis: { type: 'category', data: ['评论'] },
      yAxis: { type: 'value' },
      color: ['#16a34a', '#f59e0b', '#dc2626'],
      series: [
        { name: '已发布', type: 'bar', stack: 'total', barWidth: 36, data: [data.status.published] },
        { name: '待复核', type: 'bar', stack: 'total', data: [data.status.reviewing] },
        { name: '已驳回', type: 'bar', stack: 'total', data: [data.status.rejected] }
      ]
    });
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

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[ch]));
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
