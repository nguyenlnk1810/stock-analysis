import json
import os
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.ssi_client import SSIClient
from src.ai_agent import AIStockAgent
from src.market_sentiment import GreedFearIndex
from src.signal_scoring import SignalScorer, compute_smart_money_patterns, compute_position_score
from src.config import config


class DataExporter:
    def __init__(self, output_dir: str = None):
        self.docs_dir = str(Path(__file__).parent.parent / "docs")
        self.output_dir = output_dir or str(Path(self.docs_dir) / "data")
        os.makedirs(self.output_dir, exist_ok=True)
        self.ssi = SSIClient()
        self.agent = AIStockAgent(use_llm=False)

    def _get_all_stock_symbols(self, markets: list = None) -> dict:
        if markets is None:
            markets = ["HOSE", "HNX", "UPCOM"]
        symbol_market = {}
        for market in markets:
            try:
                df = self.ssi.get_securities_list(market)
                if not df.empty and "Symbol" in df.columns:
                    syms = df["Symbol"].tolist()
                    stock_syms = [s for s in syms if len(s) == 3 and s.isalpha() and s.isupper()]
                    for s in stock_syms:
                        symbol_market[s] = market
                    print(f"  {market}: {len(stock_syms)} stocks")
            except Exception as e:
                print(f"  {market}: LỖI {e}")
            time.sleep(1.5)
        return symbol_market

    def _screen_by_liquidity(self, symbol_market: dict, min_volume: float = 500000, cache_file: str = None) -> dict:
        cache_path = os.path.join(self.output_dir, "qualified_symbols.json") if cache_file is None else cache_file
        if cache_path and os.path.exists(cache_path):
            try:
                cached = json.load(open(cache_path, "r"))
                if isinstance(cached, dict):
                    print(f"  Dùng danh sách đã lưu ({len(cached)} mã)")
                    return cached
            except Exception:
                pass
        items = list(symbol_market.items())
        total = len(items)
        qualified = {}
        print(f"\n--- SÀNG LỌC THANH KHOẢN ({total} mã, min {min_volume:,.0f} CP/phiên) ---")
        start_time = time.time()
        for i, (symbol, market) in enumerate(items, 1):
            elapsed = time.time() - start_time
            eta = (elapsed / i) * (total - i) if i > 0 else 0
            try:
                df = self.ssi.get_daily_stock_price(symbol, page_size=15, market=market)
                if not df.empty:
                    avg_vol = df["volume"].tail(min(20, len(df))).mean()
                    if avg_vol >= min_volume:
                        qualified[symbol] = market
            except Exception:
                pass
            if i % 50 == 0 or i == total:
                pct = i / total * 100
                print(f"  [{i}/{total}] {pct:.0f}% | {len(qualified)} qualified | ETA: {eta/60:.0f}ph")
        print(f"  ✅ Sàng lọc xong: {len(qualified)}/{total} mã ({time.time()-start_time:.0f}s)")
        if cache_path:
            json.dump(qualified, open(cache_path, "w"), ensure_ascii=False)
            print(f"  Đã lưu danh sách: {cache_path}")
        return qualified

    def _fetch_vnindex(self):
        print("  VNINDEX...", end=" ")
        idx_data = {}
        try:
            df_idx = self.ssi.get_daily_index("VNINDEX", page_size=100)
            if not df_idx.empty:
                prices_cols = ["date", "close", "volume", "value", "advances", "declines", "no_changes", "ceiling", "floor"]
                idx_data = {"prices": df_idx[prices_cols].to_dict(orient="records")}
                if len(df_idx) >= 1:
                    last = df_idx.iloc[-1]
                    current_idx = float(last["close"])
                    if current_idx == 0 and len(df_idx) >= 2:
                        last = df_idx.iloc[-2]
                        current_idx = float(last["close"])
                        prev = df_idx.iloc[-3] if len(df_idx) >= 3 else last
                    else:
                        prev = df_idx.iloc[-2] if len(df_idx) >= 2 else last
                    idx_data["current"] = current_idx
                    idx_data["volume"] = int(float(last["volume"]))
                    idx_data["value"] = float(last["value"])
                    idx_data["change"] = float(current_idx - float(prev["close"]))
                    idx_data["change_pct"] = round((current_idx - float(prev["close"])) / float(prev["close"]) * 100, 2)
                    idx_data["advances"] = int(float(last["advances"]))
                    idx_data["declines"] = int(float(last["declines"]))
                    idx_data["no_changes"] = int(float(last["no_changes"]))
                    idx_data["last_date"] = str(last["date"])
                print(f"{current_idx:,.2f} (A:{idx_data.get('advances')} D:{idx_data.get('declines')})")
            else:
                print("EMPTY")
        except Exception as e:
            print(f"LỖI: {e}")
        return idx_data

    def _build_breadth_from_vnindex(self, idx_data):
        market_data = {"summary": {"total": 0, "advancing": 0, "declining": 0, "unchanged": 0}}
        if idx_data.get("advances"):
            adv = idx_data["advances"]
            dec = idx_data["declines"]
            unc = idx_data.get("no_changes", 0)
            total = adv + dec + unc
            market_data["summary"] = {
                "total": total,
                "advancing": adv,
                "declining": dec,
                "unchanged": unc,
                "breadth_ratio": round(adv / max(dec, 1), 2),
                "breadth_pct": round(adv / max(total, 1) * 100, 2),
            }
        return market_data

    def _build_trading_sessions(self, idx_data):
        sessions = []
        prices = idx_data.get("prices", [])
        for i in range(len(prices)):
            cur = prices[i]
            prev = prices[i - 1] if i > 0 else cur
            chg = cur.get("close", 0) - prev.get("close", 0)
            chg_pct = round(chg / max(prev.get("close", 1), 1) * 100, 2) if prev.get("close", 0) else 0
            sessions.append({
                "date": cur.get("date", ""),
                "index": cur.get("close", 0),
                "change": round(chg, 2),
                "change_pct": chg_pct,
                "volume": cur.get("volume", 0),
                "value": cur.get("value", cur.get("volume", 0) * cur.get("close", 0) * 10),
                "open": cur.get("open", 0),
                "high": cur.get("high", 0),
                "low": cur.get("low", 0),
                "advancing": cur.get("advances"),
                "declining": cur.get("declines"),
                "unchanged": cur.get("no_changes"),
                "ceiling": cur.get("ceiling"),
                "floor": cur.get("floor"),
                "foreign_net": 0, "foreign_buy": 0, "foreign_sell": 0,
                "proprietary_net": 0, "negotiated_value": 0,
            })
        if sessions and sessions[-1].get("index", 0) == 0:
            sessions = sessions[:-1]
        return sessions[-30:]

    def _build_sectors(self, stock_data):
        industry_map = {
            "S": "Chứng khoán", "B": "Ngân hàng", "R": "Bất động sản", "T": "Công nghệ",
            "I": "Bảo hiểm", "U": "Dịch vụ tiện ích", "C": "Vật liệu xây dựng",
            "H": "Hóa chất", "O": "Dầu khí", "F": "Thực phẩm & Đồ uống",
            "J": "Hàng tiêu dùng", "M": "Công nghiệp", "P": "Cảng & Vận tải",
            "D": "Dược phẩm", "E": "Điện & Năng lượng", "W": "Nước & Môi trường",
            "A": "Nông nghiệp", "G": "Bán lẻ", "K": "Khu công nghiệp",
            "L": "Logistics", "N": "Nguyên vật liệu", "Q": "Quỹ đầu tư",
            "V": "Dịch vụ", "Y": "Công nghệ y tế", "Z": "Khác",
        }
        sm = {}
        for sym, s in stock_data.items():
            ic = s.get("industry", "Z") or "Z"
            ind = industry_map.get(ic.upper(), f"Ngành {ic}")
            tech = s.get("technical", {})
            i = tech.get("indicators", {})
            pc = i.get("price_change_pct_1d", 0) or 0
            vr = i.get("volume_ratio", 1) or 1
            fn = i.get("foreign_net_today", 0) or 0
            if ind not in sm:
                sm[ind] = {"change": 0, "count": 0, "volume_ratio": 0, "foreign_net": 0, "strength": 0, "momentum": 0}
            sm[ind]["change"] += pc
            sm[ind]["count"] += 1
            sm[ind]["volume_ratio"] += vr
            sm[ind]["foreign_net"] += fn
            sm[ind]["strength"] += tech.get("score", 0) or 0
            sm[ind]["momentum"] += i.get("price_change_pct_20d", 0) or 0
        sectors = []
        for name, v in sm.items():
            cnt = v["count"] or 1
            avg_chg = round(v["change"] / cnt, 2)
            sectors.append({
                "name": name, "count": cnt, "change": avg_chg,
                "cashflow": round(v["foreign_net"] * 1e9, 2),
                "volume_ratio": round(v["volume_ratio"] / cnt, 2),
                "strength": round(v["strength"] / cnt, 2),
                "momentum": round(v["momentum"] / cnt, 2),
                "trend": "Tăng" if avg_chg > 0.2 else "Giảm" if avg_chg < -0.2 else "Trung tính",
            })
        sectors.sort(key=lambda x: abs(x["cashflow"]), reverse=True)
        return sectors

    def _build_market_overview(self, idx_data, market_data, sectors):
        bd = market_data.get("summary", {})
        cur = idx_data.get("current", 0)
        chg_pct = idx_data.get("change_pct", 0)
        adv = bd.get("advancing", 0)
        dec = bd.get("declining", 0)

        gf = GreedFearIndex()
        sentiment = gf.analyze(idx_data.get("prices", []))
        fear_greed = int(sentiment["index"])

        score = 5
        reasons = []
        if chg_pct and abs(chg_pct) > 0.5:
            score += 1 if chg_pct > 0 else -1
            reasons.append(f"VN-Index {'tăng' if chg_pct > 0 else 'giảm'} {abs(chg_pct)}%")
        if adv > dec:
            score += 1
            reasons.append("Độ rộng tích cực")
        elif dec > adv:
            score -= 1
            reasons.append("Độ rộng tiêu cực")
        score = max(1, min(10, score))
        if score >= 8: action = "MUA MẠNH"
        elif score >= 6: action = "MUA"
        elif score >= 4: action = "TÍCH LŨY"
        elif score >= 2: action = "TRUNG LẬP"
        elif score >= 0: action = "GIẢM TỶ TRỌNG"
        elif score >= -2: action = "BÁN"
        else: action = "BÁN MẠNH"

        top_sec = sectors[:3]
        sec_text = ", ".join([f"{s['name']} ({s['change']:+.2f}%)" for s in top_sec]) if top_sec else "chưa xác định"

        sentiment_label = sentiment.get("label", "TRUNG TÍNH")
        comp = sentiment.get("components", {})
        md = sentiment.get("market_data", {})

        ai_report = f"""**BÁO CÁO THỊ TRƯỜNG NGÀY {datetime.now().strftime('%d/%m/%Y')}**

**Chỉ số Tâm lý Thị trường: {sentiment_label} ({fear_greed}/100)**
- RSI Market: {md.get('rsi_value', 'N/A')} điểm
- Biến động: {md.get('volatility_pct', 'N/A')}% (năm)
- Động lượng 20D: {md.get('momentum_pct', 'N/A')}%
- Breadth 5D: {md.get('breadth_ratio', 'N/A')}

**Tóm tắt phiên giao dịch:**
VN-Index đóng cửa ở mức {cur:,.0f} điểm, {'tăng' if chg_pct >= 0 else 'giảm'} {abs(chg_pct):.2f}% so với phiên trước. Thị trường có {adv} mã tăng và {dec} mã giảm.

**Phân tích dòng tiền:**
Nhóm ngành thu hút dòng tiền: {sec_text}.

**Chiến lược đầu tư:**
- {'Tỷ trọng tiền mặt: 20-30%' if score >= 5 else 'Tỷ trọng tiền mặt: 50-70%'}
- Cắt lỗ nếu chỉ số vi phạm các ngưỡng hỗ trợ quan trọng"""

        return {
            "recommendation": {"action": action, "score": score, "reason": ". ".join(reasons) if reasons else "Thị trường chưa có tín hiệu rõ ràng"},
            "fear_greed": fear_greed,
            "fear_greed_label": sentiment_label,
            "fear_greed_level": sentiment.get("level", "neutral"),
            "sentiment_components": comp,
            "sentiment_market_data": md,
            "rsi_average": md.get("rsi_value", 50),
            "volume_ratio": 0,
            "total_value": idx_data.get("value", cur * 1e9) if idx_data.get("value") else (cur * 1e9 if cur else 0),
            "total_volume": idx_data.get("volume", 0),
            "negotiated_value": 0, "foreign_net": 0, "proprietary_net": 0,
            "ai_report": ai_report,
        }

    def _write_output(self, export):
        json_str = json.dumps(export, ensure_ascii=False, default=str)
        json_path = os.path.join(self.output_dir, "analysis.json")
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        js_path = os.path.join(self.output_dir, "data.js")
        with open(js_path, "w", encoding="utf-8") as f:
            f.write("window._STOCK_DATA = " + json_str + ";")
        html_path = os.path.join(self.docs_dir, "index.html")
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            inline_tag = f'<script>window._STOCK_DATA = {json_str};</script>'
            si = html.find("window._STOCK_DATA")
            if si >= 0:
                si_open = html.rfind("<script>", 0, si)
                if si_open >= 0:
                    end = html.find("</script>", si)
                    html = html.replace(html[si_open:end + 9], inline_tag)
                else:
                    html = html.replace('<script src="data/data.js"></script>', inline_tag)
            else:
                html = html.replace('<script src="data/data.js"></script>', inline_tag)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"   {html_path}")
        print(f"\n✅ Hoàn tất! {json_path}, {js_path}")
        return export

    def _build_rankings(self, stock_data: dict) -> dict:
        rankings = {
            "top_20_manh_nhat": [],
            "top_20_dong_tien": [],
            "top_10_tin_hieu_mua": [],
            "top_10_suy_yeu": [],
            "canh_bao": [],
        }
        scored_stocks = []
        money_flow_stocks = []
        buy_signals = []
        weak_stocks = []
        warnings = []

        for sym, s in stock_data.items():
            if s.get("error"):
                continue
            tech = s.get("technical", {})
            scoring = tech.get("signal_scoring", {})
            ind = tech.get("indicators", {})
            sm = tech.get("smart_money", {})

            tong_diem = scoring.get("tong_diem", 0)
            xep_loai = scoring.get("xep_loai", "LOAI")
            price = ind.get("current_price", 0)
            change = ind.get("price_change_pct_1d", 0)
            vol_ratio = ind.get("volume_ratio", 0)
            rvol = float(ind.get("volume_current", 0)) / max(float(ind.get("volume_avg_20", 1)), 1)
            rsi = ind.get("rsi_14", 0)
            macd_hist = ind.get("macd_histogram_standard", 0)
            mfi = ind.get("mfi", 50)
            obv_trend = ind.get("obv_trend", "")
            cmf = ind.get("cmf", 0)
            bos = sm.get("bos", "none")
            fvg = sm.get("fvg_signal", "none")
            choch = sm.get("choch", "none")
            supertrend_sig = sm.get("supertrend_signal", "neutral")

            # Money flow score
            mf_score = 0
            if vol_ratio > 1.5: mf_score += 5
            elif vol_ratio > 1.0: mf_score += 2
            if mfi and mfi > 60: mf_score += 5
            elif mfi and mfi > 50: mf_score += 2
            if obv_trend == "tăng": mf_score += 4
            if cmf and cmf > 0: mf_score += 4

            item = {
                "symbol": sym,
                "score": tong_diem,
                "grade": xep_loai,
                "price": price,
                "change_pct": change,
                "rsi": rsi,
                "vol_ratio": round(rvol, 2),
                "mfi": mfi,
                "macd_hist": macd_hist,
                "bos": bos,
                "fvg": fvg,
                "choch": choch,
                "supertrend": supertrend_sig,
                "money_flow_score": mf_score,
            }

            scored_stocks.append(item)
            money_flow_stocks.append(item)

            # Buy signals
            is_buy = False
            buy_reasons = []
            if tong_diem >= 70:
                is_buy = True
                buy_reasons.append(f"Tổng điểm {tong_diem} ({xep_loai})")
            if supertrend_sig == "uptrend" and rvol > 1.2:
                is_buy = True
                buy_reasons.append("SuperTrend tăng + Volume")
            if "bullish" in str(bos) and rvol > 1.3:
                is_buy = True
                buy_reasons.append("BOS tăng + Volume")
            if fvg == "bullish" and rvol > 1.3:
                is_buy = True
                buy_reasons.append("FVG tăng + Volume")
            if macd_hist and macd_hist > 0 and vol_ratio > 1.3 and rsi and rsi > 50:
                is_buy = True
                buy_reasons.append("MACD+RSI+Volume")
            if choch == "CHOCH tang" and rvol > 1.5:
                is_buy = True
                buy_reasons.append("CHOCH tăng mạnh")
            if is_buy:
                buy_signals.append({**item, "reasons": buy_reasons})

            # Weak stocks
            is_weak = False
            weak_reasons = []
            if tong_diem < 50:
                is_weak = True
                weak_reasons.append(f"Điểm thấp ({tong_diem})")
            if "downtrend" in str(supertrend_sig):
                is_weak = True
                weak_reasons.append("SuperTrend giảm")
            if "giam" in str(bos):
                is_weak = True
                weak_reasons.append("BOS giảm")
            if rsi and rsi < 40:
                is_weak = True
                weak_reasons.append(f"RSI < 40 ({rsi:.0f})")
            if macd_hist and macd_hist < 0:
                is_weak = True
                weak_reasons.append("MACD Histogram âm")
            if is_weak:
                weak_stocks.append({**item, "reasons": weak_reasons})

            # Warnings
            warnings_list = scoring.get("mien_diem", [])
            if warnings_list:
                warn_item = {**item, "warnings": [w["ten"] for w in warnings_list],
                             "penalty": sum(w["diem"] for w in warnings_list)}
                warnings.append(warn_item)

        scored_stocks.sort(key=lambda x: x["score"], reverse=True)
        money_flow_stocks.sort(key=lambda x: x["money_flow_score"], reverse=True)
        buy_signals.sort(key=lambda x: x["score"], reverse=True)
        weak_stocks.sort(key=lambda x: x["score"])

        rankings["top_20_manh_nhat"] = scored_stocks[:20]
        rankings["top_20_dong_tien"] = money_flow_stocks[:20]
        rankings["top_10_tin_hieu_mua"] = buy_signals[:10]
        rankings["top_10_suy_yeu"] = weak_stocks[:10]
        rankings["canh_bao"] = warnings[:20]

        # Summary stats
        if scored_stocks:
            avg_score = sum(s["score"] for s in scored_stocks if s["score"] > 0) / max(
                sum(1 for s in scored_stocks if s["score"] > 0), 1)
            rankings["thong_ke"] = {
                "tong_mau_phan_tich": len(scored_stocks),
                "diem_trung_binh": round(avg_score, 1),
                "so_manh": sum(1 for s in scored_stocks if s["score"] >= 70),
                "so_trung_binh": sum(1 for s in scored_stocks if 50 <= s["score"] < 70),
                "so_yeu": sum(1 for s in scored_stocks if s["score"] < 50),
                "so_co_tin_hieu_mua": len(buy_signals),
                "so_canh_bao": len(warnings),
            }
        return rankings

    # Public methods
    def export_all(self, symbols: list[str] = None):
        print("=" * 50)
        print("EXPORT DỮ LIỆU PHÂN TÍCH CHỨNG KHOÁN")
        print("=" * 50)
        symbol_market = {}
        if not symbols:
            print("\nĐang lấy danh sách cổ phiếu từ các sàn...")
            symbol_market = self._get_all_stock_symbols()
            print(f"Tổng số mã: {len(symbol_market)}")
        else:
            symbol_market = {s: "HOSE" for s in symbols}
        qualified_syms = self._screen_by_liquidity(symbol_market)
        print(f"\nPhân tích {len(qualified_syms)} mã có thanh khoản ≥ 500k CP/phiên (TB 20 phiên)")
        print("\n--- VNINDEX ---")
        idx_data = self._fetch_vnindex()
        market_data = self._build_breadth_from_vnindex(idx_data)
        print("\n--- CỔ PHIẾU ---")
        stock_data = {}
        total = len(qualified_syms)
        start_time = time.time()
        for idx, symbol in enumerate(qualified_syms, 1):
            market = qualified_syms.get(symbol, "HOSE")
            elapsed = time.time() - start_time
            eta = (elapsed / idx) * (total - idx) if idx > 0 else 0
            print(f"  [{idx}/{total}] {symbol} ({market})...", end=" ")
            sys.stdout.flush()
            retries = 0
            while retries < 2:
                try:
                    result = self.agent.analyze_symbol(symbol, skip_news=True, market=market)
                    result.pop("price_data", None)
                    stock_data[symbol] = result
                    print("OK")
                    break
                except Exception as e:
                    emsg = str(e)
                    if "quota exceeded" in emsg.lower() and retries < 1:
                        print("RL", end="->")
                        time.sleep(3)
                        retries += 1
                        continue
                    print(f"LỖI")
                    stock_data[symbol] = {"symbol": symbol, "error": str(e)[:100]}
                    break
        print(f"\n  Done: {sum(1 for s in stock_data if 'error' not in stock_data[s])}/{total} mã ({time.time()-start_time:.0f}s)")
        print("\n--- PHÂN TÍCH THỊ TRƯỜNG ---")
        print("  Trading sessions...", end=" ")
        trading_sessions = self._build_trading_sessions(idx_data)
        print(f"{len(trading_sessions)} phiên")
        print("  Sectors...", end=" ")
        sectors = self._build_sectors(stock_data)
        print(f"{len(sectors)} ngành")
        print("  Market overview...", end=" ")
        market_overview = self._build_market_overview(idx_data, market_data, sectors)
        print("OK")
        print("\n--- XẾP HẠNG TÍN HIỆU ---")
        rankings = self._build_rankings(stock_data)
        print(f"  Top 20 mạnh nhất, Top 20 dòng tiền, Top 10 tín hiệu mua, {len(rankings.get('canh_bao', []))} cảnh báo")
        print("\n--- GHI FILE ---")
        export = {
            "exported_at": datetime.now().isoformat(),
            "market_index": idx_data, "market_breadth": market_data,
            "market_overview": market_overview,
            "market_sentiment": {
                "index": market_overview.get("fear_greed", 50),
                "label": market_overview.get("fear_greed_label", "TRUNG TÍNH"),
                "level": market_overview.get("fear_greed_level", "neutral"),
                "components": market_overview.get("sentiment_components", {}),
                "market_data": market_overview.get("sentiment_market_data", {}),
            },
            "trading_sessions": trading_sessions, "sectors": sectors,
            "foreign": {"sessions": trading_sessions, "top_buy": [], "top_sell": []},
            "proprietary": {"sessions": trading_sessions, "top_buy": [], "top_sell": []},
            "rankings": rankings,
            "stocks": stock_data,
        }
        return self._write_output(export)


def main():
    exporter = DataExporter()
    exporter.export_all()


if __name__ == "__main__":
    main()
