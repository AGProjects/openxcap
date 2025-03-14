import re

from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from application import log
from sqlalchemy import create_engine

from xcap.configuration import DatabaseConfig as XCAPDatabaseConfig
from xcap.configuration import ServerConfig


class DatabaseConfig(XCAPDatabaseConfig):
    authentication_db_uri = ''
    storage_db_uri = ''


same_db = False
alembic_cfg = Config("alembic.ini", 'storage_db')  # Alembic configuration
alembic_auth_cfg = Config("alembic.ini", 'auth_db')


def retry_on_error(engine, cfg, e):
    error_message = str(e)
    log.info(f"Alembic CommandError: {error_message}")
    locations = cfg.get_main_option("version_locations")
    set_all_version_locations(cfg)

    match = re.search(r"Can't locate revision identified by '([\da-f]+)'", error_message)
    if match:
        missing_revision = match.group(1)
        log.info(f"Detected missing revision: {missing_revision}")
        try:
            command.downgrade(cfg, f'{missing_revision}@base')  # Apply Alembic migrations
            log.info("Downgrade success")
        except CommandError as retry_error:
            log.warning(f"Downgrade failed: {retry_error}")
            return

        cfg.set_main_option("version_locations", locations)
        try:
            command.upgrade(cfg, "head")  # Apply Alembic migrations
        except CommandError as e:
            log.waring(f"Migration failed: {e}")
    return


def set_all_version_locations(cfg):
    storage_locations = alembic_cfg.get_main_option("version_locations")
    auth_locations = alembic_auth_cfg.get_main_option("version_locations")
    cfg.set_main_option("version_locations", f"{storage_locations}, {auth_locations}")


def init_db():
    same_db = False
    if ServerConfig.backend not in ['Database', 'OpenSIPS'] and not DatabaseConfig.storage_db_uri or not DatabaseConfig.authentication_db_uri:
        return

    if DatabaseConfig.authentication_db_uri == DatabaseConfig.storage_db_uri:
        same_db = True
        set_all_version_locations(alembic_auth_cfg)

    if DatabaseConfig.authentication_db_uri.startswith('sqlite'):
        auth_engine = create_engine(DatabaseConfig.authentication_db_uri, connect_args={"check_same_thread": False})
        alembic_auth_cfg.set_main_option("sqlalchemy.url", DatabaseConfig.authentication_db_uri)  # Path to migrations
        with auth_engine.connect():
            if same_db:
                command.upgrade(alembic_auth_cfg, "heads")  # Apply Alembic migrations
                log.info("Database initialized and migrations applied.")
            else:
                try:
                    command.upgrade(alembic_auth_cfg, "head")  # Apply Alembic migrations
                except CommandError as e:
                    retry_on_error(auth_engine, alembic_auth_cfg, e)
                log.info("Authentication database initialized and migrations applied.")

    if not same_db and DatabaseConfig.storage_db_uri.startswith('sqlite'):
        engine = create_engine(DatabaseConfig.storage_db_uri, connect_args={"check_same_thread": False})
        alembic_cfg.set_main_option("sqlalchemy.url", DatabaseConfig.storage_db_uri)  # Path to migrations
        with engine.connect():
            try:
                command.upgrade(alembic_cfg, "head")  # Apply Alembic migrations
            except CommandError as e:
                retry_on_error(engine, alembic_cfg, e)

        log.info("Storage database initialized and migrations applied.")

# Main function to initialize and create tables
if __name__ == "__main__":
    init_db()

