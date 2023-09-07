from __future__ import annotations

from typing import List

from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, ForeignKey,
                        Integer, String, Table)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


user_projects_table = Table(
    "user_projects_table",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("project_id", ForeignKey("projects.id"), primary_key=True),
)


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(8))
    first_name: Mapped[str] = mapped_column(String(20))
    last_name: Mapped[str] = mapped_column(String(40))
    person_mail: Mapped[str] = mapped_column(String(60))
    status: Mapped[int] = mapped_column(Integer)
    project: Mapped[List[Project]] = \
        relationship(secondary=user_projects_table, back_populates="user")


class Project(Base):
    __tablename__ = 'projects'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    identifier: Mapped[str] = mapped_column(String(32))
    staff_resource_type: Mapped[JSON] = mapped_column(JSON())
    user: Mapped[List[User]] = \
        relationship(secondary=user_projects_table, back_populates="project")
