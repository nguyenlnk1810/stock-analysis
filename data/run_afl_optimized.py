import sys, os, json, time, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime

from src.afl_strategies import (
    PsychIndexStrategy, ZangerVolumeStrategy, RSVNINDEXStrategy,
    MA20CrossoverStrategy, ZigZagStrategy, ScoringStrategy,
    IchimokuStrategy, MAIStrategy, VolumePocketStrategy, NumpyEncoder
)

ALL_STRATEGIES = [
    "PsychIndex", "ZangerVolume", "RSVNINDEX", "MA20Crossover",
    "ZigZag", "Scoring", "Ichimoku", "MAI", "VolumePocket"
]

def make_strategy(name, df, index_df=None):
    if name == "PsychIndex":
        s = PsychIndexStrategy(df, lookback=12, oversold=25, overbought=75)
    elif name == "ZangerVolume":
        s = ZangerVolumeStrategy(df)
    elif name == "RSVNINDEX":
        s = RSVNINDEXStrategy(df, index_df)
    elif name == "MA20Crossover":
        s = MA20CrossoverStrategy(df, fast_period=15, slow_period=30)
    elif name == "ZigZag":
        s = ZigZagStrategy(df, pct_change=6.0)
    elif name == "Scoring":
        s = ScoringStrategy(df, index_df)
    elif name == "Ichimoku":
        s = IchimokuStrategy(df)
    elif name == "MAI":
        s = MAIStrategy(df)
    elif name == "VolumePocket":
        s = VolumePocketStrategy(df)
    else:
        raise ValueError(f"Unknown strategy: {name}")
    return s

cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_cache")
output_dir = os.path.dirname(os.path.abspath(__file__))

def compute_all_signals(df, index_df=None):
    signals_dict = {}
    for name in ALL_STRATEGIES:
        try:
            strat = make_strategy(name, df, index_df)
            _, sig = strat.compute()
            signals_dict[name] = sig
        except Exception as e:
            signals_dict[name] = np.zeros(len(df))
    return signals_dict

def combo_signals(signals_dict, combo_names):
    sig = np.zeros(len(list(signals_dict.values())[0]))
    n = len(combo_names)
    for i in range(len(sig)):
        votes = 0
        for name in combo_names:
            if i < len(signals_dict[name]) and signals_dict[name][i] == 1:
                votes += 1
            elif i < len(signals_dict[name]) and signals_dict[name][i] == -1:
                votes -= 1
        if votes > 0 and votes >= (n + 1) // 2:
            sig[i] = 1
        elif votes < 0 and abs(votes) >= (n + 1) // 2:
            sig[i] = -1
    return sig

def backtest_signals(close, sig, df):
    trades = []
    in_position = False
    entry_price = 0
    entry_idx = 0
    capital = 1.0

    warmup = 60
    for i in range(warmup, len(df)):
        if in_position:
            exit_signal = False
            exit_reason = ""
            pnl_pct = (close[i] - entry_price) / entry_price * 100

            if sig[i] == -1:
                exit_signal = True
                exit_reason = "SIGNAL"
            elif pnl_pct <= -5:
                exit_signal = True
                exit_reason = "STOP_LOSS"
            elif pnl_pct >= 15:
                exit_signal = True
                exit_reason = "TAKE_PROFIT"
            elif (i - entry_idx) >= 30:
                exit_signal = True
                exit_reason = "MAX_HOLD"

            if exit_signal:
                trade = {
                    "entry_date": str(df["date"].iloc[entry_idx]),
                    "entry_price": entry_price,
                    "exit_date": str(df["date"].iloc[i]),
                    "exit_price": close[i],
                    "pnl_pct": round(pnl_pct - 0.25, 2),
                    "bars_held": i - entry_idx,
                    "exit_reason": exit_reason,
                }
                trades.append(trade)
                capital *= (1 + trade["pnl_pct"] / 100)
                in_position = False

        if not in_position:
            if sig[i] == 1:
                entry_price = close[i]
                entry_idx = i
                in_position = True

    if in_position and trades:
        trades[-1]["exit_price"] = close[-1]
        trades[-1]["pnl_pct"] = round((close[-1] - trades[-1]["entry_price"]) / trades[-1]["entry_price"] * 100 - 0.25, 2)
        trades[-1]["exit_date"] = str(df["date"].iloc[-1])

    return trades, capital

