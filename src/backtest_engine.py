import pandas as pd
import numpy as np
import json
import os
import time
import warnings
import itertools
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict

from src.ssi_client import SSIClient
from src.technical_analysis import TechnicalAnalyzer
from src.signal_scoring import compute_smart_money_patterns

warnings.filterwarnings("ignore")

# ========================
# 1. DATA STRUCTURES
# ========================

TIMEFRAMES = ["daily", "weekly"]  # hourly requires intraday API not available from SSI

@dataclass
class Trade:
    entry_date: str
    entry_price: float
    exit_date: str = ""
    exit_price: float = 0.0
    direction: str = "long"
    quantity: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    bars_held: int = 0
    exit_reason: str = ""

@dataclass
class StrategyParams:
    name: str = ""
    ema_fast: int = 20
    ema_slow: int = 50
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    adx_threshold: float = 25.0
    bb_std: float = 2.0
    bb_period: int = 20
    supertrend_period: int = 10
    supertrend_mult: float = 3.0
    volume_ratio_min: float = 1.2
    mfi_threshold: float = 60.0
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 15.0
    max_hold_days: int = 30
    use_trend_filter: bool = True
    use_volume_filter: bool = True
    use_momentum_filter: bool = True
    use_mfi_filter: bool = False
    use_adx_filter: bool = False
    use_supertrend: bool = False
    use_bb_squeeze: bool = False
    use_cmf_filter: bool = False
    position_sizing: str = "equal"  # equal, kelly, risk_pct
    risk_per_trade_pct: float = 2.0
    combination_key: str = ""

@dataclass
class BacktestResult:
    strategy: StrategyParams = field(default_factory=StrategyParams)
    symbol: str = ""
    period: str = ""
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    win_rate: float = 0.0
    total_return_pct: float = 0.0
    annual_return_pct: float = 0.0
    cagr_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_trade_pct: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    avg_hold_bars: float = 0.0
    total_commission: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)
    monthly_returns: Dict[str, float] = field(default_factory=dict)
    composite_score: float = 0.0

# ========================
# 2. INDICATOR COMPUTER
# ========================

