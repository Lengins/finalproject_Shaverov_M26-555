#Модели данных для платформы ValutaTrade Hub.

from __future__ import annotations
from .exceptions import InsufficientFundsError

import hashlib
import secrets
from datetime import datetime
from typing import Optional


# Заглушка курсов (пока Parser Service не подключён).
# Ключ — пара "FROM_TO", значение — сколько единиц TO даёт 1 единица FROM.
DEFAULT_EXCHANGE_RATES: dict[str, float] = {
    "EUR_USD": 1.0786,
    "BTC_USD": 59337.21,
    "ETH_USD": 3720.00,
    "RUB_USD": 0.01016,
}


# ---------------------------------------------------------------------------
# Вспомогательные валидаторы
# ---------------------------------------------------------------------------
def _validate_positive_amount(amount: float, field_name: str = "amount") -> float:
    """Проверяет, что сумма — положительное число. Возвращает float."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ValueError(f"'{field_name}' должен быть числом")
    if amount <= 0:
        raise ValueError(f"'{field_name}' должен быть положительным числом")
    return float(amount)


def _validate_currency_code(code: str) -> str:
    """Проверяет и нормализует код валюты (верхний регистр, не пустой)."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты не может быть пустым")
    return code.strip().upper()


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User:
    """Пользователь системы."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    # --- Фабричный метод для регистрации (генерирует соль и хеш) ---
    @classmethod
    def create(cls, user_id: int, username: str, password: str) -> "User":
        cls._validate_username(username)
        cls._validate_password(password)
        salt = secrets.token_hex(8)
        hashed = cls._hash_password(password, salt)
        return cls(user_id, username, hashed, salt, datetime.now())

    # --- Валидация ---
    @staticmethod
    def _validate_username(username: str) -> None:
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")

    @staticmethod
    def _validate_password(password: str) -> None:
        if not isinstance(password, str) or len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    # --- Геттеры ---
    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    # --- Сеттер с проверкой ---
    @username.setter
    def username(self, value: str) -> None:
        self._validate_username(value)
        self._username = value

    # --- Публичные методы ---
    def get_user_info(self) -> dict[str, object]:
        """Информация о пользователе (без пароля и соли)."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def verify_password(self, password: str) -> bool:
        """Сверяет пароль с сохранённым хешем."""
        if not isinstance(password, str):
            return False
        return self._hash_password(password, self._salt) == self._hashed_password

    def change_password(self, new_password: str) -> None:
        """Меняет пароль: генерирует новую соль и хеш."""
        self._validate_password(new_password)
        new_salt = secrets.token_hex(8)
        self._salt = new_salt
        self._hashed_password = self._hash_password(new_password, new_salt)

    # --- Сериализация ---
    def to_dict(self) -> dict[str, object]:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )

    def __repr__(self) -> str:
        return f"User(user_id={self._user_id}, username={self._username!r})"


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------
class Wallet:
    """Кошелёк пользователя для одной конкретной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        self.currency_code = _validate_currency_code(currency_code)
        # Первичная установка через сеттер — гарантирует валидацию.
        self.balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """Пополняет баланс."""
        amount = _validate_positive_amount(amount)
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        """Снимает средства, если баланса достаточно."""
        amount = _validate_positive_amount(amount)
        if amount > self._balance:
            raise ValueError(
                f"Недостаточно средств: доступно {self._balance:.4f} "
                f"{self.currency_code}, требуется {amount:.4f} {self.currency_code}"
            )
        self._balance -= amount

    def get_balance_info(self) -> dict[str, object]:
        return {"currency_code": self.currency_code, "balance": self._balance}

    # --- Сериализация ---
    def to_dict(self) -> dict[str, object]:
        return {"currency_code": self.currency_code, "balance": self._balance}

    @classmethod
    def from_dict(cls, data: dict) -> "Wallet":
        return cls(currency_code=data["currency_code"], balance=data["balance"])

    def __repr__(self) -> str:
        return f"Wallet({self.currency_code!r}, balance={self._balance})"

    def withdraw(self, amount: float) -> None:
        amount = _validate_positive_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError(self._balance, amount, self.currency_code)
        self._balance -= amount

# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------
class Portfolio:
    """Портфель пользователя — набор кошельков по валютам."""

    def __init__(
        self,
        user_id: int,
        user: Optional[User] = None,
        wallets: Optional[dict[str, Wallet]] = None,
    ) -> None:
        self._user_id = user_id
        self._user = user
        self._wallets: dict[str, Wallet] = dict(wallets) if wallets else {}

    # --- Свойства ---
    @property
    def user(self) -> Optional[User]:
        """Пользователь-владелец (только геттер, без перезаписи)."""
        return self._user

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Копия словаря кошельков — защита от внешней мутации."""
        return dict(self._wallets)

    # --- Управление кошельками ---
    def add_currency(self, currency_code: str) -> Wallet:
        """Добавляет новый кошелёк. Возвращает созданный Wallet."""
        code = _validate_currency_code(currency_code)
        if code in self._wallets:
            raise ValueError(f"Кошелёк '{code}' уже существует в портфеле")
        wallet = Wallet(currency_code=code)
        self._wallets[code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        """Возвращает кошелёк по коду или None."""
        code = _validate_currency_code(currency_code)
        return self._wallets.get(code)

    # --- Оценка стоимости ---
    def get_total_value(
        self,
        base_currency: str = "USD",
        rates: Optional[dict[str, float]] = None,
    ) -> float:
        """Общая стоимость всех кошельков в базовой валюте."""
        base = _validate_currency_code(base_currency)
        rates_map = rates if rates is not None else DEFAULT_EXCHANGE_RATES
        total = 0.0
        for code, wallet in self._wallets.items():
            total += wallet.balance * self._rate_to_base(code, base, rates_map)
        return total

    @staticmethod
    def _rate_to_base(
        from_code: str, to_code: str, rates: dict[str, float]
    ) -> float:
        """Курс from_code → to_code (с поддержкой обратного курса)."""
        if from_code == to_code:
            return 1.0
        direct = rates.get(f"{from_code}_{to_code}")
        if direct is not None:
            return direct
        inverse = rates.get(f"{to_code}_{from_code}")
        if inverse:
            return 1.0 / inverse
        raise ValueError(f"Не удалось получить курс для {from_code}→{to_code}")

    # --- Сериализация ---
    def to_dict(self) -> dict[str, object]:
        return {
            "user_id": self._user_id,
            "wallets": {
                code: {"balance": w.balance} for code, w in self._wallets.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict, user: Optional[User] = None) -> "Portfolio":
        wallets = {
            code: Wallet(currency_code=code, balance=info["balance"])
            for code, info in data.get("wallets", {}).items()
        }
        return cls(user_id=data["user_id"], user=user, wallets=wallets)

    def __repr__(self) -> str:
        return f"Portfolio(user_id={self._user_id}, wallets={list(self._wallets)})"