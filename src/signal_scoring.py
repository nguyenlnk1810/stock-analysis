import pandas as pd
import numpy as np
from scipy import stats


class SignalScorer:
    def __init__(self, df: pd.DataFrame, indicators: dict, symbol: str = "",
                 market: str = "HOSE", sector: str = ""):
        self.df = df.copy()
        self.ind = indicators
        self.symbol = symbol
        self.market = market
        self.sector = sector
        self.close = df["close"] if not df.empty else pd.Series(dtype=float)
        self.score_breakdown = {}
        self.penalties = []
        self.signals = []

    def compute_all(self) -> dict:
        scores = {}
        scores["xu_huong"] = self._score_trend()
        scores["dong_tien"] = self._score_money_flow()
        scores["momentum"] = self._score_momentum()
        scores["price_action"] = self._score_price_action()
        scores["relative_strength"] = self._score_relative_strength()
        self._compute_penalties()
        total = sum(v["diem"] for v in scores.values()) + sum(p["diem"] for p in self.penalties)
        total = max(0, min(100, total))
        grade = self._get_grade(total)
        return {
            "tong_diem": total,
            "xep_loai": grade,
            "chi_tiet": scores,
            "mien_diem": self.penalties,
            "tin_hieu": self.signals,
            "so_luong_tin_hieu": len(self.signals),
        }

    def _get_grade(self, score: int) -> str:
        if score >= 90: return "A+"
        if score >= 80: return "A"
        if score >= 70: return "B+"
        if score >= 60: return "B"
        if score >= 50: return "C"
        return "LOAI"

    def _ma(self, period: int):
        if len(self.close) >= period:
            return float(self.close.rolling(period).mean().iloc[-1])
        return None

    def _ema(self, period: int):
        if len(self.close) >= period:
            return float(self.close.ewm(span=period, adjust=False).mean().iloc[-1])
        return None

    def _ma_slope(self, period: int, lookback: int = 5):
        if len(self.close) >= period + lookback:
            ma = self.close.rolling(period).mean()
            if len(ma) >= lookback:
                return float((ma.iloc[-1] - ma.iloc[-lookback]) / ma.iloc[-lookback] * 100)
        return 0

    def _ema_slope(self, period: int, lookback: int = 5):
        if len(self.close) >= period + lookback:
            ema = self.close.ewm(span=period, adjust=False).mean()
            if len(ema) >= lookback:
                return float((ema.iloc[-1] - ema.iloc[-lookback]) / ema.iloc[-lookback] * 100)
        return 0

    def _check_higher_high(self):
        if len(self.df) < 40:
            return False
        h = self.df["high"].values
        recent_high = max(h[-10:])
        prev_high = max(h[-20:-10])
        return recent_high > prev_high

    def _check_bos_bearish(self):
        if len(self.df) < 30:
            return False
        l = self.df["low"].values
        recent_low = min(l[-10:])
        prev_low = min(l[-20:-10])
        return recent_low < prev_low

    def _score_trend(self) -> dict:
        score = 0
        details = []
        current_price = float(self.close.iloc[-1]) if len(self.close) > 0 else 0

        ema20 = self._ema(20)
        ema50 = self._ema(50)
        ema200 = self._ema(200)

        if ema20 and current_price > ema20:
            score += 3
            pct = (current_price - ema20) / ema20 * 100
            details.append(f"Giá > EMA20 (+{pct:.1f}%) [+3]")
        else:
            details.append("Giá < EMA20 [0]")

        ema20_slope = self._ema_slope(20)
        if ema20_slope > 0:
            score += 3
            details.append(f"EMA20 dốc lên (slope={ema20_slope:.2f}%) [+3]")
        else:
            details.append("EMA20 dốc xuống [0]")

        if ema20 and ema50 and ema20 > ema50:
            score += 4
            details.append("EMA20 > EMA50 [+4]")
        else:
            details.append("EMA20 < EMA50 [0]")

        if ema50 and ema200 and ema50 > ema200:
            score += 4
            details.append("EMA50 > EMA200 [+4]")
        else:
            details.append("EMA50 < EMA200 [0]")

        ema200_slope = self._ema_slope(200, lookback=20)
        if ema200_slope > 0:
            score += 4
            details.append(f"EMA200 dốc lên (slope={ema200_slope:.3f}%) [+4]")
        else:
            details.append("EMA200 dốc xuống [0]")

        adx = self.ind.get("adx", 0)
        if adx and adx > 25:
            score += 5
            details.append(f"ADX > 25 ({adx:.1f}) [+5]")
        elif adx:
            details.append(f"ADX <= 25 ({adx:.1f}) [0]")

        pdi = self.ind.get("plus_di", 0)
        ndi = self.ind.get("minus_di", 0)
        if pdi and ndi and pdi > ndi:
            score += 4
            details.append(f"+DI > -DI (+DI={pdi:.1f}, -DI={ndi:.1f}) [+4]")
        else:
            details.append("+DI <= -DI [0]")

        if self._check_higher_high():
            score += 3
            details.append("Giá tạo Higher High [+3]")
        else:
            details.append("Không có Higher High [0]")

        self.signals.extend([
            d for d in details if d.endswith("[+3]") or d.endswith("[+4]") or d.endswith("[+5]")
        ])
        return {"diem": score, "toi_da": 30, "chi_tiet": details}

    def _score_money_flow(self) -> dict:
        score = 0
        details = []

        volume = self.df["volume"] if not self.df.empty else pd.Series(dtype=float)
        current_vol = float(volume.iloc[-1]) if len(volume) > 0 else 0
        avg_vol_20 = float(volume.tail(min(20, len(volume))).mean()) if len(volume) >= 5 else 1

        if current_vol > avg_vol_20:
            score += 4
            ratio = current_vol / avg_vol_20 if avg_vol_20 > 0 else 0
            details.append(f"Volume > MA20 ({ratio:.1f}x) [+4]")
        else:
            details.append("Volume <= MA20 [0]")

        rvol = current_vol / avg_vol_20 if avg_vol_20 > 0 else 0
        if rvol > 1.5:
            score += 5
            details.append(f"RVOL > 1.5 ({rvol:.1f}x) [+5]")
        elif rvol > 1.0:
            details.append(f"RVOL bình thường ({rvol:.1f}x) [0]")
        else:
            details.append(f"RVOL thấp ({rvol:.1f}x) [0]")

        mfi = self.ind.get("mfi", 0)
        if mfi and mfi > 60:
            score += 5
            details.append(f"MFI > 60 ({mfi:.1f}) [+5]")
        elif mfi:
            details.append(f"MFI = {mfi:.1f} [0]")

        obv_trend = self.ind.get("obv_trend", "")
        if obv_trend == "tăng":
            score += 4
            details.append("OBV đang tăng [+4]")
        else:
            details.append("OBV không tăng [0]")

        cmf = self._calc_cmf()
        if cmf and cmf > 0:
            score += 4
            details.append(f"CMF > 0 ({cmf:.3f}) [+4]")
        else:
            details.append("CMF <= 0 [0]")

        acc = self._calc_accumulation()
        if acc > 0:
            score += 3
            details.append(f"Tích lũy tốt (score={acc}) [+3]")
        else:
            details.append("Tích lũy yếu [0]")

        self.signals.extend([
            d for d in details if d.endswith("[+4]") or d.endswith("[+5]") or d.endswith("[+3]")
        ])
        return {"diem": score, "toi_da": 25, "chi_tiet": details}

    def _calc_cmf(self):
        if self.df.empty or len(self.df) < 21:
            return None
        h = self.df["high"]
        l = self.df["low"]
        c = self.df["close"]
        v = self.df["volume"]
        mfm = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
        mfm = mfm.fillna(0)
        mfv = mfm * v
        cmf = mfv.rolling(20).sum() / v.rolling(20).sum()
        return float(cmf.iloc[-1]) if not cmf.empty else 0

    def _calc_accumulation(self):
        if self.df.empty or len(self.df) < 20:
            return 0
        volume = self.df["volume"]
        close = self.df["close"]
        avg_vol = volume.tail(20).mean()
        if avg_vol == 0:
            return 0
        recent = min(10, len(self.df))
        green_days = 0
        vol_up_days = 0
        for i in range(-recent, 0):
            if close.iloc[i] > close.iloc[i - 1]:
                green_days += 1
                if volume.iloc[i] > avg_vol:
                    vol_up_days += 1
        score = (green_days / recent) + (vol_up_days / recent)
        return round(score * 5, 1)

    def _score_momentum(self) -> dict:
        score = 0
        details = []

        macd_cross = self.ind.get("macd_cross", "")
        if "bullish" in str(macd_cross):
            score += 5
            details.append("MACD cắt lên (bullish cross) [+5]")
        elif "bearish" in str(macd_cross):
            details.append("MACD cắt xuống [0]")
        else:
            details.append("MACD chưa cắt [0]")

        macd_val = self.ind.get("macd_standard", 0)
        if macd_val and macd_val > 0:
            score += 4
            details.append(f"MACD > 0 ({macd_val:.2f}) [+4]")
        else:
            details.append("MACD <= 0 [0]")

        macd_hist = self.ind.get("macd_histogram_standard", 0)
        if macd_hist and macd_hist > 0:
            score += 3
            details.append(f"Histogram tăng ({macd_hist:.2f}) [+3]")
        else:
            details.append("Histogram giảm [0]")

        rsi = self.ind.get("rsi_14", 50)
        if rsi and 55 <= rsi <= 70:
            score += 5
            details.append(f"RSI trong vùng 55-70 ({rsi:.1f}) [+5]")
        elif rsi and 50 <= rsi < 55:
            score += 2
            details.append(f"RSI trong vùng 50-55 ({rsi:.1f}) [+2]")
        else:
            details.append(f"RSI = {rsi:.1f} [0]")

        rsi_div = self.ind.get("rsi_divergence", "none")
        if rsi_div and "bearish" not in str(rsi_div):
            score += 3
            details.append("Không có phân kỳ RSI [+3]")
        else:
            details.append("Có phân kỳ RSI [0]")

        self.signals.extend([
            d for d in details if d.endswith("[+5]") or d.endswith("[+4]") or d.endswith("[+3]")
        ])
        return {"diem": score, "toi_da": 20, "chi_tiet": details}

    def _score_price_action(self) -> dict:
        score = 0
        details = []

        # Break nền giá
        if self._detect_breakout():
            score += 5
            details.append("Breakout nền giá [+5]")
        else:
            details.append("Không có breakout [0]")

        # Nến xác nhận
        if self._detect_confirmation_candle():
            score += 3
            details.append("Nến xác nhận [+3]")
        else:
            details.append("Không có nến xác nhận [0]")

        # Không có Gap giảm
        if not self._detect_gap_down():
            score += 2
            details.append("Không có Gap giảm [+2]")
        else:
            details.append("Có Gap giảm [0]")

        # Đóng cửa gần High
        if self._detect_close_near_high():
            score += 2
            details.append("Đóng cửa gần High [+2]")
        else:
            details.append("Không đóng gần High [0]")

        # Vượt kháng cự
        if self._detect_resistance_break():
            score += 3
            details.append("Vượt kháng cự [+3]")
        else:
            details.append("Chưa vượt kháng cự [0]")

        self.signals.extend([
            d for d in details if d.endswith("[+5]") or d.endswith("[+3]")
        ])
        return {"diem": score, "toi_da": 15, "chi_tiet": details}

    def _detect_breakout(self) -> bool:
        if len(self.df) < 30:
            return False
        close = self.df["close"].values
        high = self.df["high"].values[-30:]
        recent_close = close[-5:]
        consolidation_high = max(high[:-5]) if len(high) > 5 else 0
        if consolidation_high == 0:
            return False
        return float(recent_close[-1]) > consolidation_high * 1.01

    def _detect_confirmation_candle(self) -> bool:
        if len(self.df) < 3:
            return False
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        return float(last["close"]) > float(last["open"]) and \
               float(last["close"]) > float(prev["close"]) and \
               float(last["volume"]) > float(self.df["volume"].iloc[-min(5, len(self.df)):-1].mean())

    def _detect_gap_down(self) -> bool:
        if len(self.df) < 2:
            return False
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        return float(last["open"]) < float(prev["close"]) * 0.98

    def _detect_close_near_high(self) -> bool:
        if len(self.df) < 1:
            return False
        last = self.df.iloc[-1]
        hl = float(last["high"]) - float(last["low"])
        if hl == 0:
            return False
        return (float(last["close"]) - float(last["low"])) / hl > 0.7

    def _detect_resistance_break(self) -> bool:
        if len(self.df) < 50:
            return False
        high = self.df["high"].values[-50:]
        recent_close = float(self.df["close"].iloc[-1])
        resistance = np.percentile(high[:-5], 75) if len(high) > 5 else 0
        if resistance == 0:
            return False
        return recent_close > resistance * 1.01

    def _score_relative_strength(self) -> dict:
        score = 0
        details = []
        rs_vnindex = self.ind.get("rs_vnindex", 0)
        if rs_vnindex and rs_vnindex > 0:
            score += 4
            details.append(f"Mạnh hơn VNINDEX (RS={rs_vnindex:.2f}) [+4]")
        else:
            details.append("Yếu hơn VNINDEX [0]")

        rs_sector = self.ind.get("rs_nganh", 0)
        if rs_sector and rs_sector > 0:
            score += 3
            details.append(f"Mạnh hơn ngành (RS={rs_sector:.2f}) [+3]")
        else:
            details.append("Yếu hơn ngành [0]")

        beta = abs(self.ind.get("beta", 0)) if self.ind.get("beta") else 0
        if 0.5 <= beta <= 2.0:
            score += 1
            details.append(f"Beta hợp lý ({beta:.2f}) [+1]")
        else:
            details.append("Beta không phù hợp [0]")

        alpha = self.ind.get("alpha", 0)
        if alpha and alpha > 0:
            score += 2
            details.append(f"Alpha dương ({alpha:.2f}) [+2]")
        else:
            details.append("Alpha không dương [0]")

        self.signals.extend([
            d for d in details if "+" in d and "] +" not in d
        ])
        return {"diem": score, "toi_da": 10, "chi_tiet": details}

    def _compute_penalties(self):
        penalties = []

        macd_div = self.ind.get("macd_divergence", "")
        if "bearish" in str(macd_div):
            penalties.append({"ten": "Phân kỳ MACD", "diem": -5})
            self.signals.append("Cảnh báo: Phân kỳ MACD (-5)")

        rsi_div = self.ind.get("rsi_divergence", "")
        if "bearish" in str(rsi_div):
            penalties.append({"ten": "Phân kỳ RSI", "diem": -5})
            self.signals.append("Cảnh báo: Phân kỳ RSI (-5)")

        vol_ratio = self.ind.get("volume_ratio", 1)
        if vol_ratio < 0.5:
            penalties.append({"ten": "Volume giảm mạnh", "diem": -5})
            self.signals.append("Cảnh báo: Volume giảm mạnh (-5)")

        current_price = float(self.close.iloc[-1]) if len(self.close) > 0 else 0
        ema20 = self._ema(20)
        if ema20 and current_price < ema20 * 0.98:
            penalties.append({"ten": "Mất EMA20", "diem": -5})
            self.signals.append("Cảnh báo: Mất EMA20 (-5)")

        ema50 = self._ema(50)
        if ema50 and current_price < ema50 * 0.98:
            penalties.append({"ten": "Mất EMA50", "diem": -10})
            self.signals.append("Cảnh báo: Mất EMA50 (-10)")

        ema200 = self._ema(200)
        if ema200 and current_price < ema200 * 0.98:
            penalties.append({"ten": "Thủng MA200", "diem": -20})
            self.signals.append("Cảnh báo: Thủng MA200 (-20)")

        if self._check_bos_bearish():
            penalties.append({"ten": "Phá cấu trúc (BOS giảm)", "diem": -15})
            self.signals.append("Cảnh báo: Phá cấu trúc BOS giảm (-15)")

        if self._detect_gap_down():
            penalties.append({"ten": "Mất nền giá", "diem": -10})
            self.signals.append("Cảnh báo: Mất nền giá (-10)")

        self.penalties = penalties


