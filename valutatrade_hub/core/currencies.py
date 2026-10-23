"""Иерархия валют: ABC Currency + Fiat/Crypto + реестр get_currency()."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Абстрактная валюта. Инварианты: code — 2–5 символов, верхний регистр,
    без пробелов; name — непустая строка."""

    def __init__(self, name: str, code: str) -> None:
        self._validate_name(name)
        self._validate_code(code)
        self.name: str = name
        self.code: str = code

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Имя валюты не может быть пустым")

    @staticmethod
    def _validate_code(code: str) -> None:
        if not isinstance(code, str):
            raise TypeError("Код валюты должен быть строкой")
        if code != code.upper():
            raise ValueError("Код валюты должен быть в верхнем регистре")
        if not (2 <= len(code) <= 5) or not code.isalnum():
            raise ValueError(
                "Код валюты должен быть 2–5 символов, без пробелов и спецсимволов"
            )

    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление для UI/логов."""


class FiatCurrency(Currency):
    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name, code)
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("Страна/зона эмиссии не может быть пустой")
        self.issuing_country: str = issuing_country

    def get_display_info(self) -> str:
        return (f"[FIAT] {self.code} — {self.name} "
                f"(Issuing: {self.issuing_country})")


class CryptoCurrency(Currency):
    def __init__(self, name: str, code: str, algorithm: str,
                 market_cap: float) -> None:
        super().__init__(name, code)
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым")
        if isinstance(market_cap, bool) or not isinstance(market_cap, (int, float)):
            raise TypeError("market_cap должен быть числом")
        if market_cap < 0:
            raise ValueError("market_cap не может быть отрицательным")
        self.algorithm: str = algorithm
        self.market_cap: float = float(market_cap)

    def get_display_info(self) -> str:
        mcap = f"{self.market_cap:.2e}".replace("e+", "e")
        return (f"[CRYPTO] {self.code} — {self.name} "
                f"(Algo: {self.algorithm}, MCAP: {mcap})")


# ------------------------- Реестр -------------------------

_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("Pound Sterling", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.05e11),
}


def get_currency(code: str) -> Currency:
    """Возвращает валюту по коду. Бросает CurrencyNotFoundError."""
    if not isinstance(code, str) or not code.strip():
        raise CurrencyNotFoundError(code or "")
    currency = _REGISTRY.get(code.strip().upper())
    if currency is None:
        raise CurrencyNotFoundError(code.strip().upper())
    return currency


def list_currencies() -> list[str]:
    return sorted(_REGISTRY.keys())