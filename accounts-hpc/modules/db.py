from __future__ import annotations

from typing import List, Dict, Optional

from sqlalchemy import (Boolean, Column, Date, DateTime, ForeignKey, Integer,
                        String, Table)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy_json import MutableJson
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    pass


user_projects_table = Table(
    "users_projects",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("project_id", ForeignKey("projects.id"), primary_key=True),
)


class User(Base):
    __tablename__ = 'users'

    first_name: Mapped[str] = mapped_column(String(20))
    id: Mapped[int] = mapped_column(primary_key=True)
    is_activated_project: Mapped[Dict] = mapped_column(MutableJson)
    is_active: Mapped[bool] = mapped_column(Boolean)
    is_deactivated: Mapped[bool] = mapped_column(Boolean)
    is_deactivated_project: Mapped[Dict] = mapped_column(MutableJson)
    is_dir_created: Mapped[bool] = mapped_column(Boolean)
    is_opened: Mapped[bool] = mapped_column(Boolean)
    is_staff: Mapped[bool] = mapped_column(Boolean)
    last_name: Mapped[str] = mapped_column(String(40))
    ldap_gid: Mapped[int] = mapped_column(Integer)
    ldap_uid: Mapped[int] = mapped_column(Integer)
    mail_is_activated: Mapped[bool] = mapped_column(Boolean)
    mail_is_deactivated: Mapped[bool] = mapped_column(Boolean)
    mail_is_opensend: Mapped[bool] = mapped_column(Boolean)
    mail_is_sshkeyadded: Mapped[bool] = mapped_column(Boolean)
    mail_is_sshkeyremoved: Mapped[bool] = mapped_column(Boolean)
    mail_name_sshkey: Mapped[List[str]] = mapped_column(MutableJson)
    mail_project_is_activated: Mapped[Dict] = mapped_column(MutableJson)
    mail_project_is_deactivated: Mapped[Dict] = mapped_column(MutableJson)
    mail_project_is_opensend: Mapped[Dict] = mapped_column(MutableJson)
    mail_project_is_sshkeyadded: Mapped[Dict] = mapped_column(MutableJson)
    mail_project_is_sshkeyremoved: Mapped[Dict] = mapped_column(MutableJson)
    person_mail: Mapped[str] = mapped_column(String(60))
    person_type: Mapped[str] = mapped_column(String(32))
    person_uniqueid: Mapped[str] = mapped_column(String(128))
    projects_api: Mapped[List[str]] = mapped_column(MutableJson)
    skip_defgid: Mapped[bool] = mapped_column(Boolean)
    sshkey: Mapped[List["SshKey"]] = relationship(back_populates="user")
    sshkeys_api: Mapped[List[str]] = mapped_column(MutableJson)
    type_create: Mapped[str] = mapped_column(String(10))
    uid_api: Mapped[int] = mapped_column(Integer)
    username_api: Mapped[str] = mapped_column(String(10))
    project: Mapped[List[Project]] = \
        relationship(secondary=user_projects_table, back_populates="user")


class Project(Base):
    __tablename__ = 'projects'

    id: Mapped[int] = mapped_column(primary_key=True)
    identifier: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(180))
    prjid_api: Mapped[int] = mapped_column(Integer)
    ldap_gid: Mapped[int] = mapped_column(Integer)
    staff_resources_type_api: Mapped[List[str]] = mapped_column(MutableJson)
    is_dir_created: Mapped[bool] = mapped_column(Boolean)
    is_pbsfairshare_added: Mapped[bool] = mapped_column(Boolean)
    type: Mapped[str] = mapped_column(String(32))
    user: Mapped[List[User]] = \
        relationship(secondary=user_projects_table, back_populates="project")


class SshKey(Base):
    __tablename__ = 'sshkeys'

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(47))
    name: Mapped[str] = mapped_column(String(128))
    public_key: Mapped[str] = mapped_column(String(2000))
    uid_api: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="sshkey")
