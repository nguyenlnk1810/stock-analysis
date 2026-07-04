let data = null;
let breadthChart = null;
let signalChart = null;

async function loadData() {
    document.getElementById('stockGrid').innerHTML = '<div class="loading">🔄 Đang tải dữ liệu...</div>';
    try {
        const resp = await fetch('data/analysis.json?t=' + Date.now());
        data = await resp.json();
        renderDashboard();
    } catch (e) {
        document.getElementById('stockGrid').innerHTML =
            '<div class="error">❌ Không thể tải dữ liệu. Chạy <b>python export_data.py</b> trước.</div>';
        document.getElementById('lastUpdate').textContent = '⚠️ Chưa có dữ liệu';
    }
}

function renderDashboard() {
    if (!data) return;
    const { market_index, market_breadth, stocks, exported_at } = data;

    // Last update
    document.getElementById('lastUpdate').textContent =
        '📅 Cập nhật lần cuối: ' + new Date(exported_at).toLocaleString('vi-VN');

    // Market index
    if (market_index) {
        const idx = market_index;
        document.getElementById('idxPrice').textContent = idx.current?.toLocaleString() || '--';
        const chgEl = document.getElementById('idxChange');
        if (idx.change_pct != null) {
            const cls = idx.change_pct >= 0 ? 'green' : 'red';
            const sign = idx.change_pct >= 0 ? '+' : '';
            chgEl.textContent = sign + idx.change_pct + '%';
            chgEl.className = 'change ' + cls;
        }
    }

    // Market breadth
    const breadth = market_breadth?.summary || {};
    document.getElementById('breadthAdv').textContent = breadth.advancing ?? '--';
    document.getElementById('breadthDec').textContent = breadth.declining ?? '--';
    document.getElementById('aboveMA20').textContent =
        breadth.above_ma20 ? breadth.above_ma20 + '/' + breadth.total : '--';
    document.getElementById('aboveMA50').textContent =
        breadth.above_ma50 ? breadth.above_ma50 + '/' + breadth.total : '--';
    const nsEl = document.getElementById('netSignal');
    if (breadth.net_signal != null) {
        nsEl.textContent = breadth.net_signal > 0 ? '+' + breadth.net_signal : breadth.net_signal;
        nsEl.className = 'value ' + (breadth.net_signal >= 0 ? 'green' : 'red');
    }

    // Charts
    renderBreadthChart(breadth);
    renderSignalChart(breadth);

    // Stocks
    renderStocks();
}

function renderBreadthChart(breadth) {
    const ctx = document.getElementById('breadthChart').getContext('2d');
    if (breadthChart) breadthChart.destroy();
    breadthChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Tăng', 'Giảm', 'Đứng'],
            datasets: [{
                data: [breadth.advancing || 0, breadth.declining || 0, breadth.unchanged || 0],
                backgroundColor: ['#4caf50', '#f44336', '#ff9800'],
                borderWidth: 0,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#e0e6ed' } },
                title: { display: true, text: 'Tăng/Giảm hôm nay', color: '#8899aa' }
            }
        }
    });
}

function renderSignalChart(breadth) {
    const ctx = document.getElementById('signalChart').getContext('2d');
    if (signalChart) signalChart.destroy();
    signalChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Mua', 'Bán', 'Trung tính'],
            datasets: [{
                data: [
                    breadth.buy_signals || 0,
                    breadth.sell_signals || 0,
                    (breadth.total || 0) - (breadth.buy_signals || 0) - (breadth.sell_signals || 0)
                ],
                backgroundColor: ['#4caf50', '#f44336', '#ff9800'],
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                title: { display: true, text: 'Tín hiệu kỹ thuật', color: '#8899aa' }
            },
            scales: {
                y: { beginAtZero: true, ticks: { color: '#667788', stepSize: 1 } },
                x: { ticks: { color: '#8899aa' } }
            }
        }
    });
}

function renderStocks() {
    if (!data || !data.stocks) return;
    const sortBy = document.getElementById('sortSelect').value;
    const search = document.getElementById('searchInput').value.toUpperCase();

    let stocks = Object.entries(data.stocks).map(([symbol, s]) => ({ ...s, symbol }));

    // Filter
    if (search) stocks = stocks.filter(s => s.symbol.includes(search));

    // Sort
    stocks.sort((a, b) => {
        if (sortBy === 'symbol') return a.symbol.localeCompare(b.symbol);
        if (sortBy === 'price') return (b.technical?.indicators?.current_price || 0) -
            (a.technical?.indicators?.current_price || 0);
        if (sortBy === 'change') return Math.abs(b.technical?.indicators?.price_change_pct_1d || 0) -
            Math.abs(a.technical?.indicators?.price_change_pct_1d || 0);
        return Math.abs(b.technical?.score || 0) - Math.abs(a.technical?.score || 0);
    });

    const grid = document.getElementById('stockGrid');
    grid.innerHTML = stocks.map(s => renderStockCard(s)).join('');
}

