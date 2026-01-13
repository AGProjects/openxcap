import asyncio
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, Optional

from application import log
from application.notification import (IObserver, Notification,
                                      NotificationCenter)
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    create_async_engine)
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from zope.interface import implementer

from xcap.configuration import DatabaseConfig, ServerConfig
from xcap.configuration.datatypes import DatabaseURI
from xcap.errors import DBError, NoDatabase


@implementer(IObserver)
class DatabaseConnectionManager:
    AsyncSessionLocal: Optional[Callable] = None
    AsyncAuthSessionLocal: Optional[Callable] = None
    dburi = None

    _engine = None
    _auth_engine = None

    def __init__(self):
        NotificationCenter().add_observer(self)

    def handle_notification(self, notification: Notification) -> None:
        if notification.name == 'db_uri':
            self.configure_db_connection(notification.data)

    def create_engine(self, uri: DatabaseURI) -> AsyncEngine:
        if uri.startswith('sqlite'):
            engine = create_async_engine(uri, connect_args={"check_same_thread": False}, echo=False)
        elif uri.startswith('mysql'):
            engine = create_async_engine(uri, echo=False)
        else:
            raise ValueError("Unsupported database URI scheme")

        @event.listens_for(engine.sync_engine, "handle_error")
        def handle_error(exc):
            original_exception = exc.original_exception
            exception_type = type(original_exception).__name__
            error_code = getattr(original_exception, 'args', [None, None])[0]
            error_message = getattr(original_exception, 'args', [None, None])[1]

            log.error(f"{exception_type}: {error_code}, \"{error_message}\"")
            raise DBError()

        return engine

    def close_engine(self, engine):
        if engine is None:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            engine.sync_engine.dispose()
        else:
            loop.create_task(engine.dispose())

    def configure_db_connection(self, uri: Optional[DatabaseURI] = None) -> None:
        """ Configure the database connection with the provided URI for Uvicorn """
        if uri and self.dburi == uri:
            return

        self.close_engine(self._engine)
        self.close_engine(self._auth_engine)

        if uri and ServerConfig.backend == 'SIPThor':
            storage_db_uri = authentication_db_uri = uri
        elif not uri:
            storage_db_uri = DatabaseConfig.storage_db_uri
            authentication_db_uri = DatabaseConfig.authentication_db_uri

        self._engine = self.create_engine(storage_db_uri)
        self._auth_engine = self.create_engine(authentication_db_uri)

        self.dburi = uri
        self.AsyncSessionLocal = sessionmaker(bind=self._engine, class_=AsyncSession, expire_on_commit=False)
        self.AsyncAuthSessionLocal = sessionmaker(bind=self._auth_engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    if not connection_manager.AsyncSessionLocal:
        raise NoDatabase
    async with connection_manager.AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def get_auth_db_session() -> AsyncIterator[AsyncSession]:
    if not connection_manager.AsyncAuthSessionLocal:
        raise NoDatabase

    async with connection_manager.AsyncAuthSessionLocal() as session:
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


def shutdown_db():
    if getattr(connection_manager, "_engine", None):
        connection_manager.close_engine(connection_manager._engine)
    if getattr(connection_manager, "_auth_engine", None):
        connection_manager.close_engine(connection_manager._auth_engine)