def compute_metrics(trades, capital):
    total_trades = len(trades)
    if total_trades == 0:
        return {"total_trades": 0, "win_rate": 0, "total_return_pct": 0, "max_drawdown_pct": 0, "profit_factor": 0}

    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    win_rate = len(wins) / total_trades * 100
    total_return = (capital - 1) * 100

    peak = capital
    max_dd = 0
    eq = 1.0
    eq_peak = 1.0
    for t in trades:
        eq *= (1 + t["pnl_pct"] / 100)
        if eq > eq_peak:
            eq_peak = eq
        dd = (eq_peak - eq) / eq_peak * 100
        if dd > max_dd:
            max_dd = dd

    gross_profit = sum(t["pnl_pct"] for t in wins)
    gross_loss = abs(sum(t["pnl_pct"] for t in losses))
    profit_factor = gross_profit / max(gross_loss, 0.01)

    return {
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 2),
        "total_return_pct": round(total_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "avg_trade_pct": round(np.mean([t["pnl_pct"] for t in trades]), 2) if trades else 0,
        "avg_win_pct": round(np.mean([t["pnl_pct"] for t in wins]), 2) if wins else 0,
        "avg_loss_pct": round(np.mean([t["pnl_pct"] for t in losses]), 2) if losses else 0,
        "profit_factor": round(profit_factor, 2),
    }

def evaluate_method(method_name, signals_dict, close, df, min_trades=5):
    if isinstance(method_name, tuple):
        sig = combo_signals(signals_dict, list(method_name))
        label = "+".join(method_name)
    else:
        sig = signals_dict.get(method_name, np.zeros(len(df)))
        label = method_name
    trades, capital = backtest_signals(close, sig, df)
    metrics = compute_metrics(trades, capital)
    metrics["method"] = label
    metrics["trades"] = trades
    return metrics

def compute_current_signal(signals_dict, method_name, close):
    if isinstance(method_name, tuple):
        sig = combo_signals(signals_dict, list(method_name))
        label = "+".join(method_name)
    else:
        sig = signals_dict.get(method_name, np.zeros(len(close)))
        label = method_name

    last_idx = min(len(sig) - 1, len(close) - 1)
    if last_idx < 60:
        return "NEUTRAL", 0, None

    # Find the most recent signal bar
    signal_bar = None
    for i in range(last_idx, max(60, last_idx - 5) - 1, -1):
        if sig[i] == 1:
            signal_bar = i
            return "MUA", 1.0, signal_bar
        if sig[i] == -1:
            signal_bar = i
            return "BAN", -1.0, signal_bar
    return "NEUTRAL", 0, None

