import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from src.ssi_client import SSIClient

ssi = SSIClient()
cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_cache")

print("Loading qualified_symbols.json...")
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data", "qualified_symbols.json")) as f:
    qualified_all = json.load(f)

# Filter HOSE/HNX only
symbols = [k for k, v in qualified_all.items() if v in ("HOSE", "HNX")]
symbol_market = {k: v for k, v in qualified_all.items() if v in ("HOSE", "HNX")}
print(f"HOSE+HNX qualified: {len(symbols)}")

# Try to load cached parquet data first
from_cache = {}
for sym in symbols:
    p = os.path.join(cache_dir, f"{sym}.parquet")
    if os.path.exists(p):
        try:
            df = pd.read_parquet(p)
            if "volume" in df.columns and len(df) >= 10:
                from_cache[sym] = df
        except:
            pass
print(f"Found cache for {len(from_cache)} symbols")

# For uncached symbols, fetch 30 days of data
all_data = dict(from_cache)
remaining = [s for s in symbols if s not in all_data]

if remaining:
    print(f"Fetching volume data for {len(remaining)} uncached symbols (about {len(remaining)*1.2:.0f}s)...")
    for i, sym in enumerate(remaining):
        try:
            market = symbol_market.get(sym, "HOSE")
            df = ssi.get_daily_stock_price(sym, market=market)
            if not df.empty:
                all_data[sym] = df
        except:
            pass
        time.sleep(1.1)
        if (i+1) % 20 == 0:
            print(f"  {i+1}/{len(remaining)} done")

# Screen by volume > 1M
qualified = {}
for sym, df in all_data.items():
    if "volume" in df.columns:
        avg_vol = df["volume"].tail(min(30, len(df))).mean()
        if avg_vol >= 1_000_000:
            qualified[sym] = {
                "avg_volume": int(avg_vol),
                "market": symbol_market.get(sym, "HOSE")
            }
        elif avg_vol >= 800_000:
            qualified[sym] = {
                "avg_volume": int(avg_vol),
                "market": symbol_market.get(sym, "HOSE")
            }
            print(f"  {sym}: {avg_vol:,.0f} (just below 1M, still including)")

# Sort by volume descending
sorted_qualified = dict(sorted(qualified.items(), key=lambda x: x[1]["avg_volume"], reverse=True))

print(f"\n=== QUALIFIED SYMBOLS (avg vol > 1M): {len(sorted_qualified)} ===")
for sym, info in list(sorted_qualified.items())[:60]:
    print(f"  {sym} ({info['market']}): {info['avg_volume']:,}")

# Save to file
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qualified_1m_symbols.json")
with open(output_path, "w") as f:
    json.dump(sorted_qualified, f, ensure_ascii=False, indent=2)
print(f"\nSaved to {output_path}")
print(f"Total: {len(sorted_qualified)} symbols")
