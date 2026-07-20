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
        // Merge AFL data if loaded separately
        if (window.AFL_SIGNALS && DATA && DATA.rankings) {
            DATA.rankings.afl_signals = window.AFL_SIGNALS;
        }
        if (window.AFL_BACKTEST && DATA && DATA.rankings) {
            DATA.rankings.afl_backtest = window.AFL_BACKTEST;
        }
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
        'signals': 'Tín hiệu kỹ thuật (100đ)',
        'afl': 'AFL Signals',
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
    renderBacktestTable();
    renderAFLSignals();
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

/* ===== SIGNALS LIST (Dashboard card) ===== */
function renderSignals() {
    const stocks = DATA.stocks || {};
    const signals = [];
    const rankings = DATA.rankings || {};
    const topStrong = rankings.top_20_manh_nhat || [];

    // Use 100-point scoring data
    Object.entries(stocks).forEach(([sym, s]) => {
        if (s.error) return;
        const tech = s.technical || {};
        const scoring = tech.signal_scoring || {};
        const ind = tech.indicators || {};
        const change = ind.price_change_pct_1d || 0;
        const price = ind.current_price || 0;
        const score = scoring.tong_diem || 0;
        const grade = scoring.xep_loai || 'LOAI';
        const sm = tech.smart_money || {};

        if (score >= 70) signals.push({ symbol: sym, type: 'breakout', label: `${grade} (${score}đ)`, price, change, score });
        if (score >= 60 && score < 70) signals.push({ symbol: sym, type: 'macd', label: `${grade} (${score}đ)`, price, change, score });
        if (sm.supertrend_signal === 'uptrend') signals.push({ symbol: sym, type: 'rsi', label: 'SuperTrend UP', price, change, score });
        if (ind.volume_ratio >= 1.5) signals.push({ symbol: sym, type: 'volume', label: 'KL đột biến', price, change, score });
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

/* ===== SIGNALS TABLE - ENHANCED 100-POINT SYSTEM ===== */
function filterSignals(filter) {
    currentSignalFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.filter-btn[data-filter="${filter}"]`).classList.add('active');
    renderSignalsTable();
}

function renderSignalsTable() {
    if (!DATA || !DATA.rankings) return;
    const r = DATA.rankings;
    const stats = r.thong_ke || {};

    // Update stats
    document.getElementById('techTotalStocks').textContent = stats.tong_mau_phan_tich || '--';
    document.getElementById('techAvgScore').textContent = stats.diem_trung_binh != null ? stats.diem_trung_binh.toFixed(1) : '--';
    document.getElementById('techStrongCount').textContent = stats.so_manh || '--';
    document.getElementById('techBuySignals').textContent = stats.so_co_tin_hieu_mua || '--';
    document.getElementById('techWarningCount').textContent = stats.so_canh_bao || '--';

    // Render the right view based on filter
    const container = document.getElementById('signalRankingsContainer');
    const filter = currentSignalFilter;

    if (filter === 'strong' || filter === 'all') {
        container.innerHTML = renderTopStrongHtml(r.top_20_manh_nhat || []);
    }
    if (filter === 'moneyflow') {
        container.innerHTML = renderTopMoneyFlowHtml(r.top_20_dong_tien || []);
    }
    if (filter === 'buy') {
        container.innerHTML = renderBuySignalsHtml(r.top_10_tin_hieu_mua || []);
    }
    if (filter === 'weak') {
        container.innerHTML = renderWeakHtml(r.top_10_suy_yeu || []);
    }
}

function renderTopStrongHtml(list) {
    if (!list.length) return '<div class="signal-placeholder" style="padding:40px;text-align:center;color:#667788">Chưa có dữ liệu</div>';
    return `
        <div class="card full-width">
            <div class="card-header">
                <h3><i class="fas fa-trophy" style="color:#f59e0b"></i> Top 20 cổ phiếu mạnh nhất (theo tổng điểm 100)</h3>
                <span class="card-badge">${list.length}</span>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="data-table" style="font-size:0.78rem">
                        <thead>
                            <tr><th>#</th><th>Mã</th><th>Điểm</th><th>XL</th><th>Giá</th><th>%</th><th>RSI</th><th>RVOL</th><th>BOS</th><th>FVG</th><th>SuperTrend</th></tr>
                        </thead>
                        <tbody>
                            ${list.map((s, i) => {
                                const gradeClass = s.grade === 'A+' || s.grade === 'A' ? 'positive' : s.grade === 'B+' ? '' : 'negative';
                                return `<tr onclick="showStockDetail('${s.symbol}')" style="cursor:pointer">
                                    <td>${i + 1}</td>
                                    <td><strong>${s.symbol}</strong></td>
                                    <td style="font-weight:700;color:${s.score >= 80 ? '#22c55e' : s.score >= 70 ? '#f59e0b' : s.score >= 60 ? '#3b82f6' : '#ef4444'}">${s.score}</td>
                                    <td class="${gradeClass}">${s.grade || '--'}</td>
                                    <td>${formatNumber(s.price)}</td>
                                    <td class="${(s.change_pct || 0) >= 0 ? 'positive' : 'negative'}">${formatPercent(s.change_pct)}</td>
                                    <td>${s.rsi != null ? s.rsi.toFixed(1) : '--'}</td>
                                    <td>${s.vol_ratio != null ? s.vol_ratio.toFixed(1) + 'x' : '--'}</td>
                                    <td style="font-size:0.7rem">${s.bos || '--'}</td>
                                    <td style="font-size:0.7rem">${s.fvg && s.fvg !== 'none' ? s.fvg : '--'}</td>
                                    <td style="color:${s.supertrend === 'uptrend' ? '#22c55e' : s.supertrend === 'downtrend' ? '#ef4444' : '#8899aa'}">${s.supertrend || '--'}</td>
                                </tr>`;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <div class="card full-width" style="margin-top:16px">
            <div class="card-header">
                <h3><i class="fas fa-money-bill-wave" style="color:#22c55e"></i> Top 20 dòng tiền vào mạnh nhất</h3>
                <span class="card-badge">${(DATA.rankings.top_20_dong_tien || []).length}</span>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="data-table" style="font-size:0.78rem">
                        <thead>
                            <tr><th>#</th><th>Mã</th><th>Điểm MF</th><th>RVOL</th><th>MFI</th><th>Giá</th><th>%</th><th>OBV</th><th>Tổng điểm</th></tr>
                        </thead>
                        <tbody>
                            ${renderMoneyFlowRows(DATA.rankings.top_20_dong_tien || [])}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
}

function renderMoneyFlowRows(list) {
    if (!list.length) return '<tr><td colspan="9" class="empty-row">Chưa có dữ liệu</td></tr>';
    return list.map((s, i) => `
        <tr onclick="showStockDetail('${s.symbol}')" style="cursor:pointer">
            <td>${i + 1}</td>
            <td><strong>${s.symbol}</strong></td>
            <td style="font-weight:700;color:#22c55e">${s.money_flow_score || 0}</td>
            <td>${s.vol_ratio != null ? s.vol_ratio.toFixed(1) + 'x' : '--'}</td>
            <td>${s.mfi != null ? s.mfi.toFixed(1) : '--'}</td>
            <td>${formatNumber(s.price)}</td>
            <td class="${(s.change_pct || 0) >= 0 ? 'positive' : 'negative'}">${formatPercent(s.change_pct)}</td>
            <td>${s.obv_trend || '--'}</td>
            <td style="font-weight:700;color:${s.score >= 80 ? '#22c55e' : s.score >= 70 ? '#f59e0b' : '#8899aa'}">${s.score}</td>
        </tr>
    `).join('');
}

function renderTopMoneyFlowHtml(list) {
    return `
        <div class="card full-width">
            <div class="card-header">
                <h3><i class="fas fa-money-bill-wave" style="color:#22c55e"></i> Top 20 dòng tiền vào mạnh nhất</h3>
                <span class="card-badge">${list.length}</span>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="data-table" style="font-size:0.78rem">
                        <thead>
                            <tr><th>#</th><th>Mã</th><th>Điểm MF</th><th>RVOL</th><th>MFI</th><th>Giá</th><th>%</th><th>OBV</th><th>Tổng điểm</th></tr>
                        </thead>
                        <tbody>${renderMoneyFlowRows(list)}</tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
}

function renderBuySignalsHtml(list) {
    if (!list.length) return '<div class="signal-placeholder" style="padding:40px;text-align:center;color:#667788">Chưa có tín hiệu mua</div>';
    return `
        <div class="card full-width">
            <div class="card-header">
                <h3><i class="fas fa-bell" style="color:#3b82f6"></i> Top 10 tín hiệu mua mới</h3>
                <span class="card-badge">${list.length}</span>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="data-table" style="font-size:0.78rem">
                        <thead>
                            <tr><th>#</th><th>Mã</th><th>Điểm</th><th>XL</th><th>Giá</th><th>%</th><th>RVOL</th><th>Lý do</th></tr>
                        </thead>
                        <tbody>
                            ${list.map((s, i) => {
                                const reasons = s.reasons ? s.reasons.slice(0, 2).join(', ') : '';
                                return `<tr onclick="showStockDetail('${s.symbol}')" style="cursor:pointer">
                                    <td>${i + 1}</td>
                                    <td><strong>${s.symbol}</strong></td>
                                    <td style="font-weight:700;color:${s.score >= 80 ? '#22c55e' : s.score >= 70 ? '#f59e0b' : '#3b82f6'}">${s.score}</td>
                                    <td style="color:${s.grade === 'A+' || s.grade === 'A' ? '#22c55e' : '#f59e0b'}">${s.grade || '--'}</td>
                                    <td>${formatNumber(s.price)}</td>
                                    <td class="${(s.change_pct || 0) >= 0 ? 'positive' : 'negative'}">${formatPercent(s.change_pct)}</td>
                                    <td>${s.vol_ratio != null ? s.vol_ratio.toFixed(1) + 'x' : '--'}</td>
                                    <td style="font-size:0.72rem;color:#3b82f6;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${reasons || '--'}</td>
                                </tr>`;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
}

function renderWeakHtml(list) {
    if (!list.length) return '<div class="signal-placeholder" style="padding:40px;text-align:center;color:#667788">Chưa có cổ phiếu suy yếu</div>';
    return `
        <div class="card full-width">
            <div class="card-header">
                <h3><i class="fas fa-exclamation-triangle" style="color:#ef4444"></i> Cảnh báo cổ phiếu suy yếu</h3>
                <span class="card-badge">${list.length}</span>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="data-table" style="font-size:0.78rem">
                        <thead>
                            <tr><th>#</th><th>Mã</th><th>Điểm</th><th>Giá</th><th>%</th><th>RSI</th><th>Lý do</th><th>Penalty</th></tr>
                        </thead>
                        <tbody>
                            ${list.map((s, i) => {
                                const reasons = s.reasons ? s.reasons.slice(0, 2).join(', ') : '';
                                const penalty = s.penalty || 0;
                                return `<tr onclick="showStockDetail('${s.symbol}')" style="cursor:pointer">
                                    <td>${i + 1}</td>
                                    <td><strong>${s.symbol}</strong></td>
                                    <td style="font-weight:700;color:#ef4444">${s.score}</td>
                                    <td>${formatNumber(s.price)}</td>
                                    <td class="${(s.change_pct || 0) >= 0 ? 'positive' : 'negative'}">${formatPercent(s.change_pct)}</td>
                                    <td>${s.rsi != null ? s.rsi.toFixed(1) : '--'}</td>
                                    <td style="font-size:0.72rem;color:#ef4444;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${reasons || '--'}</td>
                                    <td style="color:#ef4444">${penalty < 0 ? penalty : '--'}</td>
                                </tr>`;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
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
    const scoring = tech.signal_scoring || {};
    const sm = tech.smart_money || {};

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
        { label: 'EMA20', value: ind.ema_20 },
        { label: 'EMA50', value: ind.ema_50 },
        { label: 'EMA200', value: ind.ema_200 },
        { label: 'MFI', value: ind.mfi, signal: ind.mfi > 60 ? 'dòng tiền mạnh' : ind.mfi > 50 ? 'bình thường' : 'yếu' },
        { label: 'CMF', value: ind.cmf, signal: (ind.cmf || 0) > 0 ? 'dương' : 'âm' },
        { label: 'SuperTrend', value: sm.supertrend, signal: sm.supertrend_signal },
        { label: 'Stoch RSI %K', value: ind.stoch_rsi_k },
        { label: 'Stoch RSI %D', value: ind.stoch_rsi_d },
        { label: '+DI', value: ind.plus_di },
        { label: '-DI', value: ind.minus_di },
        { label: 'BOS', value: sm.bos },
        { label: 'CHOCH', value: sm.choch },
        { label: 'FVG', value: sm.fvg_signal && sm.fvg_signal !== 'none' ? sm.fvg_signal : 'không' },
        { label: 'Liquidity Sweep', value: sm.liquidity_sweep && sm.liquidity_sweep !== 'none' ? sm.liquidity_sweep : 'không' },
        { label: 'Premium/Discount', value: sm.premium_discount },
        { label: 'Higher High', value: sm.higher_high ? 'Có' : 'Không' },
        { label: 'Higher Low', value: sm.higher_low ? 'Có' : 'Không' },
        { label: 'Cách ATH', value: ind.distance_to_ath != null ? '-' + ind.distance_to_ath.toFixed(1) + '%' : null },
        { label: 'Cách 52W High', value: ind.distance_to_52w_high != null ? '-' + ind.distance_to_52w_high.toFixed(1) + '%' : null },
        { label: 'Cách EMA20', value: ind.distance_to_ema20 != null ? formatPercent(ind.distance_to_ema20) : null },
        { label: 'Cách EMA50', value: ind.distance_to_ema50 != null ? formatPercent(ind.distance_to_ema50) : null },
        { label: 'Cách EMA200', value: ind.distance_to_ema200 != null ? formatPercent(ind.distance_to_ema200) : null },
    ];

    const detail = document.getElementById('stockDetail');
    const indicatorHtml = indicators.filter(i => i.value != null && i.value !== '--').map(i => `
        <tr>
            <td>${i.label}</td>
            <td>${typeof i.value === 'number' ? formatNumber(i.value) : i.value}</td>
            <td style="color:${i.signal === 'oversold' || i.signal?.includes('mạnh') ? '#22c55e' : i.signal === 'overbought' ? '#ef4444' : '#8899aa'}">${i.signal || ''}</td>
        </tr>
    `).join('');

    // Scoring breakdown
    const chiTiet = scoring.chi_tiet || {};
    const groups = [
        { key: 'xu_huong', label: 'Xu hướng', max: 30, icon: 'fa-chart-line', color: '#3b82f6' },
        { key: 'dong_tien', label: 'Dòng tiền', max: 25, icon: 'fa-money-bill-wave', color: '#22c55e' },
        { key: 'momentum', label: 'Momentum', max: 20, icon: 'fa-rocket', color: '#f59e0b' },
        { key: 'price_action', label: 'Price Action', max: 15, icon: 'fa-candle-sticks', color: '#a855f7' },
        { key: 'relative_strength', label: 'RS', max: 10, icon: 'fa-gauge-high', color: '#ec4899' },
    ];
    const scoringHtml = groups.map(g => {
        const data = chiTiet[g.key] || {};
        const diem = data.diem || 0;
        const toiDa = data.toi_da || g.max;
        const pct = diem > 0 ? (diem / toiDa * 100) : 0;
        return `
            <div style="margin-bottom:12px">
                <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:4px">
                    <span style="color:${g.color}"><i class="fas ${g.icon}"></i> ${g.label}</span>
                    <span style="font-weight:600">${diem}/${toiDa}</span>
                </div>
                <div class="progress-bar" style="height:6px;background:rgba(255,255,255,0.05);border-radius:3px;overflow:hidden">
                    <div class="progress-fill" style="width:${pct}%;height:100%;background:${g.color};border-radius:3px;transition:width 0.5s"></div>
                </div>
                ${data.chi_tiet ? '<div style="font-size:0.7rem;color:#667788;margin-top:4px;line-height:1.4">' + data.chi_tiet.slice(0, 3).join('<br>') + '</div>' : ''}
            </div>
        `;
    }).join('');

    // Penalties
    const penalties = scoring.mien_diem || [];
    const penaltyHtml = penalties.length ? `
        <div style="margin-top:12px">
            <div style="color:#ef4444;font-size:0.85rem;margin-bottom:6px"><i class="fas fa-exclamation-triangle"></i> Hình phạt (${penalties.reduce((a, b) => a + b.diem, 0)} điểm)</div>
            ${penalties.map(p => `<div style="font-size:0.75rem;color:#ef4444;padding:2px 0">• ${p.ten}: ${p.diem}</div>`).join('')}
        </div>
    ` : '';

    const tongDiem = scoring.tong_diem || 0;
    const xepLoai = scoring.xep_loai || 'LOAI';
    const gradeColor = xepLoai === 'A+' || xepLoai === 'A' ? '#22c55e' : xepLoai === 'B+' || xepLoai === 'B' ? '#f59e0b' : xepLoai === 'C' ? '#3b82f6' : '#ef4444';

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
            <span style="background:rgba(34,197,94,0.1);padding:6px 16px;border-radius:20px;font-size:0.85rem;border:1px solid rgba(34,197,94,0.2);font-weight:600;color:${gradeColor}">
                ${xepLoai} (${tongDiem}/100)
            </span>
        </div>

        <!-- Scoring Breakdown -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
            <div style="background:rgba(0,0,0,0.15);padding:16px;border-radius:8px">
                <h3 style="color:#8899aa;margin:0 0 12px;font-size:0.95rem"><i class="fas fa-chart-pie"></i> Chấm điểm tín hiệu</h3>
                ${scoringHtml}
                ${penaltyHtml}
            </div>
            <div>
                <h3 style="color:#8899aa;margin:0 0 8px;font-size:1rem"><i class="fas fa-chart-line"></i> Chỉ báo kỹ thuật</h3>
                <div class="table-responsive">
                    <table class="data-table" style="font-size:0.78rem">
                        <tr style="color:#667788;border-bottom:1px solid var(--border-color)">
                            <th style="text-align:left;padding:6px">Chỉ báo</th>
                            <th style="text-align:right;padding:6px">Giá trị</th>
                            <th style="text-align:right;padding:6px">Tín hiệu</th>
                        </tr>
                        ${indicatorHtml}
                    </table>
                </div>
            </div>
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

/* ===== BACKTEST TABLE ===== */
let BACKTEST_DATA = null;
function loadBacktestData(callback) {
    if (BACKTEST_DATA) { if (callback) callback(); return; }
    if (DATA && DATA.backtest) { BACKTEST_DATA = DATA.backtest; if (callback) callback(); return; }
    fetch('data/analysis.json').then(r => r.json()).then(d => {
        BACKTEST_DATA = d.backtest || null;
        if (callback) callback();
    }).catch(() => {});
}

function renderBacktestTable() {
    loadBacktestData(() => {
    if (!BACKTEST_DATA) return;
    const bt = BACKTEST_DATA;
    const perSym = bt.per_symbol_results || {};
    const symbols = Object.keys(perSym);
    if (!symbols.length) return;

    // Stats
    const cagrs = symbols.map(s => perSym[s].cagr || 0);
    const sharpes = symbols.map(s => perSym[s].sharpe || 0);
    const wrs = symbols.map(s => perSym[s].win_rate || 0);
    const bestCagr = Math.max(...cagrs);
    const bestSharpe = Math.max(...sharpes);
    const bestWr = Math.max(...wrs);
    document.getElementById('btBestCagr').textContent = bestCagr.toFixed(1) + '%';
    document.getElementById('btBestSharpe').textContent = bestSharpe.toFixed(2);
    document.getElementById('btBestWR').textContent = bestWr.toFixed(1) + '%';
    document.getElementById('btMultiSym').textContent = symbols.length + ' mã';

    // Table
    const tbody = document.getElementById('backtestTableBody');
    tbody.innerHTML = '';
    const sorted = symbols.sort((a, b) => (perSym[b].sharpe || 0) - (perSym[a].sharpe || 0));
    sorted.forEach(sym => {
        const p = perSym[sym];
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.onclick = () => showStockDetail(sym);
        const cagrColor = (p.cagr || 0) >= 0 ? '#22c55e' : '#ef4444';
        tr.innerHTML = '<td><strong>' + sym + '</strong></td>' +
            '<td style="color:' + cagrColor + ';font-weight:600">' + (p.cagr || 0).toFixed(1) + '%</td>' +
            '<td style="color:' + ((p.sharpe || 0) >= 0.5 ? '#22c55e' : (p.sharpe || 0) >= 0 ? '#f59e0b' : '#ef4444') + '">' + (p.sharpe || 0).toFixed(2) + '</td>' +
            '<td>' + (p.win_rate || 0).toFixed(1) + '%</td>' +
            '<td>' + (p.trades || 0) + '</td>' +
            '<td style="font-size:0.75rem;color:#8899aa">' + (p.key || '').slice(0, 45) + '</td>';
        tbody.appendChild(tr);
    });

    // Recommended params
    const params = bt.recommended_params || {};
    let html = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">';
    const comps = Object.keys(params);
    if (comps.length) {
        comps.forEach(comp => {
            const vals = params[comp];
            if (vals && vals.length) {
                const valList = vals.join(', ');
                html += '<div style="background:rgba(30,41,59,0.5);border-radius:8px;padding:12px">' +
                    '<div style="color:#8899aa;font-size:0.7rem;text-transform:uppercase;margin-bottom:4px">' + comp + '</div>' +
                    '<div style="color:#94a3b8;font-size:0.9rem">' + valList + '</div></div>';
            }
        });
    } else {
        // Fallback: parse best strategy
        const bestStrat = bt.best_strategy || '';
        if (bestStrat) {
            bestStrat.split('|').forEach(part => {
                const kv = part.split('_');
                const key = kv[0];
                const val = kv.slice(1).join('_');
                html += '<div style="background:rgba(30,41,59,0.5);border-radius:8px;padding:12px">' +
                    '<div style="color:#8899aa;font-size:0.7rem;text-transform:uppercase;margin-bottom:4px">' + key + '</div>' +
                    '<div style="color:#22c55e;font-size:0.9rem;font-weight:600">' + val + '</div></div>';
            });
        }
    }
    html += '</div>';
    document.getElementById('btParams').innerHTML = html;
    }); // end loadBacktestData callback
}

/* ===== AFL SIGNALS ===== */
let currentAFLFilter = 'afl-all';

function filterAFLSignals(filter) {
    currentAFLFilter = filter;
    document.querySelectorAll('.filter-btn[data-filter^="afl-"]').forEach(b => b.classList.remove('active'));
    document.querySelector(`.filter-btn[data-filter="${filter}"]`).classList.add('active');
    renderAFLSignals();
}

function renderAFLSignals() {
    if (!DATA && !window.AFL_SIGNALS) return;

    // Support both inline and separate data sources
    let afl, aflBt;
    if (DATA && DATA.rankings && DATA.rankings.afl_signals) {
        afl = DATA.rankings.afl_signals;
        aflBt = DATA.rankings.afl_backtest;
    } else if (window.AFL_SIGNALS) {
        afl = window.AFL_SIGNALS;
        aflBt = window.AFL_BACKTEST;
    }

    if (!afl) {
        document.getElementById('aflBuySignals').innerHTML = '<div class="signal-placeholder" style="padding:40px;text-align:center;color:#667788">Chưa có dữ liệu AFL. Vui lòng chạy export để cập nhật.</div>';
        if (document.getElementById('aflStrategyBody')) document.getElementById('aflStrategyBody').innerHTML = '<tr><td colspan="9" class="empty-row">Chưa có dữ liệu</td></tr>';
        return;
    }

    // Best strategy
    const bestStrat = afl.best_strategy || '--';
    document.getElementById('aflBestStrategy').textContent = bestStrat;
    document.getElementById('aflBuyCount').textContent = afl.buy_count || 0;
    document.getElementById('aflSellCount').textContent = afl.sell_count || 0;

    // Win rate from backtest
    const ranked = (aflBt && aflBt.ranked_strategies) || [];
    const best = ranked.find(r => r.strategy === bestStrat) || ranked[0] || {};
    document.getElementById('aflBestWR').textContent = (best.avg_win_rate != null ? best.avg_win_rate.toFixed(1) + '%' : '--');

    // Strategy rankings table
    const tbody = document.getElementById('aflStrategyBody');
    if (tbody) {
        document.getElementById('aflStrategyCount').textContent = ranked.length;
        if (ranked.length) {
            tbody.innerHTML = ranked.map((r, i) => {
                const wrColor = r.avg_win_rate >= 40 ? '#22c55e' : r.avg_win_rate >= 30 ? '#f59e0b' : '#ef4444';
                const retColor = (r.avg_return || 0) >= 0 ? '#22c55e' : '#ef4444';
                return `<tr>
                    <td>${i + 1}</td>
                    <td><strong>${r.strategy}</strong></td>
                    <td style="color:${wrColor};font-weight:600">${r.avg_win_rate.toFixed(1)}%</td>
                    <td style="color:${retColor}">${r.avg_return.toFixed(1)}%</td>
                    <td>${r.avg_profit_factor.toFixed(2)}</td>
                    <td style="color:#ef4444">${r.avg_max_dd.toFixed(1)}%</td>
                    <td>${r.symbols_tested}</td>
                    <td>${r.total_trades}</td>
                    <td style="font-weight:700;color:#3b82f6">${r.composite_score.toFixed(1)}</td>
                </tr>`;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="9" class="empty-row">Chưa có dữ liệu backtest</td></tr>';
        }
    }

    // Build buy/sell lists from separate arrays
    const buys = (afl.buy_signals || []).filter(s => s && s.symbol).slice(0, 10);
    const sells = (afl.sell_signals || []).filter(s => s && s.symbol).slice(0, 10);

    function renderAFLTable(list, type) {
        if (!list.length) return '<div class="signal-placeholder" style="padding:40px;text-align:center;color:#667788">Không có tín hiệu ' + type + '</div>';
        return `
            <div class="table-responsive">
                <table class="data-table" style="font-size:0.75rem">
                    <thead>
                        <tr>
                            <th>#</th><th>Mã</th><th>Giá</th><th>%</th><th>RSI</th><th>RVOL</th>
                            <th>Cắt lỗ</th><th>TP1</th><th>TP2</th><th>R:R</th><th>Lý do</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${list.map((s, i) => {
                            const reasons = (s.reasons || []).slice(0, 2).join('<br>');
                            const tooltip = (s.reasons || []).join('\\n');
                            const slColor = type === 'MUA' ? '#ef4444' : '#22c55e';
                            const tpColor = type === 'MUA' ? '#22c55e' : '#ef4444';
                            return `<tr onclick="showStockDetail('${s.symbol}')" style="cursor:pointer">
                                <td>${i + 1}</td>
                                <td><strong>${s.symbol}</strong></td>
                                <td>${formatNumber(s.price)}</td>
                                <td class="${(s.change_pct || 0) >= 0 ? 'positive' : 'negative'}">${formatPercent(s.change_pct)}</td>
                                <td>${s.rsi != null ? s.rsi.toFixed(1) : '--'}</td>
                                <td>${s.volume_ratio != null ? s.volume_ratio.toFixed(1) + 'x' : '--'}</td>
                                <td style="color:${slColor}">${s.stop_loss ? formatNumber(s.stop_loss) : '--'}</td>
                                <td style="color:${tpColor}">${s.take_profit_1 ? formatNumber(s.take_profit_1) : '--'}</td>
                                <td style="color:${tpColor}">${s.take_profit_2 ? formatNumber(s.take_profit_2) : '--'}</td>
                                <td>${s.rrr ? s.rrr.toFixed(1) : '--'}</td>
                                <td style="font-size:0.7rem;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${tooltip}">${reasons || '--'}</td>
                            </tr>`;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    // Timeline + date filter
    renderAFLTimeline(afl);
}

function renderAFLTimeline(afl) {
    const timeline = (afl && afl.signal_timeline) || [];
    const container = document.getElementById('aflTimelineBody');
    if (!container) return;

    if (!timeline.length) {
        container.innerHTML = '<div class="signal-placeholder">Chưa có dữ liệu dòng thời gian</div>';
        return;
    }

    // Get date range
    const dates = [...new Set(timeline.map(t => t.date))].sort().reverse();
    const fromInput = document.getElementById('aflFilterFrom');
    const toInput = document.getElementById('aflFilterTo');
    if (fromInput && !fromInput.value && dates.length) {
        fromInput.value = dates[dates.length - 1];
        toInput.value = dates[0];
    }

    // Filter by date
    const fromDate = fromInput ? fromInput.value : '';
    const toDate = toInput ? toInput.value : '';
    let filtered = timeline;
    if (fromDate) filtered = filtered.filter(t => t.date >= fromDate);
    if (toDate) filtered = filtered.filter(t => t.date <= toDate);

    const countEl = document.getElementById('aflFilterCount');
    if (countEl) countEl.textContent = `Hiển thị ${filtered.length} tín hiệu`;

    // Group by date
    const byDate = {};
    filtered.forEach(t => {
        if (!byDate[t.date]) byDate[t.date] = [];
        byDate[t.date].push(t);
    });

    const sortedDates = Object.keys(byDate).sort().reverse();
    if (!sortedDates.length) {
        container.innerHTML = '<div class="signal-placeholder">Không có tín hiệu trong khoảng thời gian này</div>';
        return;
    }

    container.innerHTML = `
        <div style="max-height:400px;overflow-y:auto">
            <table class="data-table" style="font-size:0.75rem">
                <thead style="position:sticky;top:0">
                    <tr>
                        <th>Ngày</th><th>Mã</th><th>Tín hiệu</th><th>Giá</th><th>Sức mạnh</th>
                    </tr>
                </thead>
                <tbody>
                    ${sortedDates.map(date => {
                        const items = byDate[date];
                        const muaCount = items.filter(t => t.signal === 'MUA').length;
                        const banCount = items.filter(t => t.signal === 'BAN').length;
                        return items.map((t, i) => {
                            const sigColor = t.signal === 'MUA' ? '#22c55e' : '#ef4444';
                            const sigLabel = t.signal === 'MUA' ? 'MUA' : 'BÁN';
                            const dateDisplay = i === 0 ? `<strong>${date}</strong>` : '';
                            const summary = i === 0 ? `<span style="color:#94a3b8;font-size:0.65rem"> (${muaCount}M/${banCount}B)</span>` : '';
                            return `<tr onclick="showStockDetail('${t.symbol}')" style="cursor:pointer">
                                <td>${dateDisplay}${summary}</td>
                                <td><strong>${t.symbol}</strong></td>
                                <td style="color:${sigColor};font-weight:600">${sigLabel}</td>
                                <td>${t.price ? t.price.toLocaleString() : '--'}</td>
                                <td>${t.strength ? t.strength + '%' : '--'}</td>
                            </tr>`;
                        }).join('');
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;
}

window.filterAFLTimeline = function() {
    const afl = window.AFL_SIGNALS;
    if (afl) renderAFLTimeline(afl);
};

window.resetAFLFilter = function() {
    const fromInput = document.getElementById('aflFilterFrom');
    const toInput = document.getElementById('aflFilterTo');
    const afl = window.AFL_SIGNALS;
    if (fromInput && afl && afl.signal_timeline && afl.signal_timeline.length) {
        const dates = [...new Set(afl.signal_timeline.map(t => t.date))].sort();
        fromInput.value = dates[0] || '';
        toInput.value = dates[dates.length - 1] || '';
    }
    if (afl) renderAFLTimeline(afl);
};

    // Signal History section
    function renderAFLSignalHistory(list) {
        const allHistory = [];
        list.forEach(s => {
            if (s.signal_history && s.signal_history.length) {
                s.signal_history.forEach(t => {
                    allHistory.push({
                        symbol: s.symbol,
                        entry_date: t.entry_date,
                        exit_date: t.exit_date,
                        pnl_pct: t.pnl_pct,
                        exit_reason: t.exit_reason,
                        bars_held: t.bars_held,
                    });
                });
            }
        });
        if (!allHistory.length) return '';

        // Sort by entry_date descending
        allHistory.sort((a, b) => (b.entry_date || '').localeCompare(a.entry_date || ''));

        return `
            <div class="card mt-3">
                <div class="card-header">📋 Lịch sử tín hiệu gần nhất</div>
                <div class="table-responsive">
                    <table class="data-table" style="font-size:0.75rem">
                        <thead>
                            <tr>
                                <th>Mã</th><th>Ngày vào</th><th>Ngày ra</th><th>P&L</th><th>Số ngày</th><th>Lý do thoát</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${allHistory.slice(0, 15).map(t => {
                                const pnlColor = (t.pnl_pct || 0) >= 0 ? '#22c55e' : '#ef4444';
                                const reasonMap = {'STOP_LOSS': 'Cắt lỗ', 'TAKE_PROFIT': 'Chốt lời', 'SIGNAL': 'Tín hiệu đảo chiều', 'MAX_HOLD': 'Hết thời gian nắm giữ'};
                                return `<tr>
                                    <td><strong>${t.symbol}</strong></td>
                                    <td>${t.entry_date || '--'}</td>
                                    <td>${t.exit_date || '--'}</td>
                                    <td style="color:${pnlColor};font-weight:600">${(t.pnl_pct || 0).toFixed(1)}%</td>
                                    <td>${t.bars_held || '--'}</td>
                                    <td>${reasonMap[t.exit_reason] || t.exit_reason || '--'}</td>
                                </tr>`;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }

    if (document.getElementById('aflBuySignals')) {
        document.getElementById('aflBuySignals').innerHTML = renderAFLTable(buys, 'MUA');
    }
    if (document.getElementById('aflSellSignals')) {
        document.getElementById('aflSellSignals').innerHTML = renderAFLTable(sells, 'BÁN');
    }
    // Signal history
    const histContainer = document.getElementById('aflSignalHistory');
    if (histContainer) {
        histContainer.innerHTML = renderAFLSignalHistory([...buys, ...sells]);
    }
}

/* ===== CLOSE MODAL ON OUTSIDE CLICK ===== */
window.onclick = function(e) {
    document.querySelectorAll('.modal').forEach(m => {
        if (e.target === m) { m.style.display = 'none'; m.classList.remove('show'); }
    });
};
