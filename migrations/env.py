import os
import sys

from alembic import context
from application.process import process
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Add the `xcap` directory to the Python path so we can import our modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from xcap.configuration import DatabaseConfig as XCAPDatabaseConfig
from xcap.db.manager import Base
from xcap.db.models import XCAP, Subscriber, Watcher

process.configuration.subdirectory = 'openxcap'
process.configuration.local_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


class DatabaseConfig(XCAPDatabaseConfig):
    authentication_db_uri = ''
    storage_db_uri = ''


config = context.config

target_metadata = Base.metadata

db_name = config.config_ini_section


def include_object(object, name, type_, reflected, compare_to):
    model_class = next(
        (cls for cls in SQLModel.__subclasses__() if getattr(cls, "__tablename__", None) == name),
        None
    )
    model_database = getattr(model_class, "__database__", None)

    if type_ == 'foreign_key_constraint' and compare_to and (
            compare_to.elements[0].target_fullname == db_name + '.' +
            object.elements[0].target_fullname or
            db_name + '.' + compare_to.elements[0].target_fullname == object.elements[
                0].target_fullname):
        return False
    if type_ == 'table':
        if model_database == db_name or model_database is None:
            return True
    elif model_database == db_name or model_database is None:
        return True
    else:
        return False


def run_migrations_online():
    """Run migrations in 'online' mode."""
    if db_name == 'auth_db':
        config.set_main_option("sqlalchemy.url", DatabaseConfig.authentication_db_uri)
    else:
        config.set_main_option("sqlalchemy.url", DatabaseConfig.storage_db_uri)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object
        )

        with context.begin_transaction():
            context.run_migrations()


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    if db_name == 'auth_db':
        url = DatabaseConfig.authentication_db_uri
    else:
        url = DatabaseConfig.storage_db_uri

    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