def compute_smart_money_patterns(df: pd.DataFrame) -> dict:
    result = {}

    # BOS - Break of Structure
    result["bos"] = _detect_bos(df)
    result["bos_tang"] = _detect_bos_bullish(df)

    # CHOCH - Change of Character
    result["choch"] = _detect_choch(df)

    # Order Block
    result["order_block"] = _detect_order_block(df)
    result["order_block_signal"] = result["order_block"]["signal"] if result["order_block"] else "none"

    # FVG - Fair Value Gap
    result["fvg"] = _detect_fvg(df)
    result["fvg_signal"] = result["fvg"]["signal"] if result["fvg"] else "none"

    # Liquidity Sweep
    result["liquidity_sweep"] = _detect_liquidity_sweep(df)

    # Breaker Block
    result["breaker_block"] = _detect_breaker_block(df)

    # Mitigation Block
    result["mitigation_block"] = _detect_mitigation_block(df)

    # Premium/Discount Zone
    result["premium_discount"] = _detect_premium_discount_zone(df)

    # SuperTrend
    result["supertrend"] = _compute_supertrend(df)

    # ATR
    result["atr"] = _compute_atr(df)

    # Stochastic RSI
    stoch_rsi = _compute_stoch_rsi(df)
    result.update(stoch_rsi)

    # DI+/DI-
    di = _compute_di(df)
    result.update(di)

    # RS vs VNINDEX (placeholder - needs external data)
    result["rs_vnindex"] = _compute_rs_vnindex(df)

    # Higher High / Higher Low
    result["higher_high"] = _detect_higher_high(df)
    result["higher_low"] = _detect_higher_low(df)

    # Volume Weighted ATR
    result["vwap_20"] = _compute_vwap(df)

    # CMF
    result["cmf"] = _calc_cmf(df)

    # Key level distance
    result["distance_to_ath"] = _distance_to_ath(df)
    result["distance_to_52w_high"] = _distance_to_52w_high(df)
    result["distance_to_ema20"] = _distance_to_ma(df, 20)
    result["distance_to_ema50"] = _distance_to_ma(df, 50)
    result["distance_to_ema200"] = _distance_to_ma(df, 200)

    return result


