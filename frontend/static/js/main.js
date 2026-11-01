let currentSummaryText = '';
let currentTopic = '';
let currentData = null;
let audioScript = '';
let allPapers = [];
let yearDistChartInstance = null;
let trendChartInstance = null;
let activeYearFilter = null;

function setTopic(t) {
  document.getElementById('topicInput').value = t;
  document.getElementById('topicInput').focus();
}

function setStep(n) {
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById(`step${i}`);
    el.className = 'lstep' + (i < n ? ' done' : i === n ? ' active' : '');
  }
}

async function startResearch() {
  const topic = document.getElementById('topicInput').value.trim();
  if (!topic) { document.getElementById('topicInput').focus(); return; }
  currentTopic = topic;

  document.getElementById('resultsArea').classList.add('hidden');
  document.getElementById('audioSection').classList.add('hidden');
  document.getElementById('trendSection').classList.add('hidden');
  document.getElementById('yearPapersSection').classList.add('hidden');
  document.getElementById('litSection').classList.add('hidden');
  document.getElementById('reportSection').classList.add('hidden');
  document.getElementById('loadingState').classList.remove('hidden');
  document.getElementById('searchBtn').disabled = true;

  setStep(1); await sleep(700);
  setStep(2);

  try {
    const res = await fetch('/api/research', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic })
    });
    await sleep(500); setStep(3);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    await sleep(300); setStep(4); await sleep(300);

    currentSummaryText = data.summary_text;
    currentData = data;
    renderResults(data);
  } catch (err) {
    alert('Error: ' + err.message);
  } finally {
    document.getElementById('loadingState').classList.add('hidden');
    document.getElementById('searchBtn').disabled = false;
  }
}

