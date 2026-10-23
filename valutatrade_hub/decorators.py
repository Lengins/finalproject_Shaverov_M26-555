"""@log_action — трассировка доменных операций (BUY/SELL/REGISTER/LOGIN...)."""
from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from .logging_config import setup_logging

_logger = setup_logging()


def _arg(args: tuple, kwargs: dict, name: str, idx: int | None = None,
         default: Any = None) -> Any:
    if name in kwargs:
        return kwargs[name]
    if idx is not None and idx < len(args):
        return args[idx]
    return default


def _format_message(action: str, username: Any, currency: Any, amount: Any,
                    rate: Any, base: Any, result: str) -> str:
    parts = [action, f"user={username!r}"]
    if currency is not None:
        parts.append(f"currency={currency!r}")
    if amount is not None:
        parts.append(f"amount={amount}")
    if rate is not None:
        parts.append(f"rate={rate:.2f}")
    if base is not None:
        parts.append(f"base={base!r}")
    parts.append(f"result={result}")
    return " ".join(parts)


def log_action(action: str, verbose: bool = False) -> Callable:
    """Декоратор для usecases.

    - не глотает исключения (пробрасывает после записи в лог);
    - verbose=True добавляет контекст «было→стало», если функция вернула dict
      с ключами old/new.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = _arg(args, kwargs, "user", 0)
            username = getattr(user, "username", None)
            user_id = getattr(user, "user_id", None)
            currency = _arg(args, kwargs, "currency", 1) \
                or _arg(args, kwargs, "currency_code", 1)
            amount = _arg(args, kwargs, "amount", 2)

            extra: dict[str, Any] = {
                "action": action,
                "username": username,
                "user_id": user_id,
                "currency": currency,
                "amount": amount,
            }

            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                extra["result"] = "ERROR"
                extra["error_type"] = type(exc).__name__
                extra["error_message"] = str(exc)
                _logger.error(
                    _format_message(action, username, currency, amount,
                                    rate=None, base=None, result="ERROR"),
                    extra=extra,
                )
                raise

            rate = base = None
            if isinstance(result, dict):
                rate = result.get("rate")
                base = "USD" if rate is not None else None
                if verbose and "old" in result and "new" in result:
                    extra["context"] = (
                        f"{result['old']:.4f}→{result['new']:.4f}"
                    )

            extra["result"] = "OK"
            if rate is not None:
                extra["rate"] = rate
                extra["base"] = base
            _logger.info(
                _format_message(action, username, currency, amount,
                                rate=rate, base=base, result="OK"),
                extra=extra,
            )
            return result
        return wrapper
    return decorator