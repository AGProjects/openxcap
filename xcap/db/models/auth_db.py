from typing import Optional

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel

from xcap.configuration import DatabaseConfig


class Subscriber(SQLModel, table=True):
    __tablename__ = DatabaseConfig.subscriber_table
    __database__ = 'auth_db'

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(default=None, max_length=64, sa_column=Column(DatabaseConfig.user_col, String(64), nullable=True))
    domain: str = Field(default=None, max_length=64, sa_column=Column(DatabaseConfig.domain_col, String(64), nullable=True))
    password: str = Field(default=None, max_length=255, sa_column=Column(DatabaseConfig.password_col, String(255), nullable=True))
    ha1: str = Field(default=None, max_length=64, sa_column=Column(DatabaseConfig.ha1_col, String(64), nullable=True))

