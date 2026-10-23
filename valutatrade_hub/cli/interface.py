"""CLI ValutaTrade Hub. Тонкий слой: парсинг + вызов usecases."""
from __future__ import annotations

import argparse
import shlex
from collections.abc import Callable

from ..core import usecases
from ..core.currencies import list_currencies
from ..core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from ..core.models import User
from ..parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from ..parser_service.config import ParserConfig
from ..parser_service.storage import ParserStorage
from ..parser_service.updater import RatesUpdater


class Session:
    def __init__(self) -> None:
        self.user: User | None = None

    def require_login(self) -> User:
        if self.user is None:
            raise RuntimeError("Сначала выполните login")
        return self.user


def _fmt(x: float, d: int = 2) -> str:
    return f"{x:,.{d}f}"


# ---------------------- Обработчики ----------------------

def cmd_register(session: Session, args: argparse.Namespace) -> None:
    user = usecases.register_user(args.username, args.password)
    print(f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
          f"Войдите: login --username {user.username} --password ****")


def cmd_login(session: Session, args: argparse.Namespace) -> None:
    session.user = usecases.login_user(args.username, args.password)
    print(f"Вы вошли как '{session.user.username}'")


def cmd_show_portfolio(session: Session, args: argparse.Namespace) -> None:
    user = session.require_login()
    data = usecases.show_portfolio(user, base=args.base)
    print(f"Портфель пользователя '{data['user']}' (база: {data['base']}):")
    if not data["wallets"]:
        print("  (кошельков нет)")
        return
    for row in data["wallets"]:
        bal = (f"{row['balance']:.4f}"
               if row["currency"] in ("BTC", "ETH") else f"{row['balance']:.2f}")
        val = ("нет курса" if row["value"] is None
               else f"{_fmt(row['value'])} {data['base']}")
        print(f"- {row['currency']}: {bal}  → {val}")
    print("-" * 33)
    print(f"ИТОГО: {_fmt(data['total'])} {data['base']}")


def cmd_buy(session: Session, args: argparse.Namespace) -> None:
    user = session.require_login()
    res = usecases.buy(user, args.currency, args.amount)
    rate_str = (f"{_fmt(res['rate'])} USD/{res['currency']}"
                if res["rate"] is not None else "нет курса")
    print(f"Покупка выполнена: {res['amount']:.4f} {res['currency']} "
          f"по курсу {rate_str}")
    print("Изменения в портфеле:")
    print(f"- {res['currency']}: было {res['old']:.4f} → стало {res['new']:.4f}")
    if res["estimated_usd"] is not None:
        print(f"Оценочная стоимость покупки: {_fmt(res['estimated_usd'])} USD")


def cmd_sell(session: Session, args: argparse.Namespace) -> None:
    user = session.require_login()
    res = usecases.sell(user, args.currency, args.amount)
    rate_str = (f"{_fmt(res['rate'])} USD/{res['currency']}"
                if res["rate"] is not None else "нет курса")
    print(f"Продажа выполнена: {res['amount']:.4f} {res['currency']} "
          f"по курсу {rate_str}")
    print("Изменения в портфеле:")
    print(f"- {res['currency']}: было {res['old']:.4f} → стало {res['new']:.4f}")
    if res["estimated_usd"] is not None:
        print(f"Оценочная выручка: {_fmt(res['estimated_usd'])} USD")


def cmd_get_rate(session: Session, args: argparse.Namespace) -> None:
    data = usecases.get_rate_info(args.from_code, args.to_code)
    updated = data["updated_at"].replace("T", " ")
    print(f"Курс {data['from']}→{data['to']}: {data['rate']:.8f} "
          f"(обновлено: {updated})")
    if data["reverse"] is not None:
        print(f"Обратный курс {data['to']}→{data['from']}: {data['reverse']:.2f}")


def cmd_help(session: Session, args: argparse.Namespace) -> None:
    print("Доступные команды:")
    print("  register --username <str> --password <str>")
    print("  login --username <str> --password <str>")
    print("  show-portfolio [--base <str>]")
    print("  buy --currency <str> --amount <float>")
    print("  sell --currency <str> --amount <float>")
    print("  get-rate --from <str> --to <str>")
    print("  update-rates [--source coingecko|exchangerate]")
    print("  show-rates [--currency <str>] [--top <int>] [--base <str>]")
    print("  exit")
    print(f"Поддерживаемые валюты: {', '.join(list_currencies())}")


def cmd_exit(session: Session, args: argparse.Namespace) -> None:
    raise SystemExit(0)


# ---------------------- Парсеры ----------------------

Command = Callable[[Session, argparse.Namespace], None]


def _build_parsers() -> dict[str, tuple[argparse.ArgumentParser, Command]]:
    parsers: dict[str, tuple[argparse.ArgumentParser, Command]] = {}

    def add(name: str, func: Command) -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(prog=name, add_help=False)
        parsers[name] = (p, func)
        return p

    p = add("register", cmd_register)
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)

    p = add("login", cmd_login)
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)

    p = add("show-portfolio", cmd_show_portfolio)
    p.add_argument("--base", default=None)

    p = add("buy", cmd_buy)
    p.add_argument("--currency", required=True)
    p.add_argument("--amount", type=float, required=True)

    p = add("sell", cmd_sell)
    p.add_argument("--currency", required=True)
    p.add_argument("--amount", type=float, required=True)

    p = add("get-rate", cmd_get_rate)
    p.add_argument("--from", dest="from_code", required=True)
    p.add_argument("--to", dest="to_code", required=True)

    p = add("update-rates", cmd_update_rates)
    p.add_argument("--source", choices=["coingecko", "exchangerate"], default=None)

    p = add("show-rates", cmd_show_rates)
    p.add_argument("--currency", default=None)
    p.add_argument("--top", type=int, default=None)
    p.add_argument("--base", default=None)

    add("help", cmd_help)
    add("exit", cmd_exit)
    return parsers


