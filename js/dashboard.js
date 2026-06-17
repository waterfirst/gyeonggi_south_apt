// ── 서울 아파트 실거래가 대시보드 ──
const DATA_URL = './data/transactions.json';
const PAGE_SIZE = 20;

let allData = null;
let filtered = [];
let currentPage = 1;
let sortKey = '거래일';
let sortAsc = false;
let selectedGu = null;
let charts = {};

// ── 데이터 로드 ──
async function loadData() {
  const res = await fetch(DATA_URL + '?t=' + Date.now());
  allData = await res.json();
  document.getElementById('updated-at').textContent = '업데이트: ' + allData.updated_at;
  if (allData.note) {
    document.getElementById('sample-badge').style.display = 'inline';
  }
  initFilters();
  applyFilters();
  renderDistrictCards();
}

// ── 필터 초기화 ──
function initFilters() {
  // 구 목록
  const guSel = document.getElementById('filter-gu');
  const gus = [...new Set(allData.transactions.map(t => t.구))].sort();
  gus.forEach(g => {
    const o = document.createElement('option');
    o.value = g; o.textContent = g;
    guSel.appendChild(o);
  });

  // 슬라이더
  document.getElementById('slider-max').addEventListener('input', function() {
    document.getElementById('val-max').textContent = this.value + '억';
    applyFilters();
  });
  document.getElementById('slider-min').addEventListener('input', function() {
    document.getElementById('val-min').textContent = this.value + '억';
    applyFilters();
  });
  document.getElementById('slider-area').addEventListener('input', function() {
    document.getElementById('val-area').textContent = this.value + '㎡~';
    applyFilters();
  });

  document.getElementById('filter-gu').addEventListener('change', applyFilters);
  document.getElementById('filter-year').addEventListener('change', applyFilters);
  document.getElementById('toggle-hangang').addEventListener('change', applyFilters);
  document.getElementById('filter-search').addEventListener('input', applyFilters);
}

// ── 필터 적용 ──
function applyFilters() {
  const gu = document.getElementById('filter-gu').value;
  const maxPrice = parseInt(document.getElementById('slider-max').value) * 10000;
  const minPrice = parseInt(document.getElementById('slider-min').value) * 10000;
  const minArea = parseFloat(document.getElementById('slider-area').value);
  const yearFrom = parseInt(document.getElementById('filter-year').value) || 0;
  const hangangOnly = document.getElementById('toggle-hangang').checked;
  const search = document.getElementById('filter-search').value.trim().toLowerCase();

  filtered = allData.transactions.filter(t => {
    if (gu && t.구 !== gu) return false;
    if (selectedGu && t.구 !== selectedGu) return false;
    if (t.거래금액 > maxPrice) return false;
    if (t.거래금액 < minPrice) return false;
    if (t.전용면적 < minArea) return false;
    if (yearFrom && parseInt(t.건축연도) < yearFrom) return false;
    if (hangangOnly && !t.한강인근) return false;
    if (search && !t.단지명.toLowerCase().includes(search) && !t.구.includes(search)) return false;
    return true;
  });

  sortFiltered();
  currentPage = 1;
  renderSummary();
  renderTable();
  renderCharts();
}

// ── 정렬 ──
function sortFiltered() {
  filtered.sort((a, b) => {
    let va = a[sortKey], vb = b[sortKey];
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    if (va < vb) return sortAsc ? -1 : 1;
    if (va > vb) return sortAsc ? 1 : -1;
    return 0;
  });
}

// ── 요약 카드 ──
function renderSummary() {
  const total = filtered.length;
  const prices = filtered.map(t => t.거래금액);
  const avg = prices.length ? Math.round(prices.reduce((s,v)=>s+v,0)/prices.length/10000*10)/10 : 0;
  const min = prices.length ? Math.min(...prices)/10000 : 0;
  const max = prices.length ? Math.max(...prices)/10000 : 0;
  const guCount = new Set(filtered.map(t=>t.구)).size;

  document.getElementById('sum-total').textContent = total.toLocaleString() + '건';
  document.getElementById('sum-avg').textContent = avg + '억';
  document.getElementById('sum-min').textContent = min.toFixed(1) + '억';
  document.getElementById('sum-max').textContent = max.toFixed(1) + '억';
  document.getElementById('sum-gu').textContent = guCount + '개구';
}

