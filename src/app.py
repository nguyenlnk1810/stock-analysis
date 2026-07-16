import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from src.ai_agent import AIStockAgent
from src.afl_strategies import compute_afl_signals_for_current
from src.config import config


st.set_page_config(
    page_title="AI Stock Analyst - SSI",
    page_icon="📈",
    layout="wide",
)


@st.cache_resource
def get_agent():
    return AIStockAgent(use_llm=True)


def plot_price_chart(df: pd.DataFrame, symbol: str, indicators: dict):
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.5, 0.25, 0.25],
        subplot_titles=(f"{symbol} - Giá & MA", "RSI", "MACD"),
    )

    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Giá",
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    # Moving Averages
    for ma_period, color in [(20, "orange"), (50, "blue"), (100, "purple"), (200, "red")]:
        ma_key = f"ma_{ma_period}"
        if ma_key in indicators:
            ma_values = df["close"].rolling(ma_period).mean()
            fig.add_trace(
                go.Scatter(
                    x=df["date"],
                    y=ma_values,
                    name=f"MA{ma_period}",
                    line=dict(color=color, width=1),
                ),
                row=1,
                col=1,
            )

    # Bollinger Bands
    if "bb_upper" in indicators:
        bb_middle = df["close"].rolling(20).mean()
        bb_std = df["close"].rolling(20).std()
        bb_upper = bb_middle + 2 * bb_std
        bb_lower = bb_middle - 2 * bb_std
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=bb_upper,
                name="BB Upper",
                line=dict(color="gray", width=1, dash="dash"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=bb_lower,
                name="BB Lower",
                line=dict(color="gray", width=1, dash="dash"),
                fill="tonexty",
                fillcolor="rgba(128,128,128,0.1)",
            ),
            row=1,
            col=1,
        )

    # Volume bars
    colors = [
        "green" if df["close"].iloc[i] >= df["open"].iloc[i] else "red"
        for i in range(len(df))
    ]
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["volume"],
            name="Volume",
            marker_color=colors,
            opacity=0.5,
        ),
        row=2,
        col=1,
    )

    # RSI
    if "rsi_14" in indicators:
        rsi_values = pd.Series(
            [float(x) for x in df.index], index=df.index
        )  # placeholder
        close = df["close"]
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi_values = 100 - (100 / (1 + rs))

        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=rsi_values,
                name="RSI(14)",
                line=dict(color="purple", width=1),
            ),
            row=3,
            col=1,
        )
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
        fig.add_hline(y=50, line_dash="dash", line_color="gray", row=3, col=1)

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=800,
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    fig.update_yaxes(title_text="Giá", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1)

    return fig