# ---------------------- Диспетчеризация ----------------------

def dispatch_tokens(session: Session, tokens: list[str],
                    parsers: dict[str, tuple[argparse.ArgumentParser, Command]]) -> None:
    if not tokens:
        return
    name, rest = tokens[0], tokens[1:]
    if name not in parsers:
        print(f"Неизвестная команда '{name}'. Введите 'help'.")
        return

    parser, func = parsers[name]
    try:
        args = parser.parse_args(rest)
    except SystemExit:
        return

    try:
        func(session, args)
    except RuntimeError as e:
        print(str(e))
    except InsufficientFundsError as e:
        print(str(e))
    except CurrencyNotFoundError as e:
        print(f"{e}. Доступные коды: {', '.join(list_currencies())}")
    except ApiRequestError as e:
        print(f"{e}. Повторите попытку позже.")
    except (ValueError, TypeError) as e:
        print(str(e))


def dispatch_line(session: Session, line: str,
                  parsers: dict[str, tuple[argparse.ArgumentParser, Command]]) -> None:
    try:
        tokens = shlex.split(line)
    except ValueError as e:
        print(f"Ошибка разбора команды: {e}")
        return
    dispatch_tokens(session, tokens, parsers)


# ---------------------- Точка входа ----------------------

def main(argv: list[str] | None = None) -> int:
    parsers = _build_parsers()
    session = Session()

    if argv:
        dispatch_tokens(session, argv, parsers)
        return 0

    print("ValutaTrade Hub. Введите 'help' для списка команд.")
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        try:
            dispatch_line(session, line, parsers)
        except SystemExit:
            return 0

def _parser_components():
    cfg = ParserConfig()
    clients = [CoinGeckoClient(cfg), ExchangeRateApiClient(cfg)]
    storage = ParserStorage(cfg.rates_path, cfg.history_path)
    return RatesUpdater(clients, storage), storage, cfg


# ---------------------- update-rates ----------------------

def cmd_update_rates(session: Session, args: argparse.Namespace) -> None:
    updater, _, _ = _parser_components()
    result = updater.run_update(source_filter=args.source)
    if result["errors"]:
        for err in result["errors"]:
            print(f"ERROR: {err}")
        print(f"Update completed with errors. Total rates updated: {result['total']}. "
              f"Check logs/ for details.")
    else:
        print(f"Update successful. Total rates updated: {result['total']}. "
              f"Last refresh: {result['last_refresh']}")


# ---------------------- show-rates ----------------------

def _convert_to_base(items: list[tuple[str, dict]], base: str) -> list[tuple[str, dict]]:
    """Пересчитать все пары в FROM_BASE через USD-пивот."""
    lookup: dict[str, dict] = dict(items)

    def usd_rate(code: str) -> float | None:
        if code == "USD":
            return 1.0
        if f"{code}_USD" in lookup:
            return float(lookup[f"{code}_USD"]["rate"])
        if f"USD_{code}" in lookup:
            inv = float(lookup[f"USD_{code}"]["rate"])
            return 1.0 / inv if inv else None
        return None

    base_usd = usd_rate(base)
    if base_usd is None:
        return items

    codes: set[str] = set()
    for key in lookup:
        f, t = key.split("_", 1)
        codes.update((f, t))
    codes.discard(base)

    result: list[tuple[str, dict]] = []
    for code in codes:
        code_usd = usd_rate(code)
        if code_usd is None:
            continue
        source_entry = lookup.get(f"{code}_USD") or lookup.get(f"USD_{code}")
        if source_entry is None:
            continue
        result.append((f"{code}_{base}", {
            "rate": code_usd / base_usd,
            "updated_at": source_entry.get("updated_at"),
            "source": source_entry.get("source"),
        }))
    return result


def cmd_show_rates(session: Session, args: argparse.Namespace) -> None:
    _, storage, cfg = _parser_components()
    snapshot = storage.load_snapshot()
    pairs = snapshot.get("pairs", {})

    if not pairs:
        print("Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.")
        return

    items: list[tuple[str, dict]] = list(pairs.items())

    if args.currency:
        code = args.currency.upper()
        items = [(k, v) for k, v in items if code in k.split("_")]
        if not items:
            print(f"Курс для '{code}' не найден в кеше.")
            return

    if args.base:
        items = _convert_to_base(items, args.base.upper())

    if args.top:
        crypto = set(cfg.CRYPTO_CURRENCIES)
        items = [(k, v) for k, v in items if k.split("_", 1)[0] in crypto]
        items = sorted(items, key=lambda x: float(x[1]["rate"]), reverse=True)[:args.top]
    else:
        items = sorted(items, key=lambda x: x[0])

    print(f"Rates from cache (updated at {snapshot.get('last_refresh')}):")
    for key, info in items:
        print(f"- {key}: {info['rate']}")