function renderResults(data) {
  document.getElementById('resTitle').textContent = data.topic;
  const count = data.paper_count || 0;
  document.getElementById('resMeta').textContent =
    `Found ${count} research paper${count !== 1 ? 's' : ''} · ${new Date(data.timestamp).toLocaleTimeString()}`;

  renderSections(data.sections);
  renderDatasets(data.datasets);
  allPapers = data.papers;
  renderYearDistChart(data.papers);
  renderPapers(data.papers);
  renderTrendGraph(data.year_distribution, data.topic);
  renderLitReview(data.introduction, data.literature_review);
  renderReport(data);

  document.getElementById('resultsArea').classList.remove('hidden');
  document.getElementById('resultsArea').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ── Section Cards ─────────────────────────── */
const SECTION_CFG = [
  { key: 'BRIEF INTRODUCTION',           icon: '💡', cls: 'sc-blue'   },
  { key: 'CURRENT STATE OF RESEARCH',    icon: '🔬', cls: 'sc-cyan'   },
  { key: 'RESEARCH GAPS & OPPORTUNITIES',icon: '🎯', cls: 'sc-amber'  },
];

function cleanMd(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>');
}

function renderSections(sections) {
  const grid = document.getElementById('sectionsGrid');
  grid.innerHTML = '';
  SECTION_CFG.forEach((cfg, idx) => {
    const raw = sections[cfg.key]; if (!raw) return;
    const lines = raw.split('\n')
      .map(l => l.replace(/^[-•*]\s*|^\d+\.\s*/, '').trim())
      .filter(l => l.length > 2 && !l.startsWith('##'));
    const body = '<ul>' + lines.map(l => `<li>${cleanMd(l)}</li>`).join('') + '</ul>';
    const card = document.createElement('div');
    card.className = `scard ${cfg.cls}`;
    card.style.animationDelay = `${idx * 0.08}s`;
    card.innerHTML = `
      <div class="scard-head">
        <div class="scard-icon">${cfg.icon}</div>
        <div class="scard-title">${cfg.key}</div>
      </div>
      <div class="scard-body">${body}</div>`;
    grid.appendChild(card);
  });
}

/* ── Datasets ──────────────────────────────── */
function renderDatasets(datasets) {
  const grid = document.getElementById('datasetsGrid');
  grid.innerHTML = '';
  if (!datasets || datasets.length === 0) {
    grid.innerHTML = '<p style="color:var(--muted);font-size:14px;">No specific datasets found.</p>';
    return;
  }
  datasets.forEach((ds, idx) => {
    const el = document.createElement('div');
    el.className = 'dcard';
    el.style.animationDelay = `${idx * 0.07}s`;
    el.innerHTML = `
      <div class="dcard-name">📦 ${ds.name || 'Dataset'}</div>
      ${ds.domain ? `<div class="dcard-domain">${ds.domain}</div>` : ''}
      <div class="dcard-desc">${ds.description || 'A benchmark dataset used in this research domain.'}</div>`;
    grid.appendChild(el);
  });
}

/* ── Papers ────────────────────────────────── */
function renderPapers(papers, container = 'papersGrid') {
  const grid = document.getElementById(container);
  grid.innerHTML = '';
  if (!papers || papers.length === 0) {
    grid.innerHTML = '<div style="padding:32px;text-align:center;color:var(--muted);background:#fff;border-radius:16px;border:1.5px solid #e2e8f0;">No papers found. Try a broader topic.</div>';
    return;
  }
  papers.forEach((p, idx) => {
    const authors = (p.authors && p.authors.length)
      ? p.authors.slice(0, 3).join(', ') + (p.authors.length > 3 ? ' et al.' : '')
      : 'Unknown Authors';
    let actions = '';
    if (p.url) actions += `<a class="pbtn pbtn-link" href="${p.url}" target="_blank" rel="noopener">🔗 View</a>`;
    if (p.pdf_url) actions += `<a class="pbtn pbtn-pdf" href="${p.pdf_url}" target="_blank" rel="noopener">📄 PDF</a>`;
    if (!p.url && !p.pdf_url) actions = '<div class="pbtn-none">No link</div>';
    const cite = p.citation_count > 0 ? `<span class="pcard-cite">📊 ${p.citation_count} citations</span>` : '';
    const venue = p.venue ? `<span class="pcard-cite">📰 ${p.venue}</span>` : '';
    const el = document.createElement('div');
    el.className = 'pcard';
    el.style.animationDelay = `${idx * 0.04}s`;
    el.innerHTML = `
      <div class="pcard-info">
        <div class="pcard-title">${p.title}</div>
        <div class="pcard-meta">
          <span class="pcard-authors">👤 ${authors}</span>
          <span class="pcard-year">${p.year || 'N/A'}</span>
          ${cite}${venue}
        </div>
        ${p.abstract ? `<div class="pcard-abstract">${p.abstract}${p.abstract.length >= 400 ? '…' : ''}</div>` : ''}
      </div>
      <div class="pcard-actions">${actions}</div>`;
    grid.appendChild(el);
  });
}

/* ── Year Selector Dropdown ────────────────── */
function buildYearSelector(papers) {
  const sel = document.getElementById('yearSelect');
  while (sel.options.length > 1) sel.remove(1);

  // Count from fetched papers
  const yearCount = {};
  papers.forEach(p => {
    const y = parseInt(p.year);
    if (!isNaN(y) && y >= 2005 && y <= 2026)
      yearCount[y] = (yearCount[y] || 0) + 1;
  });

  // Show all years 2026 down to 2005
  for (let y = 2026; y >= 2005; y--) {
    const count = yearCount[y] || 0;
    const opt = document.createElement('option');
    opt.value = y;
    opt.textContent = count > 0
      ? `${y}  ·  ${count} paper${count!==1?'s':''} found`
      : `${y}  ·  no papers in local results`;
    if (count === 0) opt.style.color = '#94a3b8';
    sel.appendChild(opt);
  }
  window._yearCountMap = yearCount;
}

async function onYearSelect(year) {
  if (!year) { clearYearSelect(); return; }
  const result = document.getElementById('yscResult');
  const loading = document.getElementById('yscLoading');
  const countEl = document.getElementById('yscCount');
  const labelEl = document.getElementById('yscLabel');
  const clearBtn = document.getElementById('yscClear');

  result.classList.remove('hidden');
  loading.classList.remove('hidden');
  clearBtn.classList.remove('hidden');
  countEl.textContent = '…';
  labelEl.textContent = `Papers in ${year}`;

  // First show local count from fetched papers
  const localCount = (window._yearCountMap || {})[year] || 0;
  const localFiltered = allPapers.filter(p => String(p.year) === String(year));
  renderPapers(localFiltered);
  document.getElementById('papersGrid').scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Then fetch more from backend
  try {
    const res = await fetch('/api/papers-by-year', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: currentTopic, year: parseInt(year) })
    });
    const data = await res.json();
    loading.classList.add('hidden');
    if (data.error) throw new Error(data.error);
    const papers = data.papers || [];
    countEl.textContent = papers.length;
    labelEl.textContent = `Papers published in ${year}`;
    document.getElementById('papersSubtitle').textContent =
      `Showing ${papers.length} real paper${papers.length!==1?'s':''} from ${year} on "${currentTopic}"`;
    renderPapers(papers);
  } catch(err) {
    loading.classList.add('hidden');
    countEl.textContent = localCount;
    labelEl.textContent = `Papers in ${year} (local)`;
    document.getElementById('papersSubtitle').textContent =
      `Showing ${localFiltered.length} paper${localFiltered.length!==1?'s':''} from ${year}`;
  }
}