def _compute_di(df: pd.DataFrame) -> dict:
    if len(df) < 15:
        return {"plus_di": 0, "minus_di": 0}
    high = df["high"]
    low = df["low"]
    close = df["close"]
    period = 14
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    up_move = high.diff()
    down_move = low.diff() * -1
    plus_dm = ((up_move > down_move) & (up_move > 0)).astype(float) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)).astype(float) * down_move
    plus_di = 100 * plus_dm.rolling(period).sum() / atr
    minus_di = 100 * minus_dm.rolling(period).sum() / atr
    return {
        "plus_di": round(float(plus_di.iloc[-1]), 2) if not plus_di.empty else 0,
        "minus_di": round(float(minus_di.iloc[-1]), 2) if not minus_di.empty else 0,
    }


def _compute_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> dict:
    if len(df) < period + 1:
        return {"supertrend": 0, "supertrend_signal": "neutral"}
    high = df["high"]
    low = df["low"]
    close = df["close"]
    hl = (high + low) / 2
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    upper_band = hl + multiplier * atr
    lower_band = hl - multiplier * atr
    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=float)
    for i in range(period, len(df)):
        if i == period:
            supertrend.iloc[i] = upper_band.iloc[i]
            direction.iloc[i] = -1
        else:
            if close.iloc[i - 1] <= supertrend.iloc[i - 1]:
                supertrend.iloc[i] = upper_band.iloc[i]
                direction.iloc[i] = -1
            else:
                supertrend.iloc[i] = lower_band.iloc[i]
                direction.iloc[i] = 1
            if direction.iloc[i] == 1 and supertrend.iloc[i] < supertrend.iloc[i - 1]:
                supertrend.iloc[i] = supertrend.iloc[i - 1]
            if direction.iloc[i] == -1 and supertrend.iloc[i] > supertrend.iloc[i - 1]:
                supertrend.iloc[i] = supertrend.iloc[i - 1]
        if close.iloc[i] > supertrend.iloc[i] and direction.iloc[i] == -1:
            direction.iloc[i] = 1
        elif close.iloc[i] < supertrend.iloc[i] and direction.iloc[i] == 1:
            direction.iloc[i] = -1
    current_st = float(supertrend.iloc[-1]) if not supertrend.empty else 0
    current_dir = int(direction.iloc[-1]) if not direction.empty else 0
    sig = "uptrend" if current_dir == 1 else "downtrend" if current_dir == -1 else "neutral"
    return {"supertrend": round(current_st, 2), "supertrend_signal": sig}