function renderStockCard(s) {
    const tech = s.technical || {};
    const ind = tech.indicators || {};
    const price = ind.current_price || 0;
    const change = ind.price_change_pct_1d || 0;
    const rsi = ind.rsi_14 || '--';
    const action = (tech.action || 'N/A').replace(/ /g, '-');
    const changeCls = change >= 0 ? 'green' : 'red';
    const changeSign = change >= 0 ? '+' : '';

    return `
        <div class="stock-card" onclick="showDetail('${s.symbol}')">
            <div class="header">
                <span class="symbol">${s.symbol}</span>
                <span class="action action-${action}">${tech.action || 'N/A'}</span>
            </div>
            <div class="details">
                <span>Giá: <span class="val">${price.toLocaleString()}</span></span>
                <span class="${changeCls}">${changeSign}${change}%</span>
                <span>RSI: <span class="val">${rsi}</span></span>
                <span>Volume: <span class="val">${ind.volume_ratio ? ind.volume_ratio + 'x' : '--'}</span></span>
                <span>Điểm: <span class="val">${tech.score ?? 0}</span></span>
                <span>MA20: <span class="val">${ind.price_vs_ma20_pct != null ? (ind.price_vs_ma20_pct >= 0 ? '+' : '') + ind.price_vs_ma20_pct + '%' : '--'}</span></span>
            </div>
        </div>
    `;
}

function showDetail(symbol) {
    if (!data || !data.stocks || !data.stocks[symbol]) return;
    const s = data.stocks[symbol];
    const tech = s.technical || {};
    const ind = tech.indicators || {};
    const signals = tech.signals || [];

    const modal = document.getElementById('stockModal');
    const detail = document.getElementById('stockDetail');

    const price = ind.current_price || 0;
    const change = ind.price_change_pct_1d || 0;
    const changeCls = change >= 0 ? 'green' : 'red';

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
    ];

    const indicatorHtml = indicators.filter(i => i.value != null).map(i => `
        <tr>
            <td>${i.label}</td>
            <td>${typeof i.value === 'number' ? i.value.toLocaleString() : i.value}</td>
            <td style="color:${i.signal === 'oversold' || i.signal?.includes('mạnh') ? '#4caf50' : i.signal === 'overbought' ? '#f44336' : '#8899aa'}">${i.signal || ''}</td>
        </tr>
    `).join('');

    detail.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
            <div>
                <h2 style="color:#4fc3f7;margin:0">${symbol}</h2>
                <small style="color:#8899aa">${s.company_name || ''}</small>
            </div>
            <div style="text-align:right">
                <div style="font-size:1.8em;font-weight:bold">${price.toLocaleString()}</div>
                <div class="${changeCls}">${change >= 0 ? '+' : ''}${change}%</div>
            </div>
        </div>

        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px">
            <span class="action action-${(tech.action || '').replace(/ /g, '-')}" style="font-size:0.9em;padding:6px 16px">
                ${tech.action || 'N/A'} (${tech.confidence || ''})
            </span>
            <span style="background:#0f1923;padding:6px 16px;border-radius:20px;font-size:0.85em">
                Điểm: ${tech.score ?? 0}
            </span>
        </div>

        <h3 style="color:#8899aa;margin:16px 0 8px">📋 Chỉ báo kỹ thuật</h3>
        <table style="width:100%;border-collapse:collapse;font-size:0.9em">
            <tr style="color:#667788;border-bottom:1px solid #1e3a5f">
                <th style="text-align:left;padding:6px">Chỉ báo</th>
                <th style="text-align:right;padding:6px">Giá trị</th>
                <th style="text-align:right;padding:6px">Tín hiệu</th>
            </tr>
            ${indicatorHtml}
        </table>

        <h3 style="color:#8899aa;margin:16px 0 8px">📌 Tín hiệu</h3>
        <ul style="list-style:none;padding:0">
            ${signals.map(s => `<li style="padding:4px 0;color:#e0e6ed">• ${s}</li>`).join('')}
        </ul>

        <h3 style="color:#8899aa;margin:16px 0 8px">📰 Tin tức</h3>
        <ul style="list-style:none;padding:0">
            ${(s.news || []).slice(0, 5).map(n =>
                `<li style="padding:4px 0;font-size:0.85em;color:#8899aa">📰 ${n.title}</li>`
            ).join('') || '<li style="color:#667788">Không có tin tức</li>'}
        </ul>

        <div style="margin-top:16px;padding:12px;background:#0f1923;border-radius:8px;font-size:0.85em;color:#667788">
            ⚠️ Phân tích tham khảo, không phải lời khuyên đầu tư
        </div>
    `;

    modal.style.display = 'block';
}

function closeModal() {
    document.getElementById('stockModal').style.display = 'none';
}

function filterStocks() { renderStocks(); }

function refreshData() { loadData(); }

// Close modal on outside click
window.onclick = function(e) {
    const modal = document.getElementById('stockModal');
    if (e.target === modal) modal.style.display = 'none';
};

// Load on page load
loadData();
