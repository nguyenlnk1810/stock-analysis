import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.backtest_engine import *
from datetime import datetime
import pandas as pd
import numpy as np
from collections import defaultdict

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cache_dir = os.path.join(base_dir, 'data', 'backtest_cache')

print('='*60)
print('BACKTEST TỐI ƯU - WALK-FORWARD + ENSEMBLE + INDICATOR ANALYSIS')
print('='*60)

# 1. Load data
symbols = ['SSI','FPT','HPG','VCB','ACB','TCB','MBB']
data = {}
for sym in symbols:
    p = os.path.join(cache_dir, f'{sym}.parquet')
    if os.path.exists(p):
        df = pd.read_parquet(p)
        df['date'] = pd.to_datetime(df['date'])
        data[sym] = df
print(f'Loaded {len(data)} symbols')

# 2. Split: Train 2021-2024, OOS 2025-2026
train_data = {}
oos_data = {}
for sym, df in data.items():
    df['date'] = pd.to_datetime(df['date'])
    train_df = df[df['date'] < '2025-01-01'].copy()
    oos_df = df[df['date'] >= '2025-01-01'].copy()
    if len(train_df) > 200: train_data[sym] = train_df
    if len(oos_df) > 50: oos_data[sym] = oos_df
print(f'Train: {len(train_data)} symbols ({min(len(v) for v in train_data.values())}-{max(len(v) for v in train_data.values())} bars)')
print(f'OOS:   {len(oos_data)} symbols')

# 3. Generate strategies (more combos)
generator = StrategyGenerator()
strategies = generator.generate(max_combinations=500)
print(f'Strategies: {len(strategies)}')

# 4. Run backtest on ALL symbols with ALL strategies
print('\n=== STEP 1: BACKTEST ALL STRATEGIES ===')
pipeline = BacktestPipeline()
all_results = []
t0 = time.time()
batch_size = 100
for i in range(0, len(strategies), batch_size):
    batch = strategies[i:i+batch_size]
    batch_results = pipeline.run_backtest_batch(train_data, batch, symbols_limit=7)
    all_results.extend(batch_results)
    print(f'  Batch {i//batch_size+1}/{(len(strategies)-1)//batch_size+1}: {len(batch_results)} results, {time.time()-t0:.0f}s')

print(f'Total: {len(all_results)} results in {time.time()-t0:.0f}s')

# 5. Cross-Validation Walk-Forward on top candidates
print('\n=== STEP 2: WALK-FORWARD CROSS-VALIDATION ===')
cv = CrossValidator(train_data)

# Group results by strategy key
strat_groups = defaultdict(list)
for r in all_results:
    strat_groups[r.strategy.combination_key].append(r)

# Compute cross-symbol averages
strat_avg = {}
for key, group in strat_groups.items():
    sym_count = len(set(r.symbol for r in group if r.total_trades >= 3))
    avg_cagr = np.mean([r.cagr_pct for r in group if r.cagr_pct != 0]) if any(r.cagr_pct != 0 for r in group) else 0
    avg_sharpe = np.mean([r.sharpe_ratio for r in group if r.sharpe_ratio != 0]) if any(r.sharpe_ratio != 0 for r in group) else 0
    strat_avg[key] = {"sym_count": sym_count, "avg_cagr": avg_cagr, "avg_sharpe": avg_sharpe}

# Only run CV on top candidates (sym_count >= 2)
cv_candidates = sorted(
    [(k, v) for k, v in strat_avg.items() if v["sym_count"] >= 2 and v["avg_cagr"] > 0 and v["avg_sharpe"] > 0.3],
    key=lambda x: x[1]["avg_cagr"], reverse=True
)[:30]

cv_results = {}
for key, stats in cv_candidates:
    # Find the strategy params
    for r in all_results:
        if r.strategy.combination_key == key:
            cv_res = cv.walk_forward(r.strategy)
            cv_results[key] = cv_res
            print(f'  {key[:50]}... sym={stats["sym_count"]} CAGR={stats["avg_cagr"]:.1f}% robustness={cv_res["robustness_score"]:.1f}')
            break

# 6. Rank with all filters
print('\n=== STEP 3: RANKING WITH FILTERS ===')
ranker = StrategyRanker()
ranked = ranker.rank(
    all_results,
    cv_results=cv_results,
    min_symbols=2,
    min_trades=5,
    min_win_rate=30,
    min_sharpe=0.3,
    max_dd=30,
    robustness_min=20,
)
top = ranker.top_n(30)
print(f'Top strategies after filters: {len(top)}')

