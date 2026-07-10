/* ============================================
   AI STOCK ANALYST - Dashboard JavaScript
   ============================================ */

let DATA = null;
let charts = {};
let currentTopList = 'gainers';
let currentSignalFilter = 'all';
let breadthChart = null;
let signalChart = null;

/* ===== INIT ===== */
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    document.getElementById('headerDate').textContent =
        new Date().toLocaleDateString('vi-VN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
});

function loadData() {
    try {
        DATA = window._STOCK_DATA;
        if (DATA) {
            document.getElementById('loadingScreen').classList.add('hidden');
            const badge = document.getElementById('dataLoadedBadge');
            badge.textContent = '✓ DATA LOADED';
            badge.style.cssText = 'position:fixed;top:4px;right:4px;background:#0f730f;color:#fff;font-size:11px;padding:3px 8px;border-radius:4px;z-index:99999';
            renderAll();
        } else {
            setTimeout(loadData, 500);
        }
    } catch (e) {
        console.error('Load error:', e);
        document.getElementById('loadingScreen').classList.add('hidden');
        showToast('Lỗi tải dữ liệu: ' + e.message, 'error');
    }
}

function refreshData() {
    showToast('Đang làm mới dữ liệu...', 'info');
    location.reload();
}

/* ===== SIDEBAR ===== */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (window.innerWidth <= 768) {
        sidebar.classList.toggle('open');
    } else {
        sidebar.classList.toggle('collapsed');
    }
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('tab-' + tabId).classList.add('active');
    document.querySelector(`.nav-item[data-tab="${tabId}"]`).classList.add('active');
    const titles = {
        'dashboard': 'Dashboard',
        'trading-stats': 'Thống kê giao dịch',
        'market-report': 'Nhận định thị trường',
        'cashflow': 'Dòng tiền',
        'sectors': 'Phân tích ngành',
        'signals': 'Top tín hiệu',
        'watchlist': 'Watchlist',
    };
    document.getElementById('pageTitle').textContent = titles[tabId] || tabId;
    if (window.innerWidth <= 768) document.getElementById('sidebar').classList.remove('open');
}

/* ===== RENDER ALL ===== */
function renderAll() {
    if (!DATA) return;
    updateSidebarStatus();
    renderAIHero();
    renderVNIndex();
    renderBreadth();
    renderSignals();
    renderTopList();
    renderSectorMini();
    renderNews();
    renderTradingTable();
    renderReportTable();
    renderBreadthDetailed();
    renderSentiment();
    renderAIReport();
    renderSectorFull();
    renderHeatmap();
    renderSignalsTable();
    renderWatchlist();
    updateAIRecommendationBadge();
}

function showToast(message, type) {
    const toast = document.getElementById('errorToast');
    toast.textContent = message;
    toast.style.borderLeft = '3px solid ' + (type === 'error' ? '#ef4444' : type === 'info' ? '#3b82f6' : '#22c55e');
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 4000);
}

function closeModal(id) {
    document.getElementById(id).classList.remove('show');
    document.getElementById(id).style.display = 'none';
}

function formatNumber(n, decimals) {
    if (n == null || isNaN(n)) return '--';
    if (decimals === undefined) decimals = n >= 1000 ? 0 : 2;
    return n.toLocaleString('vi-VN', { minimumFractionDigits: decimals, maximumFractionDigits: 2 });
}

function formatPercent(n) {
    if (n == null || isNaN(n)) return '--';
    return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
}

/* ===== SIDEBAR STATUS ===== */
function updateSidebarStatus() {
    const el = document.getElementById('lastUpdateSidebar');
    if (DATA.exported_at) {
        const d = new Date(DATA.exported_at);
        el.textContent = d.toLocaleString('vi-VN');
    }
}

/* ===== AI HERO ===== */
function renderAIHero() {
    const overview = DATA.market_overview || {};
    const breadth = DATA.market_breadth?.summary || {};
    const rec = overview.recommendation || {};
    const action = rec.action || 'TRUNG LẬP';
    const score = rec.score != null ? rec.score : 5;
    const reason = rec.reason || 'Đang chờ dữ liệu phân tích...';

    const badge = document.getElementById('aiHeroAction').querySelector('.action-badge');
    badge.textContent = action;
    badge.className = 'action-badge ' + action.toLowerCase().replace(/ /g, '-').replace(/đ/g, 'd');

    const scoreVal = document.getElementById('scoreValue');
    scoreVal.textContent = score + '/10';
    const ring = document.getElementById('scoreRing');
    const circumference = 2 * Math.PI * 42;
    const offset = circumference * (1 - score / 10);
    ring.style.strokeDasharray = circumference;
    ring.style.strokeDashoffset = offset;
    const colors = ['#ef4444', '#ef4444', '#f59e0b', '#f59e0b', '#f59e0b', '#3b82f6', '#3b82f6', '#22c55e', '#22c55e', '#22c55e', '#22c55e'];
    ring.style.stroke = colors[Math.round(score)] || '#3b82f6';

    document.getElementById('aiHeroReason').textContent = reason;

    const rsiAv = breadth.rsi_average != null ? breadth.rsi_average : overview.rsi_average;
    const fg = overview.fear_greed != null ? overview.fear_greed : 50;
    const fgLabel = overview.fear_greed_label || '';
    const br = breadth.breadth_ratio != null ? (breadth.breadth_ratio * 100).toFixed(0) + '%' : '--';
    const vol = overview.volume_ratio != null ? overview.volume_ratio.toFixed(1) + 'x' : '--';

    document.getElementById('heroRsi').textContent = rsiAv != null ? rsiAv.toFixed(1) : '--';
    const fgEl = document.getElementById('heroFearGreed');
    fgEl.textContent = fg;
    fgEl.title = fgLabel;
    const fgLabelEl = document.getElementById('heroFearGreedLabel');
    if (fgLabelEl) fgLabelEl.textContent = fgLabel;
    document.getElementById('heroBreadth').textContent = br;
    document.getElementById('heroVolume').textContent = vol;
    document.getElementById('aiHeroDate').textContent = DATA.exported_at ? new Date(DATA.exported_at).toLocaleDateString('vi-VN') : 'Hôm nay';
}

