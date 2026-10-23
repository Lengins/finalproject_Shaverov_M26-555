"""Бизнес-логика. Валидация валют — через реестр, I/O — через DatabaseManager,
логирование — через @log_action."""
from __future__ import annotations

from ..decorators import log_action
from ..infra.database import DatabaseManager
from . import utils
from .currencies import get_currency
from .exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from .models import Portfolio, User

_db = DatabaseManager()


# ---------------------- Регистрация/логин ----------------------

@log_action("REGISTER")
def register_user(username: str, password: str) -> User:
    if not username or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")
    if not password or len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    users = _db.load_users()
    if any(u["username"] == username for u in users):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    new_id = max((u["user_id"] for u in users), default=0) + 1
    user = User.create(user_id=new_id, username=username, password=password)
    users.append(user.to_dict())
    _db.save_users(users)

    portfolios = _db.load_portfolios()
    portfolios.append({"user_id": new_id, "wallets": {}})
    _db.save_portfolios(portfolios)
    return user


@log_action("LOGIN")
def login_user(username: str, password: str) -> User:
    users = _db.load_users()
    record = next((u for u in users if u["username"] == username), None)
    if record is None:
        raise ValueError(f"Пользователь '{username}' не найден")
    user = User.from_dict(record)
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")
    return user


# ---------------------- Портфель ----------------------

def load_portfolio(user: User) -> Portfolio:
    portfolios = _db.load_portfolios()
    record = next((p for p in portfolios if p["user_id"] == user.user_id), None)
    if record is None:
        record = {"user_id": user.user_id, "wallets": {}}
    return Portfolio.from_dict(record, user=user)


def save_portfolio(portfolio: Portfolio) -> None:
    portfolios = _db.load_portfolios()
    idx = next((i for i, p in enumerate(portfolios)
                if p["user_id"] == portfolio.user_id), None)
    data = portfolio.to_dict()
    if idx is None:
        portfolios.append(data)
    else:
        portfolios[idx] = data
    _db.save_portfolios(portfolios)


def show_portfolio(user: User, base: str | None = None) -> dict:
    base = (base or utils._settings.base_currency).upper()
    get_currency(base)  # CurrencyNotFoundError, если код неизвестен

    portfolio = load_portfolio(user)
    if not portfolio.wallets:
        return {"user": user.username, "base": base,
                "wallets": [], "total": 0.0}

    rates_map = utils.get_rates_map()
    rows, total = [], 0.0
    for code, wallet in portfolio.wallets.items():
        try:
            rate = Portfolio._rate_to_base(code, base, rates_map)
            value = wallet.balance * rate
            total += value
        except ValueError:
            value = None
        rows.append({"currency": code, "balance": wallet.balance, "value": value})
    return {"user": user.username, "base": base,
            "wallets": rows, "total": total}


# ---------------------- Покупка/продажа ----------------------

def _usd_rate(currency: str) -> float | None:
    if currency == "USD":
        return 1.0
    try:
        rate, _ = utils.get_rate(currency, "USD")
        return rate
    except (ApiRequestError, CurrencyNotFoundError):   
        return None


@log_action("BUY", verbose=True)
def buy(user: User, currency_code: str, amount: float) -> dict:
    currency = get_currency(currency_code)
    amount = utils.validate_positive_amount(amount)

    portfolio = load_portfolio(user)
    wallet = portfolio.get_wallet(currency.code)
    if wallet is None:
        wallet = portfolio.add_currency(currency.code)
    old = wallet.balance
    wallet.deposit(amount)

    rate = _usd_rate(currency.code)
    save_portfolio(portfolio)
    return {
        "currency": currency.code,
        "amount": amount,
        "rate": rate,
        "old": old,
        "new": wallet.balance,
        "estimated_usd": amount * rate if rate is not None else None,
    }


@log_action("SELL", verbose=True)
def sell(user: User, currency_code: str, amount: float) -> dict:
    currency = get_currency(currency_code)
    amount = utils.validate_positive_amount(amount)

    portfolio = load_portfolio(user)
    wallet = portfolio.get_wallet(currency.code)
    if wallet is None:
        raise InsufficientFundsError(0.0, amount, currency.code)
    old = wallet.balance
    wallet.withdraw(amount)  # бросает InsufficientFundsError

    rate = _usd_rate(currency.code)
    save_portfolio(portfolio)
    return {
        "currency": currency.code,
        "amount": amount,
        "rate": rate,
        "old": old,
        "new": wallet.balance,
        "estimated_usd": amount * rate if rate is not None else None,
    }


# ---------------------- Курс ----------------------

@log_action("GET_RATE")
def get_rate_info(from_code: str, to_code: str) -> dict:
    f = get_currency(from_code).code
    t = get_currency(to_code).code
    rate, updated_at = utils.get_rate(f, t)
    return {
        "from": f,
        "to": t,
        "rate": rate,
        "reverse": (1.0 / rate) if rate else None,
        "updated_at": updated_at,
    }