def compute_indicator_values(df, index_df=None):
    """Return current indicator values for all strategies for explanation."""
    vals = {}
    close = df["close"].values
    vol = df["volume"].values
    high = df["high"].values
    low = df["low"].values

    try:
        psych = PsychIndexStrategy(df, lookback=12, oversold=25, overbought=75)
        pv, _ = psych.compute()
        vals["PsychIndex"] = round(float(pv[-1]), 1) if not np.isnan(pv[-1]) else None
    except: pass
    try:
        mai = MAIStrategy(df)
        mv, _ = mai.compute()
        vals["MAI"] = round(float(mv[-1]), 1) if not np.isnan(mv[-1]) else None
    except: pass
    try:
        rsv = RSVNINDEXStrategy(df, index_df)
        rv, _ = rsv.compute()
        vals["RSVNINDEX"] = round(float(rv[-1]), 1) if rv is not None and not np.isnan(rv[-1]) else None
    except: pass
    try:
        sc = ScoringStrategy(df, index_df)
        sv, _ = sc.compute()
        vals["Scoring"] = round(float(sv[-1]), 1) if sv is not None and not np.isnan(sv[-1]) else None
    except: pass
    try:
        zp = ZangerVolumeStrategy(df)
        zv, _ = zp.compute()
        vals["ZangerVolume"] = round(float(zv[-1]), 1) if zv is not None and not np.isnan(zv[-1]) else None
    except: pass
    try:
        vp = VolumePocketStrategy(df)
        vpv, vp_sig = vp.compute()
        vals["VolumePocket"] = "triggered" if abs(vp_sig[-1]) > 0 else "none"
    except: pass

    # RSI, ATR for TP/SL
    close_s = pd.Series(close)
    diff = close_s.diff()
    gain = diff.clip(lower=0).ewm(span=14).mean()
    loss = (-diff.clip(upper=0)).ewm(span=14).mean()
    rs = gain / (loss + 1e-10)
    vals["RSI"] = round(float(100 - 100 / (1 + rs.iloc[-1])), 1) if not pd.isna(rs.iloc[-1]) else 50

    tr = np.maximum(high - low, np.maximum(abs(high - np.roll(close, 1)), abs(low - np.roll(close, 1))))
    tr[0] = tr[1] if len(tr) > 1 else 0
    atr = pd.Series(tr).ewm(span=14, adjust=False).mean().values[-1]
    vals["ATR"] = round(float(atr), 0)

    return vals, atr

def compute_signal_reasons(method_names, indicator_vals, df):
    """Generate human-readable reasons for why a signal was triggered."""
    reasons = []
    price = float(df["close"].iloc[-1])
    high = float(df["high"].iloc[-1])
    low = float(df["low"].iloc[-1])

    if isinstance(method_names, str):
        method_names = [method_names]
    for m in method_names:
        r = compute_signal_reasons_single(m, indicator_vals, price)
        if r:
            reasons.extend(r)
    return reasons[:5]

def compute_signal_reasons_single(name, iv, price):
    r = []
    if name == "PsychIndex":
        v = iv.get("PsychIndex")
        if v is not None:
            r.append(f"PsychIndex={v} (quá bán <25 → MUA, quá mua >75 → BÁN)")
    elif name == "MAI":
        v = iv.get("MAI")
        if v is not None:
            r.append(f"MA Impulse={v} (vượt ngưỡng ±5)")
    elif name == "RSVNINDEX":
        v = iv.get("RSVNINDEX")
        if v is not None:
            r.append(f"RS so VNINDEX={v} (mạnh hơn VNINDEX → MUA)")
    elif name == "ZangerVolume":
        v = iv.get("ZangerVolume")
        if v is not None:
            r.append(f"Volume Ratio={v}x TB20")
    elif name == "Scoring":
        v = iv.get("Scoring")
        if v is not None:
            r.append(f"Composite Score={v}")
    elif name == "VolumePocket":
        r.append("Volume pocket: giá tăng + KL giảm so HV10 + giá > MA20")
    elif name == "MA20Crossover":
        r.append("MA15 cắt lên MA30 + Volume > SMA20×1.2 → MUA")
    elif name == "Ichimoku":
        r.append("Ichimoku cloud: giá trên mây + đường chuyển đổi > đường cơ sở")
    elif name == "ZigZag":
        r.append("ZigZag: đáy sau cao hơn đáy trước + phá vỡ 6%")
    if not r:
        r.append(f"{name}: tín hiệu phát sinh")
    return r

# ============================================================
print("=" * 70)
print("BACKTEST AFL 2024-2025: Individual + Combination Strategies")
print("=" * 70)

# Load symbols
with open(os.path.join(output_dir, "qualified_1m_symbols.json")) as f:
    qualified = json.load(f)
symbols = sorted(qualified.keys())

print(f"Symbols: {len(symbols)}")

# Generate combo candidates
top_n_individual = 6
indiv_rank = {}  # will be filled after individual backtest

# First pass: evaluate individual strategies on all symbols
print("\n=== Phase 1: Individual Strategy Backtest ===")
all_results = {}
combo_results = {}

