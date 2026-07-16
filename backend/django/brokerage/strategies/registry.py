"""Explicit registry mapping a brokerage's stable `name` slug to its strategy class.

A plain module-level dict, not a dynamic `importlib`/`getattr`-based
dispatcher — a typo in `Brokerage.name` fails loudly here with a clear
`UnknownBrokerError`, not a silent `AttributeError` or an arbitrary-attribute
access risk.
"""

from brokerage.exceptions import UnknownBrokerError
from brokerage.strategies.angel_one import AngelOneAuthStrategy
from brokerage.strategies.base import BaseBrokerAuthStrategy

BROKER_STRATEGIES: dict[str, type[BaseBrokerAuthStrategy]] = {
    "angel_one": AngelOneAuthStrategy,
}


def get_strategy_class(brokerage_name: str) -> type[BaseBrokerAuthStrategy]:
    """Return the strategy class registered for `brokerage_name`.

    Raises `UnknownBrokerError` if no strategy is registered under that name.
    """
    try:
        return BROKER_STRATEGIES[brokerage_name]
    except KeyError as exc:
        raise UnknownBrokerError(
            f"No strategy registered for broker: {brokerage_name!r}"
        ) from exc