/* ===== VNINDEX MINI CHART ===== */
function renderVNIndex() {
    const idx = DATA.market_index || {};
    if (idx.current != null) {
        document.getElementById('idxPrice').textContent = formatNumber(idx.current);
        const chgEl = document.getElementById('idxChange');
        if (idx.change_pct != null) {
            chgEl.textContent = formatPercent(idx.change_pct);
            chgEl.className = 'index-change ' + (idx.change_pct >= 0 ? 'green' : 'red');
        }
    }
    document.getElementById('idxOpen').textContent = idx.open ? formatNumber(idx.open) : '--';
    document.getElementById('idxHigh').textContent = idx.high ? formatNumber(idx.high) : '--';
    document.getElementById('idxLow').textContent = idx.low ? formatNumber(idx.low) : '--';
    document.getElementById('idxVolume').textContent = idx.volume ? formatNumber(idx.volume / 1e6) + 'M' : '--';

    const prices = idx.prices || [];
    if (prices.length > 1) {
        const ctx = document.getElementById('vnindexMiniChart').getContext('2d');
        if (charts.vnindexMini) charts.vnindexMini.destroy();
        const values = prices.map(p => p.close);
        const isUp = values[values.length - 1] >= values[0];
        charts.vnindexMini = new Chart(ctx, {
            type: 'line',
            data: {
                labels: prices.map(p => ''),
                datasets: [{
                    data: values,
                    borderColor: isUp ? '#22c55e' : '#ef4444',
                    borderWidth: 2,
                    fill: true,
                    backgroundColor: (ctx) => {
                        const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, ctx.chart.height);
                        g.addColorStop(0, isUp ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)');
                        g.addColorStop(1, isUp ? 'rgba(34,197,94,0)' : 'rgba(239,68,68,0)');
                        return g;
                    },
                    pointRadius: 0,
                    tension: 0.4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: { display: false }
                }
            }
        });
    }
}

/* ===== BREADTH DONUT ===== */
function renderBreadth() {
    const bd = DATA.market_breadth?.summary || {};
    document.getElementById('breadthAdv').textContent = bd.advancing ?? '--';
    document.getElementById('breadthDec').textContent = bd.declining ?? '--';
    document.getElementById('breadthUnch').textContent = bd.unchanged ?? '--';
    document.getElementById('brMA20').textContent = bd.above_ma20 != null ? bd.above_ma20 + '/' + bd.total : '--';
    document.getElementById('brMA50').textContent = bd.above_ma50 != null ? bd.above_ma50 + '/' + bd.total : '--';
    document.getElementById('brMA200').textContent = bd.above_ma200 != null ? bd.above_ma200 + '/' + bd.total : '--';
    document.getElementById('brRSI50').textContent = bd.rsi_above_50 != null ? bd.rsi_above_50 + '/' + bd.total : '--';

    const ctx = document.getElementById('breadthDonut').getContext('2d');
    if (charts.breadthDonut) charts.breadthDonut.destroy();
    charts.breadthDonut = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Tăng', 'Giảm', 'Đứng'],
            datasets: [{
                data: [bd.advancing || 0, bd.declining || 0, bd.unchanged || 0],
                backgroundColor: ['#22c55e', '#ef4444', '#f59e0b'],
                borderWidth: 0,
                hoverOffset: 6,
            }]
        },
        options: {
            cutout: '70%',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            }
        }
    });
}

/* ===== SIGNALS LIST ===== */
function renderSignals() {
    const stocks = DATA.stocks || {};
    const signals = [];
    Object.entries(stocks).forEach(([sym, s]) => {
        if (s.error) return;
        const tech = s.technical || {};
        const ind = tech.indicators || {};
        const score = tech.score || 0;
        const change = ind.price_change_pct_1d || 0;
        const price = ind.current_price || 0;
        const volRatio = ind.volume_ratio || 0;
        const macd = ind.macd_histogram_standard;
        const rsi = ind.rsi_14;

        if (score >= 2) signals.push({ symbol: sym, type: 'breakout', label: 'Tích lũy', price, change, score });
        if (macd != null && macd >= 0 && score >= 1) signals.push({ symbol: sym, type: 'macd', label: 'MACD Bullish', price, change, score });
        if (rsi != null && rsi >= 50 && rsi <= 60) signals.push({ symbol: sym, type: 'rsi', label: 'RSI > 50', price, change, score });
        if (volRatio >= 1.5) signals.push({ symbol: sym, type: 'volume', label: 'KL đột biến', price, change, score });
    });
    signals.sort((a, b) => b.score - a.score);
    document.getElementById('signalCount').textContent = signals.length;

    const container = document.getElementById('signalList');
    if (signals.length === 0) {
        container.innerHTML = '<div class="signal-placeholder">Chưa có tín hiệu</div>';
        return;
    }
    container.innerHTML = signals.slice(0, 10).map(s => `
        <div class="signal-item" onclick="showStockDetail('${s.symbol}')">
            <div><span class="signal-symbol">${s.symbol}</span> <span class="signal-type ${s.type}">${s.label}</span></div>
            <div style="text-align:right">
                <div class="signal-price">${formatNumber(s.price)}</div>
                <div class="signal-change ${s.change >= 0 ? 'positive' : 'negative'}">${formatPercent(s.change)}</div>
            </div>
            <div class="signal-score">${s.score}</div>
        </div>
    `).join('');
}

