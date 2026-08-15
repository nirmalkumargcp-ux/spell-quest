"""Family, parent and child profiles (spec §6).

Child records deliberately hold the minimum needed to teach: a name, an
avatar and a birth year. No location, no contacts, no identifiers (spec §40).
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, UUIDMixin


class Family(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "families"

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    parents: Mapped[list["Parent"]] = relationship(back_populates="family", cascade="all, delete-orphan")
    children: Mapped[list["Child"]] = relationship(back_populates="family", cascade="all, delete-orphan")


class Parent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "parents"

    family_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    family: Mapped[Family] = relationship(back_populates="parents")


class Child(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "children"

    family_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Birth year only — enough to seed age-appropriate content, no more.
    birth_year: Mapped[int | None] = mapped_column(Integer)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    avatar: Mapped[str] = mapped_column(String(40), default="owl", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict] = mapped_column(JSONType, default=dict)

    family: Mapped[Family] = relationship(back_populates="children")

    @property
    def age(self) -> int | None:
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        if self.birth_year:
            return date.today().year - self.birth_year
        return None
