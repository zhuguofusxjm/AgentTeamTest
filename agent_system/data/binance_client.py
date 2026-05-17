import hashlib
import hmac
import time
import requests

def build_signature(secret: str, query_string: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

class BinanceClient:
    BASE_URL = "https://fapi.binance.com"

    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def _headers(self):
        h = {}
        if self.api_key:
            h["X-MBX-APIKEY"] = self.api_key
        return h

    def get_klines(self, symbol: str, interval: str, limit: int = 500, start_time: int = None, end_time: int = None):
        url = f"{self.BASE_URL}/fapi/v1/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_funding_rate_history(self, symbol: str, limit: int = 1000, start_time: int = None, end_time: int = None):
        url = f"{self.BASE_URL}/fapi/v1/fundingRate"
        params = {"symbol": symbol, "limit": limit}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_funding_info(self):
        url = f"{self.BASE_URL}/fapi/v1/fundingInfo"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_open_interest_hist(self, symbol: str, period: str = "1h", limit: int = 500):
        url = f"{self.BASE_URL}/futures/data/openInterestHist"
        params = {"symbol": symbol, "period": period, "limit": limit}
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_top_long_short_position_ratio(self, symbol: str, period: str = "1h", limit: int = 500):
        url = f"{self.BASE_URL}/futures/data/topLongShortPositionRatio"
        params = {"symbol": symbol, "period": period, "limit": limit}
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_top_long_short_account_ratio(self, symbol: str, period: str = "1h", limit: int = 500):
        url = f"{self.BASE_URL}/futures/data/topLongShortAccountRatio"
        params = {"symbol": symbol, "period": period, "limit": limit}
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_global_long_short_account_ratio(self, symbol: str, period: str = "1h", limit: int = 500):
        url = f"{self.BASE_URL}/futures/data/globalLongShortAccountRatio"
        params = {"symbol": symbol, "period": period, "limit": limit}
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_premium_index(self, symbol: str = None):
        url = f"{self.BASE_URL}/fapi/v1/premiumIndex"
        params = {"symbol": symbol} if symbol else {}
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_24h_ticker(self):
        url = f"{self.BASE_URL}/fapi/v1/ticker/24hr"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()
