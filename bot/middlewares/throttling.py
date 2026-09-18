"""Oddiy flood himoyasi: bir foydalanuvchi juda tez-tez bosolmaydi."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

OLDINGI: dict[int, float] = {}
TOZALASH_CHEGARASI = 10_000


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, oraliq: float = 0.35) -> None:
        self.oraliq = oraliq

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        hozir = time.monotonic()
        oxirgi = OLDINGI.get(user.id)
        if oxirgi is not None and hozir - oxirgi < self.oraliq:
            return None  # juda tez — e'tiborsiz qoldiriladi

        if len(OLDINGI) > TOZALASH_CHEGARASI:
            eski = [uid for uid, vaqt in OLDINGI.items() if hozir - vaqt > 3600]
            for uid in eski:
                OLDINGI.pop(uid, None)

        OLDINGI[user.id] = hozir
        return await handler(event, data)
