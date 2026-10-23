"""Клиенты внешних API. Унифицированный интерфейс fetch_rates() -> dict[str, float]."""
from __future__ import annotations

from abc import ABC, abstractmethod

import requests

from ..core.exceptions import ApiRequestError
from .config import ParserConfig


class BaseApiClient(ABC):
    source_name: str = ""
    source_alias: str = ""

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Возвращает {FROM_TO: rate}. Бросает ApiRequestError при сбое."""


class CoinGeckoClient(BaseApiClient):
    source_name = "CoinGecko"
    source_alias = "coingecko"

    def __init__(self, config: ParserConfig) -> None:
        self._config = config

    def fetch_rates(self) -> dict[str, float]:
        codes = self._config.CRYPTO_CURRENCIES
        ids = ",".join(self._config.CRYPTO_ID_MAP[c] for c in codes)
        base = self._config.BASE_CURRENCY.lower()
        params = {"ids": ids, "vs_currencies": base}
        try:
            resp = requests.get(
                self._config.COINGECKO_URL,
                params=params,
                timeout=self._config.REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"CoinGecko: {exc}") from exc

        if resp.status_code != 200:
            raise ApiRequestError(f"CoinGecko: HTTP {resp.status_code}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise ApiRequestError("CoinGecko: некорректный JSON") from exc

        result: dict[str, float] = {}
        for code in codes:
            raw_id = self._config.CRYPTO_ID_MAP[code]
            price = payload.get(raw_id, {}).get(base)
            if isinstance(price, (int, float)):
                result[f"{code}_{self._config.BASE_CURRENCY}"] = float(price)
        return result


class ExchangeRateApiClient(BaseApiClient):
    source_name = "ExchangeRate-API"
    source_alias = "exchangerate"

    def __init__(self, config: ParserConfig) -> None:
        self._config = config

    def fetch_rates(self) -> dict[str, float]:
        key = self._config.EXCHANGERATE_API_KEY
        if not key:
            raise ApiRequestError("ExchangeRate-API: не задан EXCHANGERATE_API_KEY")

        base = self._config.BASE_CURRENCY
        url = f"{self._config.EXCHANGERATE_API_URL}/{key}/latest/{base}"
        try:
            resp = requests.get(url, timeout=self._config.REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"ExchangeRate-API: {exc}") from exc

        if resp.status_code == 429:
            raise ApiRequestError("ExchangeRate-API: превышен лимит запросов (429)")
        if resp.status_code != 200:
            raise ApiRequestError(f"ExchangeRate-API: HTTP {resp.status_code}")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise ApiRequestError("ExchangeRate-API: некорректный JSON") from exc

        if payload.get("result") != "success":
            reason = payload.get("error-type", "unknown")
            raise ApiRequestError(f"ExchangeRate-API: {reason}")

        rates = payload.get("rates", {})
        result: dict[str, float] = {}
        for code in self._config.FIAT_CURRENCIES:
            raw = rates.get(code)
            if isinstance(raw, (int, float)) and raw > 0:
                # API отдаёт "1 base = raw code" → нам нужен "1 code = X base"
                result[f"{code}_{base}"] = 1.0 / float(raw)
        return result