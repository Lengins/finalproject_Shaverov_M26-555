#Бизнес-логика приложения. Не зависит от CLI.
from __future__ import annotations

from . import utils
from .models import Portfolio, User


# ---------------------- Пользователи ----------------------

def register_user(username: str, password: str) -> User:
    if not username or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")
    if len(password or "") < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    users = utils.load_json(utils.USERS_FILE, [])
    if any(u["username"] == username for u in users):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    new_id = max([u["user_id"] for u in users], default=0) + 1
    user = User.create(user_id=new_id, username=username, password=password)
    users.append(user.to_dict())
    utils.save_json(utils.USERS_FILE, users)

    portfolios = utils.load_json(utils.PORTFOLIOS_FILE, [])
    portfolios.append({"user_id": new_id, "wallets": {}})
    utils.save_json(utils.PORTFOLIOS_FILE, portfolios)
    return user


def login_user(username: str, password: str) -> User:
    users = utils.load_json(utils.USERS_FILE, [])
    record = next((u for u in users if u["username"] == username), None)
    if not record:
        raise ValueError(f"Пользователь '{username}' не найден")
    user = User.from_dict(record)
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")
    return user


# ---------------------- Портфель ----------------------

def load_portfolio(user: User) -> Portfolio:
    portfolios = utils.load_json(utils.PORTFOLIOS_FILE, [])
    record = next((p for p in portfolios if p["user_id"] == user.user_id), None)
    if record is None:
        record = {"user_id": user.user_id, "wallets": {}}
    return Portfolio.from_dict(record, user=user)


def save_portfolio(portfolio: Portfolio) -> None:
    portfolios = utils.load_json(utils.PORTFOLIOS_FILE, [])
    idx = next((i for i, p in enumerate(portfolios)
                if p["user_id"] == portfolio.user_id), None)
    data = portfolio.to_dict()
    if idx is None:
        portfolios.append(data)
    else:
        portfolios[idx] = data
    utils.save_json(utils.PORTFOLIOS_FILE, portfolios)


def show_portfolio(user: User, base: str = "USD") -> dict:
    base = utils.validate_currency_code(base)
    portfolio = load_portfolio(user)

    if not portfolio.wallets:
        return {"user": user.username, "base": base, "wallets": [], "total": 0.0}

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
    return {"user": user.username, "base": base, "wallets": rows, "total": total}


# ---------------------- Покупка/продажа ----------------------

def _usd_rate(currency: str) -> float | None:
    try:
        if currency == "USD":
            return 1.0
        rate, _ = utils.get_rate(currency, "USD")
        return rate
    except ValueError:
        return None


def buy_currency(user: User, currency: str, amount: float) -> dict:
    currency = utils.validate_currency_code(currency)
    amount = utils.validate_positive_amount(amount)

    portfolio = load_portfolio(user)
    wallet = portfolio.get_wallet(currency)
    if wallet is None:
        wallet = portfolio.add_currency(currency)
    old = wallet.balance
    wallet.deposit(amount)

    rate = _usd_rate(currency)
    save_portfolio(portfolio)
    return {"currency": currency, "amount": amount, "rate": rate,
            "old": old, "new": wallet.balance,
            "estimated_usd": amount * rate if rate is not None else None}


def sell_currency(user: User, currency: str, amount: float) -> dict:
    currency = utils.validate_currency_code(currency)
    amount = utils.validate_positive_amount(amount)

    portfolio = load_portfolio(user)
    wallet = portfolio.get_wallet(currency)
    if wallet is None:
        raise ValueError(
            f"У вас нет кошелька '{currency}'. "
            f"Добавьте валюту: она создаётся автоматически при первой покупке."
        )
    old = wallet.balance
    wallet.withdraw(amount)  # бросит ValueError, если недостаточно средств

    rate = _usd_rate(currency)
    save_portfolio(portfolio)
    return {"currency": currency, "amount": amount, "rate": rate,
            "old": old, "new": wallet.balance,
            "estimated_usd": amount * rate if rate is not None else None}


# ---------------------- Курс ----------------------

def get_rate_info(from_code: str, to_code: str) -> dict:
    f = utils.validate_currency_code(from_code)
    t = utils.validate_currency_code(to_code)
    rate, updated_at = utils.get_rate(f, t)
    return {"from": f, "to": t, "rate": rate,
            "reverse": (1.0 / rate) if rate else None,
            "updated_at": updated_at}