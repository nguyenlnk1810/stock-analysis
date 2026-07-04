import json
import os
from datetime import datetime
from pathlib import Path

from src.ssi_client import SSIClient
from src.ai_agent import AIStockAgent
from src.market_breadth import MarketBreadth
from src.config import config


class DataExporter:
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or str(Path(__file__).parent.parent / "docs" / "data")
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
            try:
                result = self.agent.analyze_symbol(symbol)
                # Loại bỏ DataFrame không serialize được
                result.pop("price_data", None)
                stock_data[symbol] = result
                print("OK")
            except Exception as e:
                print(f"LỖI: {e}")
                stock_data[symbol] = {"symbol": symbol, "error": str(e)}

        # 2. Export độ rộng thị trường
        print("  Đang phân tích độ rộng thị trường...", end=" ")
        try:
            breadth = MarketBreadth()
            market_data = breadth.analyze(symbols)
            print("OK")
        except Exception as e:
            print(f"LỖI: {e}")
            market_data = {"error": str(e)}

        # 3. Export thông tin index
        print("  Đang lấy dữ liệu VNINDEX...", end=" ")
        try:
            df_idx = self.ssi.get_daily_stock_price("VNINDEX", page_size=100)
            idx_data = {
                "prices": df_idx[["date", "close", "open", "high", "low", "volume"]]
                .to_dict(orient="records") if not df_idx.empty else [],
            }
            if "close" in df_idx.columns and len(df_idx) >= 2:
                idx_data["current"] = float(df_idx["close"].iloc[-1])
                idx_data["change"] = float(df_idx["close"].iloc[-1] - df_idx["close"].iloc[-2])
                idx_data["change_pct"] = round(
                    (df_idx["close"].iloc[-1] - df_idx["close"].iloc[-2]) / df_idx["close"].iloc[-2] * 100, 2
                )
            print("OK")
        except Exception as e:
            print(f"LỖI: {e}")
            idx_data = {}

        # 4. Tổng hợp
        export = {
            "exported_at": datetime.now().isoformat(),
            "market_index": idx_data,
            "market_breadth": market_data,
            "stocks": stock_data,
        }

        # 5. Ghi file
        filepath = os.path.join(self.output_dir, "analysis.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2, default=str)

        print(f"\n✅ Hoàn tất! Dữ liệu đã được lưu tại:")
        print(f"   {filepath}")
        print(f"   {sum(1 for s in stock_data if 'error' not in stock_data[s])}/{len(symbols)} mã thành công")

        return export


def main():
    exporter = DataExporter()
    exporter.export_all()


if __name__ == "__main__":
    main()
