from logging.config import fileConfig
import sys
import os

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add backend path to sys.path for imports
# In development: repo_root/GeminiOCR/backend
# In Docker: /app (backend files are copied to /app root)
current_dir = os.path.dirname(__file__)  # migrations directory
parent_dir = os.path.dirname(current_dir)  # parent directory

# Try development path first
backend_path = os.path.join(parent_dir, 'GeminiOCR', 'backend')
if os.path.exists(backend_path):
    sys.path.insert(0, backend_path)
else:
    # In Docker, backend files are at /app (parent_dir itself)
    # Check if db module exists at parent level
    if os.path.exists(os.path.join(parent_dir, 'db')):
        sys.path.insert(0, parent_dir)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import database models and connection
try:
    from db.database import Base, get_database_url
    from db import models  # Import all models to register them with Base
    target_metadata = Base.metadata

    # Set database URL from config
    if not config.get_main_option("sqlalchemy.url"):
        config.set_main_option("sqlalchemy.url", get_database_url())
except ImportError as e:
    print(f"Warning: Could not import database models: {e}")
    target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Get the configuration section
    configuration = config.get_section(config.config_ini_section, {})

    # Ensure database URL is set
    if "sqlalchemy.url" not in configuration:
        try:
            from db.database import get_database_url
            configuration["sqlalchemy.url"] = get_database_url()
        except Exception as e:
            print(f"Error getting database URL: {e}")
            raise

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