def main():
    st.title("📈 AI Stock Analyst - Hệ thống phân tích chứng khoán thông minh")
    st.markdown(
        "Dữ liệu từ **SSI FastConnect API** | Phân tích bởi **AI Agent**"
    )
    st.divider()

    # Sidebar
    with st.sidebar:
        st.header("Cấu hình")
        symbol = st.text_input(
            "Mã cổ phiếu",
            value="SSI",
            help="Nhập mã cổ phiếu (VD: VCB, SSI, FPT, HPG)",
        ).upper()

        col1, col2 = st.columns(2)
        with col1:
            days = st.selectbox(
                "Kỳ phân tích",
                options=[30, 60, 90, 180, 365],
                index=2,
            )
        with col2:
            use_llm = st.toggle("Sử dụng AI (LLM)", value=True)

        analyze_btn = st.button("🚀 Phân tích ngay", type="primary", use_container_width=True)
        st.divider()

        st.markdown("### Danh sách theo dõi")
        watchlist = st.multiselect(
            "Chọn mã",
            options=config.DEFAULT_SYMBOLS,
            default=["VNINDEX", "SSI", "FPT", "VCB"],
        )

        st.divider()
        st.caption("🔒 Dữ liệu API từ SSI - Bảo mật tuyệt đối")
        st.caption(f"Provider: {config.LLM_PROVIDER}")

    # Main content
    if analyze_btn:
        with st.spinner(f"🔄 Đang phân tích {symbol}..."):
            agent = AIStockAgent(use_llm=use_llm)
            try:
                result = agent.analyze_symbol(symbol)

                # Display sections
                tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
                    ["📊 Tổng quan", "📈 Phân tích kỹ thuật", "📰 Tin tức", "🤖 AI Analysis", "🎯 Tín hiệu 100đ", "🧪 AFL Signals"]
                )

                with tab1:
                    col1, col2, col3, col4 = st.columns(4)
                    tech = result["technical"]
                    ind = tech.get("indicators", {})
                    price = ind.get("current_price", 0)

                    with col1:
                        st.metric(
                            "Giá hiện tại",
                            f"{price:,.0f}",
                            delta=f"{ind.get('price_change_pct_1d', 0):.2f}%",
                        )
                    with col2:
                        st.metric(
                            "RSI(14)",
                            ind.get("rsi_14", "N/A"),
                            delta=ind.get("rsi_signal", ""),
                        )
                    with col3:
                        st.metric("Tín hiệu", tech.get("action", "N/A"))
                    with col4:
                        st.metric(
                            "KL đột biến",
                            f"{ind.get('volume_ratio', 1):.1f}x",
                            delta=ind.get("volume_signal", ""),
                        )

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("MA20", f"{ind.get('ma_20', 0):,.0f}")
                    with col2:
                        st.metric("MA50", f"{ind.get('ma_50', 0):,.0f}")
                    with col3:
                        st.metric("MA200", f"{ind.get('ma_200', 0):,.0f}")

                    st.divider()

                    # Price chart
                    df = result["price_data"]
                    if not df.empty:
                        fig = plot_price_chart(df, symbol, ind)
                        st.plotly_chart(fig, use_container_width=True)

                    # Company info
                    if result.get("company_name"):
                        st.subheader(f"🏢 {result['company_name']}")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.info(f"**Ngành**: {result.get('industry', 'N/A')}")
                        with c2:
                            st.info(f"**Sàn**: {result.get('exchange', 'N/A')}")

                with tab2:
                    st.subheader("Chi tiết chỉ báo kỹ thuật")

                    # Summary table
                    summary_data = {
                        "Chỉ báo": [
                            "RSI(14)",
                            "MACD",
                            "MACD Signal",
                            "MACD Histogram",
                            "Bollinger %B",
                            "ADX",
                            "Volume Ratio",
                            "Hỗ trợ S1",
                            "Kháng cự R1",
                        ],
                        "Giá trị": [
                            ind.get("rsi_14", "N/A"),
                            ind.get("macd", "N/A"),
                            ind.get("macd_signal", "N/A"),
                            ind.get("macd_histogram", "N/A"),
                            ind.get("bb_pct_b", "N/A"),
                            ind.get("adx", "N/A"),
                            ind.get("volume_ratio", "N/A"),
                            ind.get("support_1", "N/A"),
                            ind.get("resistance_1", "N/A"),
                        ],
                        "Tín hiệu": [
                            ind.get("rsi_signal", ""),
                            ind.get("macd_cross", ""),
                            "",
                            ind.get("macd_histogram_trend", ""),
                            ind.get("bb_position", ""),
                            ind.get("trend_strength", ""),
                            ind.get("volume_signal", ""),
                            "",
                            "",
                        ],
                    }
                    st.dataframe(
                        pd.DataFrame(summary_data),
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.divider()

                    # Signal details
                    signals = tech.get("signals", [])
                    if signals:
                        st.subheader("📋 Chi tiết tín hiệu")
                        for s in signals:
                            st.write(f"• {s}")

                with tab3:
                    st.subheader("📰 Tin tức liên quan")
                    news_list = result.get("news", [])
                    if news_list:
                        for i, article in enumerate(news_list[:10]):
                            with st.container():
                                st.markdown(f"**{article['title']}**")
                                c1, c2, c3 = st.columns([1, 2, 3])
                                with c1:
                                    st.caption(f"Nguồn: {article['source']}")
                                with c2:
                                    st.caption(f"Ngày: {article['date']}")
                                if article.get("url"):
                                    with c3:
                                        st.caption(
                                            f"[Đọc tiếp]({article['url']})"
                                        )
                                if article.get("summary"):
                                    st.write(article["summary"][:200] + "...")
                                st.divider()
                    else:
                        st.info("Không có tin tức mới cho mã này.")

                with tab4:
                    st.subheader("🤖 Phân tích từ AI Agent")
                    analysis = result.get("analysis", "Chưa có phân tích.")
                    st.markdown(analysis)

                    st.divider()
                    st.caption(
                        "⚠️ **Tuyên bố miễn trách**: Phân tích này được tạo ra bởi AI, "
                        "chỉ mang tính tham khảo. Không phải lời khuyên đầu tư tài chính. "
                        f"Phân tích lúc: {result.get('analyzed_at', 'N/A')}"
                    )

                with tab5:
                    st.subheader("🎯 Hệ thống chấm điểm tín hiệu 100 điểm")
                    scoring = tech.get("signal_scoring", {})
                    sm = tech.get("smart_money", {})
                    ps = tech.get("position_score", {})

                    if scoring:
                        total = scoring.get("tong_diem", 0)
                        grade = scoring.get("xep_loai", "LOAI")
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Tổng điểm", f"{total}/100")
                        col2.metric("Xếp loại", grade)
                        col3.metric("Tín hiệu", f"{scoring.get('so_luong_tin_hieu', 0)}")
                        col4.metric("Hình phạt", f"{sum(p['diem'] for p in scoring.get('mien_diem', []))}")

                        st.divider()
                        st.subheader("Chi tiết chấm điểm")

                        groups = [
                            ("xu_huong", "📈 Xu hướng", 30, "#3b82f6"),
                            ("dong_tien", "💵 Dòng tiền", 25, "#22c55e"),
                            ("momentum", "🚀 Momentum", 20, "#f59e0b"),
                            ("price_action", "🕯️ Price Action", 15, "#a855f7"),
                            ("relative_strength", "⚡ RS", 10, "#ec4899"),
                        ]
                        for key, label, toi_da, color in groups:
                            data = scoring.get("chi_tiet", {}).get(key, {})
                            diem = data.get("diem", 0)
                            chi_tiet = data.get("chi_tiet", [])
                            pct = diem / toi_da if toi_da > 0 else 0
                            st.markdown(f"**{label}**: {diem}/{toi_da}")
                            st.progress(pct, text="")
                            if chi_tiet:
                                for d in chi_tiet:
                                    st.caption(d)

                        st.divider()
                        st.subheader("⚠️ Hình phạt")
                        penalties = scoring.get("mien_diem", [])
                        if penalties:
                            for p in penalties:
                                st.warning(f"**{p['ten']}**: {p['diem']} điểm")
                        else:
                            st.info("Không có hình phạt")

                    st.divider()
                    st.subheader("🔍 Smart Money Patterns")
                    if sm:
                        c1, c2, c3 = st.columns(3)
                        c1.metric("BOS", sm.get("bos", "none"))
                        c2.metric("CHOCH", sm.get("choch", "none"))
                        c3.metric("FVG", sm.get("fvg_signal", "none"))
                        c1.metric("Liquidity Sweep", sm.get("liquidity_sweep", "none"))
                        c2.metric("SuperTrend", sm.get("supertrend_signal", "neutral"))
                        c3.metric("Premium/Discount", sm.get("premium_discount", "neutral"))

                    st.divider()
                    st.subheader("📏 Vị trí giá")
                    if ps:
                        cols = st.columns(5)
                        cols[0].metric("Cách EMA20", f"{ps.get('distance_to_ema20', 0):.1f}%")
                        cols[1].metric("Cách EMA50", f"{ps.get('distance_to_ema50', 0):.1f}%")
                        cols[2].metric("Cách EMA200", f"{ps.get('distance_to_ema200', 0):.1f}%")
                        cols[3].metric("Cách ATH", f"-{ps.get('distance_to_ath', 0):.1f}%")
                        cols[4].metric("Cách 52W H", f"-{ps.get('distance_to_52w_high', 0):.1f}%")

                with tab6:
                    st.subheader("🧪 AFL Signals - Tín hiệu từ AmiBroker Formulas")
                    st.caption("Kết hợp 9 chiến lược AFL: PsychIndex, ZangerVolume, RS-VNINDEX, MA20Crossover, ZigZag, Scoring, Ichimoku, MAI, VolumePocket")

                    try:
                        df = result["price_data"]
                        if not df.empty:
                            afl = compute_afl_signals_for_current(df)
                            col1, col2, col3, col4 = st.columns(4)
                            sig_color = "green" if afl["current_signal"] == "MUA" else "red" if afl["current_signal"] == "BAN" else "gray"
                            col1.markdown(f"**Tín hiệu tổng hợp**: :{sig_color}[{afl['current_signal']}]")
                            col2.metric("MUA", afl["buy_count"])
                            col3.metric("BÁN", afl["sell_count"])
                            col4.metric("Sức mạnh", f"{afl['strength']}%")

                            st.divider()
                            st.subheader("Chi tiết từng chiến lược")
                            details = afl.get("details", {})
                            detail_rows = []
                            for name, d in details.items():
                                sig_icon = "✅" if d.get("signal") == "MUA" else "❌" if d.get("signal") == "BAN" else "➖"
                                detail_rows.append({
                                    "Chiến lược": name,
                                    "Tín hiệu": f"{sig_icon} {d.get('signal', 'NEUTRAL')}",
                                })
                            if detail_rows:
                                st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

                            st.divider()
                            st.subheader("Lý do MUA")
                            for r in afl.get("buy_reasons", []):
                                st.write(f"• {r}")

                            st.subheader("Lý do BÁN")
                            for r in afl.get("sell_reasons", []):
                                st.write(f"• {r}")
                        else:
                            st.warning("Không có dữ liệu giá để tính AFL signals")
                    except Exception as e2:
                        st.warning(f"Không thể tính AFL signals: {e2}")

            except Exception as e:
                st.error(f"❌ Lỗi phân tích {symbol}: {str(e)}")
                st.info(
                    "💡 Gợi ý: Kiểm tra lại API key SSI trong file .env "
                    "hoặc kết nối internet."
                )

    # Comparison section
    if watchlist:
        st.divider()
        st.subheader("📊 So sánh danh mục")

        with st.spinner("🔄 Đang phân tích danh mục..."):
            agent = AIStockAgent(use_llm=False)
            try:
                comparison = agent.compare_symbols(watchlist)
                comp_df = pd.DataFrame(comparison)

                if not comp_df.empty and "error" not in comp_df.columns:
                    st.dataframe(
                        comp_df.style.apply(
                            lambda row: [
                                "background: lightgreen"
                                if row["signal"] in ["MUA", "TÍCH LŨY"]
                                else "background: lightcoral"
                                if row["signal"] in ["BÁN", "GIẢM TỶ TRỌNG"]
                                else ""
                                for _ in row
                            ],
                            axis=1,
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.warning("Không thể so sánh danh mục.")
            except Exception as e:
                st.warning(f"Lỗi so sánh: {e}")


if __name__ == "__main__":
    main()