/* ===== TOP LIST ===== */
function switchTopList(type) {
    currentTopList = type;
    document.querySelectorAll('.card-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.card-tab').forEach(t => {
        if (t.textContent.includes({ gainers: 'Tăng', losers: 'Giảm', volume: 'KL' }[type])) t.classList.add('active');
    });
    renderTopList();
}

function renderTopList() {
    const stocks = DATA.stocks || {};
    const list = Object.values(stocks).filter(s => !s.error);
    let sorted;
    if (currentTopList === 'gainers') {
        sorted = list.filter(s => (s.technical?.indicators?.price_change_pct_1d || 0) > 0)
            .sort((a, b) => (b.technical?.indicators?.price_change_pct_1d || 0) - (a.technical?.indicators?.price_change_pct_1d || 0));
    } else if (currentTopList === 'losers') {
        sorted = list.filter(s => (s.technical?.indicators?.price_change_pct_1d || 0) < 0)
            .sort((a, b) => (a.technical?.indicators?.price_change_pct_1d || 0) - (b.technical?.indicators?.price_change_pct_1d || 0));
    } else {
        sorted = list.filter(s => (s.technical?.indicators?.volume_ratio || 0) > 0)
            .sort((a, b) => (b.technical?.indicators?.volume_ratio || 0) - (a.technical?.indicators?.volume_ratio || 0));
    }

    const container = document.getElementById('topList');
    if (sorted.length === 0) {
        container.innerHTML = '<div class="signal-placeholder">Chưa có dữ liệu</div>';
        return;
    }
    container.innerHTML = sorted.slice(0, 10).map((s, i) => {
        const ind = s.technical?.indicators || {};
        const price = ind.current_price || 0;
        const change = currentTopList === 'volume' ? (ind.volume_ratio || 0) : (ind.price_change_pct_1d || 0);
        const displayChange = currentTopList === 'volume' ? (change).toFixed(1) + 'x' : formatPercent(change);
        const rankClass = i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : 'normal';
        const sym = s.symbol || '--';
        return `
            <div class="top-item" onclick="showStockDetail('${sym}')">
                <span class="top-rank ${rankClass}">${i + 1}</span>
                <div class="top-info">
                    <div class="top-name">${sym}</div>
                    <div class="top-price">${formatNumber(price)}</div>
                </div>
                <span class="top-change ${currentTopList !== 'volume' && change >= 0 ? 'positive' : currentTopList !== 'volume' && change < 0 ? 'negative' : ''}">${displayChange}</span>
            </div>
        `;
    }).join('');
}

/* ===== SECTOR MINI ===== */
function renderSectorMini() {
    const sectors = DATA.sectors || [];
    const container = document.getElementById('sectorMiniList');
    if (!sectors.length) {
        container.innerHTML = '<div class="sector-placeholder">Chưa có dữ liệu ngành</div>';
        return;
    }
    const maxChange = Math.max(...sectors.map(s => Math.abs(s.change || 0)), 1);
    container.innerHTML = sectors.slice(0, 8).map(s => {
        const change = s.change || 0;
        const pct = Math.abs(change) / maxChange * 100;
        return `
            <div class="sector-mini-item">
                <span class="sector-mini-name">${s.name}</span>
                <div class="sector-mini-bar">
                    <div class="sector-mini-bar-fill" style="width:${pct}%;background:${change >= 0 ? '#22c55e' : '#ef4444'}"></div>
                </div>
                <span class="sector-mini-change ${change >= 0 ? 'positive' : 'negative'}">${formatPercent(change)}</span>
            </div>
        `;
    }).join('');
}

/* ===== NEWS ===== */
function renderNews() {
    const stocks = DATA.stocks || {};
    const allNews = [];
    Object.values(stocks).forEach(s => {
        (s.news || []).forEach(n => {
            if (!allNews.find(x => x.title === n.title)) allNews.push({ ...n, symbol: s.symbol });
        });
    });
    allNews.sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));
    const container = document.getElementById('newsList');
    if (!allNews.length) {
        container.innerHTML = '<div class="sector-placeholder">Chưa có tin tức</div>';
        return;
    }
    container.innerHTML = allNews.slice(0, 8).map(n => `
        <div class="news-item" onclick="window.open('${n.url || '#'}','_blank')">
            <div class="news-title">${n.title || ''}</div>
            <div class="news-meta">
                <span>${n.source || ''}</span>
                <span>${n.date ? new Date(n.date).toLocaleDateString('vi-VN') : ''}</span>
                <span>${n.symbol || ''}</span>
            </div>
        </div>
    `).join('');
}