function clearYearSelect() {
  document.getElementById('yearSelect').value = '';
  document.getElementById('yscResult').classList.add('hidden');
  document.getElementById('yscClear').classList.add('hidden');
  document.getElementById('papersSubtitle').textContent = 'All fetched papers — select a year to filter';
  renderPapers(allPapers);
}

function renderYearDistChart(papers) { buildYearSelector(papers); }
function resetYearFilter() { clearYearSelect(); }

/* ── Trend Graph (click year → fetch real papers) ── */
function renderTrendGraph(yearDist, topic) {
  const section = document.getElementById('trendSection');
  if (!yearDist || Object.keys(yearDist).length === 0) { section.classList.add('hidden'); return; }
  section.classList.remove('hidden');

  const years = Object.keys(yearDist).sort();
  const counts = years.map(y => yearDist[y]);
  const total = counts.reduce((a, b) => a + b, 0);
  const peak = Math.max(...counts);
  const peakYear = years[counts.indexOf(peak)];
  const recent = counts.slice(-3).reduce((a, b) => a + b, 0);

  document.getElementById('trendStats').innerHTML = `
    <div class="tstat"><div class="tstat-val">${total}</div><div class="tstat-label">Total Papers Found</div></div>
    <div class="tstat"><div class="tstat-val">${peakYear}</div><div class="tstat-label">Peak Year</div></div>
    <div class="tstat"><div class="tstat-val">${peak}</div><div class="tstat-label">Papers in Peak Year</div></div>
    <div class="tstat"><div class="tstat-val">${recent}</div><div class="tstat-label">Papers (Last 3 Years)</div></div>`;

  if (trendChartInstance) trendChartInstance.destroy();
  const ctx = document.getElementById('trendChart').getContext('2d');
  const grad = ctx.createLinearGradient(0, 0, 0, 340);
  grad.addColorStop(0, 'rgba(37,99,235,0.25)');
  grad.addColorStop(1, 'rgba(37,99,235,0.0)');

  trendChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: years,
      datasets: [{
        label: 'Publications',
        data: counts,
        borderColor: '#2563eb', borderWidth: 2.5,
        backgroundColor: grad, fill: true, tension: 0.45,
        pointBackgroundColor: '#2563eb', pointBorderColor: '#fff',
        pointBorderWidth: 2, pointRadius: 5,
        pointHoverRadius: 9, pointHoverBackgroundColor: '#1d4ed8',
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      onClick: async (evt, elements) => {
        if (!elements.length) return;
        const year = parseInt(years[elements[0].index]);
        await fetchYearPapers(year);
      },
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          text: `Research Trend in ${topic}`,
          color: '#1e293b', font: { family: 'Syne', size: 15, weight: '700' }, padding: { bottom: 20 }
        },
        tooltip: {
          backgroundColor: '#fff', titleColor: '#0f172a', bodyColor: '#2563eb',
          borderColor: '#e2e8f0', borderWidth: 1, padding: 12, cornerRadius: 10, displayColors: false,
          callbacks: {
            title: ctx => `Year: ${ctx[0].label}`,
            label: ctx => ` ${ctx.raw} publication${ctx.raw !== 1 ? 's' : ''}`,
            afterLabel: () => 'Click to see these papers ↓'
          }
        }
      },
      scales: {
        x: { grid: { display: false }, border: { display: false },
             ticks: { font: { family: 'DM Sans', size: 12 }, color: '#64748b', maxRotation: 0 } },
        y: { beginAtZero: true, border: { display: false }, grid: { color: 'rgba(226,232,240,0.7)' },
             title: { display: true, text: 'Publications', color: '#94a3b8', font: { family: 'DM Sans', size: 12 } },
             ticks: { font: { family: 'DM Sans', size: 12 }, color: '#94a3b8', stepSize: 1, callback: v => Number.isInteger(v) ? v : '' } }
      }
    }
  });
}