def _compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < period + 1:
        return 0
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return round(float(atr.iloc[-1]), 2) if not atr.empty else 0


def _compute_stoch_rsi(df: pd.DataFrame, period: int = 14, k: int = 3, d: int = 3) -> dict:
    if len(df) < period + k + d:
        return {"stoch_rsi_k": 50, "stoch_rsi_d": 50, "stoch_rsi_signal": "neutral"}
    close = df["close"]
    rsi_series = close.diff().clip(lower=0).ewm(span=period).mean() / \
                 (-close.diff().clip(upper=0).ewm(span=period).mean() + 1e-10)
    rsi_series = 100 - 100 / (1 + rsi_series)
    min_rsi = rsi_series.rolling(period).min()
    max_rsi = rsi_series.rolling(period).max()
    stoch = 100 * (rsi_series - min_rsi) / (max_rsi - min_rsi + 1e-10)
    k_line = stoch.rolling(k).mean()
    d_line = k_line.rolling(d).mean()
    k_val = float(k_line.iloc[-1]) if not k_line.empty else 50
    d_val = float(d_line.iloc[-1]) if not d_line.empty else 50
    sig = "oversold" if k_val < 20 else "overbought" if k_val > 80 else "neutral"
    return {"stoch_rsi_k": round(k_val, 2), "stoch_rsi_d": round(d_val, 2), "stoch_rsi_signal": sig}


