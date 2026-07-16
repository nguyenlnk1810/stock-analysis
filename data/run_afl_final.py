import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime

from src.afl_strategies import run_all_afl_backtests, backtest_afl_strategy, NumpyEncoder

cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_cache")
output_dir = os.path.dirname(os.path.abspath(__file__))

# Get cached symbols
symbols = []
for fname in sorted(os.listdir(cache_dir)):
    if fname.endswith(".parquet"):
        sym = fname.replace(".parquet", "")
        try:
            df = pd.read_parquet(os.path.join(cache_dir, fname))
            if len(df) >= 100:
                symbols.append(sym)
        except:
            pass

print(f"Found {len(symbols)} cached symbols")
print(f"Symbols: {symbols}")

all_results = {}
strategy_agg = {}

for i, sym in enumerate(symbols):
    path = os.path.join(cache_dir, f"{sym}.parquet")
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    df = df.sort_values("date").reset_index(drop=True)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    print(f"\n[{i+1}/{len(symbols)}] {sym} ({len(df)} bars):")
    results = run_all_afl_backtests(df)
    all_results[sym] = results
    for r in results:
        if r["total_trades"] >= 5:
            print(f"  {r['strategy']:20s} | Trades={r['total_trades']:3d} | WR={r['win_rate']:5.1f}% | Ret={r['total_return_pct']:7.2f}% | PF={r['profit_factor']:.2f} | DD={r['max_drawdown_pct']:.1f}%")
        sn = r["strategy"]
        if sn not in strategy_agg:
            strategy_agg[sn] = {
                "total_trades": 0, "wins": 0,
                "win_rates": [], "returns": [], "profit_factors": [],
                "drawdowns": [], "count": 0, "symbols_set": set()
            }
        if r["total_trades"] >= 3:
            strategy_agg[sn]["total_trades"] += r["total_trades"]
            strategy_agg[sn]["wins"] += r.get("wins", 0)
            strategy_agg[sn]["win_rates"].append(r["win_rate"])
            strategy_agg[sn]["returns"].append(r["total_return_pct"])
            strategy_agg[sn]["profit_factors"].append(r["profit_factor"])
            strategy_agg[sn]["drawdowns"].append(r["max_drawdown_pct"])
            strategy_agg[sn]["count"] += 1
            strategy_agg[sn]["symbols_set"].add(sym)

ranked = []
for name, agg in strategy_agg.items():
    if agg["count"] < 3:
        continue
    avg_wr = np.mean(agg["win_rates"])
    avg_ret = np.mean(agg["returns"])
    avg_pf = np.mean(agg["profit_factors"])
    avg_dd = np.mean(agg["drawdowns"])
    consistency = np.std(agg["win_rates"]) if len(agg["win_rates"]) > 1 else 100
    sym_tested = len(agg["symbols_set"])
    score = avg_wr * 0.4 + min(avg_ret, 50) * 0.3 + min(avg_pf, 5) * 10 * 0.2 + (1 - min(avg_dd / 50, 1)) * 20 * 0.1
    ranked.append({
        "strategy": name,
        "avg_win_rate": round(avg_wr, 2),
        "avg_return": round(avg_ret, 2),
        "avg_profit_factor": round(avg_pf, 2),
        "avg_max_dd": round(avg_dd, 2),
        "consistency": round(consistency, 2),
        "symbols_tested": sym_tested,
        "total_trades": agg["total_trades"],
        "composite_score": round(score, 2),
    })

ranked.sort(key=lambda x: x["composite_score"], reverse=True)

print("\n\n========== AFL BACKTEST RESULTS ==========")
print(f"{'Strategy':20s} | {'WR%':>6s} | {'Return':>8s} | {'PF':>5s} | {'DD':>6s} | {'Sym':>3s} | {'Trades':>6s} | {'Score':>6s}")
print("-" * 80)
for r in ranked:
    print(f"{r['strategy']:20s} | {r['avg_win_rate']:5.1f}% | {r['avg_return']:7.2f}% | {r['avg_profit_factor']:4.2f} | {r['avg_max_dd']:5.1f}% | {r['symbols_tested']:3d} | {r['total_trades']:6d} | {r['composite_score']:5.1f}")

best_strategy = ranked[0]["strategy"] if ranked else "MAI"
best_wr = ranked[0]["avg_win_rate"] if ranked else 0
print(f"\n=== BEST STRATEGY: {best_strategy} (WR={best_wr:.1f}%) ===")