async function fetchYearPapers(year) {
  const section = document.getElementById('yearPapersSection');
  const loading = document.getElementById('yearPapersLoading');
  const list = document.getElementById('yearPapersList');
  document.getElementById('yearPapersTitle').textContent = `Papers from ${year}`;
  document.getElementById('yearPapersSubtitle').textContent = `Fetching real papers published in ${year} on "${currentTopic}"…`;
  section.classList.remove('hidden');
  loading.classList.remove('hidden');
  list.innerHTML = '';
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });

  try {
    const res = await fetch('/api/papers-by-year', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: currentTopic, year })
    });
    const data = await res.json();
    loading.classList.add('hidden');
    if (data.error) throw new Error(data.error);
    const papers = data.papers || [];
    document.getElementById('yearPapersSubtitle').textContent =
      `${papers.length} paper${papers.length !== 1 ? 's' : ''} found on "${currentTopic}" in ${year}`;
    renderPapers(papers, 'yearPapersList');
  } catch (err) {
    loading.classList.add('hidden');
    list.innerHTML = `<div style="padding:24px;color:#ef4444;">Error: ${err.message}</div>`;
  }
}

function closeYearPapers() {
  document.getElementById('yearPapersSection').classList.add('hidden');
}

/* ── Literature Review ─────────────────────── */
function renderLitReview(introduction, literatureReview) {
  const section = document.getElementById('litSection');
  const card = document.getElementById('litCard');
  if (!introduction && !literatureReview) { section.classList.add('hidden'); return; }
  section.classList.remove('hidden');

  let html = '';
  if (introduction) {
    html += `<div class="lit-section">
      <div class="lit-section-title"><span style="background:#ecfdf5;color:#059669">📝</span> Introduction</div>`;
    introduction.split('\n\n').filter(p => p.trim()).forEach(para => {
      html += `<p class="lit-para">${para.trim().replace(/\n/g, ' ')}</p>`;
    });
    html += `</div>`;
  }
  if (literatureReview) {
    html += `<div class="lit-section">
      <div class="lit-section-title"><span style="background:#eff6ff;color:#2563eb">📚</span> Literature Review</div>`;
    literatureReview.split('\n\n').filter(p => p.trim()).forEach(para => {
      html += `<p class="lit-para">${para.trim().replace(/\n/g, ' ')}</p>`;
    });
    html += `</div>`;
  }
  card.innerHTML = html;
}

/* ── PDF Download ──────────────────────────── */
async function downloadPDF() {
  const btn = document.getElementById('downloadPdfBtn');
  btn.textContent = '⏳ Generating PDF…'; btn.disabled = true;
  try {
    const res = await fetch('/api/download-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: currentData.topic,
        papers: currentData.papers,
        sections: currentData.sections,
        introduction: currentData.introduction || '',
        literature_review: currentData.literature_review || ''
      })
    });
    if (!res.ok) { const d = await res.json(); throw new Error(d.error); }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentTopic.replace(/\s+/g,'_')}_LitReview.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert('PDF error: ' + err.message);
  } finally {
    btn.textContent = '⬇ Download Full PDF'; btn.disabled = false;
  }
}

/* ── Audio ─────────────────────────────────── */
async function generateAudio() {
  const btn = document.getElementById('audioBtn');
  btn.textContent = '⏳ Generating…'; btn.disabled = true;
  try {
    const res = await fetch('/api/audio', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: currentSummaryText, topic: currentTopic })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    audioScript = data.audio_script;
    document.getElementById('audioSection').classList.remove('hidden');
    document.getElementById('audioStatus').textContent = 'Click Play to listen';
    document.getElementById('audioSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (err) {
    alert('Audio error: ' + err.message);
  } finally {
    btn.textContent = '🔊 Generate Audio Summary'; btn.disabled = false;
  }
}

function playAudio() {
  if (!audioScript) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(audioScript);
  u.rate = 0.92; u.pitch = 1;
  const voices = speechSynthesis.getVoices();
  const v = voices.find(v => v.lang === 'en-US' && v.name.includes('Google')) || voices.find(v => v.lang === 'en-US') || voices[0];
  if (v) u.voice = v;
  u.onstart = () => { document.getElementById('audioStatus').textContent = '🔊 Playing…'; };
  u.onend   = () => { document.getElementById('audioStatus').textContent = 'Finished'; };
  speechSynthesis.speak(u);
}