def _compute_vwap(df: pd.DataFrame) -> float:
    if df.empty:
        return 0
    typical = (df["high"] + df["low"] + df["close"]) / 3
    vwap_20 = (typical * df["volume"]).rolling(20).sum() / df["volume"].rolling(20).sum()
    return round(float(vwap_20.iloc[-1]), 2) if not vwap_20.empty else 0


def _detect_bos(df: pd.DataFrame) -> str:
    if len(df) < 30:
        return "none"
    high = df["high"].values
    low = df["low"].values
    recent_high = max(high[-5:])
    prior_high = max(high[-15:-5])
    recent_low = min(low[-5:])
    prior_low = min(low[-15:-5])
    if recent_high > prior_high:
        return "BOS tang"
    if recent_low < prior_low:
        return "BOS giam"
    return "none"


def _detect_bos_bullish(df: pd.DataFrame) -> bool:
    if len(df) < 30:
        return False
    high = df["high"].values
    recent = max(high[-5:])
    prior = max(high[-15:-5])
    return recent > prior


def _detect_choch(df: pd.DataFrame) -> str:
    if len(df) < 40:
        return "none"
    high = df["high"].values
    low = df["low"].values
    mid1 = high[-20:-10].max() if len(high) >= 20 else 0
    mid2 = low[-10:].min() if len(low) >= 10 else 0
    mid3 = high[-15:-5].max() if len(high) >= 15 else 0
    if mid1 and mid2 and high[-1] > mid1 and low[-1] > mid2:
        return "CHOCH tang"
    if mid3 and low[-1] < mid2:
        return "CHOCH giam"
    return "none"


