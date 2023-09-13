from __future__ import annotations

from typing import List, Dict, Optional

from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, ForeignKey,
                        Integer, String, Table)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy_json import MutableJson


class Base(DeclarativeBase):
    pass


user_projects_table = Table(
    "users_projects",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("project_id", ForeignKey("projects.id"), primary_key=True),
)


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    person_uniqueid: Mapped[str] = mapped_column(String(128))
    first_name: Mapped[str] = mapped_column(String(20))
    last_name: Mapped[str] = mapped_column(String(40))
    person_mail: Mapped[str] = mapped_column(String(60))
    is_active: Mapped[bool] = mapped_column(Boolean)
    is_staff: Mapped[bool] = mapped_column(Boolean)
    is_opened: Mapped[bool] = mapped_column(Boolean)
    projects_api: Mapped[List[str]] = mapped_column(MutableJson)
    sshkey: Mapped[List["SshKey"]] = relationship(back_populates="user")
    sshkeys_api: Mapped[List[str]] = mapped_column(MutableJson)
    project: Mapped[List[Project]] = \
        relationship(secondary=user_projects_table, back_populates="user", cascade="all")


class Project(Base):
    __tablename__ = 'projects'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    identifier: Mapped[str] = mapped_column(String(32))
    staff_resources_type_api: Mapped[List[str]] = mapped_column(MutableJson)
    user: Mapped[List[User]] = \
        relationship(secondary=user_projects_table, back_populates="project")


class SshKey(Base):
    __tablename__ = 'sshkeys'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(47))
    public_key: Mapped[str] = mapped_column(String(2000))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="sshkey")