function stopAudio() { speechSynthesis.cancel(); document.getElementById('audioStatus').textContent = 'Stopped'; }

function downloadAudioScript() {
  if (!audioScript) return;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([audioScript], { type: 'text/plain' }));
  a.download = `${currentTopic.replace(/\s+/g,'_')}_Audio_Summary.txt`;
  a.click();
}

/* ── Final Report ──────────────────────────── */
function renderReport(data) {
  const section = document.getElementById('reportSection');
  const card = document.getElementById('reportCard');
  section.classList.remove('hidden');

  const ts = new Date(data.timestamp);
  const dateStr = ts.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
  const timeStr = ts.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  const sections = data.sections || {};
  const datasets = data.datasets || [];
  const papers = data.papers || [];

  const sectionCfg = [
    { key: 'BRIEF INTRODUCTION',           icon: '💡', bg: '#eff6ff', color: '#2563eb' },
    { key: 'KEY CONCEPTS & DEFINITIONS',   icon: '📖', bg: '#f5f3ff', color: '#7c3aed' },
    { key: 'CURRENT STATE OF RESEARCH',    icon: '🔬', bg: '#ecfeff', color: '#0891b2' },
    { key: 'RESEARCH GAPS & OPPORTUNITIES',icon: '🎯', bg: '#fffbeb', color: '#d97706' },
    { key: 'METHODOLOGY OVERVIEW',         icon: '⚙️', bg: '#fdf2f8', color: '#db2777' },
    { key: 'KEY TAKEAWAYS',               icon: '✨', bg: '#f0fdf4', color: '#059669' },
  ];

  let sectionsHTML = '';
  sectionCfg.forEach(cfg => {
    const content = sections[cfg.key]; if (!content) return;
    const lines = content.split('\n').map(l => l.replace(/^[-•*]\s*|^\d+\.\s*/, '').trim()).filter(l => l.length > 2);
    sectionsHTML += `<div class="report-section">
      <div class="report-section-title"><span style="background:${cfg.bg};color:${cfg.color}">${cfg.icon}</span>${cfg.key}</div>
      <ul class="report-points">${lines.map(l => `<li>${cleanMd(l)}</li>`).join('')}</ul>
    </div>`;
  });

  let dsHTML = datasets.slice(0, 6).map(ds => `
    <div class="report-ds-item"><strong>📦 ${ds.name || 'Dataset'}</strong>
    <span>${ds.domain || ''} ${ds.description ? '— ' + ds.description : ''}</span></div>`).join('');

  let papersHTML = papers.slice(0, 5).map((p, i) => {
    const authors = (p.authors || []).slice(0, 2).join(', ') + (p.authors?.length > 2 ? ' et al.' : '');
    const link = p.url ? `<a href="${p.url}" target="_blank" style="color:var(--primary);font-size:11px;text-decoration:none;">View →</a>` : '';
    return `<div class="report-ds-item" style="border-left-color:var(--primary);">
      <strong>${i+1}. ${p.title}</strong><span>${authors} · ${p.year} ${link}</span></div>`;
  }).join('');

  card.innerHTML = `
    <div class="report-header">
      <h2>📋 Research Report: ${data.topic}</h2>
      <p>AI-Generated Literature Review Summary</p>
      <div class="report-meta">
        <div class="report-meta-item">📅 ${dateStr} at ${timeStr}</div>
        <div class="report-meta-item">📄 ${data.paper_count} papers analyzed</div>
        <div class="report-meta-item">🗃️ ${datasets.length} datasets identified</div>
      </div>
    </div>
    <div class="report-body">
      ${sectionsHTML}
      <div class="report-section">
        <div class="report-section-title"><span style="background:#eff6ff;color:#2563eb">📄</span> Key Papers Analyzed</div>
        <div class="report-datasets">${papersHTML || '<p style="color:var(--muted);font-size:13px;">No papers found.</p>'}</div>
      </div>
    </div>
    <div class="report-footer">
      <div class="report-footer-text">ResearchMind AI · Team: P. Bharani, Ch. Bharathi, V. Anusha, K. Deena Flarance · Guide: Dr. K. Prasanthi</div>
      <button class="report-print-btn" onclick="window.print()">🖨️ Print / Save as PDF</button>
    </div>`;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('topicInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') startResearch();
  });
});