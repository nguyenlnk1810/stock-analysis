import pandas as pd
import numpy as np
from ta.trend import MACD, SMAIndicator, EMAIndicator, ADXIndicator, IchimokuIndicator, CCIIndicator
from ta.momentum import RSIIndicator, StochasticOscillator, WilliamsRIndicator, ROCIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice, OnBalanceVolumeIndicator
from scipy import stats


class TechnicalAnalyzer:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._validate_data()

    def _validate_data(self):
        required = ["close", "high", "low", "volume"]
        for col in required:
            if col not in self.df.columns:
                raise ValueError(f"Missing required column: {col}")

    def compute_all(self) -> dict:
        result = {}
        result.update(self._compute_moving_averages())
        result.update(self._compute_rsi())
        result.update(self._compute_stochastic())
        result.update(self._compute_williams_r())
        result.update(self._compute_macd())
        result.update(self._compute_bollinger_bands())
        result.update(self._compute_ichimoku())
        result.update(self._compute_volume_indicators())
        result.update(self._compute_cashflow())
        result.update(self._compute_support_resistance())
        result.update(self._compute_trend_strength())
        result.update(self._compute_market_summary())
        result.update(self._compute_risk_metrics())
        result.update(self._compute_pivot_points())
        result.update(self._compute_candlestick_patterns())
        return result

    def _compute_moving_averages(self) -> dict:
        close = self.df["close"]
        mas = {}
        for period in [5, 10, 20, 50, 100, 200]:
            if len(close) >= period:
                ma = SMAIndicator(close, window=period).sma_indicator()
                mas[f"ma_{period}"] = round(float(ma.iloc[-1]), 2)
                mas[f"ma_{period}_slope"] = round(
                    float((ma.iloc[-1] - ma.iloc[-min(5, len(ma))]) / ma.iloc[-min(5, len(ma))] * 100), 2
                ) if len(ma) > 5 else 0

        current_price = float(close.iloc[-1])
        mas["price_vs_ma20_pct"] = round(
            (current_price - mas.get("ma_20", current_price)) / mas.get("ma_20", current_price) * 100, 2
        ) if "ma_20" in mas else 0
        mas["price_vs_ma50_pct"] = round(
            (current_price - mas.get("ma_50", current_price)) / mas.get("ma_50", current_price) * 100, 2
        ) if "ma_50" in mas else 0
        mas["current_price"] = current_price

        for period in [20, 50, 200]:
            if len(close) >= period:
                ema = EMAIndicator(close, window=period).ema_indicator()
                mas[f"ema_{period}"] = round(float(ema.iloc[-1]), 2)

        # MA alignment signal
        if all(k in mas for k in ["ma_20", "ma_50", "ma_100"]):
            if mas["ma_20"] > mas["ma_50"] > mas["ma_100"]:
                mas["ma_alignment"] = "uptrend"
            elif mas["ma_20"] < mas["ma_50"] < mas["ma_100"]:
                mas["ma_alignment"] = "downtrend"
            else:
                mas["ma_alignment"] = "mixed"

        return mas

    def _compute_rsi(self) -> dict:
        close = self.df["close"]
        result = {}
        if len(close) >= 14:
            rsi = RSIIndicator(close, window=14).rsi()
            rsi_val = float(rsi.iloc[-1])
            result["rsi_14"] = round(rsi_val, 2)
            result["rsi_signal"] = "oversold" if rsi_val < 30 else "overbought" if rsi_val > 70 else "neutral"
            result["rsi_trend"] = "tăng" if rsi_val > 50 else "giảm"

            # RSI divergence
            if len(close) >= 20:
                rsi_5d_ago = float(rsi.iloc[-5]) if len(rsi) >= 5 else rsi_val
                price_5d_ago = float(close.iloc[-5]) if len(close) >= 5 else float(close.iloc[-1])
                if rsi_val > rsi_5d_ago and float(close.iloc[-1]) < price_5d_ago:
                    result["rsi_divergence"] = "bullish divergence"
                elif rsi_val < rsi_5d_ago and float(close.iloc[-1]) > price_5d_ago:
                    result["rsi_divergence"] = "bearish divergence"
                else:
                    result["rsi_divergence"] = "none"

            # RSI multi-timeframe
            for period, label in [(7, 7), (14, 14), (21, 21)]:
                if len(close) >= period:
                    rsi_m = RSIIndicator(close, window=period).rsi()
                    result[f"rsi_{label}"] = round(float(rsi_m.iloc[-1]), 2)

        return result

    def _compute_stochastic(self) -> dict:
        result = {}
        if len(self.df) >= 14:
            stoch = StochasticOscillator(
                self.df["high"], self.df["low"], self.df["close"], window=14, smooth_window=3
            )
            result["stoch_k"] = round(float(stoch.stoch().iloc[-1]), 2)
            result["stoch_d"] = round(float(stoch.stoch_signal().iloc[-1]), 2)
            result["stoch_signal"] = (
                "oversold" if result["stoch_k"] < 20
                else "overbought" if result["stoch_k"] > 80
                else "neutral"
            )
        return result

    def _compute_williams_r(self) -> dict:
        result = {}
        if len(self.df) >= 14:
            wr = WilliamsRIndicator(
                self.df["high"], self.df["low"], self.df["close"], lbp=14
            ).williams_r()
            wr_val = float(wr.iloc[-1])
            result["williams_r"] = round(wr_val, 2)
            result["williams_r_signal"] = (
                "oversold" if wr_val < -80
                else "overbought" if wr_val > -20
                else "neutral"
            )
        return result

    def _compute_macd(self) -> dict:
        close = self.df["close"]
        result = {}
        if len(close) >= 26:
            for fast, slow, signal, label in [(12, 26, 9, "standard"), (8, 17, 9, "fast")]:
                macd = MACD(close, window_slow=slow, window_fast=fast, window_sign=signal)
                macd_line = macd.macd()
                macd_signal = macd.macd_signal()
                macd_hist = macd.macd_diff()
                result[f"macd_{label}"] = round(float(macd_line.iloc[-1]), 4)
                result[f"macd_signal_{label}"] = round(float(macd_signal.iloc[-1]), 4)
                result[f"macd_histogram_{label}"] = round(float(macd_hist.iloc[-1]), 4)

            result["macd_cross"] = (
                "bullish cross"
                if result.get("macd_standard", 0) > result.get("macd_signal_standard", 0)
                else "bearish cross"
            )
            result["macd_histogram_trend"] = (
                "mở rộng" if result.get("macd_histogram_standard", 0) > 0 else "thu hẹp"
            )

            # MACD divergence
            if len(close) >= 50:
                macd_line = macd.macd()
                macd_5d_ago = float(macd_line.iloc[-5])
                price_5d_ago = float(close.iloc[-5])
                macd_now = float(macd_line.iloc[-1])
                price_now = float(close.iloc[-1])
                if macd_now > macd_5d_ago and price_now < price_5d_ago:
                    result["macd_divergence"] = "bullish divergence"
                elif macd_now < macd_5d_ago and price_now > price_5d_ago:
                    result["macd_divergence"] = "bearish divergence"
                else:
                    result["macd_divergence"] = "none"

        return result

    def _compute_bollinger_bands(self) -> dict:
        close = self.df["close"]
        result = {}
        if len(close) >= 20:
            for period, std in [(20, 2), (20, 2.5)]:
                bb = BollingerBands(close, window=period, window_dev=std)
                result["bb_upper"] = round(float(bb.bollinger_hband().iloc[-1]), 2)
                result["bb_middle"] = round(float(bb.bollinger_mavg().iloc[-1]), 2)
                result["bb_lower"] = round(float(bb.bollinger_lband().iloc[-1]), 2)
                result["bb_width"] = round(
                    (result["bb_upper"] - result["bb_lower"]) / result["bb_middle"] * 100, 2
                )
                result["bb_bandwidth_pct"] = round(
                    (result["bb_upper"] - result["bb_lower"]) / result["bb_middle"] * 100, 2
                )

            current = float(close.iloc[-1])
            if current >= result["bb_upper"]:
                result["bb_position"] = "trên dải trên"
                result["bb_signal"] = "overbought"
            elif current <= result["bb_lower"]:
                result["bb_position"] = "dưới dải dưới"
                result["bb_signal"] = "oversold"
            else:
                result["bb_position"] = "trong dải Bollinger"
                result["bb_signal"] = "neutral"

            result["bb_pct_b"] = round(
                (current - result["bb_lower"])
                / (result["bb_upper"] - result["bb_lower"]), 4,
            )

            # Bollinger squeeze
            bb_20ago = BollingerBands(close.shift(20), window=20, window_dev=2)
            old_width = bb_20ago.bollinger_hband().iloc[-1] - bb_20ago.bollinger_lband().iloc[-1]
            if old_width > 0:
                squeeze_ratio = result["bb_width"] / (old_width / result["bb_middle"] * 100)
                result["bb_squeeze"] = "squeeze" if squeeze_ratio < 0.8 else "expansion"

        return result

    def _compute_ichimoku(self) -> dict:
        result = {}
        if len(self.df) >= 52:
            ichi = IchimokuIndicator(self.df["high"], self.df["low"], self.df["close"])
            result["ichimoku_tenkan"] = round(float(ichi.ichimoku_conversion_line().iloc[-1]), 2)
            result["ichimoku_kijun"] = round(float(ichi.ichimoku_base_line().iloc[-1]), 2)
            result["ichimoku_senkou_a"] = round(float(ichi.ichimoku_a().iloc[-1]), 2)
            current = float(self.df["close"].iloc[-1])
            if current > result["ichimoku_senkou_a"]:
                result["ichimoku_signal"] = "bullish"
            else:
                result["ichimoku_signal"] = "bearish"
        return result

    def _compute_volume_indicators(self) -> dict:
        vol = self.df["volume"]
        close = self.df["close"]
        result = {}
        if len(vol) >= 20:
            avg_vol_20 = vol.tail(20).mean()
            avg_vol_50 = vol.tail(50).mean() if len(vol) >= 50 else avg_vol_20
            current_vol = float(vol.iloc[-1])
            result["volume_current"] = int(current_vol)
            result["volume_avg_20"] = int(avg_vol_20)
            result["volume_avg_50"] = int(avg_vol_50)
            result["volume_ratio"] = round(current_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 1
            result["volume_signal"] = (
                "đột biến" if result["volume_ratio"] > 1.5
                else "bình thường" if result["volume_ratio"] > 0.5
                else "thấp"
            )

            # On-Balance Volume
            obv = OnBalanceVolumeIndicator(close, vol).on_balance_volume()
            result["obv"] = round(float(obv.iloc[-1]), 2)
            if len(obv) >= 5:
                obv_trend = obv.iloc[-1] - obv.iloc[-5]
                result["obv_trend"] = "tăng" if obv_trend > 0 else "giảm"

            # Volume price trend
            vpt = (vol * close).rolling(14).sum()
            result["vpt"] = round(float(vpt.iloc[-1]) / 1e9, 2) if len(vpt) > 0 else 0

            # Volume weighted average price
            if len(self.df) >= 20:
                vwap = VolumeWeightedAveragePrice(
                    self.df["high"], self.df["low"], self.df["close"], self.df["volume"], window=20
                ).volume_weighted_average_price()
                result["vwap"] = round(float(vwap.iloc[-1]), 2)

            # Volume accumulation/distribution
            mfm = ((close - self.df["low"]) - (self.df["high"] - close)) / (self.df["high"] - self.df["low"])
            mfm = mfm.fillna(0)
            mfv = mfm * vol
            ad_line = mfv.cumsum()
            result["ad_line"] = round(float(ad_line.iloc[-1]) / 1e6, 2)

        return result

    def _compute_cashflow(self) -> dict:
        result = {}
        if "foreign_buy" in self.df.columns and "foreign_sell" in self.df.columns:
            fb = self.df["foreign_buy"]
            fs = self.df["foreign_sell"]
            if len(fb) > 0:
                result["foreign_net"] = round(float((fb.sum() - fs.sum()) / 1e9), 2)
                result["foreign_buy_total"] = round(float(fb.sum() / 1e9), 2)
                result["foreign_sell_total"] = round(float(fs.sum() / 1e9), 2)
                result["foreign_net_today"] = round(float((fb.iloc[-1] - fs.iloc[-1]) / 1e9), 2)

        if "value" in self.df.columns:
            total_val = self.df["value"].sum()
            result["total_value"] = round(float(total_val / 1e9), 2)

        return result

    def _compute_support_resistance(self) -> dict:
        close = self.df["close"].values
        high = self.df["high"].values
        low = self.df["low"].values
        result = {}
        if len(close) >= 50:
            result["support_1"] = round(float(np.percentile(low[-50:], 25)), 2)
            result["resistance_1"] = round(float(np.percentile(high[-50:], 75)), 2)
            result["support_2"] = round(float(np.min(low[-50:])), 2)
            result["resistance_2"] = round(float(np.max(high[-50:])), 2)

            # Pivot points using local min/max
            if len(close) >= 20:
                recent = close[-20:]
                local_max = max(recent)
                local_min = min(recent)
                pivot = (local_max + local_min + close[-1]) / 3
                result["pivot"] = round(float(pivot), 2)
                result["r1"] = round(float(2 * pivot - local_min), 2)
                result["s1"] = round(float(2 * pivot - local_max), 2)
        return result

    def _compute_trend_strength(self) -> dict:
        result = {}
        if len(self.df) >= 50:
            adx = ADXIndicator(
                self.df["high"], self.df["low"], self.df["close"], window=14
            ).adx()
            adx_val = float(adx.iloc[-1])
            result["adx"] = round(adx_val, 2)
            result["trend_strength"] = (
                "mạnh" if adx_val > 25 else "trung bình" if adx_val > 20 else "yếu"
            )

            # CCI
            cci = CCIIndicator(self.df["high"], self.df["low"], self.df["close"], window=20).cci()
            if not cci.empty:
                result["cci"] = round(float(cci.iloc[-1]), 2)
                result["cci_signal"] = (
                    "oversold" if result["cci"] < -100
                    else "overbought" if result["cci"] > 100
                    else "neutral"
                )

            # ROC
            roc = ROCIndicator(self.df["close"], window=12).roc()
            if not roc.empty:
                result["roc"] = round(float(roc.iloc[-1]), 2)

        return result

    def _compute_market_summary(self) -> dict:
        close = self.df["close"]
        result = {}
        if len(close) >= 2:
            result["price_change_1d"] = round(float(close.iloc[-1] - close.iloc[-2]), 2)
            result["price_change_pct_1d"] = round(
                (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100, 2
            )
        if len(close) >= 5:
            result["price_change_5d"] = round(float(close.iloc[-1] - close.iloc[-5]), 2)
            result["price_change_pct_5d"] = round(
                (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100, 2
            )
        if len(close) >= 20:
            result["price_change_20d"] = round(float(close.iloc[-1] - close.iloc[-20]), 2)
            result["price_change_pct_20d"] = round(
                (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100, 2
            )
        if len(close) >= 50:
            result["price_change_50d"] = round(float(close.iloc[-1] - close.iloc[-50]), 2)
            result["price_change_pct_50d"] = round(
                (close.iloc[-1] - close.iloc[-50]) / close.iloc[-50] * 100, 2
            )

        if len(close) >= 20:
            returns = close.pct_change().dropna()
            result["volatility_20d"] = round(float(returns.tail(20).std() * np.sqrt(252) * 100), 2)

        return result

    def _compute_risk_metrics(self) -> dict:
        close = self.df["close"]
        result = {}
        if len(close) >= 20:
            returns = close.pct_change().dropna()
            latest_returns = returns.tail(20)

            # VaR (95%)
            var_95 = np.percentile(latest_returns, 5)
            result["var_95"] = round(float(var_95 * 100), 2)

            # Max drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            result["max_drawdown"] = round(float(drawdown.min() * 100), 2)

            # Sharpe ratio (assuming 5% risk-free)
            sharpe = (latest_returns.mean() * 252 - 0.05) / (latest_returns.std() * np.sqrt(252))
            result["sharpe_ratio"] = round(float(sharpe), 2)

            # Beta (vs market - using equal weight)
            result["beta"] = round(float(stats.linregress(
                range(len(latest_returns)), latest_returns.values
            ).slope * 10), 2)

            # Skewness
            result["skewness"] = round(float(latest_returns.skew()), 2)

            # Kurtosis
            result["kurtosis"] = round(float(latest_returns.kurtosis()), 2)

        return result

    def _compute_pivot_points(self) -> dict:
        result = {}
        if len(self.df) >= 1:
            high = float(self.df["high"].iloc[-1])
            low = float(self.df["low"].iloc[-1])
            close = float(self.df["close"].iloc[-1])
            pivot = (high + low + close) / 3
            result["pivot_pp"] = round(pivot, 2)
            result["pivot_r1"] = round(2 * pivot - low, 2)
            result["pivot_r2"] = round(pivot + (high - low), 2)
            result["pivot_s1"] = round(2 * pivot - high, 2)
            result["pivot_s2"] = round(pivot - (high - low), 2)
        return result

    def _compute_candlestick_patterns(self) -> dict:
        result = {}
        if len(self.df) >= 3:
            open_ = self.df["open"].values
            high = self.df["high"].values
            low = self.df["low"].values
            close = self.df["close"].values
            o, h, l, c = open_[-1], high[-1], low[-1], close[-1]
            body = abs(c - o)
            upper_wick = h - max(o, c)
            lower_wick = min(o, c) - l

            # Doji
            if body < (h - l) * 0.1:
                result["pattern"] = "doji"
                result["pattern_signal"] = "potential reversal"

            # Hammer
            elif lower_wick > body * 2 and upper_wick < body * 0.3:
                result["pattern"] = "hammer"
                result["pattern_signal"] = "bullish reversal"

            # Shooting star
            elif upper_wick > body * 2 and lower_wick < body * 0.3:
                result["pattern"] = "shooting star"
                result["pattern_signal"] = "bearish reversal"

            # Marubozu
            elif upper_wick < body * 0.1 and lower_wick < body * 0.1:
                if c > o:
                    result["pattern"] = "marubozu xanh"
                    result["pattern_signal"] = "bullish strong"
                else:
                    result["pattern"] = "marubozu đỏ"
                    result["pattern_signal"] = "bearish strong"

            # Engulfing
            if len(self.df) >= 2:
                prev_body = abs(close[-2] - open_[-2])
                if body > prev_body * 1.5 and c > o and close[-2] < open_[-2]:
                    result["pattern_engulfing"] = "bullish engulfing"
                elif body > prev_body * 1.5 and c < o and close[-2] > open_[-2]:
                    result["pattern_engulfing"] = "bearish engulfing"

        return result

    def get_technical_signal(self) -> dict:
        indicators = self.compute_all()

        score = 0
        signals = []

        # === RSI ===
        rsi = indicators.get("rsi_14", 50)
        if rsi < 30:
            score += 2
            signals.append("RSI quá bán (bullish)")
        elif rsi < 40:
            score += 1
            signals.append("RSI thấp (bullish nhẹ)")
        elif rsi > 70:
            score -= 2
            signals.append("RSI quá mua (bearish)")
        elif rsi > 60:
            score -= 1
            signals.append("RSI cao (bearish nhẹ)")

        # === Stochastic ===
        stoch = indicators.get("stoch_k", 50)
        if stoch < 20:
            score += 1
            signals.append(f"Stochastic quá bán ({stoch})")
        elif stoch > 80:
            score -= 1
            signals.append(f"Stochastic quá mua ({stoch})")

        # === Williams %R ===
        wr = indicators.get("williams_r", -50)
        if wr < -80:
            score += 1
            signals.append("Williams %R quá bán")
        elif wr > -20:
            score -= 1
            signals.append("Williams %R quá mua")

        # === MACD ===
        macd_hist = indicators.get("macd_histogram_standard", 0)
        if macd_hist > 0:
            score += 1
            signals.append("MACD histogram dương (bullish)")
        else:
            score -= 1
            signals.append("MACD histogram âm (bearish)")

        macd_cross = indicators.get("macd_cross", "")
        if "bullish" in macd_cross:
            score += 1
            signals.append("MACD cắt lên (bullish cross)")
        elif "bearish" in macd_cross:
            score -= 1
            signals.append("MACD cắt xuống (bearish cross)")

        # MACD divergence
        macd_div = indicators.get("macd_divergence", "none")
        if "bullish" in macd_div:
            score += 2
            signals.append("MACD divergence dương (bullish)")
        elif "bearish" in macd_div:
            score -= 2
            signals.append("MACD divergence âm (bearish)")

        # === MA Alignment ===
        alignment = indicators.get("ma_alignment", "")
        if alignment == "uptrend":
            score += 1
            signals.append("MA xếp theo xu hướng tăng")
        elif alignment == "downtrend":
            score -= 1
            signals.append("MA xếp theo xu hướng giảm")

        # === MA vs Price ===
        price = indicators.get("current_price", 0)
        ma20 = indicators.get("ma_20", 0)
        ma50 = indicators.get("ma_50", 0)
        if ma20 > 0 and price > ma20:
            score += 1
            signals.append(f"Giá trên MA20 (+{indicators['price_vs_ma20_pct']}%)")
        elif ma20 > 0:
            score -= 1
            signals.append(f"Giá dưới MA20 ({indicators['price_vs_ma20_pct']}%)")

        if ma50 > 0 and price > ma50:
            score += 1
            signals.append(f"Giá trên MA50 (+{indicators['price_vs_ma50_pct']}%)")
        elif ma50 > 0:
            score -= 1
            signals.append(f"Giá dưới MA50 ({indicators['price_vs_ma50_pct']}%)")

        # === Bollinger Bands ===
        bb_signal = indicators.get("bb_signal", "neutral")
        if bb_signal == "oversold":
            score += 1
            signals.append("Bollinger Band chạm dải dưới (oversold)")
        elif bb_signal == "overbought":
            score -= 1
            signals.append("Bollinger Band chạm dải trên (overbought)")

        # BB Squeeze
        bb_squeeze = indicators.get("bb_squeeze", "")
        if bb_squeeze == "squeeze":
            signals.append("Bollinger Band squeeze (sắp bùng nổ)")

        # === Volume ===
        vol_ratio = indicators.get("volume_ratio", 1)
        if vol_ratio > 1.5:
            if score > 0:
                signals.append("Volume đột biến xác nhận xu hướng tăng")
                score += 1
            elif score < 0:
                signals.append("Volume đột biến xác nhận xu hướng giảm")
                score -= 1
        elif vol_ratio < 0.5:
            signals.append("Volume thấp (thiếu xác nhận)")

        # === ADX ===
        adx = indicators.get("adx", 0)
        if adx > 25:
            signals.append(f"Xu hướng mạnh (ADX={adx})")
        elif adx > 20:
            signals.append(f"Xu hướng trung bình (ADX={adx})")

        # === Candlestick ===
        pattern = indicators.get("pattern", "")
        pattern_signal = indicators.get("pattern_signal", "")
        if pattern:
            signals.append(f"Mô hình nến: {pattern} ({pattern_signal})")

        # === Ichimoku ===
        ichi = indicators.get("ichimoku_signal", "")
        if ichi == "bullish":
            score += 1
            signals.append("Ichimoku: bullish")
        elif ichi == "bearish":
            score -= 1
            signals.append("Ichimoku: bearish")

        # === Foreign cash flow ===
        foreign_net = indicators.get("foreign_net_today", 0)
        if foreign_net > 0:
            signals.append(f"Khối ngoại mua ròng hôm nay ({foreign_net} tỷ)")
        elif foreign_net < 0:
            signals.append(f"Khối ngoại bán ròng hôm nay ({abs(foreign_net)} tỷ)")

        if score >= 5:
            action = "MUA MẠNH"
            confidence = "rất cao"
        elif score >= 3:
            action = "MUA"
            confidence = "cao"
        elif score >= 1:
            action = "TÍCH LŨY"
            confidence = "trung bình"
        elif score <= -5:
            action = "BÁN MẠNH"
            confidence = "rất cao"
        elif score <= -3:
            action = "BÁN"
            confidence = "cao"
        elif score <= -1:
            action = "GIẢM TỶ TRỌNG"
            confidence = "trung bình"
        else:
            action = "NẮM GIỮ"
            confidence = "thấp"

        return {
            "action": action,
            "score": score,
            "confidence": confidence,
            "signals": signals,
            "indicators": indicators,
        }