def _detect_order_block(df: pd.DataFrame) -> dict:
    if len(df) < 10:
        return {"found": False, "signal": "none"}
    close = df["close"].values
    open_ = df["open"].values
    high = df["high"].values
    low = df["low"].values
    for i in range(-10, -1):
        body = abs(close[i] - open_[i])
        range_ = high[i] - low[i]
        if range_ == 0 or body == 0:
            continue
        wick_ratio = (range_ - body) / range_
        if wick_ratio < 0.3:
            if close[i] > open_[i]:
                next_change = (close[i + 1] - open_[i + 1]) if i + 1 < len(close) else 0
                if next_change > 0:
                    return {"found": True, "signal": "bullish", "index": i, "price": round(float(high[i]), 2)}
            else:
                next_change = (close[i + 1] - open_[i + 1]) if i + 1 < len(close) else 0
                if next_change < 0:
                    return {"found": True, "signal": "bearish", "index": i, "price": round(float(low[i]), 2)}
    return {"found": False, "signal": "none"}


def _detect_fvg(df: pd.DataFrame) -> dict:
    if len(df) < 5:
        return {"found": False, "signal": "none"}
    high = df["high"].values
    low = df["low"].values
    for i in range(-5, -1):
        if i + 2 >= len(high):
            continue
        if low[i + 2] > high[i]:
            return {"found": True, "signal": "bullish", "gap_high": round(float(low[i + 2]), 2), "gap_low": round(float(high[i]), 2)}
        if high[i + 2] < low[i]:
            return {"found": True, "signal": "bearish", "gap_low": round(float(high[i + 2]), 2), "gap_high": round(float(low[i]), 2)}
    return {"found": False, "signal": "none"}


