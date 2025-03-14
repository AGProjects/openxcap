import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, Optional

from application import log
from application.notification import (IObserver, Notification,
                                      NotificationCenter)
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    async_sessionmaker, create_async_engine)
from sqlmodel import SQLModel
from zope.interface import implementer

from xcap.configuration import DatabaseConfig, ServerConfig
from xcap.errors import DBError, NoDatabase


@implementer(IObserver)
class DatabaseConnectionManager:
    AsyncSessionLocal: Optional[Callable] = None
    AsyncAuthSessionLocal: Optional[Callable] = None
    dburi = None

    def __init__(self):
        NotificationCenter().add_observer(self)

    def handle_notification(self, notification: Notification) -> None:
        if notification.name == 'db_uri':
            self.configure_db_connection(notification.data)

    def create_engine(self, uri) -> AsyncEngine:
        if uri.startswith('sqlite'):
            return create_async_engine(uri, connect_args={"check_same_thread": False}, echo=False)
        elif uri.startswith('mysql'):
            return create_async_engine(uri, echo=False)
        else:
            raise ValueError("Unsupported database URI scheme")

    def configure_db_connection(self, uri=None) -> None:
        """ Configure the database connection with the provided URI for Uvicorn """
        if uri and self.dburi == uri:
            return

        if uri and ServerConfig.backend == 'Sipthor':
            storage_db_uri = authentication_db_uri = uri
        elif not uri:
            storage_db_uri = DatabaseConfig.storage_db_uri
            authentication_db_uri = DatabaseConfig.authentication_db_uri

        engine = self.create_engine(storage_db_uri)
        auth_engine = self.create_engine(authentication_db_uri)

        self.dburi = uri
        self.AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        self.AsyncAuthSessionLocal = async_sessionmaker(bind=auth_engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    if not connection_manager.AsyncSessionLocal:
        raise NoDatabase
    async with connection_manager.AsyncSessionLocal() as session:

        @event.listens_for(session.get_bind(), 'handle_error')
        def handle_error(exc):
            original_exception = exc.original_exception

            exception_type = type(original_exception).__name__
            error_code = getattr(original_exception, 'args', [None, None])[0]  # Error code if available
            error_message = getattr(original_exception, 'args', [None, None])[1]  # Error message if available

            log.error(f"{exception_type}: {error_code}, \"{error_message}\"")
            raise DBError

        yield session


@asynccontextmanager
async def get_auth_db_session() -> AsyncIterator[AsyncSession]:
    if not connection_manager.AsyncAuthSessionLocal:
        raise NoDatabase

    async with connection_manager.AsyncAuthSessionLocal() as session:
        @event.listens_for(session.get_bind(), 'handle_error')
        def handle_error(exc):
            original_exception = exc.original_exception

            exception_type = type(original_exception).__name__
            error_code = getattr(original_exception, 'args', [None, None])[0]  # Error code if available
            error_message = getattr(original_exception, 'args', [None, None])[1]  # Error message if available

            log.error(f"{exception_type}: {error_code}, \"{error_message}\"")
            raise DBError

        yield session

connection_manager = DatabaseConnectionManager()

Base = SQLModel

# logger = log.get_logger('sqlalchemy.engine')
# logger.setLevel(log.level.DEBUG)

if ServerConfig.backend == 'OpenSIPS' or ServerConfig.backend == 'Database':
    if not DatabaseConfig.authentication_db_uri or not DatabaseConfig.storage_db_uri:
        log.critical('Authentication DB URI and Storage DB URI must be provided')
        sys.exit(1)
    connection_manager.configure_db_connection()

