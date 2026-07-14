import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.backtest_engine import *
from datetime import datetime
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cache_dir = os.path.join(base_dir, 'data', 'backtest_cache')

pipeline = BacktestPipeline()
generator = StrategyGenerator()
strategies = generator.generate(max_combinations=300)
print(f'Strategies: {len(strategies)}')

symbols = ['SSI','FPT','HPG','VCB','ACB','TCB','MBB']
data = {}
for sym in symbols:
    p = os.path.join(cache_dir, f'{sym}.parquet')
    if os.path.exists(p):
        df = pd.read_parquet(p)
        df['date'] = pd.to_datetime(df['date'])
        data[sym] = df
        print(f'{sym}: {len(df)} rows')

train_data, val_data, oos_data = {}, {}, {}
for sym, df in data.items():
    train_df = df[df['date'] < '2025-01-01'].copy()
    val_df = df[(df['date'] >= '2025-01-01') & (df['date'] < '2025-07-01')].copy()
    oos_df = df[df['date'] >= '2025-07-01'].copy()
    if len(train_df) > 200: train_data[sym] = train_df
    if len(val_df) > 30: val_data[sym] = val_df
    if len(oos_df) > 30: oos_data[sym] = oos_df
print(f'Train: {len(train_data)}, Val: {len(val_data)}, OOS: {len(oos_data)}')

print('\n=== DAILY ===')
t0 = time.time()
batch_size = 100
all_daily_results = []
for i in range(0, len(strategies), batch_size):
    batch = strategies[i:i+batch_size]
    batch_results = pipeline.run_backtest_batch(train_data, batch, symbols_limit=7)
    all_daily_results.extend(batch_results)
    print(f'  Batch {i//batch_size+1}/{(len(strategies)-1)//batch_size+1}: {len(batch_results)} results, {time.time()-t0:.0f}s')

print(f'Daily total: {len(all_daily_results)} results in {time.time()-t0:.0f}s')
daily_ranker = StrategyRanker()
daily_ranked = daily_ranker.rank(all_daily_results)
daily_top = daily_ranked[:20]
print(f'Top: {len(daily_top)}')

combined = {
    'timeframes_tested': [],
    'timestamp': datetime.now().isoformat(),
    'note': 'Hourly khong co API tu SSI',
    'results': {},
}

if daily_top:
    for i, r in enumerate(daily_top[:10]):
        print(f'  #{i+1} {r.symbol:6s} CAGR={r.cagr_pct:6.1f}% SR={r.sharpe_ratio:.2f} WR={r.win_rate:.1f}% T={r.total_trades} Comp={r.composite_score:.1f}')
    
    daily_report = pipeline.generate_report(daily_ranked, 'Daily 2021-2024')
    combined['timeframes_tested'].append('daily')
    combined['results']['daily'] = daily_report
    
    best = daily_top[0].strategy
    print(f'\nBest strategy: {best.combination_key}')
    
    # OOS test
    for pname, pdata in [('Val 2025H1', val_data), ('OOS 2025H2-2026', oos_data)]:
        if pdata:
            print(f'\n--- {pname} ---')
            oos_r = pipeline.run_backtest_batch(pdata, [best], symbols_limit=len(pdata))
            for r in oos_r:
                print(f'  {r.symbol}: CAGR={r.cagr_pct:6.1f}% SR={r.sharpe_ratio:.2f} WR={r.win_rate:.1f}% T={r.total_trades}')

# WEEKLY
print('\n=== WEEKLY ===')
weekly_train = pipeline.resample_to_timeframe(train_data, 'weekly')
weekly_val = pipeline.resample_to_timeframe(val_data, 'weekly')
weekly_oos = pipeline.resample_to_timeframe(oos_data, 'weekly')

weekly_results = pipeline.run_backtest_batch(weekly_train, strategies, symbols_limit=7)
weekly_ranker = StrategyRanker()
weekly_ranked = weekly_ranker.rank(weekly_results)
weekly_top = weekly_ranked[:20]
print(f'Weekly top: {len(weekly_top)}')
if weekly_top:
    combined['timeframes_tested'].append('weekly')
    for i, r in enumerate(weekly_top[:5]):
        print(f'  #{i+1} {r.symbol:6s} CAGR={r.cagr_pct:6.1f}% SR={r.sharpe_ratio:.2f} WR={r.win_rate:.1f}% T={r.total_trades}')

# Save
report_path = os.path.join(base_dir, 'data', 'backtest_mtf_report.json')
with open(report_path, 'w') as f:
    json.dump(combined, f, ensure_ascii=False, indent=2)
print(f'Saved: {report_path}')
print(f'Total time: {time.time()-t0:.0f}s')
