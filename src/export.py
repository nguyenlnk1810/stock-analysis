import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from src.ssi_client import SSIClient
from src.ai_agent import AIStockAgent
from src.market_breadth import MarketBreadth
from src.config import config


class DataExporter:
    def __init__(self, output_dir: str = None):
        self.docs_dir = str(Path(__file__).parent.parent / "docs")
        self.output_dir = output_dir or str(Path(self.docs_dir) / "data")
        os.makedirs(self.output_dir, exist_ok=True)
        self.ssi = SSIClient()
        self.agent = AIStockAgent(use_llm=False)

    def export_all(self, symbols: list[str] = None):
        if not symbols:
            symbols = config.DEFAULT_SYMBOLS

        print("=" * 50)
        print("EXPORT DỮ LIỆU PHÂN TÍCH CHỨNG KHOÁN")
        print("=" * 50)

        # 1. Export từng mã cổ phiếu
        stock_data = {}
        for symbol in symbols:
            print(f"  Đang xử lý {symbol}...", end=" ")
            retries = 0
            while retries < 2:
                try:
                    result = self.agent.analyze_symbol(symbol)
                    # Loại bỏ DataFrame không serialize được
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
                    print(f"LỖI: {emsg}")
                    stock_data[symbol] = {"symbol": symbol, "error": emsg}
                    break

        # 2. Export độ rộng thị trường
        print("  Đang phân tích độ rộng thị trường...", end=" ")
        try:
            breadth = MarketBreadth()
            market_data = breadth.analyze(symbols)
            print("OK")
        except Exception as e:
            print(f"LỖI: {e}")
            market_data = {"error": str(e)}

        # 3. Export thông tin index (DailyIndex API)
        print("  Đang lấy dữ liệu VNINDEX...", end=" ")
        idx_data = {}
        try:
            df_idx = self.ssi.get_daily_index("VNINDEX", page_size=100)
            if not df_idx.empty:
                prices_cols = ["date", "close", "volume", "value", "advances", "declines", "no_changes", "ceiling", "floor"]
                idx_data = {
                    "prices": df_idx[prices_cols].to_dict(orient="records"),
                }
                if len(df_idx) >= 1:
                    # Bỏ qua session cuối nếu index=0 (phiên hôm nay chưa đóng cửa)
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
                    idx_data["change_pct"] = round(
                        (current_idx - float(prev["close"])) / float(prev["close"]) * 100, 2
                    )
                    idx_data["advances"] = int(float(last["advances"]))
                    idx_data["declines"] = int(float(last["declines"]))
                    idx_data["no_changes"] = int(float(last["no_changes"]))
                    idx_data["last_date"] = str(last["date"])
                print("OK")
            else:
                print("EMPTY")
        except Exception as e:
            emsg = str(e)
            print(f"LỖI: {emsg}")
        if not idx_data:
            print("  Đang thử DailyOhlc...", end=" ")
            try:
                df_ohlc = self.ssi._get("/api/v2/Market/DailyOhlc", {
                    "symbol": "VNINDEX", "fromDate": (datetime.now() - timedelta(days=29)).strftime("%d/%m/%Y"),
                    "toDate": datetime.now().strftime("%d/%m/%Y"), "pageIndex": 1, "pageSize": 100, "ascending": "true"
                })
                items = df_ohlc.get("data", [])
                if items:
                    recs = []
                    for item in items:
                        recs.append({
                            "date": item.get("TradingDate"),
                            "close": float(item.get("Close", 0)),
                            "open": float(item.get("Open", 0)),
                            "high": float(item.get("High", 0)),
                            "low": float(item.get("Low", 0)),
                            "volume": int(float(item.get("Volume", 0))),
                            "value": float(item.get("Value", 0)),
                        })
                    import pandas as pd
                    df_ohlc = pd.DataFrame(recs)
                    df_ohlc["date"] = pd.to_datetime(df_ohlc["date"], format="%d/%m/%Y")
                    df_ohlc = df_ohlc.sort_values("date").reset_index(drop=True)
                    idx_data = {
                        "prices": df_ohlc[["date", "close", "open", "high", "low", "volume"]].to_dict(orient="records"),
                    }
                    if len(df_ohlc) >= 2:
                        last = df_ohlc.iloc[-1]
                        prev = df_ohlc.iloc[-2]
                        idx_data["current"] = float(last["close"])
                        idx_data["open"] = float(last["open"])
                        idx_data["high"] = float(last["high"])
                        idx_data["low"] = float(last["low"])
                        idx_data["volume"] = int(float(last["volume"]))
                        idx_data["change"] = float(last["close"] - prev["close"])
                        idx_data["change_pct"] = round((last["close"] - prev["close"]) / prev["close"] * 100, 2)
                        idx_data["last_date"] = str(last["date"])
                    print("OK")
                else:
                    print("EMPTY")
            except Exception as e2:
                print(f"LỖI: {e2}")

        # Cập nhật độ rộng thị trường từ VNINDEX thực tế
        if idx_data.get("advances"):
            bd_summary = market_data.get("summary", {})
            bd_summary["advancing"] = idx_data["advances"]
            bd_summary["declining"] = idx_data["declines"]
            bd_summary["unchanged"] = idx_data.get("no_changes", 0)
            bd_summary["total"] = idx_data["advances"] + idx_data["declines"] + idx_data.get("no_changes", 0)
            market_data["summary"] = bd_summary

        # 4. Tạo dữ liệu trading_sessions từ VNINDEX
        print("  Đang tạo dữ liệu phiên giao dịch...", end=" ")
        trading_sessions = []
        idx_prices = idx_data.get("prices", [])
        for i in range(len(idx_prices)):
            cur = idx_prices[i]
            prev = idx_prices[i - 1] if i > 0 else cur
            chg = cur.get("close", 0) - prev.get("close", 0)
            chg_pct = round(chg / prev.get("close", 1) * 100, 2) if prev.get("close", 0) else 0
            trading_sessions.append({
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
                "foreign_net": 0,
                "foreign_buy": 0,
                "foreign_sell": 0,
                "proprietary_net": 0,
                "negotiated_value": 0,
            })
        # Bỏ session cuối nếu index=0 (phiên hôm nay chưa đóng cửa)
        if trading_sessions and trading_sessions[-1].get("index", 0) == 0:
            trading_sessions = trading_sessions[:-1]
        trading_sessions = trading_sessions[-30:]
        print(f"{len(trading_sessions)} phiên")

        # 5. Tạo dữ liệu ngành (sectors)
        print("  Đang phân tích nhóm ngành...", end=" ")
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
        sector_map = {}
        for sym, s in stock_data.items():
            industry_code = s.get("industry", "Z") or "Z"
            industry = industry_map.get(industry_code.upper(), f"Ngành {industry_code}")
            tech = s.get("technical", {})
            ind = tech.get("indicators", {})
            price_change = ind.get("price_change_pct_1d", 0) or 0
            volume_ratio = ind.get("volume_ratio", 1) or 1
            foreign_net = ind.get("foreign_net_today", 0) or 0
            if industry not in sector_map:
                sector_map[industry] = {"change": 0, "count": 0, "volume_ratio": 0, "foreign_net": 0, "strength": 0, "momentum": 0}
            sector_map[industry]["change"] += price_change
            sector_map[industry]["count"] += 1
            sector_map[industry]["volume_ratio"] += volume_ratio
            sector_map[industry]["foreign_net"] += foreign_net
            sector_map[industry]["strength"] += tech.get("score", 0) or 0
            sector_map[industry]["momentum"] += ind.get("price_change_pct_20d", 0) or 0
        sectors = []
        for name, v in sector_map.items():
            cnt = v["count"] or 1
            avg_change = round(v["change"] / cnt, 2)
            trend = "Tăng" if avg_change > 0.2 else "Giảm" if avg_change < -0.2 else "Trung tính"
            sectors.append({
                "name": name,
                "change": avg_change,
                "cashflow": round(v["foreign_net"] * 1e9, 2),
                "volume_ratio": round(v["volume_ratio"] / cnt, 2),
                "strength": round(v["strength"] / cnt, 2),
                "momentum": round(v["momentum"] / cnt, 2),
                "trend": trend,
            })
        sectors.sort(key=lambda x: abs(x["cashflow"]), reverse=True)
        print(f"{len(sectors)} ngành")

        # 6. Tạo báo cáo thị trường
        print("  Đang tạo nhận định thị trường...", end=" ")
        bd_summary = market_data.get("summary", {})
        idx_current = idx_data.get("current", 0)
        idx_change_pct = idx_data.get("change_pct", 0)
        adv = bd_summary.get("advancing", 0)
        dec = bd_summary.get("declining", 0)
        breadth_ratio = bd_summary.get("breadth_ratio", 0.5)
        fear_greed = max(1, min(99, int((bd_summary.get("rsi_average", 50) or 50) * 1.2)))
        # Build recommendation
        score = 5  # neutral baseline
        reasons = []
        if idx_change_pct and abs(idx_change_pct) > 0.5:
            if idx_change_pct > 0:
                score += 1
                reasons.append(f"VN-Index tăng {idx_change_pct}%")
            else:
                score -= 1
                reasons.append(f"VN-Index giảm {idx_change_pct}%")
        if breadth_ratio > 0.6:
            score += 1
            reasons.append("Độ rộng thị trường tích cực")
        elif breadth_ratio < 0.4:
            score -= 1
            reasons.append("Độ rộng thị trường tiêu cực")
        rsi_avg = bd_summary.get("rsi_average", 50) or 50
        if rsi_avg > 60:
            score += 1
        elif rsi_avg < 40:
            score -= 1
        if bd_summary.get("high_volume", 0) > 0:
            score += 1
            reasons.append("Thanh khoản cải thiện")
        # Determine action text
        if score >= 8:
            action = "MUA MẠNH"
        elif score >= 6:
            action = "MUA"
        elif score >= 4:
            action = "TÍCH LŨY"
        elif score >= 2:
            action = "TRUNG LẬP"
        elif score >= 0:
            action = "GIẢM TỶ TRỌNG"
        elif score >= -2:
            action = "BÁN"
        else:
            action = "BÁN MẠNH"
        score = max(1, min(10, score))

        # AI report text
        top_sectors = sectors[:3]
        sector_text = ", ".join([f"{s['name']} ({s['change']:+.2f}%)" for s in top_sectors]) if top_sectors else "chưa xác định"
        ai_report = f"""**BÁO CÁO THỊ TRƯỜNG NGÀY {datetime.now().strftime('%d/%m/%Y')}**

**Tóm tắt phiên giao dịch:**
VN-Index đóng cửa ở mức {idx_current:,.0f} điểm, {'tăng' if idx_change_pct >= 0 else 'giảm'} {abs(idx_change_pct):.2f}% so với phiên trước. Thị trường có {adv} mã tăng và {dec} mã giảm, cho thấy {'tâm lý tích cực' if adv > dec else 'áp lực điều chỉnh'}.

**Điểm nổi bật:**
- Chỉ số RSI trung bình thị trường ở mức {rsi_avg:.1f} điểm
- Độ rộng thị trường đạt {breadth_ratio:.0%}
- Chỉ số Fear & Greed: {fear_greed}/100

**Phân tích dòng tiền:**
Nhóm ngành thu hút dòng tiền: {sector_text}.

**Đánh giá kỹ thuật:**
Thị trường đang trong xu hướng {'tích cực' if score >= 5 else 'thận trọng'} với điểm số kỹ thuật {score}/10. {'Khuyến nghị nhà đầu tư có thể xem xét giải ngân từng phần tại các vùng hỗ trợ.' if score >= 5 else 'Nhà đầu tư nên thận trọng, hạn chế mua đuổi và ưu tiên quản trị rủi ro.'}

**Chiến lược đầu tư:**
- {'Tỷ trọng tiền mặt: 20-30%' if score >= 5 else 'Tỷ trọng tiền mặt: 50-70%'}
- {'Ưu tiên các cổ phiếu có nền tảng cơ bản tốt, thanh khoản cao' if score >= 5 else 'Tập trung phòng thủ, giảm đòn bẩy'}
- Cắt lỗ nếu chỉ số vi phạm các ngưỡng hỗ trợ quan trọng

**Dự báo phiên tiếp theo:**
Thị trường {'dự báo tiếp tục duy trì đà tăng' if idx_change_pct >= 0 else 'có thể còn áp lực điều chỉnh trong phiên tới'} với khả năng {'phục hồi' if idx_change_pct < 0 else 'rung lắc'} tại vùng {idx_current * 0.99:,.0f}-{idx_current * 1.01:,.0f} điểm."""

        market_overview = {
            "recommendation": {
                "action": action,
                "score": score,
                "reason": ". ".join(reasons) if reasons else "Thị trường chưa có tín hiệu rõ ràng",
            },
            "fear_greed": fear_greed,
            "rsi_average": rsi_avg,
            "volume_ratio": bd_summary.get("high_volume", 0),
            "total_value": idx_data.get("value", idx_data.get("current", 0) * 1e9) if idx_data.get("value") else (idx_data.get("current", 0) * 1e9 if idx_data.get("current") else 0),
            "total_volume": idx_data.get("volume", 0),
            "negotiated_value": 0,
            "foreign_net": 0,
            "proprietary_net": 0,
            "ai_report": ai_report,
        }
        print("OK")

        # 7. Tổng hợp
        export = {
            "exported_at": datetime.now().isoformat(),
            "market_index": idx_data,
            "market_breadth": market_data,
            "market_overview": market_overview,
            "trading_sessions": trading_sessions,
            "sectors": sectors,
            "foreign": {"sessions": trading_sessions, "top_buy": [], "top_sell": []},
            "proprietary": {"sessions": trading_sessions, "top_buy": [], "top_sell": []},
            "stocks": stock_data,
        }

        json_str = json.dumps(export, ensure_ascii=False, default=str)

        # 5. Ghi file JSON (cho debug)
        json_path = os.path.join(self.output_dir, "analysis.json")
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(json_str)

        # 6. Ghi file JS (cho script tag thông thường)
        js_path = os.path.join(self.output_dir, "data.js")
        with open(js_path, "w", encoding="utf-8") as f:
            f.write("window._STOCK_DATA = " + json_str + ";")

        # 7. Ghi index.html với data nhúng trực tiếp
        html_path = os.path.join(self.docs_dir, "index.html")
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()

            inline_tag = f'<script>window._STOCK_DATA = {json_str};</script>'

            # Trường hợp 1: Đã có inline data → thay thế
            tag_start = '<script>'
            data_var = 'window._STOCK_DATA'
            si = html.find(data_var)
            if si >= 0:
                # Tìm <script> đứng trước data_var
                si_open = html.rfind(tag_start, 0, si)
                if si_open >= 0:
                    end = html.find('</script>', si)
                    old = html[si_open:end + 9]
                    html = html.replace(old, inline_tag)
                else:
                    html = html.replace(
                        '<script src="data/data.js"></script>',
                        inline_tag,
                    )
            else:
                # Trường hợp 2: Chưa có inline data → thay thế <script src="data/data.js">
                html = html.replace(
                    '<script src="data/data.js"></script>',
                    inline_tag,
                )

            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"   {html_path} (data inline)")

        print(f"\n✅ Hoàn tất! Dữ liệu đã được lưu tại:")
        print(f"   {json_path}")
        print(f"   {js_path}")
        print(f"   {sum(1 for s in stock_data if 'error' not in stock_data[s])}/{len(symbols)} mã thành công")

        return export


def main():
    exporter = DataExporter()
    exporter.export_all()


if __name__ == "__main__":
    main()
