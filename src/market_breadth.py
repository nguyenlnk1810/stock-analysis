import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.ssi_client import SSIClient
from src.technical_analysis import TechnicalAnalyzer


class MarketBreadth:
    def __init__(self):
        self.ssi = SSIClient()

    def analyze(self, symbols: list[str] = None) -> dict:
        if not symbols:
            try:
                df = self.ssi.get_index_components("VNINDEX")
                if not df.empty and "Symbol" in df.columns:
                    symbols = df["Symbol"].tolist()[:50]
                else:
                    symbols = ["VCB", "SSI", "FPT", "HPG", "MWG", "VNM", "VIC",
                               "BID", "CTG", "GAS", "PLX", "SAB", "VRE", "VHM",
                               "MSN", "MBB", "TCB", "ACB", "VPB", "TPB"]
            except Exception:
                symbols = ["VCB", "SSI", "FPT", "HPG", "MWG", "VNM", "VIC"]

        advancing = 0
        declining = 0
        unchanged = 0
        above_ma20 = 0
        above_ma50 = 0
        rsi_oversold = 0
        rsi_overbought = 0
        high_volume = 0
        buy_signals = 0
        sell_signals = 0
        data_rows = []

        for symbol in symbols:
            try:
                df = self.ssi.get_daily_stock_price(symbol, page_size=60)
                if df.empty or len(df) < 2:
                    continue

                analyzer = TechnicalAnalyzer(df)
                signal = analyzer.get_technical_signal()
                ind = signal["indicators"]

                change = ind.get("price_change_pct_1d", 0)
                if change > 0:
                    advancing += 1
                elif change < 0:
                    declining += 1
                else:
                    unchanged += 1

                price = ind.get("current_price", 0)
                ma20 = ind.get("ma_20", 0)
                ma50 = ind.get("ma_50", 0)

                if price > ma20:
                    above_ma20 += 1
                if price > ma50:
                    above_ma50 += 1

                rsi = ind.get("rsi_14", 50)
                if rsi < 30:
                    rsi_oversold += 1
                elif rsi > 70:
                    rsi_overbought += 1

                vol_ratio = ind.get("volume_ratio", 1)
                if vol_ratio > 1.5:
                    high_volume += 1

                action = signal.get("action", "")
                if action in ["MUA", "MUA MẠNH", "TÍCH LŨY"]:
                    buy_signals += 1
                elif action in ["BÁN", "BÁN MẠNH", "GIẢM TỶ TRỌNG"]:
                    sell_signals += 1

                data_rows.append({
                    "symbol": symbol,
                    "price": price,
                    "change": change,
                    "rsi": rsi,
                    "action": action,
                    "score": signal.get("score", 0),
                    "volume_ratio": vol_ratio,
                    "ma20_pct": ind.get("price_vs_ma20_pct", 0),
                    "ma50_pct": ind.get("price_vs_ma50_pct", 0),
                })

            except Exception:
                continue

        total = advancing + declining + unchanged
        if total == 0:
            total = 1

        return {
            "summary": {
                "total": total,
                "advancing": advancing,
                "declining": declining,
                "unchanged": unchanged,
                "breadth_ratio": round(advancing / max(declining, 1), 2),
                "breadth_pct": round(advancing / total * 100, 2),
                "above_ma20": above_ma20,
                "above_ma20_pct": round(above_ma20 / total * 100, 2),
                "above_ma50": above_ma50,
                "above_ma50_pct": round(above_ma50 / total * 100, 2),
                "rsi_oversold": rsi_oversold,
                "rsi_overbought": rsi_overbought,
                "high_volume": high_volume,
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
                "net_signal": buy_signals - sell_signals,
            },
            "stocks": sorted(data_rows, key=lambda x: abs(x.get("score", 0)), reverse=True),
            "analyzed_at": datetime.now().isoformat(),
        }
