import sys, os, json, time, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.backtest_engine import *
from datetime import datetime
import pandas as pd
import numpy as np
from collections import defaultdict, Counter

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cache_dir = os.path.join(base_dir, 'data', 'backtest_cache')
results_pkl = os.path.join(base_dir, 'data', 'all_results.pkl')
report_json = os.path.join(base_dir, 'data', 'backtest_optimized_report.json')
indicators_json = os.path.join(base_dir, 'data', 'best_indicators.json')

print('='*50)
print('BACKTEST TOI U V2')
print('='*50)

# 1. Load data
symbols = ['SSI','FPT','HPG','VCB','ACB','TCB','MBB']
data = {}
for sym in symbols:
    p = os.path.join(cache_dir, f'{sym}.parquet')
    if os.path.exists(p):
        df = pd.read_parquet(p)
        df['date'] = pd.to_datetime(df['date'])
        data[sym] = df

train_data = {}
oos_data = {}
for sym, df in data.items():
    train_df = df[df['date'] < '2025-01-01'].copy()
    oos_df = df[df['date'] >= '2025-01-01'].copy()
    if len(train_df) > 200: train_data[sym] = train_df
    if len(oos_df) > 50: oos_data[sym] = oos_df
print(f'Train: {len(train_data)} sym, OOS: {len(oos_data)} sym')

# 2. Generate strategies
generator = StrategyGenerator()
strategies = generator.generate(max_combinations=300)
print(f'Strategies: {len(strategies)}')

# 3. Backtest with batched saving
all_results = []
pipeline = BacktestPipeline()
t0 = time.time()
for i in range(0, len(strategies), 75):
    batch = strategies[i:i+75]
    batch_results = pipeline.run_backtest_batch(train_data, batch, symbols_limit=7)
    all_results.extend(batch_results)
    # Save progress every batch
    with open(results_pkl, 'wb') as f:
        pickle.dump(all_results, f)
    elapsed = time.time() - t0
    print(f'Batch {i//75+1}/4: {len(batch_results)} results ({len(all_results)} total, {elapsed:.0f}s)')

print(f'Total: {len(all_results)} results in {time.time()-t0:.0f}s')

# 4. Cross-symbol analysis
strat_groups = defaultdict(list)
for r in all_results:
    strat_groups[r.strategy.combination_key].append(r)

print(f'\n=== CROSS-SYMBOL ANALYSIS ===')
multi_sym = []
for key, group in strat_groups.items():
    sym_with_trades = set(r.symbol for r in group if r.total_trades >= 3)
    sym_count = len(sym_with_trades)
    if sym_count < 1:
        continue
    cagrs = [r.cagr_pct for r in group if r.cagr_pct != 0]
    sharpes = [r.sharpe_ratio for r in group if r.sharpe_ratio != 0]
    wrs = [r.win_rate for r in group if r.win_rate > 0]
    dds = [r.max_drawdown_pct for r in group if r.max_drawdown_pct > 0]
    if not cagrs or not sharpes:
        continue
    avg_cagr = np.mean(cagrs)
    avg_sharpe = np.mean(sharpes)
    avg_wr = np.mean(wrs) if wrs else 0
    avg_dd = np.mean(dds) if dds else 100
    total_trades = sum(r.total_trades for r in group)
    
    if avg_cagr > 0 and avg_sharpe > 0.2:
        multi_sym.append({
            'key': key, 'symbols': sym_count, 'symbol_list': list(sym_with_trades),
            'cagr': round(avg_cagr, 2), 'sharpe': round(avg_sharpe, 3), 'win_rate': round(avg_wr, 1),
            'max_dd': round(avg_dd, 2), 'total_trades': total_trades,
            'profit_factor': round(np.mean([r.profit_factor for r in group if r.profit_factor > 0]), 2),
        })