class IndicatorComputer:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.indicators = {}

    def compute_all(self, params: StrategyParams) -> pd.DataFrame:
        df = self.df.copy()
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        volume = df["volume"].values
        length = len(df)

        # EMA
        df["ema_fast"] = self._ema(close, params.ema_fast)
        df["ema_slow"] = self._ema(close, params.ema_slow)

        # SMA
        df["sma_20"] = self._sma(close, 20)
        df["sma_50"] = self._sma(close, 50)
        df["sma_200"] = self._sma(close, 200)

        # RSI
        df["rsi"] = self._rsi(close, params.rsi_period)

        # MACD
        macd, macd_signal, macd_hist = self._macd(
            close, params.macd_fast, params.macd_slow, params.macd_signal
        )
        df["macd"] = macd
        df["macd_signal"] = macd_signal
        df["macd_hist"] = macd_hist

        # ADX
        df["adx"] = self._adx(high, low, close, 14)
        df["plus_di"] = self._plus_di(high, low, close, 14)
        df["minus_di"] = self._minus_di(high, low, close, 14)

        # ATR
        df["atr"] = self._atr(high, low, close, 14)

        # Bollinger Bands
        bb_mid, bb_upper, bb_lower = self._bollinger(close, params.bb_period, params.bb_std)
        df["bb_mid"] = bb_mid
        df["bb_upper"] = bb_upper
        df["bb_lower"] = bb_lower
        df["bb_width"] = (bb_upper - bb_lower) / bb_mid * 100
        df["bb_pct_b"] = (close - bb_lower) / (bb_upper - bb_lower + 1e-10)

        # OBV
        df["obv"] = self._obv(close, volume)

        # CMF
        df["cmf"] = self._cmf(high, low, close, volume, 20)

        # MFI
        df["mfi"] = self._mfi(high, low, close, volume, 14)

        # SuperTrend
        st, st_dir = self._supertrend(high, low, close, params.supertrend_period, params.supertrend_mult)
        df["supertrend"] = st
        df["supertrend_dir"] = st_dir

        # VWAP
        df["vwap"] = self._vwap(high, low, close, volume)

        # Donchian Channel
        dc_upper, dc_lower = self._donchian(high, low, 20)
        df["dc_upper"] = dc_upper
        df["dc_lower"] = dc_lower

        # Keltner Channel
        kc_mid, kc_upper, kc_lower = self._keltner(high, low, close, 20, 2)
        df["kc_mid"] = kc_mid
        df["kc_upper"] = kc_upper
        df["kc_lower"] = kc_lower

        # Relative Volume
        df["rvol"] = self._rvol(volume, 20)

        # Volume MA
        df["vol_ma_20"] = self._sma(volume, 20)
        df["volume_ratio"] = volume / (df["vol_ma_20"] + 1e-10)

        # Ichimoku
        tenkan, kijun, senkou_a, senkou_b = self._ichimoku(high, low)
        df["tenkan"] = tenkan
        df["kijun"] = kijun
        df["senkou_a"] = senkou_a
        df["senkou_b"] = senkou_b

        # Price changes
        df["return_1d"] = df["close"].pct_change()
        df["return_5d"] = df["close"].pct_change(5)
        df["return_20d"] = df["close"].pct_change(20)

        # Volatility
        df["volatility"] = df["return_1d"].rolling(20).std() * np.sqrt(252)

        return df

    def _ema(self, arr, period):
        return pd.Series(arr).ewm(span=period, adjust=False).mean().values

    def _sma(self, arr, period):
        s = pd.Series(arr)
        return s.rolling(period).mean().values

    def _rsi(self, arr, period):
        s = pd.Series(arr)
        delta = s.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs)).values

    def _macd(self, arr, fast, slow, signal):
        s = pd.Series(arr)
        ema_fast = s.ewm(span=fast, adjust=False).mean()
        ema_slow = s.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        hist = macd - signal_line
        return macd.values, signal_line.values, hist.values

    def _adx(self, high, low, close, period):
        tr = pd.concat([
            pd.Series(high - low),
            pd.Series(np.abs(high - pd.Series(close).shift(1))),
            pd.Series(np.abs(low - pd.Series(close).shift(1)))
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        up_move = pd.Series(high).diff()
        down_move = pd.Series(low).diff() * -1
        plus_dm = ((up_move > down_move) & (up_move > 0)).astype(float) * up_move
        minus_dm = ((down_move > up_move) & (down_move > 0)).astype(float) * down_move
        plus_di = 100 * plus_dm.rolling(period).sum() / (atr + 1e-10)
        minus_di = 100 * minus_dm.rolling(period).sum() / (atr + 1e-10)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(period).mean()
        return adx.values

    def _plus_di(self, high, low, close, period):
        tr = pd.concat([
            pd.Series(high - low),
            pd.Series(np.abs(high - pd.Series(close).shift(1))),
            pd.Series(np.abs(low - pd.Series(close).shift(1)))
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        up_move = pd.Series(high).diff()
        down_move = pd.Series(low).diff() * -1
        plus_dm = ((up_move > down_move) & (up_move > 0)).astype(float) * up_move
        return (100 * plus_dm.rolling(period).sum() / (atr + 1e-10)).values

    def _minus_di(self, high, low, close, period):
        tr = pd.concat([
            pd.Series(high - low),
            pd.Series(np.abs(high - pd.Series(close).shift(1))),
            pd.Series(np.abs(low - pd.Series(close).shift(1)))
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        down_move = pd.Series(low).diff() * -1
        up_move = pd.Series(high).diff()
        minus_dm = ((down_move > up_move) & (down_move > 0)).astype(float) * down_move
        return (100 * minus_dm.rolling(period).sum() / (atr + 1e-10)).values

    def _atr(self, high, low, close, period):
        tr = pd.concat([
            pd.Series(high - low),
            pd.Series(np.abs(high - pd.Series(close).shift(1))),
            pd.Series(np.abs(low - pd.Series(close).shift(1)))
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean().values

    def _bollinger(self, arr, period, std):
        s = pd.Series(arr)
        mid = s.rolling(period).mean()
        upper = mid + std * s.rolling(period).std()
        lower = mid - std * s.rolling(period).std()
        return mid.values, upper.values, lower.values

    def _obv(self, close, volume):
        s_close = pd.Series(close)
        s_vol = pd.Series(volume)
        direction = np.sign(s_close.diff()).fillna(0)
        obv = (direction * s_vol).fillna(0).cumsum()
        return obv.values

    def _cmf(self, high, low, close, volume, period):
        mfm = ((close - low) - (high - close)) / (high - low + 1e-10)
        mfv = mfm * volume
        cmf = pd.Series(mfv).rolling(period).sum() / (pd.Series(volume).rolling(period).sum() + 1e-10)
        return cmf.values

    def _mfi(self, high, low, close, volume, period):
        typical = (high + low + close) / 3
        money_flow = typical * volume
        s_close = pd.Series(close)
        direction = np.sign(s_close.diff()).fillna(0)
        pos_flow = pd.Series(money_flow) * (direction > 0).astype(float)
        neg_flow = pd.Series(money_flow) * (direction < 0).astype(float)
        pos_sum = pos_flow.rolling(period).sum()
        neg_sum = neg_flow.rolling(period).sum() + 1e-10
        mfi = 100 - (100 / (1 + pos_sum / neg_sum))
        return mfi.values

    def _supertrend(self, high, low, close, period, mult):
        length = len(close)
        st = np.full(length, np.nan)
        direction = np.full(length, 1)
        hl = (high + low) / 2
        tr = pd.concat([
            pd.Series(high - low),
            pd.Series(np.abs(high - pd.Series(close).shift(1))),
            pd.Series(np.abs(low - pd.Series(close).shift(1)))
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().values
        upper = hl + mult * atr
        lower = hl - mult * atr
        for i in range(period, length):
            if i == period:
                st[i] = upper[i]
                direction[i] = -1
            else:
                if close[i - 1] <= st[i - 1]:
                    st[i] = upper[i]
                    direction[i] = -1
                else:
                    st[i] = lower[i]
                    direction[i] = 1
                if direction[i] == 1 and st[i] < st[i - 1]:
                    st[i] = st[i - 1]
                if direction[i] == -1 and st[i] > st[i - 1]:
                    st[i] = st[i - 1]
            if close[i] > st[i] and direction[i] == -1:
                direction[i] = 1
            elif close[i] < st[i] and direction[i] == 1:
                direction[i] = -1
        return st, direction

    def _vwap(self, high, low, close, volume):
        typical = (high + low + close) / 3
        vwap = pd.Series(typical * volume).rolling(20).sum() / (pd.Series(volume).rolling(20).sum() + 1e-10)
        return vwap.values

    def _donchian(self, high, low, period):
        upper = pd.Series(high).rolling(period).max().values
        lower = pd.Series(low).rolling(period).min().values
        return upper, lower

    def _keltner(self, high, low, close, period, mult):
        mid = pd.Series(close).rolling(period).mean()
        tr = pd.concat([
            pd.Series(high - low),
            pd.Series(np.abs(high - pd.Series(close).shift(1))),
            pd.Series(np.abs(low - pd.Series(close).shift(1)))
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        upper = mid + mult * atr
        lower = mid - mult * atr
        return mid.values, upper.values, lower.values

    def _rvol(self, volume, period):
        return (pd.Series(volume) / (pd.Series(volume).rolling(period).mean() + 1e-10)).values

    def _ichimoku(self, high, low):
        tenkan = (pd.Series(high).rolling(9).max() + pd.Series(low).rolling(9).min()) / 2
        kijun = (pd.Series(high).rolling(26).max() + pd.Series(low).rolling(26).min()) / 2
        senkou_a = ((tenkan + kijun) / 2).shift(26)
        senkou_b = ((pd.Series(high).rolling(52).max() + pd.Series(low).rolling(52).min()) / 2).shift(26)
        return tenkan.values, kijun.values, senkou_a.values, senkou_b.values


# ========================
# 3. STRATEGY GENERATOR
# ========================

class StrategyGenerator:
    def __init__(self):
        self.param_grid = {
            "ema_fast": [10, 20, 30, 50],
            "ema_slow": [50, 100, 150, 200],
            "rsi_period": [7, 14, 21],
            "rsi_oversold": [25, 30, 35],
            "rsi_overbought": [65, 70, 75],
            "macd_fast": [8, 12, 16],
            "macd_slow": [17, 26, 34],
            "macd_signal": [7, 9, 12],
            "adx_threshold": [20, 25, 30],
            "supertrend_period": [7, 10, 14],
            "supertrend_mult": [2.0, 3.0, 4.0],
            "volume_ratio_min": [1.0, 1.2, 1.5],
            "mfi_threshold": [55, 60, 65],
            "stop_loss_pct": [3.0, 5.0, 8.0],
            "take_profit_pct": [10.0, 15.0, 20.0],
            "max_hold_days": [10, 15, 20, 30],
        }

        self.filter_combos = [
            {"use_trend_filter": True, "use_volume_filter": True, "use_momentum_filter": True},
            {"use_trend_filter": True, "use_volume_filter": True, "use_momentum_filter": False},
            {"use_trend_filter": True, "use_volume_filter": False, "use_momentum_filter": True},
            {"use_trend_filter": False, "use_volume_filter": True, "use_momentum_filter": True},
            {"use_trend_filter": True, "use_volume_filter": False, "use_momentum_filter": False},
            {"use_trend_filter": False, "use_volume_filter": True, "use_momentum_filter": False},
            {"use_trend_filter": False, "use_volume_filter": False, "use_momentum_filter": True},
            {"use_trend_filter": False, "use_volume_filter": False, "use_momentum_filter": False},
            {"use_adx_filter": True, "use_trend_filter": True},
            {"use_mfi_filter": True, "use_volume_filter": True},
            {"use_supertrend": True},
            {"use_cmf_filter": True, "use_volume_filter": True},
        ]

    def generate(self, max_combinations: int = 5000) -> List[StrategyParams]:
        param_names = list(self.param_grid.keys())
        param_values = list(self.param_grid.values())
        combos = []

        for values in itertools.product(*param_values):
            if len(combos) >= max_combinations:
                break
            params = dict(zip(param_names, values))
            if params["ema_fast"] >= params["ema_slow"]:
                continue
            for fc in self.filter_combos:
                if len(combos) >= max_combinations:
                    break
                p = StrategyParams(**params, **fc)
                p.combination_key = self._make_key(p)
                combos.append(p)
        return combos

    def _make_key(self, p: StrategyParams) -> str:
        return (f"EMA{p.ema_fast}_{p.ema_slow}|RSI{p.rsi_period}_{int(p.rsi_oversold)}_{int(p.rsi_overbought)}"
                f"|MACD{p.macd_fast}_{p.macd_slow}_{p.macd_signal}"
                f"|ADX{int(p.adx_threshold)}|ST{p.supertrend_period}_{p.supertrend_mult}"
                f"|VOL{int(p.volume_ratio_min*10)}|MFI{int(p.mfi_threshold)}"
                f"|SL{int(p.stop_loss_pct)}_TP{int(p.take_profit_pct)}"
                f"|TREND{int(p.use_trend_filter)}_VOL{int(p.use_volume_filter)}_MOM{int(p.use_momentum_filter)}"
                f"|ADXF{int(p.use_adx_filter)}_MFIF{int(p.use_mfi_filter)}_SUPERT{int(p.use_supertrend)}_CMFF{int(p.use_cmf_filter)}")


# ========================
# 4. BACKTEST EXECUTOR
# ========================

class BacktestExecutor:
    def __init__(self, commission_pct: float = 0.0015, tax_pct: float = 0.001):
        self.commission_pct = commission_pct
        self.tax_pct = tax_pct

    def run(self, df: pd.DataFrame, params: StrategyParams) -> BacktestResult:
        ic = IndicatorComputer(df)
        df = ic.compute_all(params)

        # Only drop rows where SIGNAL columns are NaN (allow auxiliary indicators to be NaN)
        signal_cols = ["ema_fast", "ema_slow", "rsi", "macd", "macd_signal", "macd_hist", "adx",
                       "plus_di", "minus_di", "atr", "bb_mid", "bb_upper", "bb_lower",
                       "obv", "cmf", "mfi", "supertrend", "supertrend_dir", "vwap",
                       "dc_upper", "dc_lower", "volume_ratio", "vol_ma_20"]
        existing_signal = [c for c in signal_cols if c in df.columns]
        df = df.dropna(subset=existing_signal).reset_index(drop=True)

        result = BacktestResult(strategy=params, symbol="PORTFOLIO", period=f"{df['date'].iloc[0]}-{df['date'].iloc[-1]}")
        if len(df) < 30:
            return result

        close = df["close"].values
        trades = []
        in_position = False
        entry_price = 0
        entry_idx = 0
        entry_date = ""
        capital = 1.0
        equity = [1.0]

        warmup = 30
        for i in range(warmup, len(df)):
            row = df.iloc[i]
            date = str(row["date"]) if hasattr(row, "date") else str(df.index[i])

            # Exit logic
            if in_position:
                bars_held = i - entry_idx
                exit_signal = self._check_exit(row, params, bars_held)

                if exit_signal:
                    exit_price = close[i]
                    pnl_pct = (exit_price - entry_price) / entry_price * 100
                    pnl_pct -= self.commission_pct * 100 + self.tax_pct * 100
                    trade = Trade(
                        entry_date=entry_date, entry_price=entry_price,
                        exit_date=date, exit_price=exit_price,
                        pnl_pct=pnl_pct, bars_held=bars_held,
                        exit_reason=exit_signal
                    )
                    trades.append(trade)
                    capital *= (1 + pnl_pct / 100)
                    in_position = False

            # Entry logic
            if not in_position:
                entry_signal = self._check_entry(row, params)
                if entry_signal:
                    entry_price = close[i]
                    entry_idx = i
                    entry_date = date
                    in_position = True
                    trade = Trade(entry_date=date, entry_price=entry_price)
                    trades.append(trade)

            equity.append(capital)

        result.equity_curve = equity
        result.trades = [t for t in trades if t.exit_price > 0]
        self._compute_metrics(result, df)
        return result

    def _check_entry(self, row: pd.Series, p: StrategyParams) -> bool:
        checks = []

        # Trend filter
        if p.use_trend_filter:
            checks.append(row["ema_fast"] > row["ema_slow"])
            checks.append(row["close"] > row["ema_slow"])

        # Volume filter
        if p.use_volume_filter:
            checks.append(row["volume_ratio"] >= p.volume_ratio_min)

        # Momentum filter
        if p.use_momentum_filter:
            checks.append(row["macd"] > row["macd_signal"])
            checks.append(p.rsi_oversold < row["rsi"] < p.rsi_overbought)

        # ADX filter
        if p.use_adx_filter:
            checks.append(row["adx"] >= p.adx_threshold)
            checks.append(row["plus_di"] > row["minus_di"])

        # MFI filter
        if p.use_mfi_filter:
            checks.append(row["mfi"] >= p.mfi_threshold)

        # SuperTrend
        if p.use_supertrend:
            checks.append(row["supertrend_dir"] == 1)

        # CMF filter
        if p.use_cmf_filter:
            checks.append(row["cmf"] > 0)

        # BB Squeeze
        if p.use_bb_squeeze:
            bb_width = row["bb_width"]
            checks.append(bb_width < bb_width * 0.8 if hasattr(row, "bb_width_prev") else False)

        return all(checks) if checks else False

    def _check_exit(self, row: pd.Series, p: StrategyParams, bars_held: int) -> str:
        exit_reason = ""

        # Trend reversal
        if p.use_trend_filter:
            if row["close"] < row["ema_slow"] * 0.98:
                exit_reason = "MAT_EMA"

        # RSI overbought
        if p.use_momentum_filter and row["rsi"] > p.rsi_overbought + 10:
            exit_reason = "RSI_QUA_MUA"

        # Stop loss
        if exit_reason == "" and hasattr(row, "entry_price") and row["close"] < row["entry_price"] * (1 - p.stop_loss_pct / 100):
            exit_reason = "STOP_LOSS"

        # SuperTrend reversal
        if p.use_supertrend and exit_reason == "" and row["supertrend_dir"] == -1:
            exit_reason = "SUPERTREND"

        # Max hold
        if exit_reason == "" and bars_held >= p.max_hold_days:
            exit_reason = "MAX_HOLD"

        return exit_reason

    def _compute_metrics(self, result: BacktestResult, df: pd.DataFrame):
        trades = result.trades
        if not trades:
            return

        result.total_trades = len(trades)
        result.win_trades = sum(1 for t in trades if t.pnl_pct > 0)
        result.loss_trades = sum(1 for t in trades if t.pnl_pct <= 0)
        result.win_rate = result.win_trades / result.total_trades * 100 if result.total_trades > 0 else 0

        equity = np.array(result.equity_curve)
        result.total_return_pct = (equity[-1] - 1) * 100

        # CAGR
        years = len(equity) / 252
        result.cagr_pct = ((equity[-1] / equity[0]) ** (1 / max(years, 0.01)) - 1) * 100 if years > 0 else 0

        # Annual return
        daily_returns = np.diff(equity) / equity[:-1]
        result.annual_return_pct = np.mean(daily_returns) * 252 * 100 if len(daily_returns) > 0 else 0

        # Sharpe Ratio
        if len(daily_returns) > 1 and np.std(daily_returns) > 0:
            result.sharpe_ratio = (np.mean(daily_returns) * 252) / (np.std(daily_returns) * np.sqrt(252))

        # Sortino Ratio
        neg_returns = daily_returns[daily_returns < 0]
        if len(neg_returns) > 0 and np.std(neg_returns) > 0:
            result.sortino_ratio = (np.mean(daily_returns) * 252) / (np.std(neg_returns) * np.sqrt(252))

        # Max Drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        result.max_drawdown_pct = np.max(drawdown) * 100

        # Calmar Ratio
        result.calmar_ratio = result.cagr_pct / max(result.max_drawdown_pct, 0.01)

        # Profit Factor
        gross_profit = sum(t.pnl_pct for t in trades if t.pnl_pct > 0)
        gross_loss = abs(sum(t.pnl_pct for t in trades if t.pnl_pct < 0))
        result.profit_factor = gross_profit / max(gross_loss, 0.01)

        # Expectancy
        result.expectancy = np.mean([t.pnl_pct for t in trades]) if trades else 0

        # Avg trade
        result.avg_trade_pct = np.mean([t.pnl_pct for t in trades]) if trades else 0
        wins = [t.pnl_pct for t in trades if t.pnl_pct > 0]
        losses = [t.pnl_pct for t in trades if t.pnl_pct <= 0]
        result.avg_win_pct = np.mean(wins) if wins else 0
        result.avg_loss_pct = np.mean(losses) if losses else 0
        result.avg_hold_bars = np.mean([t.bars_held for t in trades]) if trades else 0

        # Composite score (risk-adjusted)
        result.composite_score = self._compute_composite_score(result)

    def _compute_composite_score(self, r: BacktestResult) -> float:
        score = 0.0
        if r.sharpe_ratio > 0:
            score += min(r.sharpe_ratio * 15, 25)
        if r.sortino_ratio > 0:
            score += min(r.sortino_ratio * 10, 20)
        if r.calmar_ratio > 0:
            score += min(r.calmar_ratio * 10, 15)
        score += min(r.win_rate * 0.15, 15)
        if r.profit_factor > 1:
            score += min((r.profit_factor - 1) * 10, 15)
        score += min(r.total_trades * 0.1, 10)
        if r.max_drawdown_pct > 0:
            score += max(0, 10 - r.max_drawdown_pct * 0.2)
        return round(score, 2)


# ========================
# 5. BAYESIAN OPTIMIZATION
# ========================

class BayesianOptimizer:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.results = []

    def optimize(self, param_space: Dict, n_iter: int = 50):
        try:
            from skopt import gp_minimize
            from skopt.space import Integer, Real, Categorical
        except ImportError:
            return self._random_search(param_space, n_iter)

        dimensions = []
        for name, values in param_space.items():
            if isinstance(values[0], int):
                dimensions.append(Integer(min(values), max(values), name=name))
            elif isinstance(values[0], float):
                dimensions.append(Real(min(values), max(values), name=name))
            else:
                dimensions.append(Categorical(values, name=name))

        def objective(params):
            p = StrategyParams()
            for name, val in zip(param_space.keys(), params):
                setattr(p, name, int(val) if isinstance(val, (np.integer,)) else float(val) if isinstance(val, (np.floating,)) else val)
            p.combination_key = StrategyGenerator()._make_key(p)
            executor = BacktestExecutor()
            result = executor.run(self.df, p)
            return -result.composite_score if result.total_trades > 5 else 1e9

        try:
            res = gp_minimize(objective, dimensions, n_calls=n_iter, random_state=42, verbose=False)
            best_params = {}
            for i, name in enumerate(param_space.keys()):
                best_params[name] = res.x[i]
            best_params["composite_score"] = -res.fun
            return best_params
        except Exception:
            return self._random_search(param_space, n_iter)

    def _random_search(self, param_space: Dict, n_iter: int) -> Dict:
        best_score = -1e9
        best_params = {}
        sg = StrategyGenerator()
        for _ in range(n_iter):
            p = StrategyParams()
            for name, values in param_space.items():
                setattr(p, name, np.random.choice(values))
            p.combination_key = sg._make_key(p)
            executor = BacktestExecutor()
            result = executor.run(self.df, p)
            if result.composite_score > best_score and result.total_trades > 5:
                best_score = result.composite_score
                best_params = {k: getattr(p, k) for k in param_space.keys()}
                best_params["composite_score"] = best_score
        return best_params


# ========================
# 6. ROBUST CROSS-VALIDATION (Walk-Forward + Multi-Symbol)
# ========================

class CrossValidator:
    def __init__(self, data: Dict[str, pd.DataFrame]):
        self.data = data

    def walk_forward(self, strategy: StrategyParams, train_years: int = 2, test_months: int = 6) -> dict:
        """Test strategy across multiple time windows on multiple symbols.
        Returns aggregated robustness metrics."""
        window_results = []
        for sym, df in self.data.items():
            df = df.copy()
            df["date"] = pd.to_datetime(df["date"])
            start = df["date"].min()
            end = df["date"].max()
            window_start = start
            while True:
                train_end = window_start + pd.DateOffset(years=train_years)
                test_end = train_end + pd.DateOffset(months=test_months)
                if test_end > end:
                    break
                train_df = df[(df["date"] >= window_start) & (df["date"] < train_end)]
                test_df = df[(df["date"] >= train_end) & (df["date"] < test_end)]
                if len(train_df) < 100 or len(test_df) < 20:
                    pass
                else:
                    executor = BacktestExecutor()
                    test_result = executor.run(test_df, strategy)
                    train_result = executor.run(train_df, strategy)
                    window_results.append({
                        "symbol": sym,
                        "train_start": str(window_start.date()),
                        "test_start": str(train_end.date()),
                        "test_end": str(test_end.date()),
                        "train_trades": train_result.total_trades,
                        "train_cagr": train_result.cagr_pct,
                        "train_sharpe": train_result.sharpe_ratio,
                        "test_trades": test_result.total_trades,
                        "test_cagr": test_result.cagr_pct,
                        "test_sharpe": test_result.sharpe_ratio,
                        "test_max_dd": test_result.max_drawdown_pct,
                    })
                window_start += pd.DateOffset(months=6)

        if not window_results:
            return {"consistency_score": 0, "avg_test_cagr": 0, "windows": 0}

        test_cagrs = [w["test_cagr"] for w in window_results if w["test_trades"] >= 2]
        test_sharpes = [w["test_sharpe"] for w in window_results if w["test_trades"] >= 2]
        train_cagrs = [w["train_cagr"] for w in window_results if w["train_trades"] >= 2]

        consistency = 0
        if test_cagrs:
            positive_windows = sum(1 for c in test_cagrs if c > 0)
            consistency = positive_windows / len(test_cagrs) * 100 if test_cagrs else 0

        # Penalize if train is good but test is bad (overfitting gap)
        avg_train = np.mean(train_cagrs) if train_cagrs else 0
        avg_test = np.mean(test_cagrs) if test_cagrs else 0
        overfit_penalty = max(0, avg_train - avg_test * 2) * 0.5 if avg_test > 0 else max(0, avg_train) * 2

        # Composite robustness
        robustness = 0
        if test_cagrs:
            robustness += min(consistency * 0.3, 30)
            robustness += min(max(avg_test, 0) * 0.5, 25)
            robustness += min(np.mean(test_sharpes) * 5 if test_sharpes else 0, 20)
            robustness -= min(overfit_penalty, 25)
            robustness = max(0, min(100, robustness))

        unique_symbols = len(set(w["symbol"] for w in window_results if w["test_trades"] >= 2))

        return {
            "symbols_tested": unique_symbols,
            "total_windows": len(window_results),
            "positive_windows": len([w for w in window_results if w["test_cagr"] > 0 and w["test_trades"] >= 2]),
            "consistency_pct": round(consistency, 1),
            "avg_train_cagr": round(avg_train, 2),
            "avg_test_cagr": round(avg_test, 2),
            "avg_test_sharpe": round(np.mean(test_sharpes), 2) if test_sharpes else 0,
            "avg_test_maxdd": round(np.mean([w["test_max_dd"] for w in window_results if w["test_trades"] >= 2]), 2),
            "overfit_penalty": round(overfit_penalty, 2),
            "robustness_score": round(robustness, 1),
        }


# ========================
# 7. ENSEMBLE STRATEGY
# ========================

class EnsembleStrategy:
    def __init__(self, strategies: List[StrategyParams], weights: List[float] = None):
        self.strategies = strategies
        self.weights = weights or [1.0 / len(strategies)] * len(strategies)

    def run(self, df: pd.DataFrame) -> BacktestResult:
        """Run ensemble: execute each strategy and combine signals via weighted majority vote."""
        executor = BacktestExecutor()
        all_trades = []
        combined_equity = None

        for i, strat in enumerate(self.strategies):
            result = executor.run(df, strat)
            w = self.weights[i]
            if result.trades:
                for t in result.trades:
                    t.quantity = int(w * 100)
                all_trades.extend(result.trades)
            # Weighted equity contribution
            eq = np.array(result.equity_curve) * w
            if combined_equity is None:
                combined_equity = eq
            else:
                min_len = min(len(combined_equity), len(eq))
                combined_equity = combined_equity[:min_len] + eq[:min_len]

        # Build ensemble result
        ensemble = BacktestResult(strategy=self.strategies[0], symbol="ENSEMBLE")
        ensemble.trades = all_trades
        ensemble.total_trades = len(all_trades)
        ensemble.win_trades = sum(1 for t in all_trades if t.pnl_pct > 0)
        ensemble.loss_trades = sum(1 for t in all_trades if t.pnl_pct <= 0)
        ensemble.win_rate = ensemble.win_trades / max(ensemble.total_trades, 1) * 100
        ensemble.equity_curve = combined_equity.tolist() if combined_equity is not None else [1.0]
        executor._compute_metrics(ensemble, df)
        return ensemble


# ========================
# 8. INDICATOR ANALYZER
# ========================

class IndicatorAnalyzer:
    def __init__(self):
        self.indicator_stats = defaultdict(lambda: {"count": 0, "wins": 0, "total_composite": 0})

    def analyze_top_strategies(self, ranked: List[BacktestResult], top_n: int = 50):
        for r in ranked[:top_n]:
            key = r.strategy.combination_key
            parts = key.split("|")
            for part in parts:
                self.indicator_stats[part]["count"] += 1
                self.indicator_stats[part]["wins"] += 1 if r.cagr_pct > 0 else 0
                self.indicator_stats[part]["total_composite"] += r.composite_score

        # Calculate success rates
        results = {}
        for ind, stats in sorted(self.indicator_stats.items(), key=lambda x: x[1]["count"], reverse=True):
            results[ind] = {
                "count": stats["count"],
                "win_rate": round(stats["wins"] / max(stats["count"], 1) * 100, 1),
                "avg_composite": round(stats["total_composite"] / max(stats["count"], 1), 1),
            }
        return results


# ========================
# 9. STRATEGY RANKER (ENHANCED)
# ========================

class StrategyRanker:
    def __init__(self):
        self.rankings = []

    def rank(self, results: List[BacktestResult], cv_results: Dict[str, dict] = None,
             min_symbols: int = 1, min_trades: int = 5, min_win_rate: float = 30,
             min_sharpe: float = 0.3, max_dd: float = 30, robustness_min: float = 0) -> List[BacktestResult]:
        filtered = []

        # Group by strategy key
        from collections import defaultdict as dd
        strat_results = dd(list)
        for r in results:
            strat_results[r.strategy.combination_key].append(r)

        for key, group in strat_results.items():
            # Must work on multiple symbols
            symbols_with_trades = len(set(r.symbol for r in group if r.total_trades >= min_trades))
            if symbols_with_trades < min_symbols:
                continue

            # Average across symbols
            avg_cagr = np.mean([r.cagr_pct for r in group if r.cagr_pct != 0]) if any(r.cagr_pct != 0 for r in group) else 0
            avg_sharpe = np.mean([r.sharpe_ratio for r in group if r.sharpe_ratio != 0]) if any(r.sharpe_ratio != 0 for r in group) else 0
            avg_wr = np.mean([r.win_rate for r in group if r.win_rate > 0]) if any(r.win_rate > 0 for r in group) else 0
            avg_dd = np.mean([r.max_drawdown_pct for r in group if r.max_drawdown_pct > 0]) if any(r.max_drawdown_pct > 0 for r in group) else 100
            total_trades = sum(r.total_trades for r in group)
            avg_pf = np.mean([r.profit_factor for r in group if r.profit_factor > 1]) if any(r.profit_factor > 1 for r in group) else 0

            if avg_cagr <= 0 or avg_sharpe < min_sharpe or avg_wr < min_win_rate or avg_dd > max_dd or total_trades < min_trades:
                continue

            # Composite score (enhanced)
            comp = 0
            comp += min(avg_sharpe * 12, 20)
            comp += min(max(avg_cagr, 0) * 0.8, 15)
            comp += min(avg_wr * 0.12, 12)
            comp += min((avg_pf - 1) * 8 if avg_pf > 1 else 0, 12)
            comp += min(symbols_with_trades * 3, 12)
            comp += min(max(30 - avg_dd, 0) * 0.5, 10)
            comp += min(total_trades * 0.3, 10)
            comp += min(avg_wr * 0.05, 5)

            # Boost by cross-validation robustness
            robustness_boost = 0
            if cv_results and key in cv_results:
                robust = cv_results[key].get("robustness_score", 0)
                if robust >= robustness_min:
                    robustness_boost = min(robust * 0.15, 10)
            comp += robustness_boost

            # Use first result as template
            best_result = max(group, key=lambda r: r.composite_score)
            best_result.composite_score = round(comp, 2)
            best_result._extra = {
                "symbols_passed": symbols_with_trades,
                "avg_cagr": round(avg_cagr, 2),
                "avg_sharpe": round(avg_sharpe, 3),
                "avg_win_rate": round(avg_wr, 1),
                "avg_max_dd": round(avg_dd, 2),
                "total_trades_all": total_trades,
                "robustness_boost": round(robustness_boost, 2),
                "cv_score": cv_results.get(key, {}).get("robustness_score", 0) if cv_results else 0,
            }
            filtered.append(best_result)

        filtered.sort(key=lambda r: r.composite_score, reverse=True)
        self.rankings = filtered
        return filtered

    def top_n(self, n: int = 20) -> List[BacktestResult]:
        return self.rankings[:n]

    def to_dict(self, results: List[BacktestResult]) -> List[Dict]:
        out = []
        for r in results[:20]:
            extra = getattr(r, "_extra", {}) or {}
            out.append({
                "key": r.strategy.combination_key,
                "symbols": extra.get("symbols_passed", 1),
                "total_trades": r.total_trades,
                "win_rate": round(r.win_rate, 2),
                "cagr": round(r.cagr_pct, 2),
                "sharpe": round(r.sharpe_ratio, 3),
                "sortino": round(r.sortino_ratio, 3),
                "max_dd": round(r.max_drawdown_pct, 2),
                "profit_factor": round(r.profit_factor, 3),
                "composite": round(r.composite_score, 2),
                "cv_robustness": extra.get("cv_score", 0),
            })
        return out


# ========================
# 8. MAIN BACKTEST PIPELINE
# ========================

class BacktestPipeline:
    def __init__(self):
        self.ssi = SSIClient()
        self.results = []

    def load_data(self, symbols: List[str], years: int = 3, cache_dir: str = None) -> Dict[str, pd.DataFrame]:
        data = {}
        today = datetime.now()

        # Try loading from cache first
        if cache_dir and os.path.exists(cache_dir):
            loaded = 0
            for fname in os.listdir(cache_dir):
                if fname.endswith(".parquet"):
                    sym = fname.replace(".parquet", "")
                    if sym in symbols:
                        try:
                            df = pd.read_parquet(os.path.join(cache_dir, fname))
                            df["date"] = pd.to_datetime(df["date"])
                            data[sym] = df
                            loaded += 1
                        except Exception:
                            pass
            if loaded > 0:
                print(f"Loaded {loaded}/{len(symbols)} from cache ({cache_dir})")
                return data

        print(f"Loading data for {len(symbols)} symbols ({years} years, chunked 30-day requests)...")
        chunk_size_days = 25
        n_chunks = int(years * 365 / chunk_size_days) + 1

        for i, symbol in enumerate(symbols):
            try:
                all_dfs = []
                for c in range(n_chunks):
                    chunk_end = today - timedelta(days=c * chunk_size_days)
                    chunk_start = chunk_end - timedelta(days=chunk_size_days)
                    fs = chunk_start.strftime("%d/%m/%Y")
                    ts = chunk_end.strftime("%d/%m/%Y")
                    df_chunk = self.ssi.get_daily_stock_price(
                        symbol, from_date=fs, to_date=ts, page_size=100, market="HOSE"
                    )
                    if not df_chunk.empty:
                        all_dfs.append(df_chunk)
                    time.sleep(1.1)
                if all_dfs:
                    df = pd.concat(all_dfs).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
                    if len(df) > 100:
                        data[symbol] = df
                        # Cache to parquet
                        if cache_dir:
                            os.makedirs(cache_dir, exist_ok=True)
                            df.to_parquet(os.path.join(cache_dir, f"{symbol}.parquet"), index=False)
                if (i + 1) % 5 == 0:
                    print(f"  [{i + 1}/{len(symbols)}] {len(data)} loaded")
            except Exception as e:
                pass
        print(f"Loaded {len(data)}/{len(symbols)} symbols")
        return data

    def run_backtest_batch(self, data: Dict[str, pd.DataFrame], strategies: List[StrategyParams],
                           symbols_limit: int = 5) -> List[BacktestResult]:
        results = []
        symbols = list(data.keys())[:symbols_limit]
        total = len(strategies) * len(symbols)
        count = 0

        for sym in symbols:
            df = data[sym]
            for strat in strategies:
                count += 1
                if count % 100 == 0:
                    print(f"  Backtest {count}/{total}")
                try:
                    executor = BacktestExecutor()
                    result = executor.run(df, strat)
                    result.symbol = sym
                    results.append(result)
                except Exception:
                    continue
        return results

    def filter_by_period(self, data: Dict[str, pd.DataFrame], period_name: str):
        periods = {
            "train": ("2018-01-01", "2023-12-31"),
            "validation": ("2024-01-01", "2024-12-31"),
            "test": ("2025-01-01", "2027-12-31"),
        }
        if period_name not in periods:
            return data
        start, end = periods[period_name]
        filtered = {}
        for sym, df in data.items():
            df["date"] = pd.to_datetime(df["date"])
            mask = (df["date"] >= start) & (df["date"] <= end)
            subset = df[mask].copy()
            if len(subset) > 50:
                filtered[sym] = subset
        return filtered

    def resample_to_timeframe(self, data: Dict[str, pd.DataFrame], timeframe: str = "weekly") -> Dict[str, pd.DataFrame]:
        if timeframe == "daily":
            return data
        if timeframe not in ["weekly"]:
            print(f"  Unsupported timeframe '{timeframe}', using daily")
            return data

        resampled = {}
        for sym, df in data.items():
            try:
                df = df.copy()
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date")
                rule = "W-FRI" if timeframe == "weekly" else "D"
                agg_dict = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
                for c in df.columns:
                    if c not in agg_dict and c not in ["symbol", "adj_close", "change", "change_pct",
                                                        "ceiling", "floor", "ref", "foreign_buy", "foreign_sell", "foreign_room", "value"]:
                        agg_dict[c] = "last"
                wk = df.resample(rule).agg(agg_dict).dropna()
                wk = wk[wk["volume"] > 0].reset_index()
                wk.rename(columns={"index": "date"}, inplace=True)
                if len(wk) > 30:
                    resampled[sym] = wk
                    print(f"  {sym}: {len(df)} {timeframe.lower()} bars -> {len(wk)} bars")
            except Exception as e:
                pass
        return resampled

    def generate_report(self, ranked: List[BacktestResult], period: str = "") -> dict:
        top = ranked[:20]
        if not top:
            return {"error": "No results"}

        report = {
            "period": period,
            "total_strategies_tested": len(self.results),
            "total_trades_all": sum(r.total_trades for r in top),
            "top_strategies": [],
            "best_params_summary": {},
            "average_metrics": {},
            "top_3_detail": [],
        }

        # Top strategies summary
        report["top_strategies"] = [{
            "rank": i + 1,
            "key": r.strategy.combination_key[:60],
            "cagr": round(r.cagr_pct, 2),
            "sharpe": round(r.sharpe_ratio, 3),
            "sortino": round(r.sortino_ratio, 3),
            "calmar": round(r.calmar_ratio, 3),
            "max_dd": round(r.max_drawdown_pct, 2),
            "win_rate": round(r.win_rate, 1),
            "profit_factor": round(r.profit_factor, 3),
            "total_trades": r.total_trades,
            "avg_trade": round(r.avg_trade_pct, 2),
            "avg_hold": round(r.avg_hold_bars, 1),
            "composite": round(r.composite_score, 2),
        } for i, r in enumerate(top)]

        # Average metrics
        avg_metrics = {
            "avg_cagr": round(np.mean([r.cagr_pct for r in top if r.cagr_pct != 0]), 2),
            "avg_sharpe": round(np.mean([r.sharpe_ratio for r in top if r.sharpe_ratio != 0]), 3),
            "avg_win_rate": round(np.mean([r.win_rate for r in top]), 1),
            "avg_max_dd": round(np.mean([r.max_drawdown_pct for r in top]), 2),
            "avg_profit_factor": round(np.mean([r.profit_factor for r in top]), 3),
            "avg_trades": int(np.mean([r.total_trades for r in top])),
        }
        report["average_metrics"] = avg_metrics

        # Best params analysis
        param_counts = defaultdict(int)
        for r in top:
            p = r.strategy
            param_counts[f"EMA_F{p.ema_fast}"] += 1
            param_counts[f"EMA_S{p.ema_slow}"] += 1
            param_counts[f"RSI{p.rsi_period}"] += 1
            param_counts[f"MACD{p.macd_fast}_{p.macd_slow}_{p.macd_signal}"] += 1
        report["best_params_summary"] = dict(sorted(param_counts.items(), key=lambda x: x[1], reverse=True)[:15])

        # Top 3 detail
        for r in top[:3]:
            entry_signals = []
            if r.strategy.use_trend_filter:
                entry_signals.append("Trend Filter (EMA)")
            if r.strategy.use_volume_filter:
                entry_signals.append(f"Volume > {r.strategy.volume_ratio_min}x")
            if r.strategy.use_momentum_filter:
                entry_signals.append("MACD + RSI")
            if r.strategy.use_adx_filter:
                entry_signals.append(f"ADX > {r.strategy.adx_threshold}")
            if r.strategy.use_mfi_filter:
                entry_signals.append(f"MFI > {r.strategy.mfi_threshold}")
            if r.strategy.use_supertrend:
                entry_signals.append("SuperTrend")

            report["top_3_detail"].append({
                "rank": len(report["top_3_detail"]) + 1,
                "params": {
                    "ema": f"{r.strategy.ema_fast}/{r.strategy.ema_slow}",
                    "rsi": f"{r.strategy.rsi_period}({r.strategy.rsi_oversold:.0f}-{r.strategy.rsi_overbought:.0f})",
                    "macd": f"{r.strategy.macd_fast}/{r.strategy.macd_slow}/{r.strategy.macd_signal}",
                    "stoploss": f"{r.strategy.stop_loss_pct}%",
                    "takeprofit": f"{r.strategy.take_profit_pct}%",
                    "max_hold": f"{r.strategy.max_hold_days} ngày",
                },
                "entry_signals": entry_signals,
                "performance": report["top_strategies"][len(report["top_3_detail"])] if len(report["top_strategies"]) > len(report["top_3_detail"]) else {},
            })

        return report


def run_timeframe_backtest(pipeline, ranker, generator, data, timeframe: str, strategies, max_strategies=100):
    print(f"\n{'='*60}")
    print(f"TIMEFRAME: {timeframe.upper()}")
    print(f"{'='*60}")

    # Resample data to timeframe
    tf_data = pipeline.resample_to_timeframe(data, timeframe) if timeframe != "daily" else data
    if not tf_data:
        print(f"Khong co du lieu cho khung {timeframe}")
        return None, None

    # Split periods
    all_symbols = list(tf_data.keys())[:5]
    train_data = {}
    val_data = {}
    for sym in all_symbols:
        df = tf_data[sym].copy()
        df["date"] = pd.to_datetime(df["date"])
        cutoff1 = datetime.now() - timedelta(days=365)
        cutoff2 = datetime.now() - timedelta(days=180)
        train_df = df[df["date"] < cutoff1].copy()
        val_df = df[(df["date"] >= cutoff1) & (df["date"] < cutoff2)].copy()
        min_bars = 30 if timeframe == "weekly" else 100
        if len(train_df) > min_bars: train_data[sym] = train_df
        if len(val_df) > 10: val_data[sym] = val_df

    print(f"Train: {len(train_data)} symbols | Val: {len(val_data)} symbols")

    # Run backtest
    print(f"\nBacktesting {min(max_strategies, len(strategies))} strategies x {len(train_data)} symbols...")
    results = pipeline.run_backtest_batch(train_data, strategies[:max_strategies], symbols_limit=5)

    if not results:
        print("Khong co ket qua backtest")
        return None, None

    # Rank
    ranked = ranker.rank(results)
    top20 = ranker.top_n(20)
    print(f"Top strategies after filter: {len(top20)}")

    if not top20:
        print(f"Khong co chien luoc dat filter cho khung {timeframe}")
        return None, None

    # Report
    report = pipeline.generate_report(ranked, f"{timeframe} train")
    print(f"\nTop 5 - {timeframe}:")
    for i, r in enumerate(top20[:5]):
        k = r.strategy.combination_key[:50]
        print(f"  #{i+1}: {k}... CAGR={r.cagr_pct:.1f}% SR={r.sharpe_ratio:.2f} WR={r.win_rate:.1f}% Trades={r.total_trades} PF={r.profit_factor:.2f} Comp={r.composite_score:.1f}")

    # OOS test
    oos_result = None
    if val_data:
        best_strat = top20[0].strategy
        print(f"\nOOS test: {best_strat.combination_key[:50]}...")
        oos_results = pipeline.run_backtest_batch(val_data, [best_strat], symbols_limit=3)
        if oos_results:
            oos_result = oos_results[0]
            print(f"OOS: CAGR={oos_result.cagr_pct:.1f}% SR={oos_result.sharpe_ratio:.2f} DD={oos_result.max_drawdown_pct:.1f}% Trades={oos_result.total_trades}")
            print(f"Train CAGR: {top20[0].cagr_pct:.1f}% -> OOS CAGR: {oos_result.cagr_pct:.1f}%")
            if oos_result.cagr_pct > 0:
                print("=> Chiến lược bền vững (out-of-sample vẫn có lãi)")
            else:
                print("=> Chiến lược có dấu hiệu overfitting")

    return ranked, report


def main():
    print("=" * 60)
    print("BACKTEST ENGINE - THI TRUONG CHUNG KHOAN VIET NAM")
    print("=" * 60)
    print("Khung giao dich: Daily + Weekly (hourly can intraday API tu SSI - chua co)")

    pipeline = BacktestPipeline()
    ranker = StrategyRanker()
    generator = StrategyGenerator()

    # Step 1: Generate strategies
    print("\n--- SINH CHIEN LUOC ---")
    strategies = generator.generate(max_combinations=200)
    print(f"Sinh {len(strategies)} chien luoc")

    # Step 2: Load data
    print("\n--- LAY DU LIEU ---")
    hose_symbols = ["SSI", "FPT", "HPG", "VCB", "ACB", "TCB", "MBB", "STB", "VNM", "MWG",
                    "CTG", "BID", "GAS", "VHM", "MSN", "PNJ", "REE", "SAB", "PLX", "VIC"]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(script_dir, "..", "data", "backtest_cache")
    data = pipeline.load_data(hose_symbols[:10], years=3, cache_dir=cache_dir)

    if not data:
        print("Khong co du lieu! Hay thu lai sau.")
        return

    # Step 3: Run multi-timeframe backtest
    all_reports = {}

    # DAILY
    daily_ranked, daily_report = run_timeframe_backtest(
        pipeline, StrategyRanker(), generator, data, "daily", strategies, max_strategies=100
    )
    if daily_report:
        all_reports["daily"] = daily_report

    # WEEKLY
    weekly_ranked, weekly_report = run_timeframe_backtest(
        pipeline, StrategyRanker(), generator, data, "weekly", strategies, max_strategies=100
    )
    if weekly_report:
        all_reports["weekly"] = weekly_report

    # Step 4: Save combined report
    combined = {
        "timeframes_tested": list(all_reports.keys()),
        "note": "Hourly khong kha dung do SSI API khong cung cap intraday data",
        "timestamp": datetime.now().isoformat(),
        "results": all_reports,
    }
    report_path = os.path.join(script_dir, "..", "data", "backtest_mtf_report.json")
    with open(report_path, "w") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print(f"\nLuu bao cao multi-timeframe: {report_path}")

    # Step 5: Summary
    print(f"\n{'='*60}")
    print("KET QUA MULTI-TIMEFRAME BACKTEST")
    print(f"{'='*60}")
    for tf, rep in all_reports.items():
        print(f"\n--- {tf.upper()} ---")
        top = rep.get("top_strategies", [])[:3]
        for s in top:
            print(f"  #{s['rank']}: CAGR={s['cagr']}% Sharpe={s['sharpe']} WR={s['win_rate']}% PF={s['profit_factor']} Comp={s['composite_score']}")

    print("\nDone!")


if __name__ == "__main__":
    main()
