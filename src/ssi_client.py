import json
import time
from datetime import datetime, timedelta
from typing import Optional
import threading
import requests
import pandas as pd
from dataclasses import dataclass, asdict
from src.config import config


@dataclass
class AccessTokenReq:
    consumerID: str = ""
    consumerSecret: str = ""


@dataclass
class DailyStockPriceReq:
    symbol: str = ""
    fromDate: str = ""
    toDate: str = ""
    pageIndex: int = 1
    pageSize: int = 100
    market: str = ""


@dataclass
class SecuritiesDetailsReq:
    market: str = ""
    symbol: str = ""
    pageIndex: int = 1
    pageSize: int = 10


class SSIClient:
    def __init__(self):
        self.consumer_id = config.SSI_CONSUMER_ID
        self.consumer_secret = config.SSI_CONSUMER_SECRET
        self.data_api_url = config.SSI_DATA_API_URL.rstrip("/")
        self.access_token = None
        self.token_expires_at = 0

    def _get_access_token(self) -> str:
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        url = f"{self.data_api_url}/api/v2/Market/AccessToken"
        payload = {
            "consumerID": self.consumer_id,
            "consumerSecret": self.consumer_secret,
        }
        resp = requests.post(url, json=payload, timeout=30)
        data = resp.json()
        if data.get("status") != 200 and data.get("message") != "Success":
            raise Exception(f"SSI Auth failed: {data.get('message', 'Unknown error')}")

        self.access_token = data["data"]["accessToken"]
        self.token_expires_at = time.time() + 3600
        return self.access_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    _last_request_time = 0
    _rate_lock = threading.Lock()

    def _rate_limit(self):
        with self._rate_lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < 1.1:
                time.sleep(1.1 - elapsed)
            self._last_request_time = time.time()

    def _get(self, endpoint: str, params: dict) -> dict:
        self._rate_limit()
        url = f"{self.data_api_url}{endpoint}"
        resp = requests.get(url, params=params, headers=self._headers(), timeout=30)
        data = resp.json()
        if data.get("message") != "Success":
            raise Exception(f"API error {endpoint}: {data.get('message', 'Unknown')}")
        return data

    def get_daily_stock_price(
        self,
        symbol: str,
        from_date: str = None,
        to_date: str = None,
        page_size: int = 100,
        market: str = "HOSE",
    ) -> pd.DataFrame:
        if not from_date or not to_date:
            today = datetime.now()
            from_date = (today - timedelta(days=30)).strftime("%d/%m/%Y")
            to_date = today.strftime("%d/%m/%Y")
        params = {
            "symbol": symbol.upper(),
            "fromDate": from_date,
            "toDate": to_date,
            "pageSize": page_size,
            "market": market,
        }

        data = self._get("/api/v2/Market/DailyStockPrice", params)
        items = data.get("data", [])
        if not items:
            return pd.DataFrame()

        records = []
        for item in items:
            records.append(
                {
                    "symbol": item.get("Symbol"),
                    "date": item.get("TradingDate"),
                    "open": float(item.get("OpenPrice", 0)),
                    "high": float(item.get("HighestPrice", 0)),
                    "low": float(item.get("LowestPrice", 0)),
                    "close": float(item.get("ClosePrice", 0)),
                    "adj_close": float(item.get("ClosePriceAdjusted", 0)),
                    "volume": int(float(item.get("TotalMatchVol", 0))),
                    "value": float(item.get("TotalMatchVal", 0)),
                    "change": float(item.get("PriceChange", 0)),
                    "change_pct": float(item.get("PerPriceChange", 0)),
                    "ceiling": float(item.get("CeilingPrice", 0)),
                    "floor": float(item.get("FloorPrice", 0)),
                    "ref": float(item.get("RefPrice", 0)),
                    "foreign_buy": float(item.get("ForeignBuyValTotal", 0)),
                    "foreign_sell": float(item.get("ForeignSellValTotal", 0)),
                    "foreign_room": float(item.get("ForeignCurrentRoom", 0)),
                }
            )

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y")
        df = df.sort_values("date").reset_index(drop=True)
        return df

    def get_company_info(self, symbol: str) -> dict:
        params = {"symbol": symbol.upper()}
        try:
            data = self._get("/api/v2/Market/SecuritiesDetails", params)
            items = data.get("data", [])
            if items:
                repeated = items[0].get("RepeatedInfo", [])
                if repeated:
                    info = repeated[0]
                    return {
                        "symbol": info.get("Symbol", ""),
                        "companyName": info.get("SymbolName", ""),
                        "companyEngName": info.get("SymbolEngName", ""),
                        "exchange": info.get("Exchange", ""),
                        "industry": info.get("SecType", ""),
                        "listedShares": info.get("ListedShare", "0"),
                    }
        except Exception:
            pass
        return {}

    def get_securities_list(self, market: str = "HOSE") -> pd.DataFrame:
        params = {"market": market, "pageIndex": 1, "pageSize": 1000}
        try:
            data = self._get("/api/v2/Market/Securities", params)
            return pd.DataFrame(data.get("data", []))
        except Exception:
            return pd.DataFrame()

    def get_index_components(self, index_symbol: str = "VNINDEX") -> pd.DataFrame:
        params = {"indexCode": index_symbol}
        try:
            data = self._get("/api/v2/Market/IndexComponents", params)
            return pd.DataFrame(data.get("data", []))
        except Exception:
            return pd.DataFrame()