def _detect_liquidity_sweep(df: pd.DataFrame) -> str:
    if len(df) < 30:
        return "none"
    high = df["high"].values
    low = df["low"].values
    swing_high = max(high[-20:-5]) if len(high) > 5 else 0
    swing_low = min(low[-20:-5]) if len(low) > 5 else 0
    recent_high = max(high[-5:])
    recent_low = min(low[-5:])
    if recent_high > swing_high and float(df["close"].iloc[-1]) < recent_high:
        return "Liquidity Sweep bearish"
    if recent_low < swing_low and float(df["close"].iloc[-1]) > recent_low:
        return "Liquidity Sweep bullish"
    return "none"


def _detect_breaker_block(df: pd.DataFrame) -> str:
    if len(df) < 15:
        return "none"
    ob = _detect_order_block(df)
    if not ob["found"]:
        return "none"
    close_val = float(df["close"].iloc[-1])
    ob_price = ob["price"]
    if ob["signal"] == "bullish" and close_val < ob_price * 0.98:
        return "Breaker Block bearish"
    if ob["signal"] == "bearish" and close_val > ob_price * 1.02:
        return "Breaker Block bullish"
    return "none"


def _detect_mitigation_block(df: pd.DataFrame) -> str:
    if len(df) < 20:
        return "none"
    ob = _detect_order_block(df)
    if not ob["found"]:
        return "none"
    close_val = float(df["close"].iloc[-1])
    ob_price = ob["price"]
    tolerance = ob_price * 0.01
    if abs(close_val - ob_price) <= tolerance:
        return f"Mitigation Block {ob['signal']}"
    return "none"