if top:
    for i, r in enumerate(top[:10]):
        k = r.strategy.combination_key[:55]
        extra = getattr(r, "_extra", {}) or {}
        print(f'  #{i+1} sym={extra.get("symbols_passed",1)} CAGR={r.cagr_pct:.1f}% SR={r.sharpe_ratio:.2f} WR={r.win_rate:.1f}% T={r.total_trades} Comp={r.composite_score:.1f}')
        print(f'       CV={extra.get("cv_score",0)} boost={extra.get("robustness_boost",0)} {k}')

    # 7. Indicator Analysis
    print('\n=== STEP 4: INDICATOR ANALYSIS ===')
    ind_analyzer = IndicatorAnalyzer()
    ind_results = ind_analyzer.analyze_top_strategies(top, top_n=30)
    print('Top indicator components by frequency:')
    for i, (ind, stats) in enumerate(sorted(ind_results.items(), key=lambda x: x[1]['count'], reverse=True)[:20]):
        print(f'  {ind:40s} count={stats["count"]:3d} win_rate={stats["win_rate"]:5.1f}% avg_comp={stats["avg_composite"]:.1f}')

    # 8. Ensemble
    print('\n=== STEP 5: ENSEMBLE TEST ===')
    top_strats = [r.strategy for r in top[:5]]
    weights = [r.composite_score for r in top[:5]]
    total_w = sum(weights)
    weights = [w / total_w for w in weights]
    ensemble = EnsembleStrategy(top_strats, weights)

    # Test ensemble on OOS data
    ensemble_results = []
    for sym, df in oos_data.items():
        result = ensemble.run(df)
        result.symbol = sym
        ensemble_results.append(result)

    print('Ensemble OOS results:')
    avg_cagr_ensemble = 0
    for r in ensemble_results:
        avg_cagr_ensemble += r.cagr_pct
        print(f'  {r.symbol}: CAGR={r.cagr_pct:.1f}% SR={r.sharpe_ratio:.2f} WR={r.win_rate:.1f}% T={r.total_trades} DD={r.max_drawdown_pct:.1f}%')
    avg_cagr_ensemble /= max(len(ensemble_results), 1)
    print(f'  Average OOS CAGR: {avg_cagr_ensemble:.1f}%')

    # 9. Generate report
    print('\n=== STEP 6: REPORT ===')
    report = pipeline.generate_report(ranked, 'Optimized 2021-2024')
    report["indicator_analysis"] = dict(sorted(ind_results.items(), key=lambda x: x[1]["count"], reverse=True)[:30])
    report["ensemble"] = {
        "strategies": [r.strategy.combination_key[:40] for r in top[:5]],
        "weights": [round(w, 3) for w in weights],
        "oos_results": [{"symbol": r.symbol, "cagr": round(r.cagr_pct, 2), "sharpe": round(r.sharpe_ratio, 2),
                         "win_rate": round(r.win_rate, 1), "trades": r.total_trades,
                         "max_dd": round(r.max_drawdown_pct, 2)} for r in ensemble_results],
        "avg_oos_cagr": round(avg_cagr_ensemble, 2),
    }
    report["cv_summary"] = {k: {"robustness": v["robustness_score"], "consistency": v["consistency_pct"],
                                "avg_test_cagr": v["avg_test_cagr"]} for k, v in cv_results.items()}

    report_path = os.path.join(base_dir, 'data', 'backtest_optimized_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'Saved: {report_path}')

    # 10. Save best indicator combination for dashboard
    best_indicators = {}
    for k in top[:5]:
        best_indicators[k] = {
            "cagr": round(k.cagr_pct, 2),
            "sharpe": round(k.sharpe_ratio, 2),
            "win_rate": round(k.win_rate, 1),
            "composite": round(k.composite_score, 1),
        }
    # Extract key components from best strategies
    key_components = {}
    for r in top[:10]:
        for part in r.strategy.combination_key.split("|"):
            base = part.split("_")[0] if "_" in part else part
            if base not in key_components:
                key_components[base] = {"variants": [], "count": 0}
            key_components[base]["variants"].append(part)
            key_components[base]["count"] += 1
    # Most common values per component
    best_params = {}
    for comp, info in sorted(key_components.items(), key=lambda x: x[1]["count"], reverse=True):
        from collections import Counter
        most_common = Counter(info["variants"]).most_common(3)
        best_params[comp] = [v for v, c in most_common]

    dashboard_indicators = {
        "best_indicators": best_indicators,
        "recommended_params": best_params,
        "ensemble_oos_cagr": round(avg_cagr_ensemble, 2),
        "generated_at": datetime.now().isoformat(),
    }
    dash_path = os.path.join(base_dir, 'data', 'best_indicators.json')
    with open(dash_path, 'w') as f:
        json.dump(dashboard_indicators, f, ensure_ascii=False, indent=2)
    print(f'Saved best indicators: {dash_path}')

    # Print summary
    print(f'\n{"="*60}')
    print('KẾT QUẢ TỐI ƯU')
    print(f'{"="*60}')
    print(f'Tổng số chiến lược: {len(strategies)}')
    print(f'Qua filter (>=2 symbols, WR>=30%, SR>=0.3, DD<=30%): {len(top)}')
    print(f'Best strategy: CAGR={top[0].cagr_pct:.1f}% SR={top[0].sharpe_ratio:.2f} WR={top[0].win_rate:.1f}%')
    print(f'Ensemble OOS CAGR: {avg_cagr_ensemble:.1f}%')
    print(f'Thời gian: {time.time()-t0:.0f}s')
else:
    print('Không có chiến lược nào đạt filter!')
