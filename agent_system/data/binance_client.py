import hashlib
import hmac
import requests

def build_signature(secret: str, query_string: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

class BinanceClient:
    BASE_URL = "https://fapi.binance.com"
    DEFAULT_TIMEOUT = 30

    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def _headers(self):
        h = {}
        if self.api_key:
            h["X-MBX-APIKEY"] = self.api_key
        return h

    def _get(self, path: str, params: dict = None) -> dict | list:
        url = f"{self.BASE_URL}{path}"
        r = requests.get(url, params=params, headers=self._headers(), timeout=self.DEFAULT_TIMEOUT)
        r.raise_for_status()
        return r.json()

    def get_klines(self, symbol, interval, limit=500, start_time=None, end_time=None):
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time is not None: params["startTime"] = start_time
        if end_time is not None: params["endTime"] = end_time
        return self._get("/fapi/v1/klines", params)

    def get_funding_rate_history(self, symbol, limit=1000, start_time=None, end_time=None):
        params = {"symbol": symbol, "limit": limit}
        if start_time is not None: params["startTime"] = start_time
        if end_time is not None: params["endTime"] = end_time
        return self._get("/fapi/v1/fundingRate", params)

    def get_funding_info(self):
        return self._get("/fapi/v1/fundingInfo")

    def get_open_interest_hist(self, symbol, period="1h", limit=500):
        return self._get("/futures/data/openInterestHist",
                          {"symbol": symbol, "period": period, "limit": limit})

    def get_top_long_short_position_ratio(self, symbol, period="1h", limit=500):
        return self._get("/futures/data/topLongShortPositionRatio",
                          {"symbol": symbol, "period": period, "limit": limit})

    def get_top_long_short_account_ratio(self, symbol, period="1h", limit=500):
        return self._get("/futures/data/topLongShortAccountRatio",
                          {"symbol": symbol, "period": period, "limit": limit})

    def get_global_long_short_account_ratio(self, symbol, period="1h", limit=500):
        return self._get("/futures/data/globalLongShortAccountRatio",
                          {"symbol": symbol, "period": period, "limit": limit})

    def get_premium_index(self, symbol=None):
        params = {"symbol": symbol} if symbol else None
        return self._get("/fapi/v1/premiumIndex", params)

    def get_24h_ticker(self):
        return self._get("/fapi/v1/ticker/24hr")
