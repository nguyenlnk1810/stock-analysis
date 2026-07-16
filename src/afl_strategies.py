import pandas as pd
import numpy as np
import json
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        if isinstance(obj, np.bool_): return bool(obj)
        return super().default(obj)


def _to_python(val):
    if isinstance(val, (np.integer,)): return int(val)
    if isinstance(val, (np.floating,)): return float(val)
    if isinstance(val, np.ndarray): return val.tolist()
    if isinstance(val, np.bool_): return bool(val)
    return val


@dataclass
class AFLSignal:
    symbol: str
    strategy_name: str
    signal: str  # MUA or BAN
    score: float
    current_price: float
    change_pct: float
    volume_ratio: float
    rsi: float
    mfi: float
    extra: Dict = field(default_factory=dict)


class AFLStrategyBase:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.close = df["close"].values if not df.empty else np.array([])
        self.high = df["high"].values if not df.empty else np.array([])
        self.low = df["low"].values if not df.empty else np.array([])
        self.volume = df["volume"].values if not df.empty else np.array([])
        self.open_p = df["open"].values if not df.empty else np.array([])
        self.length = len(df)

    def _sma(self, arr, period):
        s = pd.Series(arr)
        return s.rolling(period).mean().values

    def _ema(self, arr, period):
        return pd.Series(arr).ewm(span=period, adjust=False).mean().values

    def _rsi(self, arr, period=14):
        s = pd.Series(arr)
        delta = s.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs)).values

    def _rsi_array(self, arr, period=14):
        return self._rsi(arr, period)

    def _hhv(self, arr, period):
        return pd.Series(arr).rolling(period).max().values

    def _llv(self, arr, period):
        return pd.Series(arr).rolling(period).min().values

    def _macd(self, arr, fast=12, slow=26, signal=9):
        s = pd.Series(arr)
        ema_f = s.ewm(span=fast, adjust=False).mean()
        ema_s = s.ewm(span=slow, adjust=False).mean()
        macd = ema_f - ema_s
        sig = macd.ewm(span=signal, adjust=False).mean()
        hist = macd - sig
        return macd.values, sig.values, hist.values


class PsychIndexStrategy(AFLStrategyBase):
    """Tam ly dam dong - PsychIndex strategy"""
    def __init__(self, df: pd.DataFrame, lookback=12, oversold=25, overbought=75):
        super().__init__(df)
        self.lookback = lookback
        self.oversold = oversold
        self.overbought = overbought

    def compute(self):
        if self.length < self.lookback + 5:
            return np.full(self.length, np.nan), np.full(self.length, 0)

        up_day = np.zeros(self.length)
        up_day[1:] = (self.close[1:] > self.close[:-1]).astype(float)

        psych = np.full(self.length, np.nan)
        for i in range(self.lookback, self.length):
            psych[i] = 100 * np.sum(up_day[i - self.lookback + 1:i + 1]) / self.lookback

        signals = np.zeros(self.length)
        for i in range(1, self.length):
            if not np.isnan(psych[i]) and not np.isnan(psych[i - 1]):
                if psych[i - 1] > self.oversold and psych[i] <= self.oversold:
                    signals[i] = 1
                elif psych[i - 1] < self.overbought and psych[i] >= self.overbought:
                    signals[i] = -1

        return psych, signals


class ZangerVolumeStrategy(AFLStrategyBase):
    """Zanger Volume Ratio + Pivot Pocket Volume strategy"""
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)

    def compute(self):
        if self.length < 55:
            return np.zeros(self.length)

        vdn = np.where(self.close < np.roll(self.close, 1), self.volume, 0)
        vup = np.where(self.close > np.roll(self.close, 1), self.volume, 0)
        vdn[0] = 0
        vup[0] = 0

        hv10 = self._hhv(vdn, 10)
        hvup10 = self._hhv(vup, 10)
        v50 = self._sma(self.volume, 50)
        vol_ratio = self.volume / (v50 + 1e-10) * 100

        signals = np.zeros(self.length)
        for i in range(20, self.length):
            up_day = self.close[i] > self.close[i - 1]
            down_day = self.close[i] < self.close[i - 1]

            pivot_pocket = up_day and self.volume[i] > hv10[i]
            max_vol_down = down_day and self.volume[i] > hvup10[i]
            zanger_buy = vol_ratio[i] > 110

            if pivot_pocket or zanger_buy:
                if self.close[i] > self._sma(self.close, 20)[i] * 1.01:
                    signals[i] = 1
            if max_vol_down:
                signals[i] = -1

        return vol_ratio, signals


