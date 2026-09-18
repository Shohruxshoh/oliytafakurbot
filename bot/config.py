"""Bot sozlamalari — barchasi .env fayldan o'qiladi."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    admin_ids: tuple[int, ...]
    database_url: str
    majburiy_kanal: str | None
    aloqa: str

    def is_admin(self, telegram_id: int) -> bool:
        return telegram_id in self.admin_ids


def _parse_admin_ids(raw: str) -> tuple[int, ...]:
    ids: list[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            raise RuntimeError(
                f"ADMIN_IDS noto'g'ri: '{part}' raqam emas. Namuna: ADMIN_IDS=123456789,987654321"
            ) from None
    return tuple(ids)


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            ".env faylda BOT_TOKEN ko'rsatilmagan. "
            ".env.example faylidan nusxa oling va tokenni yozing."
        )

    return Config(
        bot_token=token,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        database_url=os.getenv("DATABASE_URL", "").strip() or "sqlite+aiosqlite:///bot.db",
        majburiy_kanal=(os.getenv("MAJBURIY_KANAL") or "").strip() or None,
        aloqa=(os.getenv("ALOQA") or "").strip() or "@admin",
    )