# Current signals for the best strategy
print(f"\n=== CURRENT SIGNALS ({best_strategy}) ===")
all_current_signals = {}
for sym in symbols:
    path = os.path.join(cache_dir, f"{sym}.parquet")
    if not os.path.exists(path):
        continue
    try:
        df = pd.read_parquet(path)
        df.columns = [c.lower() for c in df.columns]
        df = df.sort_values("date").reset_index(drop=True)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        if df.empty:
            continue
        
        result = backtest_afl_strategy(df, best_strategy)
        signals = result.get("trades", [])
        last_signal = None
        for t in reversed(signals):
            if t["exit_reason"] != "MAX_HOLD":
                last_signal = t
                break

        current_price = float(df["close"].iloc[-1])
        prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else current_price
        change_pct = round((current_price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0

        close_series = df["close"]
        diff = close_series.diff()
        gain = diff.clip(lower=0).ewm(span=14).mean()
        loss = (-diff.clip(upper=0)).ewm(span=14).mean()
        rs = gain / (loss + 1e-10)
        rsi_val = round(float(100 - 100 / (1 + rs.iloc[-1])), 1) if not pd.isna(rs.iloc[-1]) else 50
        vol_ratio = float(df["volume"].iloc[-1]) / max(float(df["volume"].tail(20).mean()), 1)

        signal_type = "NEUTRAL"
        if last_signal and last_signal["pnl_pct"] > 0:
            signal_type = "MUA"
        elif last_signal and last_signal["pnl_pct"] <= 0:
            signal_type = "BAN"

        all_current_signals[sym] = {
            "symbol": sym,
            "signal": signal_type,
            "price": current_price,
            "change_pct": change_pct,
            "rsi": rsi_val,
            "volume_ratio": round(vol_ratio, 2),
        }
        print(f"  {sym}: {signal_type} @ {current_price:.0f} ({change_pct:+.2f}%) RSI={rsi_val}")
    except Exception as e:
        print(f"  {sym}: ERROR - {e}")

buys = [v for k, v in all_current_signals.items() if v.get("signal") == "MUA"]
sells = [v for k, v in all_current_signals.items() if v.get("signal") == "BAN"]
neutrals = [v for k, v in all_current_signals.items() if v.get("signal") == "NEUTRAL"]

# Save results
output = {
    "generated_at": datetime.now().isoformat(),
    "best_strategy": best_strategy,
    "best_win_rate": best_wr,
    "ranked_strategies": ranked,
    "current_signals": all_current_signals,
    "total_symbols_tested": len(symbols),
    "buy_count": len(buys),
    "sell_count": len(sells),
}

out_path = os.path.join(output_dir, "afl_backtest_results.json")
with open(out_path, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
print(f"\nSaved: {out_path}")
print(f"Total: {len(buys)} MUA | {len(sells)} BÁN | {len(neutrals)} TRUNG TÍNH (trên {len(symbols)} mã)")

# Update dashboard
afl_data = {
    "best_strategy": best_strategy,
    "buy_signals": sorted(buys, key=lambda x: x.get("change_pct", 0), reverse=True)[:15],
    "sell_signals": sorted(sells, key=lambda x: x.get("change_pct", 0))[:15],
    "neutral_signals": neutrals[:15],
    "buy_count": len(buys),
    "sell_count": len(sells),
}

js_block = '<script>window.AFL_SIGNALS=' + json.dumps(afl_data, ensure_ascii=False, cls=NumpyEncoder) + ';' + \
           'window.AFL_BACKTEST=' + json.dumps(output, ensure_ascii=False, cls=NumpyEncoder) + ';</script>'

# Update index.html
idx_path = os.path.join(os.path.dirname(output_dir), "docs", "index.html")
if os.path.exists(idx_path):
    with open(idx_path, "r") as f:
        html = f.read()
    lines = html.split("\n")
    clean_lines = [l for l in lines if "AFL_SIGNALS" not in l and "AFL_BACKTEST" not in l]
    html = "\n".join(clean_lines)
    html = html.replace(
        '<script src="js/dashboard.js?v=4"></script>',
        "    " + js_block + '\n    <script src="js/dashboard.js?v=4"></script>'
    )
    with open(idx_path, "w") as f:
        f.write(html)
    print("✅ Updated docs/index.html")

# Update data.js
data_js_path = os.path.join(os.path.dirname(output_dir), "docs", "data", "data.js")
if os.path.exists(data_js_path):
    with open(data_js_path, "r") as f:
        content = f.read()
    lines = content.split("\n")
    clean_lines = [l for l in lines if "AFL_SIGNALS" not in l and "AFL_BACKTEST" not in l]
    content = "\n".join(clean_lines).rstrip()
    content += '\nwindow.AFL_SIGNALS=' + json.dumps(afl_data, ensure_ascii=False, cls=NumpyEncoder) + ';'
    content += '\nwindow.AFL_BACKTEST=' + json.dumps(output, ensure_ascii=False, cls=NumpyEncoder) + ';'
    with open(data_js_path, "w") as f:
        f.write(content)
    print("✅ Updated docs/data/data.js")

print("\n✅ DONE!")