class RSVNINDEXStrategy(AFLStrategyBase):
    """Relative Strength vs VNINDEX strategy"""
    def __init__(self, df: pd.DataFrame, index_df: pd.DataFrame = None):
        super().__init__(df)
        self.index_df = index_df

    def compute(self, index_close=None):
        if self.length < 66:
            return np.full(self.length, np.nan), np.zeros(self.length)

        if index_close is None and self.index_df is not None:
            index_close = self.index_df["close"].values

        if index_close is None or len(index_close) < self.length:
            idx_min = min(len(index_close) if index_close is not None else 0, self.length)
            ref_close = np.full(self.length, np.nan)
            if index_close is not None:
                ref_close[-idx_min:] = index_close[-idx_min:]
            ref_close[:self.length - idx_min] = self.close[:self.length - idx_min]
        else:
            ref_close = index_close[:self.length]

        rs_line = np.full(self.length, np.nan)
        rs_high = np.full(self.length, 0)
        for i in range(1, self.length):
            if ref_close[i] > 0:
                rs_line[i] = self.close[i] / ref_close[i] * 1000

        for i in range(65, self.length):
            if not np.isnan(rs_line[i]):
                window = rs_line[i - 64:i + 1]
                if np.nanmax(window) == rs_line[i]:
                    rs_high[i] = 1

        signals = np.zeros(self.length)
        for i in range(1, self.length):
            if rs_high[i] == 1 and self.volume[i] > 100000 and self.close[i] * self.volume[i] > 3000000:
                signals[i] = 1

        return rs_line, signals


class MA20CrossoverStrategy(AFLStrategyBase):
    """MA20/MA50 crossover (simplified from MA 20 50 .afl)"""
    def __init__(self, df: pd.DataFrame, fast_period=15, slow_period=30):
        super().__init__(df)
        self.fast_period = fast_period
        self.slow_period = slow_period

    def compute(self):
        if self.length < self.slow_period + 10:
            return np.zeros(self.length)

        ma_fast = self._sma(self.close, self.fast_period)
        ma_slow = self._sma(self.close, self.slow_period)

        signals = np.zeros(self.length)
        for i in range(2, self.length):
            if ma_fast[i - 1] <= ma_slow[i - 1] and ma_fast[i] > ma_slow[i]:
                if self.volume[i] > self._sma(self.volume, 20)[i] * 1.2:
                    signals[i] = 1
            elif ma_fast[i - 1] >= ma_slow[i - 1] and ma_fast[i] < ma_slow[i]:
                signals[i] = -1

        return ma_fast, signals


class ZigZagStrategy(AFLStrategyBase):
    """Zig Zag pivot strategy (from Luot It.afl)"""
    def __init__(self, df: pd.DataFrame, pct_change=6.0):
        super().__init__(df)
        self.pct_change = pct_change

    def compute(self):
        if self.length < 30:
            return np.full(self.length, np.nan), np.zeros(self.length)

        zz = np.full(self.length, np.nan)
        zz[0] = self.close[0]
        last_pivot_idx = 0
        direction = 0

        for i in range(1, self.length):
            if direction == 0:
                if self.close[i] >= zz[last_pivot_idx] * (1 + self.pct_change / 100):
                    zz[i] = self.close[i]
                    direction = 1
                elif self.close[i] <= zz[last_pivot_idx] * (1 - self.pct_change / 100):
                    zz[i] = self.close[i]
                    direction = -1
                else:
                    zz[i] = zz[last_pivot_idx]
            elif direction == 1:
                if self.close[i] > zz[last_pivot_idx]:
                    zz[i] = self.close[i]
                    zz[last_pivot_idx] = np.nan
                elif self.close[i] <= zz[last_pivot_idx] * (1 - self.pct_change / 100):
                    zz[i] = self.close[i]
                    direction = -1
                else:
                    zz[i] = zz[last_pivot_idx]
            elif direction == -1:
                if self.close[i] < zz[last_pivot_idx]:
                    zz[i] = self.close[i]
                    zz[last_pivot_idx] = np.nan
                elif self.close[i] >= zz[last_pivot_idx] * (1 + self.pct_change / 100):
                    zz[i] = self.close[i]
                    direction = 1
                else:
                    zz[i] = zz[last_pivot_idx]
            last_pivot_idx = i

        roc_zz = np.diff(zz, prepend=zz[0])
        signals = np.zeros(self.length)
        for i in range(2, self.length):
            if roc_zz[i - 1] < 0 and roc_zz[i] > 0 and not np.isnan(zz[i]):
                signals[i] = 1
            elif roc_zz[i - 1] > 0 and roc_zz[i] < 0 and not np.isnan(zz[i]):
                signals[i] = -1

        return zz, signals


