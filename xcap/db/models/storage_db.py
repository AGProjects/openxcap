from datetime import datetime
from typing import Optional

from sqlmodel import (Column, Field, ForeignKey, Index, Integer, Relationship,
                      SQLModel, UniqueConstraint)

from xcap.configuration import DatabaseConfig


class XCAP(SQLModel, table=True):
    __tablename__ = DatabaseConfig.xcap_table
    __database__ = 'storage_db'
    id: Optional[int] = Field(default=None, primary_key=True)
    subscriber_id: Optional[int] = Field(default=None, sa_column=Column(Integer, ForeignKey("subscriber.id", ondelete="CASCADE")))
    username: str = Field(max_length=64)
    domain: str = Field(max_length=64)
    doc: bytes  # Representing longblob as bytes
    doc_type: int
    etag: str = Field(max_length=64)
    source: int = Field(default=0)
    doc_uri: str = Field(max_length=255)
    port: int = Field(default=0)

    __table_args__ = (
        UniqueConstraint("username", "domain", "doc_type", "doc_uri", name="account_doc_type_idx"),
        Index("xcap_subscriber_id_exists", "subscriber_id"),
        Index("source_idx", "source"),
    )

#    subscriber: Optional["Subscriber"] = Relationship(back_populates="none", cascade="all, delete-orphan")


class Watcher(SQLModel, table=True):
    __tablename__ = 'watchers'
    __database__ = 'storage_db'

    id: int = Field(default=None, primary_key=True)
    presentity_uri: str = Field(max_length=255)
    watcher_username: str = Field(max_length=64)
    watcher_domain: str = Field(max_length=64)
    event: str = Field(default="presence", max_length=64)
    status: int
    reason: Optional[str] = Field(default=None, max_length=64)
    inserted_time: int

    # Unique constraint for multiple columns
    __table_args__ = (
        UniqueConstraint('presentity_uri', 'watcher_username', 'watcher_domain', 'event', name='watcher_idx'),
    )