for i, sym in enumerate(symbols):
    path = os.path.join(cache_dir, f"{sym}.parquet")
    if not os.path.exists(path):
        continue
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])

    # Filter to 2024-2025
    df = df[(df["date"] >= "2024-01-01") & (df["date"] <= "2025-12-31")].reset_index(drop=True)
    if len(df) < 200:
        continue

    close = df["close"].values
    signals_dict = compute_all_signals(df)
    all_results[sym] = signals_dict

    print(f"\n[{i+1}/{len(symbols)}] {sym} ({len(df)} bars):")

    # Individual
    for name in ALL_STRATEGIES:
        m = evaluate_method(name, signals_dict, close, df, min_trades=3)
        if m["total_trades"] >= 3:
            print(f"  {name:20s} | Trades={m['total_trades']:3d} | WR={m['win_rate']:5.1f}% | Ret={m['total_return_pct']:7.2f}%")

# Aggregate individual results
indiv_agg = {name: {"win_rates": [], "returns": [], "profit_factors": [], "drawdowns": [], "count": 0, "total_trades": 0} for name in ALL_STRATEGIES}

for sym, signals_dict in all_results.items():
    path = os.path.join(cache_dir, f"{sym}.parquet")
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= "2024-01-01") & (df["date"] <= "2025-12-31")].reset_index(drop=True)
    close = df["close"].values

    for name in ALL_STRATEGIES:
        m = evaluate_method(name, signals_dict, close, df, min_trades=1)
        if m["total_trades"] >= 3:
            indiv_agg[name]["win_rates"].append(m["win_rate"])
            indiv_agg[name]["returns"].append(m["total_return_pct"])
            indiv_agg[name]["profit_factors"].append(m["profit_factor"])
            indiv_agg[name]["drawdowns"].append(m["max_drawdown_pct"])
            indiv_agg[name]["count"] += 1
            indiv_agg[name]["total_trades"] += m["total_trades"]

print("\n\n=== INDIVIDUAL STRATEGY RANKING (2024-2025) ===")
print(f"{'Strategy':20s} | {'WR%':>6s} | {'Return':>8s} | {'PF':>5s} | {'DD':>6s} | {'Sym':>3s} | {'Trades':>5s}")
print("-" * 70)
indiv_ranked = []
for name, agg in indiv_agg.items():
    if agg["count"] < 3:
        continue
    avg_wr = np.mean(agg["win_rates"])
    avg_ret = np.mean(agg["returns"])
    avg_pf = np.mean(agg["profit_factors"])
    avg_dd = np.mean(agg["drawdowns"])
    score = avg_wr * 0.4 + min(avg_ret, 50) * 0.3 + min(avg_pf, 5) * 10 * 0.2 + (1 - min(avg_dd / 50, 1)) * 20 * 0.1
    indiv_ranked.append((name, avg_wr, avg_ret, avg_pf, avg_dd, agg["count"], agg["total_trades"], score))
    print(f"{name:20s} | {avg_wr:5.1f}% | {avg_ret:7.2f}% | {avg_pf:4.2f} | {avg_dd:5.1f}% | {agg['count']:3d} | {agg['total_trades']:5d} | {score:5.1f}")

indiv_ranked.sort(key=lambda x: x[1], reverse=True)  # Sort by WR
top6 = [r[0] for r in indiv_ranked[:6]]
print(f"\nTop 6 by Win Rate: {top6}")

# Phase 2: Test combinations of top 6
print("\n\n=== Phase 2: Combination Strategy Backtest ===")

combos_to_test = []
# Pairs
for pair in itertools.combinations(top6, 2):
    combos_to_test.append(pair)
# Triples
for triple in itertools.combinations(top6, 3):
    combos_to_test.append(triple)
# All-top6
combos_to_test.append(tuple(top6))

print(f"Testing {len(combos_to_test)} combinations...")