def _detect_premium_discount_zone(df: pd.DataFrame) -> str:
    if df.empty or len(df) < 20:
        return "neutral"
    vwap = _compute_vwap(df)
    close = float(df["close"].iloc[-1])
    if vwap == 0:
        return "neutral"
    pct = (close - vwap) / vwap * 100
    if pct > 3:
        return "premium"
    if pct < -3:
        return "discount"
    return "neutral"


def _detect_higher_high(df: pd.DataFrame) -> bool:
    if len(df) < 30:
        return False
    high = df["high"].values
    recent = max(high[-10:])
    prior = max(high[-20:-10])
    return recent > prior


def _detect_higher_low(df: pd.DataFrame) -> bool:
    if len(df) < 30:
        return False
    low = df["low"].values
    recent = min(low[-10:])
    prior = min(low[-20:-10])
    return recent > prior


def _compute_rs_vnindex(df: pd.DataFrame) -> float:
    if len(df) < 21:
        return 0
    close = df["close"].values
    ret_stock = (close[-1] - close[-21]) / close[-21] * 100 if close[-21] != 0 else 0
    return round(ret_stock, 2)


def _distance_to_ath(df: pd.DataFrame) -> float:
    if df.empty:
        return 0
    high = df["high"].values
    ath = max(high)
    close = float(df["close"].iloc[-1])
    if ath == 0:
        return 0
    return round((ath - close) / ath * 100, 2)


def _distance_to_52w_high(df: pd.DataFrame) -> float:
    if len(df) < 252:
        lookback = len(df)
    else:
        lookback = 252
    high = df["high"].values[-lookback:]
    max_52w = max(high)
    close = float(df["close"].iloc[-1])
    if max_52w == 0:
        return 0
    return round((max_52w - close) / max_52w * 100, 2)


def _distance_to_ma(df: pd.DataFrame, period: int) -> float:
    if len(df) < period:
        return 0
    ma = df["close"].rolling(period).mean().iloc[-1]
    close = float(df["close"].iloc[-1])
    if ma == 0:
        return 0
    return round((close - ma) / ma * 100, 2)


def _calc_cmf(df: pd.DataFrame) -> float:
    if df.empty or len(df) < 21:
        return 0
    h = df["high"]
    l = df["low"]
    c = df["close"]
    v = df["volume"]
    mfm = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    mfm = mfm.fillna(0)
    mfv = mfm * v
    cmf = mfv.rolling(20).sum() / v.rolling(20).sum()
    return round(float(cmf.iloc[-1]), 4) if not cmf.empty else 0


def compute_position_score(indicators: dict) -> dict:
    scores = {}
    for key in ["distance_to_ema20", "distance_to_ema50", "distance_to_ema200",
                "distance_to_ath", "distance_to_52w_high"]:
        val = indicators.get(key, 0)
        scores[key] = val
    if all(v is not None for v in [scores.get("distance_to_ema20"),
                                    scores.get("distance_to_ema50"),
                                    scores.get("distance_to_ema200")]):
        avg = (abs(scores["distance_to_ema20"]) + abs(scores["distance_to_ema50"]) +
               abs(scores["distance_to_ema200"])) / 3
        if avg < 3:
            scores["position_assessment"] = "tich_luy"
        elif avg < 10:
            scores["position_assessment"] = "on_dinh"
        elif avg < 20:
            scores["position_assessment"] = "nong"
        else:
            scores["position_assessment"] = "qua_nong"
    scores["con_du_dia"] = max(0, 100 - (abs(scores.get("distance_to_ath", 0)) * 2 +
                                          abs(scores.get("distance_to_52w_high", 0))))
    return scores
