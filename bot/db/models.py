"""Ma'lumotlar bazasi modellari.

Uchta asosiy jadval:
  users    — o'quvchi profili (bir marta to'ldiriladi)
  arizalar — har bir fan uchun alohida yozuv (bir o'quvchi -> ko'p ariza)
  fanlar   — olimpiada fanlari ro'yxati
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.base import Base


class Holat(str, enum.Enum):
    """Ariza holati."""

    YANGI = "yangi"
    TASDIQLANGAN = "tasdiqlangan"
    RAD_ETILGAN = "rad_etilgan"
    BEKOR_QILINGAN = "bekor_qilingan"


HOLAT_NOMI: dict[Holat, str] = {
    Holat.YANGI: "🕐 Ko'rib chiqilmoqda",
    Holat.TASDIQLANGAN: "✅ Qabul qilindi",
    Holat.RAD_ETILGAN: "❌ Rad etilgan",
    Holat.BEKOR_QILINGAN: "🚫 Bekor qilingan",
}

# Olimpiadada qatnashadigan arizalar: statistika, Excel va hisobotda faqat shular sanaladi.
# Arizalar avtomatik qabul qilinadi (TASDIQLANGAN). YANGI — avto-qabuldan oldingi eski yozuvlar.
QATNASHUVCHI_HOLATLAR: tuple[Holat, ...] = (Holat.TASDIQLANGAN, Holat.YANGI)


class AdminRol(str, enum.Enum):
    SUPER = "super"
    ADMIN = "admin"


class AdminHolat(str, enum.Enum):
    KUTILMOQDA = "kutilmoqda"
    TASDIQLANGAN = "tasdiqlangan"
    RAD_ETILGAN = "rad_etilgan"


ADMIN_ROL_NOMI: dict[AdminRol, str] = {
    AdminRol.SUPER: "👑 Super admin",
    AdminRol.ADMIN: "👮 Admin",
}

ADMIN_HOLAT_NOMI: dict[AdminHolat, str] = {
    AdminHolat.KUTILMOQDA: "🕐 Tasdiq kutmoqda",
    AdminHolat.TASDIQLANGAN: "✅ Faol",
    AdminHolat.RAD_ETILGAN: "❌ Rad etilgan",
}


def _enum(klass: type[enum.Enum], uzunlik: int = 20) -> SAEnum:
    return SAEnum(
        klass,
        native_enum=False,
        length=uzunlik,
        values_callable=lambda e: [m.value for m in e],
    )


def _holat_enum() -> SAEnum:
    return _enum(Holat)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Texnik — avtomatik olinadi
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manba: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bloklangan: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Foydalanuvchidan so'raladi — 6 ta maydon
    familiya: Mapped[str] = mapped_column(String(40))
    ism: Mapped[str] = mapped_column(String(40))
    sharif: Mapped[str] = mapped_column(String(40))
    telefon: Mapped[str] = mapped_column(String(20), index=True)
    maktab: Mapped[str] = mapped_column(String(100))
    sinf: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    arizalar: Mapped[list["Ariza"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def fish(self) -> str:
        return f"{self.familiya} {self.ism} {self.sharif}".strip()

    def __repr__(self) -> str:
        return f"<User {self.id} {self.fish}>"


class Fan(Base):
    __tablename__ = "fanlar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kod: Mapped[str] = mapped_column(String(8), unique=True)
    nomi: Mapped[str] = mapped_column(String(64))
    faol: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tartib: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    arizalar: Mapped[list["Ariza"]] = relationship(back_populates="fan")

    def __repr__(self) -> str:
        return f"<Fan {self.kod} {self.nomi}>"


class Ariza(Base):
    __tablename__ = "arizalar"
    __table_args__ = (
        UniqueConstraint("user_id", "fan_id", name="uq_ariza_user_fan"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ariza_raqami: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fan_id: Mapped[int] = mapped_column(ForeignKey("fanlar.id"), index=True)

    holat: Mapped[Holat] = mapped_column(_holat_enum(), default=Holat.YANGI, nullable=False)
    admin_izohi: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="arizalar", lazy="selectin")
    fan: Mapped["Fan"] = relationship(back_populates="arizalar", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Ariza {self.ariza_raqami}>"


class Admin(Base):
    """Bot adminlari.

    .env dagi ADMIN_IDS — doimiy super adminlar, ular bu jadvalda bo'lmasligi
    ham mumkin. Qolganlari shu yerda saqlanadi va super admin tomonidan
    tasdiqlanadi.
    """

    __tablename__ = "adminlar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    fish: Mapped[str] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)

    rol: Mapped[AdminRol] = mapped_column(
        _enum(AdminRol), default=AdminRol.ADMIN, nullable=False
    )
    holat: Mapped[AdminHolat] = mapped_column(
        _enum(AdminHolat), default=AdminHolat.KUTILMOQDA, nullable=False
    )

    # Kim tasdiqladi / qo'shdi (telegram_id)
    tasdiqlagan_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Admin {self.telegram_id} {self.rol.value} {self.holat.value}>"


class Sozlama(Base):
    """Oddiy kalit-qiymat sozlamalari (koddan emas, admindan boshqariladi)."""

    __tablename__ = "sozlamalar"

    kalit: Mapped[str] = mapped_column(String(64), primary_key=True)
    qiymat: Mapped[str] = mapped_column(Text)
