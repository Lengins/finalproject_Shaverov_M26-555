#CLI ValutaTrade Hub. Тонкий слой: парсинг + вызов usecases.
from __future__ import annotations

import argparse
import shlex
from typing import Callable, Optional

from ..core import usecases
from ..core.models import User


class Session:
    def __init__(self) -> None:
        self.user: Optional[User] = None

    def require_login(self) -> User:
        if self.user is None:
            raise RuntimeError("Сначала выполните login")
        return self.user


def _fmt(x: float, d: int = 2) -> str:
    return f"{x:,.{d}f}"


# ---------------------- Обработчики команд ----------------------

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
        bal = f"{row['balance']:.4f}" if row["currency"] in ("BTC", "ETH") \
            else f"{row['balance']:.2f}"
        val = "нет курса" if row["value"] is None \
            else f"{_fmt(row['value'])} {data['base']}"
        print(f"- {row['currency']}: {bal}  → {val}")
    print("-" * 33)
    print(f"ИТОГО: {_fmt(data['total'])} {data['base']}")


def cmd_buy(session: Session, args: argparse.Namespace) -> None:
    user = session.require_login()
    res = usecases.buy_currency(user, args.currency, args.amount)
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
    res = usecases.sell_currency(user, args.currency, args.amount)
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
    print("  exit — выход")


def cmd_exit(session: Session, args: argparse.Namespace) -> None:
    raise SystemExit(0)


# ---------------------- Сборка парсеров ----------------------

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
    p.add_argument("--base", default="USD")

    p = add("buy", cmd_buy)
    p.add_argument("--currency", required=True)
    p.add_argument("--amount", type=float, required=True)

    p = add("sell", cmd_sell)
    p.add_argument("--currency", required=True)
    p.add_argument("--amount", type=float, required=True)

    p = add("get-rate", cmd_get_rate)
    p.add_argument("--from", dest="from_code", required=True)
    p.add_argument("--to", dest="to_code", required=True)

    add("help", cmd_help)
    add("exit", cmd_exit)
    return parsers


# ---------------------- Диспетчеризация ----------------------

def dispatch_tokens(
    session: Session,
    tokens: list[str],
    parsers: dict[str, tuple[argparse.ArgumentParser, Command]],
) -> None:
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
        return  # argparse уже вывел сообщение

    try:
        func(session, args)
    except RuntimeError as e:
        print(str(e))
    except ValueError as e:
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

def main(argv: Optional[list[str]] = None) -> int:
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