combo_agg = {}
for combo in combos_to_test:
    combo_name = "+".join(combo)
    combo_agg[combo_name] = {"win_rates": [], "returns": [], "profit_factors": [], "drawdowns": [], "count": 0, "total_trades": 0}

for sym, signals_dict in all_results.items():
    path = os.path.join(cache_dir, f"{sym}.parquet")
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= "2024-01-01") & (df["date"] <= "2025-12-31")].reset_index(drop=True)
    close = df["close"].values

    for combo in combos_to_test:
        m = evaluate_method(combo, signals_dict, close, df, min_trades=1)
        cn = "+".join(combo)
        if m["total_trades"] >= 3:
            combo_agg[cn]["win_rates"].append(m["win_rate"])
            combo_agg[cn]["returns"].append(m["total_return_pct"])
            combo_agg[cn]["profit_factors"].append(m["profit_factor"])
            combo_agg[cn]["drawdowns"].append(m["max_drawdown_pct"])
            combo_agg[cn]["count"] += 1
            combo_agg[cn]["total_trades"] += m["total_trades"]

print("\n=== COMBINATION RANKING (2024-2025) ===")
all_ranked = []
for name, agg in combo_agg.items():
    if agg["count"] < 5:
        continue
    avg_wr = np.mean(agg["win_rates"])
    avg_ret = np.mean(agg["returns"])
    avg_pf = np.mean(agg["profit_factors"])
    avg_dd = np.mean(agg["drawdowns"])
    score = avg_wr * 0.4 + min(avg_ret, 50) * 0.3 + min(avg_pf, 5) * 10 * 0.2 + (1 - min(avg_dd / 50, 1)) * 20 * 0.1
    all_ranked.append((name, avg_wr, avg_ret, avg_pf, avg_dd, agg["count"], agg["total_trades"], score, "combo"))

# Add individuals also
for name, avg_wr, avg_ret, avg_pf, avg_dd, cnt, ttrades, score in indiv_ranked:
    if cnt >= 3:
        all_ranked.append((name, avg_wr, avg_ret, avg_pf, avg_dd, cnt, ttrades, score, "individual"))

all_ranked.sort(key=lambda x: x[1], reverse=True)  # Sort by WR

print(f"{'Method':30s} | {'Type':12s} | {'WR%':>6s} | {'Return':>8s} | {'PF':>5s} | {'DD':>6s} | {'Sym':>3s} | {'Trades':>5s} | {'Score':>5s}")
print("-" * 95)
for name, wr, ret, pf, dd, cnt, tt, score, typ in all_ranked[:30]:
    print(f"{name:30s} | {typ:12s} | {wr:5.1f}% | {ret:7.2f}% | {pf:4.2f} | {dd:5.1f}% | {cnt:3d} | {tt:5d} | {score:5.1f}")

# Select top 3-5 best methods
best_methods = []
seen = set()
for name, wr, ret, pf, dd, cnt, tt, score, typ in all_ranked:
    if len(best_methods) >= 5:
        break
    if cnt >= 5 and tt >= 30 and wr >= 35:
        if name not in seen:
            best_methods.append((name, typ, wr, score))
            seen.add(name)

if len(best_methods) < 3:
    for name, wr, ret, pf, dd, cnt, tt, score, typ in all_ranked:
        if len(best_methods) >= 3:
            break
        if name not in seen and cnt >= 3:
            best_methods.append((name, typ, wr, score))
            seen.add(name)

print(f"\n\n=== TOP {len(best_methods)} BEST SIGNAL METHODS ===")
for i, (name, typ, wr, score) in enumerate(best_methods):
    print(f"{i+1}. {name} ({typ}) - WR={wr:.1f}%, Score={score:.1f}")

# Phase 3: Current signals using best methods + TP/SL + reasons + history
print("\n\n=== Phase 3: Current Signals + TP/SL + Reasons + History ===")
print(f"Using top {len(best_methods)} methods: {[m[0] for m in best_methods]}")

all_buy_signals = {}
all_sell_signals = {}
all_signal_history = {}