class ScoringStrategy(AFLStrategyBase):
    """Composite scoring strategy (from Giu dai han.afl)"""
    def __init__(self, df: pd.DataFrame, index_df: pd.DataFrame = None):
        super().__init__(df)
        self.index_df = index_df

    def compute(self, index_close=None):
        if self.length < 30:
            return np.full(self.length, np.nan), np.zeros(self.length)

        rsi_vol = self._rsi_array(self.volume, 14)
        rsi_close = self._rsi_array(self.close, 14)
        rsi_low = self._rsi_array(self.low, 14)
        rsi_high = self._rsi_array(self.high, 14)

        obv = np.zeros(self.length)
        for i in range(1, self.length):
            if self.close[i] > self.close[i - 1]:
                obv[i] = obv[i - 1] + self.volume[i]
            elif self.close[i] < self.close[i - 1]:
                obv[i] = obv[i - 1] - self.volume[i]
            else:
                obv[i] = obv[i - 1]
        rsi_obv = self._rsi_array(obv, 14)

        if index_close is None and self.index_df is not None:
            index_close = self.index_df["close"].values

        rs = np.full(self.length, np.nan)
        if index_close is not None:
            min_len = min(len(index_close), self.length)
            for i in range(min_len):
                if index_close[i] > 0:
                    rs[i] = self.close[i] / index_close[i] * 1000
        else:
            vnindex = self.close.copy()
            rs = np.full(self.length, 50.0)

        rsi_rs = self._rsi_array(np.nan_to_num(rs, nan=50.0), 14)

        total_score = np.full(self.length, np.nan)
        for i in range(20, self.length):
            s = (rsi_vol[i] + rsi_obv[i] * 2 + rsi_close[i] * 2 + rsi_low[i] + rsi_high[i] + rsi_rs[i]) / 8
            total_score[i] = s * 10 / 100

        signals = np.zeros(self.length)
        for i in range(2, self.length):
            if not np.isnan(total_score[i]) and not np.isnan(total_score[i - 1]):
                if total_score[i - 1] <= 5 and total_score[i] > 5:
                    signals[i] = 1
                elif total_score[i - 1] > 5 and total_score[i] <= 5:
                    signals[i] = -1

        return total_score, signals


class IchimokuStrategy(AFLStrategyBase):
    """Ichimoku Kinko Hyo strategy (from 3 may ichi.afl)"""
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)

    def compute(self):
        if self.length < 52:
            return np.zeros(self.length)

        tenkan = (self._hhv(self.high, 9) + self._llv(self.low, 9)) / 2
        kijun = (self._hhv(self.high, 26) + self._llv(self.low, 26)) / 2
        senkou_a = (np.roll(tenkan, 26) + np.roll(kijun, 26)) / 2
        senkou_b = np.roll((self._hhv(self.high, 52) + self._llv(self.low, 52)) / 2, 26)
        senkou_a[:26] = np.nan
        senkou_b[:26] = np.nan

        signals = np.zeros(self.length)
        for i in range(1, self.length):
            if not np.isnan(tenkan[i]) and not np.isnan(kijun[i]):
                if tenkan[i - 1] < kijun[i - 1] and tenkan[i] > kijun[i]:
                    if not np.isnan(senkou_a[i]) and not np.isnan(senkou_b[i]):
                        if self.close[i] > max(senkou_a[i], senkou_b[i]):
                            signals[i] = 1
                elif tenkan[i - 1] > kijun[i - 1] and tenkan[i] < kijun[i]:
                    if not np.isnan(senkou_a[i]) and not np.isnan(senkou_b[i]):
                        if self.close[i] < min(senkou_a[i], senkou_b[i]):
                            signals[i] = -1

        return tenkan, signals