multi_sym.sort(key=lambda x: x['sharpe'], reverse=True)
print(f'Strategies with >=1 symbol + CAGR>0 + SR>0.2: {len(multi_sym)}')
for s in multi_sym[:15]:
    print(f'  sym={s["symbols"]} CAGR={s["cagr"]:6.1f}% SR={s["sharpe"]:.2f} WR={s["win_rate"]:5.1f}% T={s["total_trades"]} DD={s["max_dd"]:.1f}% PF={s["profit_factor"]:.2f}')
    key_short = s["key"][:65]
    print(f'       {key_short}')

# 5. Indicator Analysis
print(f'\n=== INDICATOR ANALYSIS ===')
indicator_stats = defaultdict(lambda: {'count': 0, 'composites': []})
for r in all_results:
    if r.cagr_pct > 0 and r.sharpe_ratio > 0.2:
        for part in r.strategy.combination_key.split('|'):
            indicator_stats[part]['count'] += 1
            indicator_stats[part]['composites'].append(r.composite_score)

print('Top indicators by frequency in profitable strategies:')
ind_sorted = sorted(indicator_stats.items(), key=lambda x: x[1]['count'], reverse=True)
for ind, stats in ind_sorted[:25]:
    avg_comp = round(np.mean(stats['composites']), 1) if stats['composites'] else 0
    cnt = stats["count"]
    print(f'  {ind:40s} count={cnt:3d} avg_comp={avg_comp:.1f}')

# 6. Best parameter analysis
print(f'\n=== BEST PARAMETER ANALYSIS ===')
param_analysis = {}
for s in multi_sym[:30]:
    for part in s['key'].split('|'):
        base = part.split('_')[0] if '_' in part else part
        if base not in param_analysis:
            param_analysis[base] = {'variants': [], 'avg_sharpes': []}
        param_analysis[base]['variants'].append(part)
        param_analysis[base]['avg_sharpes'].append(s['sharpe'])

# Most common & best performing parameter values
best_params = {}
for comp, info in sorted(param_analysis.items(), key=lambda x: len(x[1]['variants']), reverse=True):
    variant_stats = Counter(info['variants'])
    most_common = variant_stats.most_common(5)
    best_params[comp] = []
    for v, c in most_common:
        avg_s = np.mean([s['sharpe'] for s in multi_sym[:30] if v in s['key']]) if multi_sym else 0
        best_params[comp].append({'value': v, 'count': c, 'avg_sharpe': round(avg_s, 2)})
    if best_params[comp]:
        print(f'  {comp}:')
        for bp in best_params[comp]:
            val = bp["value"]
            cnt = bp["count"]
            sr = bp["avg_sharpe"]
            print(f'    {val:30s} count={cnt} avg_SR={sr:.2f}')

# 7. Save results
report = {
    'timestamp': datetime.now().isoformat(),
    'symbols_tested': symbols,
    'train_period': '2021-01 to 2024-12',
    'oos_period': '2025-01 to 2026-07',
    'total_strategies': len(strategies),
    'total_symbols': len(data),
    'ranked_strategies': multi_sym[:50],
    'indicator_analysis': {k: v for k, v in ind_sorted[:40]},
    'best_params': best_params,
}
with open(report_json, 'w') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

# 8. Best indicators for dashboard
dashboard = {
    'generated_at': datetime.now().isoformat(),
    'source': 'Optimized Backtest 2021-2024',
    'top_strategies': multi_sym[:10],
    'recommended_params': {k: [v[0]['value'] for v in vals][:3] for k, vals in best_params.items() if vals},
    'best_indicator_combos': [s['key'] for s in multi_sym[:5]],
    'backtest_note': 'Filters: CAGR>0, SR>0.2, >=1 symbol',
}
with open(indicators_json, 'w') as f:
    json.dump(dashboard, f, ensure_ascii=False, indent=2)

print(f'\nSaved: {report_json}')
print(f'Saved: {indicators_json}')
print(f'Total time: {time.time()-t0:.0f}s')