for sym in symbols:
    path = os.path.join(cache_dir, f"{sym}.parquet")
    if not os.path.exists(path):
        continue
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values

    signals_dict = compute_all_signals(df)
    indicator_vals, atr = compute_indicator_values(df)
    mua_votes = 0
    ban_votes = 0
    details = {}
    signal_bar_idx = None

    for method_name, typ, wr, score in best_methods:
        if typ == "combo":
            combo_names = tuple(method_name.split("+"))
            sig_type, strength, sbar = compute_current_signal(signals_dict, combo_names, close)
        else:
            sig_type, strength, sbar = compute_current_signal(signals_dict, method_name, close)

        details[method_name] = sig_type
        if sig_type == "MUA":
            mua_votes += 1
            if signal_bar_idx is None or (sbar is not None and sbar < signal_bar_idx):
                signal_bar_idx = sbar
        elif sig_type == "BAN":
            ban_votes += 1
            if signal_bar_idx is None or (sbar is not None and sbar < signal_bar_idx):
                signal_bar_idx = sbar

    # Overall signal: majority vote of best methods
    if mua_votes > ban_votes and mua_votes >= len(best_methods) * 0.4:
        final_signal = "MUA"
        strength_pct = mua_votes / len(best_methods) * 100
    elif ban_votes > mua_votes and ban_votes >= len(best_methods) * 0.4:
        final_signal = "BAN"
        strength_pct = ban_votes / len(best_methods) * 100
    else:
        final_signal = "NEUTRAL"
        strength_pct = 0

    current_price = float(close[-1])
    prev_close = float(close[-2]) if len(df) >= 2 else current_price
    change_pct = round((current_price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0

    close_series = pd.Series(close)
    diff = close_series.diff()
    gain = diff.clip(lower=0).ewm(span=14).mean()
    loss = (-diff.clip(upper=0)).ewm(span=14).mean()
    rs = gain / (loss + 1e-10)
    rsi_val = round(float(100 - 100 / (1 + rs.iloc[-1])), 1) if not pd.isna(rs.iloc[-1]) else 50
    vol_ratio = float(df["volume"].iloc[-1]) / max(float(df["volume"].tail(20).mean()), 1)

    # Compute TP/SL levels
    atr_val = max(float(atr), current_price * 0.005)  # Minimum ATR = 0.5% of price
    if final_signal == "MUA":
        stop_loss = round(current_price - 2.0 * atr_val, 0)
        take_profit_1 = round(current_price + 2.0 * atr_val, 0)
        take_profit_2 = round(current_price + 3.0 * atr_val, 0)
        rrr = round((take_profit_1 - current_price) / (current_price - stop_loss + 1), 2) if stop_loss > 0 else 0
    elif final_signal == "BAN":
        stop_loss = round(current_price + 2.0 * atr_val, 0)
        take_profit_1 = round(current_price - 2.0 * atr_val, 0)
        take_profit_2 = round(current_price - 3.0 * atr_val, 0)
        rrr = round((current_price - take_profit_1) / (stop_loss - current_price + 1), 2) if take_profit_1 > 0 else 0
    else:
        stop_loss = 0
        take_profit_1 = 0
        take_profit_2 = 0
        rrr = 0

    # Compute signal date (most recent signal bar)
    signal_date = ""
    if signal_bar_idx is not None and signal_bar_idx < len(df):
        signal_date = str(df["date"].iloc[signal_bar_idx]).split()[0]

    # Compute reasons
    all_method_names = []
    for m in best_methods:
        if m[1] == "combo":
            all_method_names.extend(m[0].split("+"))
        else:
            all_method_names.append(m[0])
    reasons = compute_signal_reasons(all_method_names, indicator_vals, df) if final_signal != "NEUTRAL" else []

    # Compute signal history from backtest trades
    try:
        result = backtest_afl_strategy(df, "VolumePocket")
        all_trades = result.get("trades", [])
        recent_trades = []
        for t in all_trades[-20:]:
            recent_trades.append({
                "entry_date": t["entry_date"],
                "exit_date": t["exit_date"],
                "pnl_pct": t["pnl_pct"],
                "exit_reason": t["exit_reason"],
                "bars_held": t["bars_held"],
            })
        signal_history = recent_trades[-10:]
    except Exception:
        signal_history = []

    signal_entry = {
        "symbol": sym,
        "signal": final_signal,
        "price": current_price,
        "change_pct": change_pct,
        "rsi": rsi_val,
        "volume_ratio": round(vol_ratio, 2),
        "strength": round(strength_pct, 0) if strength_pct > 0 else 0,
        "details": details,
        "stop_loss": stop_loss,
        "take_profit_1": take_profit_1,
        "take_profit_2": take_profit_2,
        "rrr": rrr,
        "atr": round(atr_val, 0),
        "signal_date": signal_date,
        "reasons": reasons[:5],
        "signal_history": signal_history,
    }

    if final_signal == "MUA":
        all_buy_signals[sym] = signal_entry
    elif final_signal == "BAN":
        all_sell_signals[sym] = signal_entry

# Sort and get top 10
buys_sorted = sorted(all_buy_signals.values(), key=lambda x: x["strength"], reverse=True)[:10]
sells_sorted = sorted(all_sell_signals.values(), key=lambda x: x["strength"], reverse=True)[:10]

print(f"\n=== TOP 10 MUA ===")
for s in buys_sorted:
    print(f"  {s['symbol']} ({s['strength']:.0f}%) @ {s['price']:.0f} ({s['change_pct']:+.2f}%)")
    print(f"    SL={s['stop_loss']:.0f} TP1={s['take_profit_1']:.0f} TP2={s['take_profit_2']:.0f} R:R={s['rrr']}")
    print(f"    Signal: {s['signal_date']} | ATR={s['atr']:.0f}")
    for r in s['reasons']:
        print(f"    -> {r}")

print(f"\n=== TOP 10 BAN ===")
for s in sells_sorted:
    print(f"  {s['symbol']} ({s['strength']:.0f}%) @ {s['price']:.0f} ({s['change_pct']:+.2f}%)")
    print(f"    SL={s['stop_loss']:.0f} TP1={s['take_profit_1']:.0f} TP2={s['take_profit_2']:.0f} R:R={s['rrr']}")
    print(f"    Signal: {s['signal_date']} | ATR={s['atr']:.0f}")
    for r in s['reasons']:
        print(f"    -> {r}")

# Build output with backward-compatible ranked_strategies for dashboard
ranked_strategies = [
    {"strategy": r[0], "type": r[7], "avg_win_rate": r[1], "avg_return": r[2], "avg_profit_factor": r[3],
     "avg_max_dd": r[4], "symbols_tested": r[5], "total_trades": r[6],
     "composite_score": r[7] if len(r) > 7 and isinstance(r[7], (int, float)) else r[8] if len(r) > 8 else 0}
    for r in all_ranked[:30]
]

output = {
    "generated_at": datetime.now().isoformat(),
    "backtest_period": "2024-01-01 to 2025-12-31",
    "symbols_tested": len(symbols),
    "best_strategy": best_methods[0][0] if best_methods else "VolumePocket",
    "best_win_rate": best_methods[0][2] if best_methods else 0,
    "best_methods": [{"name": m[0], "type": m[1], "win_rate": m[2], "composite_score": m[3]} for m in best_methods],
    "ranked_strategies": ranked_strategies,
    "all_ranked_methods": ranked_strategies,
    "buy_signals": buys_sorted,
    "sell_signals": sells_sorted,
    "buy_count": len(buys_sorted),
    "sell_count": len(sells_sorted),
}

out_path = os.path.join(output_dir, "afl_optimized_results.json")
with open(out_path, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
print(f"\nSaved: {out_path}")

# Phase 4: Build signal timeline for current top stocks
print("\n\n=== Phase 4: Signal Timeline (Current Data) ===")
signal_timeline = []
timeline_symbols = [s["symbol"] for s in buys_sorted + sells_sorted]

for sym in timeline_symbols:
    path = os.path.join(cache_dir, f"{sym}.parquet")
    if not os.path.exists(path):
        continue
    df = pd.read_parquet(path)
    df.columns = [c.lower() for c in df.columns]
    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    close = df["close"].values

    # Only look at recent data (last 90 trading days)
    df_bt = df.tail(120).reset_index(drop=True)
    if len(df_bt) < 60:
        continue
    close_bt = df_bt["close"].values
    signals_dict_bt = compute_all_signals(df_bt)

    last_signal = None
    for i in range(60, len(df_bt)):
        bar_close = close_bt[:i+1]
        bar_signals = {k: v[:i+1] for k, v in signals_dict_bt.items()}
        mua_votes = 0
        ban_votes = 0
        for method_name, typ, wr, score in best_methods:
            if typ == "combo":
                combo_names = tuple(method_name.split("+"))
                sig_type, _, _ = compute_current_signal(bar_signals, combo_names, bar_close)
            else:
                sig_type, _, _ = compute_current_signal(bar_signals, method_name, bar_close)
            if sig_type == "MUA":
                mua_votes += 1
            elif sig_type == "BAN":
                ban_votes += 1
        if mua_votes > ban_votes and mua_votes >= len(best_methods) * 0.4:
            overall = "MUA"
        elif ban_votes > mua_votes and ban_votes >= len(best_methods) * 0.4:
            overall = "BAN"
        else:
            overall = "NEUTRAL"
        if overall != last_signal and overall in ("MUA", "BAN"):
            signal_timeline.append({
                "date": str(df_bt["date"].iloc[i]).split()[0],
                "symbol": sym,
                "signal": overall,
                "strength": round(max(mua_votes, ban_votes) / len(best_methods) * 100, 0),
                "price": float(close_bt[i]),
            })
        last_signal = overall

print(f"  Generated {len(signal_timeline)} timeline events across {len(timeline_symbols)} symbols (recent data)")

# Build output with backward-compatible ranked_strategies for dashboard
ranked_strategies = [
    {"strategy": r[0], "type": r[7], "avg_win_rate": r[1], "avg_return": r[2], "avg_profit_factor": r[3],
     "avg_max_dd": r[4], "symbols_tested": r[5], "total_trades": r[6],
     "composite_score": r[7] if len(r) > 7 and isinstance(r[7], (int, float)) else r[8] if len(r) > 8 else 0}
    for r in all_ranked[:30]
]

output = {
    "generated_at": datetime.now().isoformat(),
    "backtest_period": "2024-01-01 to 2025-12-31",
    "symbols_tested": len(symbols),
    "best_strategy": best_methods[0][0] if best_methods else "VolumePocket",
    "best_win_rate": best_methods[0][2] if best_methods else 0,
    "best_methods": [{"name": m[0], "type": m[1], "win_rate": m[2], "composite_score": m[3]} for m in best_methods],
    "ranked_strategies": ranked_strategies,
    "all_ranked_methods": ranked_strategies,
    "buy_signals": buys_sorted,
    "sell_signals": sells_sorted,
    "buy_count": len(buys_sorted),
    "sell_count": len(sells_sorted),
    "signal_timeline": sorted(signal_timeline, key=lambda x: x["date"], reverse=True),
}

# Update dashboard
print("\n=== Update Dashboard ===")
afl_data = {
    "best_strategy": best_methods[0][0] if best_methods else "VolumePocket",
    "buy_signals": buys_sorted[:10],
    "sell_signals": sells_sorted[:10],
    "neutral_signals": [],
    "buy_count": len(buys_sorted),
    "sell_count": len(sells_sorted),
    "signal_timeline": sorted(signal_timeline, key=lambda x: x["date"], reverse=True),
}

js_block = '<script>window.AFL_SIGNALS=' + json.dumps(afl_data, ensure_ascii=False, cls=NumpyEncoder) + ';' + \
           'window.AFL_BACKTEST=' + json.dumps(output, ensure_ascii=False, cls=NumpyEncoder) + ';</script>'

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