class MAIStrategy(AFLStrategyBase):
    """MAI (MA Impulse) momentum strategy from Tam ly dam dong"""
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)

    def compute(self):
        if self.length < 30:
            return np.full(self.length, np.nan), np.zeros(self.length)

        bias6 = ((self.close - self._sma(self.close, 6)) / (self._sma(self.close, 6) + 1e-10)) * 100
        bias12 = ((self.close - self._sma(self.close, 12)) / (self._sma(self.close, 12) + 1e-10)) * 100
        bias24 = ((self.close - self._sma(self.close, 24)) / (self._sma(self.close, 24) + 1e-10)) * 100
        mm = (bias6 + 2 * bias12 + 3 * bias24) / 6
        mn = self._sma(mm, 5)

        signals = np.zeros(self.length)
        for i in range(2, self.length):
            if not np.isnan(mn[i]) and not np.isnan(mn[i - 1]):
                if mn[i - 1] < -5 and mn[i] >= -5:
                    signals[i] = 1
                elif mn[i - 1] > 5 and mn[i] <= 5:
                    signals[i] = -1

        return mn, signals


class VolumePocketStrategy(AFLStrategyBase):
    """Simple volume pocket strategy from MA 20 50 .afl"""
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)

    def compute(self):
        if self.length < 55:
            return np.zeros(self.length)

        vdn = np.where(self.close < np.roll(self.close, 1), self.volume, 0)
        vup = np.where(self.close > np.roll(self.close, 1), self.volume, 0)
        vdn[0] = 0
        vup[0] = 0

        hv10 = self._hhv(vdn, 10)
        hvup10 = self._hhv(vup, 10)
        v50 = self._sma(self.volume, 50)
        vol_ratio = self.volume / (v50 + 1e-10) * 100

        signals = np.zeros(self.length)
        for i in range(20, self.length):
            up_day = self.close[i] > self.close[i - 1]
            down_day = self.close[i] < self.close[i - 1]
            ma20 = self._sma(self.close, 20)[i]
            ma50 = self._sma(self.close, 50)[i]

            pivot_pocket_buy = up_day and self.volume[i] < hv10[i] and self.close[i] > ma20
            pivot_pocket_strong = up_day and self.volume[i] > hv10[i] and self.close[i] > ma50
            max_vol_sell = down_day and self.volume[i] > hvup10[i]

            if pivot_pocket_buy or pivot_pocket_strong:
                signals[i] = 1
            if max_vol_sell:
                signals[i] = -1

        return vol_ratio, signals


