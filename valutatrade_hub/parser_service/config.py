"""Конфигурация Parser Service: ключи, эндпоинты, списки валют, пути."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return here.parents[2]


def _load_dotenv(path: Path) -> None:
    """Простейший .env-парсер: KEY=VALUE, без внешних зависимостей."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


@dataclass
class ParserConfig:
    # Загружается из .env или переменной окружения
    EXCHANGERATE_API_KEY: str = ""
    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"
    # Списки валют
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict = field(default_factory=lambda: {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
    })
    # Сетевые параметры
    REQUEST_TIMEOUT: int = 10
    # Относительные пути (разрешаются в __post_init__)
    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"
    # Производные (не передаются в конструктор)
    rates_path: Path = field(init=False)
    history_path: Path = field(init=False)

    def __post_init__(self) -> None:
        root = _project_root()
        _load_dotenv(root / ".env")
        if not self.EXCHANGERATE_API_KEY:
            self.EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY", "")
        self.rates_path = root / self.RATES_FILE_PATH
        self.history_path = root / self.HISTORY_FILE_PATH
        self.rates_path.parent.mkdir(parents=True, exist_ok=True)