// ── 테이블 렌더 ──
function renderTable() {
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';
  const start = (currentPage - 1) * PAGE_SIZE;
  const page = filtered.slice(start, start + PAGE_SIZE);

  page.forEach(t => {
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    tr.innerHTML = `
      <td><strong>${t.단지명}</strong>${t.한강인근 ? ' <span class="hangang-tag">한강</span>':''}
      </td>
      <td>${t.구}</td>
      <td>${t.법정동}</td>
      <td>${t.전용면적}㎡</td>
      <td>${t.층}층</td>
      <td>${t.건축연도}년</td>
      <td class="price-cell">${t.거래금액_억}억</td>
      <td>${t.거래일}</td>
    `;
    tr.addEventListener('click', () => openModal(t));
    tbody.appendChild(tr);
  });

  renderPagination();
  document.getElementById('table-count').textContent = `총 ${filtered.length.toLocaleString()}건`;
}

// ── 페이지네이션 ──
function renderPagination() {
  const total = Math.ceil(filtered.length / PAGE_SIZE);
  const el = document.getElementById('pagination');
  el.innerHTML = '';

  const btn = (label, page, disabled=false, active=false) => {
    const b = document.createElement('button');
    b.textContent = label;
    if (disabled) b.disabled = true;
    if (active) b.classList.add('active');
    b.addEventListener('click', () => { currentPage = page; renderTable(); });
    return b;
  };

  el.appendChild(btn('◀', currentPage-1, currentPage<=1));
  const range = 2;
  for (let i=Math.max(1,currentPage-range); i<=Math.min(total,currentPage+range); i++) {
    el.appendChild(btn(i, i, false, i===currentPage));
  }
  el.appendChild(btn('▶', currentPage+1, currentPage>=total));
}

// ── 구별 카드 렌더 ──
function renderDistrictCards() {
  const container = document.getElementById('district-cards');
  container.innerHTML = '';
  allData.district_stats.forEach(s => {
    const card = document.createElement('div');
    card.className = 'district-card' + (s.한강인근 ? ' hangang' : '');
    card.innerHTML = `
      <div class="gu-name">${s.구} ${s.한강인근 ? '<span class="hangang-label">한강</span>':''}</div>
      <div class="gu-count">${s.거래수}건</div>
      <div class="gu-avg">평균 ${s.평균가_억}억</div>
      <div class="gu-range">${s.최저가_억}~${s.최고가_억}억</div>
    `;
    card.addEventListener('click', () => {
      if (selectedGu === s.구) {
        selectedGu = null;
        card.classList.remove('active');
      } else {
        document.querySelectorAll('.district-card').forEach(c => c.classList.remove('active'));
        selectedGu = s.구;
        card.classList.add('active');
        document.getElementById('filter-gu').value = '';
      }
      applyFilters();
    });
    container.appendChild(card);
  });
}

// ── 차트 렌더 ──
function renderCharts() {
  renderBarChart();
  renderLineChart();
  renderAreaChart();
}

function renderBarChart() {
  const guStats = {};
  filtered.forEach(t => {
    if (!guStats[t.구]) guStats[t.구] = { sum: 0, cnt: 0 };
    guStats[t.구].sum += t.거래금액;
    guStats[t.구].cnt++;
  });
  const sorted = Object.entries(guStats)
    .map(([g, v]) => ({ gu: g, avg: Math.round(v.sum/v.cnt/10000*10)/10 }))
    .sort((a,b) => b.avg - a.avg)
    .slice(0, 15);

  const ctx = document.getElementById('chart-bar').getContext('2d');
  if (charts.bar) charts.bar.destroy();
  charts.bar = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(s => s.gu),
      datasets: [{
        label: '평균 거래가 (억)',
        data: sorted.map(s => s.avg),
        backgroundColor: sorted.map(s => {
          const hangangSet = new Set(['마포구','용산구','영등포구','성동구','광진구','동작구','강동구','강남구','서초구','송파구']);
          return hangangSet.has(s.gu) ? '#0097a7cc' : '#1a73e8cc';
        }),
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { callback: v => v+'억' } },
        x: { ticks: { font: { size: 10 } } }
      }
    }
  });
}

function renderLineChart() {
  const monthStats = {};
  filtered.forEach(t => {
    const ym = t.년 + '-' + t.월;
    monthStats[ym] = (monthStats[ym] || 0) + 1;
  });
  const sorted = Object.entries(monthStats).sort((a,b) => a[0].localeCompare(b[0])).slice(-12);

  const ctx = document.getElementById('chart-line').getContext('2d');
  if (charts.line) charts.line.destroy();
  charts.line = new Chart(ctx, {
    type: 'line',
    data: {
      labels: sorted.map(e => e[0]),
      datasets: [{
        label: '거래량',
        data: sorted.map(e => e[1]),
        borderColor: '#1a73e8',
        backgroundColor: '#1a73e820',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { font: { size: 10 } } } }
    }
  });
}