def backtest_afl_strategy(df: pd.DataFrame, strategy_name: str, index_df: pd.DataFrame = None) -> Dict:
    """Run backtest for a specific AFL strategy and return performance metrics."""
    strategies = {
        "PsychIndex": lambda: PsychIndexStrategy(df, lookback=12, oversold=25, overbought=75),
        "ZangerVolume": lambda: ZangerVolumeStrategy(df),
        "RSVNINDEX": lambda: RSVNINDEXStrategy(df, index_df),
        "MA20Crossover": lambda: MA20CrossoverStrategy(df),
        "ZigZag": lambda: ZigZagStrategy(df),
        "Scoring": lambda: ScoringStrategy(df, index_df),
        "Ichimoku": lambda: IchimokuStrategy(df),
        "MAI": lambda: MAIStrategy(df),
        "VolumePocket": lambda: VolumePocketStrategy(df),
    }

    if strategy_name not in strategies:
        raise ValueError(f"Unknown strategy: {strategy_name}. Choose from {list(strategies.keys())}")

    strat = strategies[strategy_name]()
    _, signals = strat.compute()

    close = df["close"].values
    trades = []
    in_position = False
    entry_price = 0
    entry_idx = 0
    capital = 1.0
    equity = [1.0]

    warmup = 60
    for i in range(warmup, len(df)):
        if in_position:
            exit_signal = False
            exit_reason = ""
            pnl_pct = (close[i] - entry_price) / entry_price * 100

            if signals[i] == -1:
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
                    "entry_date": str(df["date"].iloc[entry_idx]) if "date" in df.columns else str(entry_idx),
                    "entry_price": entry_price,
                    "exit_date": str(df["date"].iloc[i]) if "date" in df.columns else str(i),
                    "exit_price": close[i],
                    "pnl_pct": round(pnl_pct - 0.25, 2),
                    "bars_held": i - entry_idx,
                    "exit_reason": exit_reason,
                }
                trades.append(trade)
                capital *= (1 + trade["pnl_pct"] / 100)
                in_position = False

        if not in_position:
            if signals[i] == 1:
                entry_price = close[i]
                entry_idx = i
                in_position = True

        equity.append(capital)

    if in_position and trades:
        trades[-1]["exit_price"] = close[-1]
        trades[-1]["pnl_pct"] = round((close[-1] - trades[-1]["entry_price"]) / trades[-1]["entry_price"] * 100 - 0.25, 2)
        if "date" in df.columns:
            trades[-1]["exit_date"] = str(df["date"].iloc[-1])

    total_trades = len(trades)
    if total_trades == 0:
        return {
            "strategy": strategy_name,
            "total_trades": 0,
            "win_rate": 0,
            "total_return_pct": 0,
            "max_drawdown_pct": 0,
            "avg_trade_pct": 0,
            "profit_factor": 0,
        }

    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
    total_return = (capital - 1) * 100

    equity_arr = np.array(equity)
    peak = np.maximum.accumulate(equity_arr)
    drawdown = (peak - equity_arr) / peak
    max_dd = np.max(drawdown) * 100

    gross_profit = sum(t["pnl_pct"] for t in wins)
    gross_loss = abs(sum(t["pnl_pct"] for t in losses))
    profit_factor = gross_profit / max(gross_loss, 0.01)

    avg_trade = np.mean([t["pnl_pct"] for t in trades])

    return {
        "strategy": strategy_name,
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 2),
        "total_return_pct": round(total_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "avg_trade_pct": round(avg_trade, 2),
        "avg_win_pct": round(np.mean([t["pnl_pct"] for t in wins]), 2) if wins else 0,
        "avg_loss_pct": round(np.mean([t["pnl_pct"] for t in losses]), 2) if losses else 0,
        "profit_factor": round(profit_factor, 2),
        "trades": trades,
        "equity_curve": equity,
    }


def run_all_afl_backtests(df: pd.DataFrame, index_df: pd.DataFrame = None) -> List[Dict]:
    """Run all AFL strategies and return ranked results."""
    strategy_names = ["PsychIndex", "ZangerVolume", "RSVNINDEX", "MA20Crossover", "ZigZag", "Scoring", "Ichimoku", "MAI", "VolumePocket"]
    results = []
    for name in strategy_names:
        try:
            result = backtest_afl_strategy(df, name, index_df)
            results.append(result)
        except Exception as e:
            results.append({"strategy": name, "error": str(e), "total_trades": 0, "win_rate": 0})
    results.sort(key=lambda r: (r.get("total_trades", 0) >= 5) * r.get("win_rate", 0), reverse=True)
    return results


