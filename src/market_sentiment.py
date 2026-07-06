import math
from datetime import datetime


class GreedFearIndex:
    def __init__(self):
        self.components = {}

    def compute_rsi_component(self, close_prices: list) -> float:
        if len(close_prices) < 15:
            return 50
        gains, losses = 0, 0
        for i in range(1, 15):
            chg = close_prices[-i] - close_prices[-i - 1]
            if chg >= 0:
                gains += chg
            else:
                losses += abs(chg)
        avg_gain = gains / 14
        avg_loss = losses / 14
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        if rsi <= 30:
            return max(0, 25 - ((30 - rsi) / 30) * 25)
        elif rsi <= 45:
            return 25 + ((rsi - 30) / 15) * 20
        elif rsi <= 55:
            return 45 + ((rsi - 45) / 10) * 10
        elif rsi <= 70:
            return 55 + ((rsi - 55) / 15) * 20
        else:
            return min(100, 75 + ((rsi - 70) / 30) * 25)

    def compute_volatility_component(self, close_prices: list) -> float:
        if len(close_prices) < 21:
            return 50
        returns = []
        for i in range(1, 21):
            r = (close_prices[-i] - close_prices[-i - 1]) / close_prices[-i - 1]
            returns.append(r)
        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        daily_vol = math.sqrt(variance)
        annual_vol = daily_vol * math.sqrt(252)
        vol_pct = annual_vol * 100
        if vol_pct >= 40:
            return max(0, 25 - ((vol_pct - 40) / 40) * 25)
        elif vol_pct >= 25:
            return 25 + ((40 - vol_pct) / 15) * 20
        elif vol_pct >= 15:
            return 45 + ((25 - vol_pct) / 10) * 10
        elif vol_pct >= 10:
            return 55 + ((15 - vol_pct) / 5) * 20
        else:
            return min(100, 75 + ((10 - vol_pct) / 10) * 25)

    def compute_momentum_component(self, close_prices: list) -> float:
        if len(close_prices) < 21:
            return 50
        mom = (close_prices[-1] - close_prices[-21]) / close_prices[-21] * 100
        if mom <= -5:
            return max(0, 25 - ((abs(mom) - 5) / 10) * 25)
        elif mom <= -1:
            return 25 + ((abs(mom) - 1) / 4) * 20
        elif mom <= 1:
            return 45 + ((1 - abs(mom)) / 1) * 10
        elif mom <= 5:
            return 55 + ((mom - 1) / 4) * 20
        else:
            return min(100, 75 + ((mom - 5) / 10) * 25)

    def compute_breadth_component(self, advances: list, declines: list) -> float:
        if not advances or not declines:
            return 50
        recent_a = advances[-5:] if len(advances) >= 5 else advances
        recent_d = declines[-5:] if len(declines) >= 5 else declines
        total_a = sum(recent_a)
        total_d = sum(recent_d)
        if total_a + total_d == 0:
            return 50
        breadth_ratio = total_a / (total_a + total_d)
        if breadth_ratio <= 0.25:
            return max(0, 25 - ((0.25 - breadth_ratio) / 0.25) * 25)
        elif breadth_ratio <= 0.40:
            return 25 + ((breadth_ratio - 0.25) / 0.15) * 20
        elif breadth_ratio <= 0.55:
            return 45 + ((breadth_ratio - 0.40) / 0.15) * 10
        elif breadth_ratio <= 0.70:
            return 55 + ((breadth_ratio - 0.55) / 0.15) * 20
        else:
            return min(100, 75 + ((breadth_ratio - 0.70) / 0.30) * 25)

    def analyze(self, idx_prices: list) -> dict:
        if not idx_prices:
            return {"index": 50, "label": "TRUNG TÍNH", "components": {}}

        close_prices = [p.get("close", 0) for p in idx_prices if p.get("close", 0) > 0]
        advances = [p.get("advances", 0) for p in idx_prices if p.get("advances") is not None]
        declines = [p.get("declines", 0) for p in idx_prices if p.get("declines") is not None]

        if not close_prices:
            return {"index": 50, "label": "TRUNG TÍNH", "components": {}}

        rsi_score = self.compute_rsi_component(close_prices)
        vol_score = self.compute_volatility_component(close_prices)
        mom_score = self.compute_momentum_component(close_prices)
        breadth_score = self.compute_breadth_component(advances, declines)

        weights = {"rsi": 0.25, "volatility": 0.25, "momentum": 0.25, "breadth": 0.25}
        combined = (
            rsi_score * weights["rsi"]
            + vol_score * weights["volatility"]
            + mom_score * weights["momentum"]
            + breadth_score * weights["breadth"]
        )

        if combined >= 75:
            label = "THAM LAM CỰC ĐỘ"
            level = "extreme_greed"
        elif combined >= 55:
            label = "THAM LAM"
            level = "greed"
        elif combined >= 45:
            label = "TRUNG TÍNH"
            level = "neutral"
        elif combined >= 25:
            label = "SỢ HÃI"
            level = "fear"
        else:
            label = "SỢ HÃI CỰC ĐỘ"
            level = "extreme_fear"

        last_close = close_prices[-1] if close_prices else 0
        last_adv = advances[-1] if advances else 0
        last_dec = declines[-1] if declines else 0

        self.components = {
            "rsi": round(rsi_score, 1),
            "volatility": round(vol_score, 1),
            "momentum": round(mom_score, 1),
            "breadth": round(breadth_score, 1),
        }

        return {
            "index": round(combined, 1),
            "label": label,
            "level": level,
            "components": self.components,
            "market_data": {
                "vnindex": last_close,
                "advances": last_adv,
                "declines": last_dec,
                "rsi_value": round(self.compute_rsi_component(close_prices), 1),
                "volatility_pct": round(self._calc_volatility(close_prices), 2) if len(close_prices) >= 2 else 0,
                "momentum_pct": round(
                    (close_prices[-1] - close_prices[-21]) / close_prices[-21] * 100, 2
                ) if len(close_prices) >= 21 else 0,
                "breadth_ratio": round(
                    sum(advances[-5:]) / (sum(advances[-5:]) + sum(declines[-5:])), 2
                ) if len(advances) >= 5 and (sum(advances[-5:]) + sum(declines[-5:])) > 0 else 0,
            },
            "analyzed_at": datetime.now().isoformat(),
        }

    def _calc_volatility(self, close_prices: list) -> float:
        if len(close_prices) < 2:
            return 0
        returns = []
        for i in range(1, len(close_prices)):
            r = (close_prices[i] - close_prices[i - 1]) / close_prices[i - 1]
            returns.append(r)
        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        return math.sqrt(variance) * math.sqrt(252) * 100