function renderAreaChart() {
  const buckets = { '84~95㎡': 0, '95~115㎡': 0, '115~135㎡': 0, '135㎡ 이상': 0 };
  filtered.forEach(t => {
    const a = t.전용면적;
    if (a < 95) buckets['84~95㎡']++;
    else if (a < 115) buckets['95~115㎡']++;
    else if (a < 135) buckets['115~135㎡']++;
    else buckets['135㎡ 이상']++;
  });

  const ctx = document.getElementById('chart-area').getContext('2d');
  if (charts.area) charts.area.destroy();
  charts.area = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: Object.keys(buckets),
      datasets: [{
        data: Object.values(buckets),
        backgroundColor: ['#1a73e8','#0097a7','#34a853','#fbbc04'],
        borderWidth: 2,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { font: { size: 11 } } } }
    }
  });
}

// ── 모달 ──
function openModal(t) {
  document.getElementById('modal-title').textContent = t.단지명;
  const history = filtered.filter(x => x.단지명 === t.단지명)
    .sort((a,b) => b.거래일.localeCompare(a.거래일))
    .slice(0, 10);

  let rows = `
    <table>
      <tr><th>구/동</th><td>${t.구} ${t.법정동}</td></tr>
      <tr><th>전용면적</th><td>${t.전용면적}㎡</td></tr>
      <tr><th>층수</th><td>${t.층}층</td></tr>
      <tr><th>건축연도</th><td>${t.건축연도}년</td></tr>
      <tr><th>거래금액</th><td class="price-cell"><strong>${t.거래금액_억}억원</strong></td></tr>
      <tr><th>거래일</th><td>${t.거래일}</td></tr>
    </table>
    <h4 style="margin:16px 0 8px;font-size:13px;color:#5f6368">최근 거래 이력</h4>
    <table>
      <thead><tr>
        <th style="font-size:11px">거래일</th>
        <th style="font-size:11px">면적</th>
        <th style="font-size:11px">층</th>
        <th style="font-size:11px">금액</th>
      </tr></thead>
      <tbody>`;
  history.forEach(h => {
    rows += `<tr>
      <td>${h.거래일}</td>
      <td>${h.전용면적}㎡</td>
      <td>${h.층}층</td>
      <td class="price-cell">${h.거래금액_억}억</td>
    </tr>`;
  });
  rows += `</tbody></table>`;

  const naverUrl = `https://new.land.naver.com/search?query=${encodeURIComponent(t.단지명)}`;
  rows += `<a href="${naverUrl}" target="_blank" class="naver-link">네이버 부동산에서 보기 →</a>`;

  document.getElementById('modal-body').innerHTML = rows;
  document.getElementById('modal-overlay').classList.add('open');
}

// ── 정렬 헤더 클릭 ──
document.querySelectorAll('th[data-key]').forEach(th => {
  th.addEventListener('click', () => {
    const key = th.dataset.key;
    if (sortKey === key) sortAsc = !sortAsc;
    else { sortKey = key; sortAsc = false; }
    document.querySelectorAll('th[data-key]').forEach(t => {
      t.classList.remove('sorted');
      t.querySelector('.sort-icon').textContent = '↕';
    });
    th.classList.add('sorted');
    th.querySelector('.sort-icon').textContent = sortAsc ? '↑' : '↓';
    sortFiltered();
    currentPage = 1;
    renderTable();
  });
});

// ── 필터 초기화 버튼 ──
document.getElementById('btn-reset').addEventListener('click', () => {
  document.getElementById('filter-gu').value = '';
  document.getElementById('slider-max').value = 25;
  document.getElementById('slider-min').value = 10;
  document.getElementById('slider-area').value = 84;
  document.getElementById('filter-year').value = '';
  document.getElementById('toggle-hangang').checked = false;
  document.getElementById('filter-search').value = '';
  document.getElementById('val-max').textContent = '25억';
  document.getElementById('val-min').textContent = '10억';
  document.getElementById('val-area').textContent = '84㎡~';
  selectedGu = null;
  document.querySelectorAll('.district-card').forEach(c => c.classList.remove('active'));
  applyFilters();
});

// ── 모달 닫기 ──
document.getElementById('modal-close').addEventListener('click', () => {
  document.getElementById('modal-overlay').classList.remove('open');
});
document.getElementById('modal-overlay').addEventListener('click', (e) => {
  if (e.target === document.getElementById('modal-overlay'))
    document.getElementById('modal-overlay').classList.remove('open');
});

// ── 시작 ──
loadData().catch(e => {
  document.getElementById('tbody').innerHTML = '<tr><td colspan="8" style="text-align:center;padding:40px;color:#999">데이터를 불러오는 중 오류가 발생했습니다.</td></tr>';
  console.error(e);
});
