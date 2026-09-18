"""Telegram API o'rniga ishlaydigan soxta sessiya — testlar uchun.

Hech qanday tarmoq so'rovi yubormaydi, chaqirilgan metodlarni ro'yxatga yozib boradi.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod
from aiogram.types import Chat, Message, MessageId


class MockSession(BaseSession):
    """Barcha API chaqiruvlarini ushlab qoladi va soxta javob qaytaradi."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, TelegramMethod]] = []
        self._message_id = 1000

    async def close(self) -> None:
        pass

    async def stream_content(self, *args: Any, **kwargs: Any):  # pragma: no cover
        yield b""

    async def make_request(
        self, bot: Bot, method: TelegramMethod, timeout: int | None = None
    ) -> Any:
        nom = type(method).__name__
        self.calls.append((nom, method))

        if nom == "GetMe":
            from aiogram.types import User as TgUser

            return TgUser(id=bot.id, is_bot=True, first_name="TestBot", username="testbot")
        if nom == "CopyMessage":
            self._message_id += 1
            return MessageId(message_id=self._message_id)
        if nom == "SendChatAction":
            return True
        # SendMessage, SendVenue, SendLocation, SendDocument, EditMessageText ...
        if nom.startswith(("Send", "EditMessage")):
            return self._soxta_xabar(method)
        return True

    def _soxta_xabar(self, method: TelegramMethod) -> Message:
        self._message_id += 1
        chat_id = getattr(method, "chat_id", 1)
        return Message(
            message_id=self._message_id,
            date=datetime.now(),
            chat=Chat(id=int(chat_id) if chat_id else 1, type="private"),
            text=getattr(method, "text", None) or getattr(method, "caption", None),
        )

    # ---- qulay yordamchilar ----

    def matnlar(self) -> list[str]:
        """Yuborilgan barcha xabar matnlari."""
        natija = []
        for nom, method in self.calls:
            if nom in ("SendMessage", "EditMessageText"):
                matn = getattr(method, "text", None)
                if matn:
                    natija.append(matn)
        return natija

    def oxirgi_matn(self) -> str:
        matnlar = self.matnlar()
        return matnlar[-1] if matnlar else ""

    def oxirgi_markup(self):
        """Oxirgi yuborilgan xabardagi klaviatura."""
        for _, method in reversed(self.calls):
            markup = getattr(method, "reply_markup", None)
            if markup is not None:
                return markup
        return None

    def metodlar(self) -> list[str]:
        return [nom for nom, _ in self.calls]

    def tozalash(self) -> None:
        self.calls.clear()
