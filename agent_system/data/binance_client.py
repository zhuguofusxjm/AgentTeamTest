import hashlib
import hmac
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def build_signature(secret: str, query_string: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _build_session() -> requests.Session:
    """Session with HTTP-level retry on 5xx and connect errors.

    Note: 仅 urllib3 Retry 不挡住 mid-stream RST(ConnectionResetError),
    所以 _get 还要再做一层 wall.
    """
    s = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,  # 0.5, 1, 2 秒
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=16)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


class BinanceClient:
    BASE_URL = "https://fapi.binance.com"
    DEFAULT_TIMEOUT = 30
    APP_RETRY_MAX = 3   # 应用层重试次数(挡 mid-stream reset)
    APP_RETRY_BACKOFF = 1.0

    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self._session = _build_session()

    def _headers(self):
        h = {}
        if self.api_key:
            h["X-MBX-APIKEY"] = self.api_key
        return h

    def _get(self, path: str, params: dict = None) -> dict | list:
        url = f"{self.BASE_URL}{path}"
        last_err = None
        for attempt in range(self.APP_RETRY_MAX):
            try:
                r = self._session.get(url, params=params, headers=self._headers(),
                                       timeout=self.DEFAULT_TIMEOUT)
                r.raise_for_status()
                return r.json()
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.Timeout) as e:
                last_err = e
                if attempt < self.APP_RETRY_MAX - 1:
                    time.sleep(self.APP_RETRY_BACKOFF * (2 ** attempt))
                    continue
                raise
        raise last_err  # unreachable, 但让静态分析放心

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