/* ===== TRADING TABLE ===== */
function renderTradingTable() {
    const sessions = DATA.trading_sessions || [];
    const tbody = document.getElementById('tradingBody');
    if (!sessions.length) {
        tbody.innerHTML = '<tr><td colspan="12" class="empty-row">Chưa có dữ liệu phiên giao dịch</td></tr>';
        return;
    }
    tbody.innerHTML = sessions.slice(0, 10).map(s => `
        <tr>
            <td>${s.date || '--'}</td>
            <td class="${(s.change || 0) >= 0 ? 'positive' : 'negative'}">${formatNumber(s.index)}</td>
            <td class="${(s.change || 0) >= 0 ? 'positive' : 'negative'}">${formatNumber(s.change)}</td>
            <td class="${(s.change_pct || 0) >= 0 ? 'positive' : 'negative'}">${formatPercent(s.change_pct)}</td>
            <td>${s.volume ? formatNumber(s.volume / 1e6) + 'M' : '--'}</td>
            <td>${s.value ? formatNumber(s.value / 1e9) + ' tỷ' : '--'}</td>
            <td class="positive">${s.advancing ?? '--'}</td>
            <td class="negative">${s.declining ?? '--'}</td>
            <td>${s.unchanged ?? '--'}</td>
            <td class="${(s.foreign_net || 0) >= 0 ? 'positive' : 'negative'}">${s.foreign_net != null ? formatNumber(s.foreign_net / 1e9) + ' tỷ' : '--'}</td>
            <td class="${(s.proprietary_net || 0) >= 0 ? 'positive' : 'negative'}">${s.proprietary_net != null ? formatNumber(s.proprietary_net / 1e9) + ' tỷ' : '--'}</td>
            <td>${s.negotiated_value ? formatNumber(s.negotiated_value / 1e9) + ' tỷ' : '--'}</td>
        </tr>
    `).join('');
}

/* ===== REPORT TABLE ===== */
function renderReportTable() {
    const idx = DATA.market_index || {};
    const ov = DATA.market_overview || {};
    const container = document.getElementById('reportTable');
    const rows = [
        { label: 'Ngày giao dịch', value: idx.last_date || DATA.exported_at ? new Date(DATA.exported_at).toLocaleDateString('vi-VN') : '--' },
        { label: 'VN-Index', value: formatNumber(idx.current) },
        { label: 'Thay đổi', value: formatPercent(idx.change_pct), color: (idx.change_pct || 0) >= 0 ? '#22c55e' : '#ef4444' },
        { label: 'Mở cửa', value: formatNumber(idx.open) },
        { label: 'Cao nhất', value: formatNumber(idx.high) },
        { label: 'Thấp nhất', value: formatNumber(idx.low) },
        { label: 'KLGD', value: idx.volume ? formatNumber(idx.volume / 1e6) + 'M' : '--' },
        { label: 'GTGD', value: ov.total_value ? formatNumber(ov.total_value / 1e9) + ' tỷ' : '--' },
        { label: 'Mã tăng', value: DATA.market_breadth?.summary?.advancing ?? '--', color: '#22c55e' },
        { label: 'Mã giảm', value: DATA.market_breadth?.summary?.declining ?? '--', color: '#ef4444' },
        { label: 'Mã đứng', value: DATA.market_breadth?.summary?.unchanged ?? '--' },
        { label: 'NN ròng', value: ov.foreign_net != null ? formatNumber(ov.foreign_net / 1e9) + ' tỷ' : '--', color: (ov.foreign_net || 0) >= 0 ? '#22c55e' : '#ef4444' },
        { label: 'TD ròng', value: ov.proprietary_net != null ? formatNumber(ov.proprietary_net / 1e9) + ' tỷ' : '--', color: (ov.proprietary_net || 0) >= 0 ? '#22c55e' : '#ef4444' },
    ];
    container.innerHTML = rows.map(r => `
        <div class="report-row">
            <span class="label">${r.label}</span>
            <span class="value" ${r.color ? `style="color:${r.color}"` : ''}>${r.value}</span>
        </div>
    `).join('');
    document.getElementById('reportDate').textContent = idx.last_date || new Date(DATA.exported_at).toLocaleDateString('vi-VN');
}

/* ===== BREADTH DETAILED ===== */
function renderBreadthDetailed() {
    const bd = DATA.market_breadth?.summary || {};
    const container = document.getElementById('breadthDetailed');
    const metrics = [
        { label: 'Trên MA20', value: bd.above_ma20, total: bd.total, good: true },
        { label: 'Trên MA50', value: bd.above_ma50, total: bd.total, good: true },
        { label: 'Trên MA200', value: bd.above_ma200, total: bd.total, good: true },
        { label: 'Thanh khoản > MA20', value: bd.above_volume_ma20, total: bd.total, good: true },
        { label: 'RSI quá bán (<30)', value: bd.rsi_oversold, total: bd.total, good: false },
        { label: 'RSI quá mua (>70)', value: bd.rsi_overbought, total: bd.total, good: false },
        { label: 'Đỉnh 52 tuần', value: bd.high_52w, total: bd.total, good: true },
        { label: 'Đáy 52 tuần', value: bd.low_52w, total: bd.total, good: false },
    ];
    container.innerHTML = metrics.map(m => {
        const pct = m.total > 0 ? (m.value / m.total * 100) : 0;
        return `
            <div class="breadth-metric">
                <div class="metric-header">
                    <span class="metric-label">${m.label}</span>
                    <span class="metric-value">${m.value ?? '--'}/${m.total ?? '--'}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width:${pct}%;background:${m.good ? '#22c55e' : '#ef4444'}"></div>
                </div>
            </div>
        `;
    }).join('');
}

