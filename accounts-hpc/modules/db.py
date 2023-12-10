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
    first_name: Mapped[str] = mapped_column(String(20))
    last_name: Mapped[str] = mapped_column(String(40))
    person_mail: Mapped[str] = mapped_column(String(60))
    person_uniqueid: Mapped[str] = mapped_column(String(128))
    person_oib: Mapped[str] = mapped_column(String(11))
    type_create: Mapped[str] = mapped_column(String(10))
    projects_api: Mapped[List[str]] = mapped_column(MutableJson)
    uid_api: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean)
    is_deactivated: Mapped[bool] = mapped_column(Boolean)
    is_opened: Mapped[bool] = mapped_column(Boolean)
    is_staff: Mapped[bool] = mapped_column(Boolean)
    is_dir_created: Mapped[bool] = mapped_column(Boolean)
    mail_is_subscribed: Mapped[bool] = mapped_column(Boolean)
    mail_is_opensend: Mapped[bool] = mapped_column(Boolean)
    mail_is_sshkeyadded: Mapped[bool] = mapped_column(Boolean)
    mail_name_sshkey: Mapped[List[str]] = mapped_column(MutableJson)
    mail_project_is_opensend: Mapped[List[dict]] = mapped_column(MutableJson)
    mail_project_is_sshkeyadded: Mapped[List[dict]] = mapped_column(MutableJson)
    mail_project_sshkey: Mapped[List[str]] = mapped_column(MutableJson)
    mail_project_name_sshkey: Mapped[List[str]] = mapped_column(MutableJson)
    sshkey: Mapped[List["SshKey"]] = relationship(back_populates="user")
    sshkeys_api: Mapped[List[str]] = mapped_column(MutableJson)
    ldap_username: Mapped[str] = mapped_column(String(8))
    ldap_uid: Mapped[int] = mapped_column(Integer)
    ldap_gid: Mapped[int] = mapped_column(Integer)
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
