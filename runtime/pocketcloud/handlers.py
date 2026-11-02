from __future__ import annotations

from collections.abc import Callable
from typing import Any


Handler = Callable[[dict[str, Any]], dict[str, Any]]


def _self_test_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic echo result; perform no filesystem or network effects."""
    return {"handler": "self_test.v1", "echo": payload["message"]}


HANDLERS: dict[str, Handler] = {"self_test.v1": _self_test_v1}


def get_handler(handler_id: str) -> Handler:
    try:
        return HANDLERS[handler_id]
    except KeyError as exc:
        raise ValueError("handler_not_registered") from exc


def registered_handler_ids() -> tuple[str, ...]:
    return tuple(sorted(HANDLERS))
