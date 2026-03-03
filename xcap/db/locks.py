import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text

from xcap.db.manager import connection_manager, get_db_session


@asynccontextmanager
async def lock_document(
    user: str,
    timeout: int = 3
) -> AsyncGenerator[None, None]:
    """
    Acquire a named lock per user using database-level locking.
    All documents for a user are protected by a single lock.

    MySQL: Uses GET_LOCK() / RELEASE_LOCK()
    SQLite: Uses a locks table with atomic updates
    """
    lock_name = f"xcap_{user}"

    async with get_db_session() as session:
        db_uri = connection_manager.dburi or str(connection_manager._engine.url)

        if 'mysql' in db_uri:
            # MySQL: Use GET_LOCK for named locks
            result = await session.execute(
                text("SELECT GET_LOCK(:lock_name, :timeout)"),
                {"lock_name": lock_name, "timeout": timeout}
            )
            locked = result.scalar()

            if not locked:
                raise TimeoutError(f"Failed to acquire lock on {lock_name}")

            try:
                yield
            finally:
                await session.execute(
                    text("SELECT RELEASE_LOCK(:lock_name)"),
                    {"lock_name": lock_name}
                )
                await session.commit()

        elif 'sqlite' in db_uri:
            # SQLite: Use a locks table
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS document_locks (
                    lock_name TEXT PRIMARY KEY,
                    acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    pid INTEGER
                )
            """))
            await session.commit()

            start_time = time.time()
            while True:
                try:
                    await session.execute(
                        text("""
                            INSERT INTO document_locks (lock_name, pid)
                            VALUES (:lock_name, :pid)
                        """),
                        {"lock_name": lock_name, "pid": os.getpid()}
                    )
                    await session.commit()
                    break
                except Exception:
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"Failed to acquire lock on {lock_name}")
                    await session.rollback()
                    await asyncio.sleep(0.01)

            try:
                yield
            finally:
                await session.execute(
                    text("DELETE FROM document_locks WHERE lock_name = :lock_name"),
                    {"lock_name": lock_name}
                )
                await session.commit()

        else:
            raise ValueError(f"Unsupported database: {db_uri}")