/* ===== SENTIMENT ===== */
function renderSentiment() {
    const ov = DATA.market_overview || {};
    const fg = ov.fear_greed != null ? ov.fear_greed : 50;
    const fgLabel = ov.fear_greed_label || '';
    const comps = ov.sentiment_components || {};
    const container = document.getElementById('sentimentSection');
    const angle = (fg / 100) * 180 - 90;
    const labels = ['Cực kỳ sợ hãi', 'Sợ hãi', 'Trung lập', 'Tham lam', 'Cực kỳ tham lam'];
    const labelIdx = fg < 20 ? 0 : fg < 40 ? 1 : fg < 60 ? 2 : fg < 80 ? 3 : 4;

    const compNames = {rsi: 'RSI', volatility: 'Biến động', momentum: 'Động lượng', breadth: 'Bề rộng'};
    const compHtml = Object.keys(compNames).filter(k => comps[k] != null).map(k => {
        const v = comps[k];
        const pct = Math.round(v);
        const c = pct >= 60 ? '#22c55e' : pct <= 40 ? '#ef4444' : '#f59e0b';
        return `<div class="sentiment-comp">
            <div class="comp-label">${compNames[k]}</div>
            <div class="comp-bar"><div class="comp-fill" style="width:${pct}%;background:${c}"></div></div>
            <div class="comp-value" style="color:${c}">${v}</div>
        </div>`;
    }).join('');

    container.innerHTML = `
        <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">
            <div style="text-align:center">
                <div class="sentiment-gauge">
                    <div class="gauge-needle" style="transform:rotate(${angle}deg)"></div>
                    <div class="gauge-mask"></div>
                </div>
                <div class="sentiment-value" style="color:${fg >= 60 ? '#22c55e' : fg <= 40 ? '#ef4444' : '#f59e0b'}">${fg}</div>
                <div class="sentiment-label" style="font-size:13px">${fgLabel}</div>
            </div>
            <div style="flex:1;min-width:200px">
                <div class="sentiment-sub" style="margin-bottom:8px">Chi tiết thành phần</div>
                ${compHtml}
            </div>
        </div>
    `;
}

/* ===== AI REPORT ===== */
function renderAIReport() {
    const ov = DATA.market_overview || {};
    const aiText = ov.ai_report || '';
    const container = document.getElementById('aiReport');
    if (!aiText) {
        container.innerHTML = '<div class="report-placeholder">Chưa có báo cáo AI. Vui lòng chạy phân tích.</div>';
        return;
    }
    const formatted = aiText
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
    container.innerHTML = `<div class="report-section"><p>${formatted}</p></div>`;
}