def compute_afl_signals_for_current(df: pd.DataFrame, index_df: pd.DataFrame = None) -> Dict:
    """Compute current AFL signals for the latest bar across all strategies.
    Uses both crossover signals and zone-based signals for more comprehensive coverage."""
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    vol = df["volume"].values
    current_price = float(close[-1]) if len(close) > 0 else 0
    current_vol = float(vol[-1]) if len(vol) > 0 else 0
    vol_ma20 = float(pd.Series(vol).rolling(20).mean().iloc[-1]) if len(df) >= 20 else 1
    vol_ratio = current_vol / max(vol_ma20, 1)
    price_above_ma20 = current_price > float(pd.Series(close).rolling(20).mean().iloc[-1]) if len(close) >= 20 else False
    price_above_ma50 = current_price > float(pd.Series(close).rolling(50).mean().iloc[-1]) if len(close) >= 50 else False
    rsi_val = float(pd.Series(close).diff().clip(lower=0).ewm(span=14).mean().iloc[-1] / \
             (-pd.Series(close).diff().clip(upper=0).ewm(span=14).mean().iloc[-1] + 1e-10))
    rsi_val = float(100 - 100 / (1 + rsi_val)) if not pd.isna(rsi_val) else 50

    signals_found = {"MUA": 0, "BAN": 0, "NEUTRAL": 0}
    buy_reasons = []
    sell_reasons = []
    details = {}
    combined_score = 0

    # --- PsychIndex zone-based ---
    try:
        ps = PsychIndexStrategy(df)
        psych, _ = ps.compute()
        last_psych = psych[-1] if len(psych) > 0 and not np.isnan(psych[-1]) else 50
        if last_psych <= 25:
            signals_found["MUA"] += 1
            buy_reasons.append(f"PsychIndex quá bán ({last_psych:.0f})")
            combined_score += 2
            details["PsychIndex"] = {"signal": "MUA", "value": round(last_psych, 1)}
        elif last_psych >= 75:
            signals_found["BAN"] += 1
            sell_reasons.append(f"PsychIndex quá mua ({last_psych:.0f})")
            combined_score -= 2
            details["PsychIndex"] = {"signal": "BAN", "value": round(last_psych, 1)}
        else:
            details["PsychIndex"] = {"signal": "NEUTRAL", "value": round(last_psych, 1)}
            signals_found["NEUTRAL"] += 1
    except Exception as e:
        details["PsychIndex"] = {"signal": "ERROR", "error": str(e)[:30]}

    # --- MAI zone-based ---
    try:
        mai = MAIStrategy(df)
        mn, _ = mai.compute()
        last_mn = mn[-1] if len(mn) > 0 and not np.isnan(mn[-1]) else 0
        if last_mn < -5:
            signals_found["MUA"] += 1
            buy_reasons.append(f"MAI quá bán (MN={last_mn:.1f})")
            combined_score += 2
            details["MAI"] = {"signal": "MUA", "value": round(last_mn, 1)}
        elif last_mn > 5:
            signals_found["BAN"] += 1
            sell_reasons.append(f"MAI quá mua (MN={last_mn:.1f})")
            combined_score -= 2
            details["MAI"] = {"signal": "BAN", "value": round(last_mn, 1)}
        else:
            details["MAI"] = {"signal": "NEUTRAL", "value": round(last_mn, 1)}
            signals_found["NEUTRAL"] += 1
    except Exception as e:
        details["MAI"] = {"signal": "ERROR", "error": str(e)[:30]}

    # --- ZangerVolume ---
    try:
        zv = ZangerVolumeStrategy(df)
        vr, sigs = zv.compute()
        last_sig = sigs[-1] if len(sigs) > 0 else 0
        last_vr = vr[-1] if len(vr) > 0 else 0
        if last_sig == 1 or last_vr > 150:
            signals_found["MUA"] += 1
            buy_reasons.append(f"Zanger Volume mạnh (VR={last_vr:.0f}%)")
            combined_score += 1
            details["ZangerVolume"] = {"signal": "MUA", "value": round(last_vr, 1)}
        elif last_sig == -1:
            signals_found["BAN"] += 1
            sell_reasons.append(f"Zanger Volume yếu (VR={last_vr:.0f}%)")
            combined_score -= 1
            details["ZangerVolume"] = {"signal": "BAN", "value": round(last_vr, 1)}
        else:
            details["ZangerVolume"] = {"signal": "NEUTRAL", "value": round(last_vr, 1)}
            signals_found["NEUTRAL"] += 1
    except Exception as e:
        details["ZangerVolume"] = {"signal": "ERROR", "error": str(e)[:30]}

    # --- RS VNINDEX ---
    try:
        rs = RSVNINDEXStrategy(df, index_df)
        rs_line, sigs = rs.compute()
        last_sig = sigs[-1] if len(sigs) > 0 else 0
        if last_sig == 1:
            signals_found["MUA"] += 1
            buy_reasons.append("RS tạo đỉnh mới 65 ngày vs VNINDEX")
            combined_score += 2
            details["RSVNINDEX"] = {"signal": "MUA"}
        else:
            details["RSVNINDEX"] = {"signal": "NEUTRAL"}
            signals_found["NEUTRAL"] += 1
    except Exception as e:
        details["RSVNINDEX"] = {"signal": "ERROR", "error": str(e)[:30]}

    # --- MA20Crossover ---
    try:
        ma20 = MA20CrossoverStrategy(df)
        _, sigs = ma20.compute()
        last_sig = sigs[-1] if len(sigs) > 0 else 0
        if last_sig == 1:
            signals_found["MUA"] += 1
            buy_reasons.append("MA20 cắt lên MA50 (+Volume)")
            combined_score += 1
            details["MA20Crossover"] = {"signal": "MUA"}
        elif last_sig == -1:
            signals_found["BAN"] += 1
            sell_reasons.append("MA20 cắt xuống MA50")
            combined_score -= 1
            details["MA20Crossover"] = {"signal": "BAN"}
        else:
            details["MA20Crossover"] = {"signal": "NEUTRAL"}
            signals_found["NEUTRAL"] += 1
    except Exception as e:
        details["MA20Crossover"] = {"signal": "ERROR", "error": str(e)[:30]}

    # --- VolumePocket ---
    try:
        vp = VolumePocketStrategy(df)
        _, sigs = vp.compute()
        last_sig = sigs[-1] if len(sigs) > 0 else 0
        if last_sig == 1:
            signals_found["MUA"] += 1
            buy_reasons.append("Volume Pocket (Pivot Pocket Volume)")
            combined_score += 1
            details["VolumePocket"] = {"signal": "MUA"}
        elif last_sig == -1:
            signals_found["BAN"] += 1
            sell_reasons.append("Max Volume down")
            combined_score -= 1
            details["VolumePocket"] = {"signal": "BAN"}
        else:
            details["VolumePocket"] = {"signal": "NEUTRAL"}
            signals_found["NEUTRAL"] += 1
    except Exception as e:
        details["VolumePocket"] = {"signal": "ERROR", "error": str(e)[:30]}

    # --- Scoring ---
    try:
        sc = ScoringStrategy(df, index_df)
        score_vals, sigs = sc.compute()
        last_sig = sigs[-1] if len(sigs) > 0 else 0
        last_score = score_vals[-1] if len(score_vals) > 0 and not np.isnan(score_vals[-1]) else 0
        if last_sig == 1 or last_score > 5:
            signals_found["MUA"] += 1
            buy_reasons.append(f"Scoring > 5 (điểm={last_score:.1f})")
            combined_score += 2
            details["Scoring"] = {"signal": "MUA", "value": round(last_score, 1)}
        elif last_sig == -1 or (last_score < 3 and last_score > 0):
            signals_found["BAN"] += 1
            sell_reasons.append(f"Scoring <= 3 (điểm={last_score:.1f})")
            combined_score -= 2
            details["Scoring"] = {"signal": "BAN", "value": round(last_score, 1)}
        else:
            details["Scoring"] = {"signal": "NEUTRAL", "value": round(last_score, 1)}
            signals_found["NEUTRAL"] += 1
    except Exception as e:
        details["Scoring"] = {"signal": "ERROR", "error": str(e)[:30]}

    # --- Ichimoku ---
    try:
        ic = IchimokuStrategy(df)
        _, sigs = ic.compute()
        last_sig = sigs[-1] if len(sigs) > 0 else 0
        if last_sig == 1:
            signals_found["MUA"] += 1
            buy_reasons.append("Ichimoku TK cắt lên KJ + trên mây")
            combined_score += 2
            details["Ichimoku"] = {"signal": "MUA"}
        elif last_sig == -1:
            signals_found["BAN"] += 1
            sell_reasons.append("Ichimoku TK cắt xuống KJ + dưới mây")
            combined_score -= 2
            details["Ichimoku"] = {"signal": "BAN"}
        else:
            details["Ichimoku"] = {"signal": "NEUTRAL"}
            signals_found["NEUTRAL"] += 1
    except Exception as e:
        details["Ichimoku"] = {"signal": "ERROR", "error": str(e)[:30]}

    # Determine overall signal
    if signals_found["MUA"] > signals_found["BAN"] and signals_found["MUA"] >= 2:
        current_signal = "MUA"
    elif signals_found["BAN"] > signals_found["MUA"] and signals_found["BAN"] >= 2:
        current_signal = "BAN"
    else:
        current_signal = "NEUTRAL"

    mua_count = signals_found["MUA"]
    ban_count = signals_found["BAN"]
    total_active = mua_count + ban_count
    strength = round(mua_count / total_active * 100 if total_active > 0 and current_signal == "MUA"
                     else ban_count / total_active * 100 if total_active > 0 and current_signal == "BAN"
                     else 0, 1)

    return json.loads(json.dumps({
        "current_signal": current_signal,
        "strength": strength,
        "buy_count": mua_count,
        "sell_count": ban_count,
        "neutral_count": signals_found["NEUTRAL"],
        "buy_reasons": buy_reasons,
        "sell_reasons": sell_reasons,
        "combined_score": combined_score,
        "details": details,
    }, cls=NumpyEncoder))
