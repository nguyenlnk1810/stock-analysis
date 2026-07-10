import json
from typing import Optional, List
from datetime import datetime
from src.config import config
from src.ssi_client import SSIClient
from src.technical_analysis import TechnicalAnalyzer
from src.signal_scoring import SignalScorer, compute_smart_money_patterns, compute_position_score
from src.news_fetcher import NewsFetcher


class AIStockAgent:
    def __init__(self, use_llm: bool = True):
        self.ssi = SSIClient()
        self.news = NewsFetcher()
        self.use_llm = use_llm
        self.llm_client = self._init_llm() if use_llm else None

    def _init_llm(self):
        if config.LLM_PROVIDER == "openai":
            from openai import OpenAI
            return OpenAI(api_key=config.OPENAI_API_KEY)
        elif config.LLM_PROVIDER == "ollama":
            from openai import OpenAI as OllamaClient
            return OllamaClient(
                base_url=config.OLLAMA_BASE_URL + "/v1",
                api_key="ollama",
            )
        return None

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        model = (
            "gpt-4"
            if config.LLM_PROVIDER == "openai"
            else config.OLLAMA_MODEL
        )
        try:
            resp = self.llm_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"[Lỗi gọi LLM: {e}]"

    def analyze_symbol(self, symbol: str, skip_news: bool = False, market: str = "HOSE") -> dict:
        symbol = symbol.upper()
        # 1. Lấy dữ liệu giá lịch sử
        df = self.ssi.get_daily_stock_price(symbol, page_size=200, market=market)

        # 2. Phân tích kỹ thuật
        tech_signal = {}
        smart_money = {}
        signal_scoring = {}
        position_score = {}
        if not df.empty:
            analyzer = TechnicalAnalyzer(df)
            tech_signal = analyzer.get_technical_signal()
            indicators = tech_signal.get("indicators", {})

            # Smart Money Patterns
            smart_money = compute_smart_money_patterns(df)
            indicators.update(smart_money)

            # Position Score
            position_score = compute_position_score(indicators)
            indicators.update(position_score)

            # 100-point Signal Scoring
            scorer = SignalScorer(df, indicators, symbol=symbol, market=market)
            signal_scoring = scorer.compute_all()

            # Add new signals to existing signal list
            for sig in signal_scoring.get("tin_hieu", []):
                existing = tech_signal.get("signals", [])
                if sig not in existing:
                    existing.append(sig)

            tech_signal["signal_scoring"] = signal_scoring
            tech_signal["smart_money"] = smart_money
            tech_signal["position_score"] = position_score

        # 3. Thông tin doanh nghiệp
        company_info = self.ssi.get_company_info(symbol)
        if not company_info:
            company_info = {"symbol": symbol, "companyName": symbol}

        # 4. Tin tức (skip khi bulk)
        news = []
        market_news = []
        if not skip_news:
            try:
                news = self.news.fetch_all_news(symbol)
                market_news = self.news.fetch_market_news()
            except Exception:
                pass

        # 5. AI Analysis
        analysis = self._analyze_with_ai(
            symbol=symbol,
            company_info=company_info,
            tech_signal=tech_signal,
            news=news,
            market_news=market_news,
            df=df,
        )

        return {
            "symbol": symbol,
            "company_name": company_info.get("companyName", company_info.get("companyName", "")),
            "exchange": company_info.get("exchange", ""),
            "industry": company_info.get("industry", ""),
            "price_data": df,
            "technical": tech_signal,
            "news": news,
            "analysis": analysis,
            "analyzed_at": datetime.now().isoformat(),
        }

    def _analyze_with_ai(
        self,
        symbol: str,
        company_info: dict,
        tech_signal: dict,
        news: list,
        market_news: list,
        df,
    ) -> str:
        # Build context
        indicators = tech_signal.get("indicators", {})
        tech_action = tech_signal.get("action", "N/A")
        tech_signals = tech_signal.get("signals", [])

        latest_price = indicators.get("current_price", 0)
        price_change_1d = indicators.get("price_change_pct_1d", 0)
        price_change_5d = indicators.get("price_change_pct_5d", 0)
        price_change_20d = indicators.get("price_change_pct_20d", 0)

        company_name = company_info.get("companyName", symbol)
        industry = company_info.get("industry", "N/A")
        exchange = company_info.get("exchange", "N/A")

        # News summary
        news_summary = "\n".join(
            [f"- [{n.get('source','')}] {n['title']}" for n in news[:5]]
        ) or "Không có tin tức mới."

        # Market context
        if not df.empty and len(df) >= 20:
            latest_volume = int(df["volume"].iloc[-1])
            avg_volume = int(df["volume"].tail(20).mean())
        else:
            latest_volume = 0
            avg_volume = 0

        user_prompt = f"""
Phân tích cổ phiếu {symbol} - {company_name}

## THÔNG TIN DOANH NGHIỆP
- Ngành: {industry}
- Sàn: {exchange}

## DỮ LIỆU THỊ TRƯỜNG
- Giá hiện tại: {latest_price:,}
- Thay đổi 1 ngày: {price_change_1d}%
- Thay đổi 5 ngày: {price_change_5d}%
- Thay đổi 20 ngày: {price_change_20d}%
- Khối lượng hôm nay: {latest_volume:,}
- KL trung bình 20 phiên: {avg_volume:,}

## CHỈ BÁO KỸ THUẬT
- RSI(14): {indicators.get('rsi_14', 'N/A')} ({indicators.get('rsi_signal', 'N/A')})
- MACD: {indicators.get('macd', 'N/A')}
- MACD Signal: {indicators.get('macd_signal', 'N/A')}
- MACD Histogram: {indicators.get('macd_histogram', 'N/A')}
- Bollinger %B: {indicators.get('bb_pct_b', 'N/A')}
- Bollinger: {indicators.get('bb_position', 'N/A')}
- MA20: {indicators.get('ma_20', 'N/A')}
- MA50: {indicators.get('ma_50', 'N/A')}
- MA200: {indicators.get('ma_200', 'N/A')}
- ADX: {indicators.get('adx', 'N/A')} ({indicators.get('trend_strength', 'N/A')})
- Kháng cự 1: {indicators.get('resistance_1', 'N/A')}
- Hỗ trợ 1: {indicators.get('support_1', 'N/A')}

## TÍN HIỆU KỸ THUẬT
- Hành động: {tech_action}
- Chi tiết: {', '.join(tech_signals)}

## TIN TỨC MỚI NHẤT
{news_summary}

## YÊU CẦU PHÂN TÍCH
Hãy đóng vai trò là một chuyên gia phân tích chứng khoán cao cấp tại SSI Research.
Đưa ra nhận định chuyên sâu về cổ phiếu này với cấu trúc sau. **TRẢ LỜI BẰNG TIẾNG VIỆT.**

1. **TỔNG QUAN NHẬN ĐỊNH**: Kết luận ngắn gọn (MUA/BÁN/NẮM GIỮ) kèm luận điểm chính.

2. **PHÂN TÍCH KỸ THUẬT**: Xu hướng ngắn hạn, trung hạn, dài hạn. Các ngưỡng kháng cự và hỗ trợ quan trọng.

3. **PHÂN TÍCH CƠ BẢN**: Đánh giá dựa trên ngành, tin tức, và bối cảnh thị trường.

4. **RỦI RO**: Các rủi ro chính cần lưu ý.

5. **KHUYẾN NGHỊ**: Hành động cụ thể, ngưỡng giá mục tiêu, và stop-loss (nếu có).
"""

        system_prompt = """Bạn là một chuyên gia phân tích chứng khoán cao cấp (Senior Equity Analyst) tại SSI Research với hơn 20 năm kinh nghiệm trên thị trường chứng khoán Việt Nam.

Phong cách phân tích:
- Chuyên nghiệp, dữ liệu-driven, khách quan
- Đưa ra nhận định rõ ràng kèm luận điểm và dẫn chứng
- Chỉ ra cả cơ hội và rủi ro
- Sử dụng thuật ngữ chuyên ngành tài chính
- Kết luận phải có tính hành động (actionable)

QUY TẮC NGÔN NGỮ:
- PHẢI trả lời bằng TIẾNG VIỆT. Tuyệt đối không dùng tiếng Anh.
- Dữ liệu số và thuật ngữ chuyên ngành (RSI, MACD, MA, v.v.) giữ nguyên tiếng Anh.

LUẬT BẮT BUỘC:
1. KHÔNG đưa ra lời khuyên tài chính cá nhân hay khuyến nghị mua/bán cụ thể.
2. Luôn nói rõ đây là phân tích tham khảo, không phải lời khuyên đầu tư.
3. Phân tích phải cân bằng giữa góc nhìn tích cực và tiêu cực.
4. Nếu thiếu dữ liệu, hãy nêu rõ giả định đang sử dụng."""

        if self.use_llm and self.llm_client:
            return self._call_llm(system_prompt, user_prompt)
        else:
            return self._rule_based_analysis(
                symbol, company_name, tech_signal, indicators, latest_price
            )

    def _rule_based_analysis(
        self,
        symbol: str,
        company_name: str,
        tech_signal: dict,
        indicators: dict,
        latest_price: float,
    ) -> str:
        action = tech_signal.get("action", "N/A")
        signals = tech_signal.get("signals", [])
        rsi = indicators.get("rsi_14", 50)
        ma20 = indicators.get("ma_20", 0)
        ma50 = indicators.get("ma_50", 0)

        lines = [
            f"📊 **PHÂN TÍCH CỔ PHIẾU {symbol} - {company_name}**\n",
            f"**Giá hiện tại**: {latest_price:,}",
            f"**Tín hiệu**: {action}",
            f"**RSI(14)**: {rsi} - {'Quá bán' if rsi < 30 else 'Quá mua' if rsi > 70 else 'Trung tính'}",
            f"**MA20**: {ma20} | **MA50**: {ma50}",
            f"**Giá/MA20**: {'Trên' if latest_price > ma20 else 'Dưới'} MA20",
            "",
            "**Chi tiết tín hiệu:**",
        ]
        for s in signals:
            lines.append(f"  • {s}")
        lines.append("")
        lines.append(
            "⚠️ **Lưu ý**: Đây là phân tích kỹ thuật tham khảo, không phải lời khuyên đầu tư. "
            "Cần kết hợp với phân tích cơ bản và quản trị rủi ro."
        )
        return "\n".join(lines)

    def analyze_multiple_symbols(self, symbols: List[str]) -> dict:
        results = {}
        for symbol in symbols:
            try:
                results[symbol] = self.analyze_symbol(symbol)
            except Exception as e:
                results[symbol] = {"error": str(e), "symbol": symbol}
        return results

    def compare_symbols(self, symbols: List[str]) -> List[dict]:
        comparison = []
        for symbol in symbols:
            try:
                result = self.analyze_symbol(symbol)
                tech = result.get("technical", {})
                indicators = tech.get("indicators", {})
                comparison.append({
                    "symbol": symbol,
                    "price": indicators.get("current_price", 0),
                    "change_1d": indicators.get("price_change_pct_1d", 0),
                    "change_5d": indicators.get("price_change_pct_5d", 0),
                    "rsi": indicators.get("rsi_14", "N/A"),
                    "signal": tech.get("action", "N/A"),
                    "volume_ratio": indicators.get("volume_ratio", 1),
                })
            except Exception as e:
                comparison.append({"symbol": symbol, "error": str(e)})
        return comparison