/* ===== SECTOR FULL ===== */
function renderSectorFull() {
    const sectors = DATA.sectors || [];
    const tbody = document.getElementById('sectorBody');
    if (!sectors.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-row">Chưa có dữ liệu ngành</td></tr>';
        return;
    }
    tbody.innerHTML = sectors.sort((a, b) => Math.abs(b.cashflow || 0) - Math.abs(a.cashflow || 0)).map(s => `
        <tr>
            <td><strong>${s.name}</strong></td>
            <td class="${(s.cashflow || 0) >= 0 ? 'positive' : 'negative'}">${s.cashflow != null ? formatNumber(s.cashflow / 1e9) + ' tỷ' : '--'}</td>
            <td class="${(s.change || 0) >= 0 ? 'positive' : 'negative'}">${formatPercent(s.change)}</td>
            <td>${s.volume_ratio != null ? s.volume_ratio.toFixed(1) + 'x' : '--'}</td>
            <td>${s.strength != null ? s.strength.toFixed(1) : '--'}</td>
            <td class="${(s.momentum || 0) >= 0 ? 'positive' : 'negative'}">${s.momentum != null ? s.momentum.toFixed(2) : '--'}</td>
            <td><span class="signal-type ${(s.trend || 'neutral').toLowerCase()}">${s.trend || '--'}</span></td>
        </tr>
    `).join('');

    // Sector rotation chart
    const ctx = document.getElementById('sectorRotationChart').getContext('2d');
    if (charts.sectorRotation) charts.sectorRotation.destroy();
    charts.sectorRotation = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: sectors.map(s => s.name),
            datasets: [{
                label: 'Sức mạnh',
                data: sectors.map(s => s.strength || 0),
                backgroundColor: 'rgba(59,130,246,0.15)',
                borderColor: '#3b82f6',
                borderWidth: 2,
                pointRadius: 3,
                pointBackgroundColor: '#3b82f6',
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#8899bb' } }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    ticks: { color: '#556688', backdropColor: 'transparent' },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    angleLines: { color: 'rgba(255,255,255,0.05)' },
                    pointLabels: { color: '#8899bb', font: { size: 10 } }
                }
            }
        }
    });

    // Sector bubble chart
    const ctx2 = document.getElementById('sectorBubbleChart').getContext('2d');
    if (charts.sectorBubble) charts.sectorBubble.destroy();
    charts.sectorBubble = new Chart(ctx2, {
        type: 'bubble',
        data: {
            datasets: sectors.map(s => ({
                label: s.name,
                data: [{ x: s.strength || 0, y: s.cashflow || 0, r: Math.abs(s.momentum || 10) * 3 + 5 }],
                backgroundColor: (s.change || 0) >= 0 ? 'rgba(34,197,94,0.6)' : 'rgba(239,68,68,0.6)',
                borderColor: (s.change || 0) >= 0 ? '#22c55e' : '#ef4444',
                borderWidth: 1,
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${formatPercent(ctx.raw.x)} / ${formatNumber(ctx.raw.y / 1e9)} tỷ`
                    }
                }
            },
            scales: {
                x: { title: { display: true, text: 'Sức mạnh', color: '#8899bb' }, ticks: { color: '#556688' }, grid: { color: 'rgba(255,255,255,0.03)' } },
                y: { title: { display: true, text: 'Dòng tiền', color: '#8899bb' }, ticks: { color: '#556688' }, grid: { color: 'rgba(255,255,255,0.03)' } }
            }
        }
    });
}

/* ===== HEATMAP ===== */
function renderHeatmap() {
    const sectors = DATA.sectors || [];
    const container = document.getElementById('heatmapContainer');
    if (!sectors.length) {
        container.innerHTML = '<div class="signal-placeholder">Chưa có dữ liệu</div>';
        return;
    }
    const maxChange = Math.max(...sectors.map(s => Math.abs(s.change || 0)), 1);
    container.innerHTML = sectors.map(s => {
        const change = s.change || 0;
        const intensity = Math.abs(change) / maxChange;
        const r = change >= 0 ? Math.round(34 * (1 - intensity) + 220 * intensity) : 239;
        const g = change >= 0 ? 197 : Math.round(68 * (1 - intensity) + 68 * intensity);
        const b = change >= 0 ? 94 : Math.round(68 * (1 - intensity) + 68 * intensity);
        return `
            <div class="heatmap-cell" style="background:rgba(${r},${g},${b},0.2);border:1px solid rgba(${r},${g},${b},0.3)">
                <div class="cell-name">${s.name}</div>
                <div class="cell-change" style="color:rgb(${r},${g},${b})">${formatPercent(change)}</div>
            </div>
        `;
    }).join('');
}

/* ===== SIGNALS TABLE ===== */
function filterSignals(filter) {
    currentSignalFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.filter-btn[data-filter="${filter}"]`).classList.add('active');
    renderSignalsTable();
}

function renderSignalsTable() {
    const stocks = DATA.stocks || {};
    const rows = [];
    Object.entries(stocks).forEach(([sym, s]) => {
        if (s.error) return;
        const tech = s.technical || {};
        const ind = tech.indicators || {};
        const signals = [];
        const score = tech.score || 0;
        const change = ind.price_change_pct_1d || 0;
        const price = ind.current_price || 0;
        const rsi = ind.rsi_14;
        const macd = ind.macd_histogram_standard;
        const vol = ind.volume_ratio || 0;
        const macdBullish = macd != null && macd >= 0;
        const rsiBullish = rsi != null && rsi > 50;
        const volumeSpike = vol >= 1.5;
        const isBreakout = score >= 2;

        if (isBreakout) signals.push('Breakout');
        if (macdBullish) signals.push('MACD Bullish');
        if (rsiBullish) signals.push('RSI > 50');
        if (volumeSpike) signals.push('KL đột biến');

        const matchFilter = currentSignalFilter === 'all' ||
            (currentSignalFilter === 'breakout' && isBreakout) ||
            (currentSignalFilter === 'macd_bullish' && macdBullish) ||
            (currentSignalFilter === 'rsi_bullish' && rsiBullish) ||
            (currentSignalFilter === 'volume_spike' && volumeSpike);

        if (matchFilter && signals.length > 0) {
            rows.push({ symbol: sym, signals, price, change, rsi, macd, volume: vol, score });
        }
    });
    rows.sort((a, b) => b.score - a.score);

    const tbody = document.getElementById('signalsBody');
    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-row">Không có tín hiệu phù hợp</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map(r => `
        <tr onclick="showStockDetail('${r.symbol}')" style="cursor:pointer">
            <td><strong>${r.symbol}</strong></td>
            <td>${r.signals.map(s => `<span class="signal-type ${s.includes('Breakout') ? 'breakout' : s.includes('MACD') ? 'macd' : s.includes('RSI') ? 'rsi' : 'volume'}">${s}</span>`).join(' ')}</td>
            <td>${formatNumber(r.price)}</td>
            <td class="${r.change >= 0 ? 'positive' : 'negative'}">${formatPercent(r.change)}</td>
            <td>${r.rsi != null ? r.rsi.toFixed(1) : '--'}</td>
            <td class="${(r.macd || 0) >= 0 ? 'positive' : 'negative'}">${r.macd != null ? r.macd.toFixed(2) : '--'}</td>
            <td>${r.volume > 0 ? r.volume.toFixed(1) + 'x' : '--'}</td>
            <td><span class="signal-score">${r.score}</span></td>
        </tr>
    `).join('');
}

/* ===== WATCHLIST ===== */
function getWatchlist() {
    try {
        return JSON.parse(localStorage.getItem('ai_stock_watchlist') || '[]');
    } catch { return []; }
}

function saveWatchlist(wl) {
    localStorage.setItem('ai_stock_watchlist', JSON.stringify(wl));
}

function showAddToWatchlist() {
    document.getElementById('watchlistModal').style.display = 'flex';
    document.getElementById('watchlistModal').classList.add('show');
    document.getElementById('watchlistSymbolInput').value = '';
    document.getElementById('watchlistBuyPrice').value = '';
    document.getElementById('symbolSuggestions').innerHTML = '';
}

function suggestSymbols(query) {
    const container = document.getElementById('symbolSuggestions');
    if (!query || query.length < 1) { container.innerHTML = ''; return; }
    const stocks = DATA.stocks || {};
    const matches = Object.keys(stocks).filter(s => s.includes(query.toUpperCase()) && !s.includes('ERROR')).slice(0, 10);
    if (!matches.length) { container.innerHTML = ''; return; }
    container.innerHTML = matches.map(s => `<div class="suggestion-item" onclick="selectSymbolSuggestion('${s}')">${s}</div>`).join('');
}

function selectSymbolSuggestion(sym) {
    document.getElementById('watchlistSymbolInput').value = sym;
    document.getElementById('symbolSuggestions').innerHTML = '';
}

function addToWatchlist() {
    const sym = document.getElementById('watchlistSymbolInput').value.toUpperCase().trim();
    const price = parseFloat(document.getElementById('watchlistBuyPrice').value) || 0;
    if (!sym) { showToast('Vui lòng nhập mã cổ phiếu', 'error'); return; }
    const wl = getWatchlist();
    if (wl.find(w => w.symbol === sym)) { showToast('Mã ' + sym + ' đã có trong Watchlist', 'error'); return; }
    wl.push({ symbol: sym, buyPrice: price, addedAt: new Date().toISOString() });
    saveWatchlist(wl);
    closeModal('watchlistModal');
    renderWatchlist();
    showToast('Đã thêm ' + sym + ' vào Watchlist', 'info');
}

function removeFromWatchlist(sym) {
    let wl = getWatchlist();
    wl = wl.filter(w => w.symbol !== sym);
    saveWatchlist(wl);
    renderWatchlist();
    showToast('Đã xóa ' + sym, 'info');
}

function renderWatchlist() {
    const wl = getWatchlist();
    const tbody = document.getElementById('watchlistBody');
    if (!wl.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-row">Chưa có cổ phiếu trong danh sách theo dõi. Nhấn "Thêm mã" để bắt đầu.</td></tr>';
        return;
    }
    tbody.innerHTML = wl.map(w => {
        const s = DATA.stocks?.[w.symbol];
        const tech = s?.technical || {};
        const ind = tech.indicators || {};
        const price = ind.current_price || 0;
        const change = ind.price_change_pct_1d || 0;
        const rsi = ind.rsi_14 || '--';
        const action = tech.action || '--';
        const buyPrice = w.buyPrice || 0;
        const pl = buyPrice > 0 ? ((price - buyPrice) / buyPrice * 100) : null;
        return `
            <tr>
                <td><strong>${w.symbol}</strong></td>
                <td>${formatNumber(price)}</td>
                <td class="${change >= 0 ? 'positive' : 'negative'}">${formatPercent(change)}</td>
                <td>${buyPrice > 0 ? formatNumber(buyPrice) : '--'}</td>
                <td class="${pl != null ? (pl >= 0 ? 'positive' : 'negative') : ''}">${pl != null ? formatPercent(pl) : '--'}</td>
                <td>${rsi}</td>
                <td>${action}</td>
                <td><button class="btn-secondary" onclick="removeFromWatchlist('${w.symbol}')" style="padding:4px 8px;font-size:0.75rem">Xóa</button></td>
            </tr>
        `;
    }).join('');
}

/* ===== SEARCH ===== */
function searchSymbol(query) {
    if (!query || query.length < 1) return;
    const stocks = DATA.stocks || {};
    const match = Object.keys(stocks).find(s => s === query.toUpperCase());
    if (match) showStockDetail(match);
}

/* ===== STOCK DETAIL MODAL ===== */
function showStockDetail(symbol) {
    if (!DATA?.stocks?.[symbol]) return;
    const s = DATA.stocks[symbol];
    if (s.error) {
        showToast('Lỗi dữ liệu ' + symbol + ': ' + s.error, 'error');
        return;
    }

    document.getElementById('modalStockTitle').textContent = symbol + ' - Chi tiết cổ phiếu';
    const modal = document.getElementById('stockModal');
    modal.style.display = 'flex';
    modal.classList.add('show');

    const tech = s.technical || {};
    const ind = tech.indicators || {};
    const signals = tech.signals || [];

    const price = ind.current_price || 0;
    const change = ind.price_change_pct_1d || 0;
    const changeCls = change >= 0 ? 'positive' : 'negative';

    const indicators = [
        { label: 'RSI(14)', value: ind.rsi_14, signal: ind.rsi_signal },
        { label: 'RSI(7)', value: ind.rsi_7 },
        { label: 'RSI(21)', value: ind.rsi_21 },
        { label: 'Stoch %K', value: ind.stoch_k, signal: ind.stoch_signal },
        { label: 'Williams %R', value: ind.williams_r, signal: ind.williams_r_signal },
        { label: 'MACD', value: ind.macd_standard },
        { label: 'MACD Signal', value: ind.macd_signal_standard },
        { label: 'MACD Hist', value: ind.macd_histogram_standard },
        { label: 'Bollinger %B', value: ind.bb_pct_b },
        { label: 'MA20', value: ind.ma_20 },
        { label: 'MA50', value: ind.ma_50 },
        { label: 'MA100', value: ind.ma_100 },
        { label: 'MA200', value: ind.ma_200 },
        { label: 'ADX', value: ind.adx, signal: ind.trend_strength },
        { label: 'CCI', value: ind.cci, signal: ind.cci_signal },
        { label: 'Volume Ratio', value: ind.volume_ratio },
        { label: 'ATR', value: ind.atr },
        { label: 'VaR 95%', value: ind.var_95 },
        { label: 'Sharpe', value: ind.sharpe_ratio },
        { label: 'Max Drawdown', value: ind.max_drawdown },
        { label: 'Hỗ trợ S1', value: ind.support_1 },
        { label: 'Kháng cự R1', value: ind.resistance_1 },
        { label: 'Pivot Point', value: ind.pivot_pp },
        { label: 'OBV', value: ind.obv },
        { label: 'VWAP', value: ind.vwap },
        { label: 'NN ròng (tỷ)', value: ind.foreign_net_today },
        { label: 'Giá/MA20', value: ind.price_vs_ma20_pct != null ? formatPercent(ind.price_vs_ma20_pct) : null },
        { label: 'Giá/MA50', value: ind.price_vs_ma50_pct != null ? formatPercent(ind.price_vs_ma50_pct) : null },
    ];

    const detail = document.getElementById('stockDetail');
    const indicatorHtml = indicators.filter(i => i.value != null && i.value !== '--').map(i => `
        <tr>
            <td>${i.label}</td>
            <td>${typeof i.value === 'number' ? formatNumber(i.value) : i.value}</td>
            <td style="color:${i.signal === 'oversold' || i.signal?.includes('mạnh') ? '#22c55e' : i.signal === 'overbought' ? '#ef4444' : '#8899aa'}">${i.signal || ''}</td>
        </tr>
    `).join('');

    detail.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;flex-wrap:wrap;gap:12px">
            <div>
                <h2 style="color:#3b82f6;margin:0;font-size:1.4rem">${symbol}</h2>
                <small style="color:#8899aa">${s.company_name || ''} | ${s.exchange || ''} | ${s.industry || ''}</small>
            </div>
            <div style="text-align:right">
                <div style="font-size:2rem;font-weight:700">${formatNumber(price)}</div>
                <div style="font-size:1rem;font-weight:600" class="${changeCls}">${formatPercent(change)}</div>
            </div>
        </div>

        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px">
            <span class="action-badge ${(tech.action || '').toLowerCase().replace(/ /g, '-').replace(/đ/g, 'd')}" style="font-size:0.85rem;padding:6px 16px">
                ${tech.action || 'N/A'}
            </span>
            <span style="background:rgba(59,130,246,0.1);padding:6px 16px;border-radius:20px;font-size:0.85rem;border:1px solid rgba(59,130,246,0.2)">
                Điểm: ${tech.score ?? 0}/10 | ${tech.confidence || ''}
            </span>
        </div>

        <h3 style="color:#8899aa;margin:16px 0 8px;font-size:1rem"><i class="fas fa-chart-line"></i> Chỉ báo kỹ thuật</h3>
        <div class="table-responsive">
            <table class="data-table" style="font-size:0.82rem">
                <tr style="color:#667788;border-bottom:1px solid var(--border-color)">
                    <th style="text-align:left;padding:8px">Chỉ báo</th>
                    <th style="text-align:right;padding:8px">Giá trị</th>
                    <th style="text-align:right;padding:8px">Tín hiệu</th>
                </tr>
                ${indicatorHtml}
            </table>
        </div>

        <h3 style="color:#8899aa;margin:16px 0 8px;font-size:1rem"><i class="fas fa-list"></i> Tín hiệu</h3>
        <ul style="list-style:none;padding:0">
            ${signals.map(s => `<li style="padding:6px 0;color:#e0e6ed;border-bottom:1px solid rgba(255,255,255,0.05)">• ${s}</li>`).join('') || '<li style="color:#667788">Không có tín hiệu</li>'}
        </ul>

        <h3 style="color:#8899aa;margin:16px 0 8px;font-size:1rem"><i class="fas fa-newspaper"></i> Tin tức</h3>
        <ul style="list-style:none;padding:0">
            ${(s.news || []).slice(0, 5).map(n =>
                '<li style="padding:6px 0;font-size:0.85rem;border-bottom:1px solid rgba(255,255,255,0.05)"><a href="' + (n.url || '#') + '" target="_blank" style="color:#8899aa;text-decoration:none">📰 ' + (n.title || '') + '</a></li>'
            ).join('') || '<li style="color:#667788">Không có tin tức</li>'}
        </ul>

        <div style="margin-top:16px;padding:12px 16px;background:rgba(0,0,0,0.15);border-radius:8px;font-size:0.8rem;color:#667788;border-left:3px solid #f59e0b">
            ⚠️ Phân tích tham khảo, không phải lời khuyên đầu tư
        </div>
    `;
}

/* ===== AI BADGE ===== */
function updateAIRecommendationBadge() {
    const ov = DATA.market_overview || {};
    const rec = ov.recommendation || {};
    const action = rec.action || 'TRUNG LẬP';
    const el = document.getElementById('aiBadgeText');
    el.textContent = action;
    const badge = document.getElementById('aiBadge');
    badge.className = 'ai-recommendation-badge';
    badge.style.border = '1px solid ' + (action.includes('MUA') || action.includes('TÍCH') ? 'rgba(34,197,94,0.3)' : action.includes('BÁN') || action.includes('GIẢM') ? 'rgba(239,68,68,0.3)' : 'rgba(245,158,11,0.3)');
}

/* ===== CLOSE MODAL ON OUTSIDE CLICK ===== */
window.onclick = function(e) {
    document.querySelectorAll('.modal').forEach(m => {
        if (e.target === m) { m.style.display = 'none'; m.classList.remove('show'); }
    });
};
