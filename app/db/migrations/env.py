from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.db.database import Base
from app.config.setting import settings

# Import all models so Alembic can detect them
from app.db.models.Users import User
from app.db.models.Chat import Chat
from app.db.models.Message import Message
from app.db.models.Document import Document
from app.db.models.Persona import Persona
from app.db.models.Feature import Feature
from app.db.models.File import File
from app.db.models.Classroom import Classroom
from app.db.models.ClassroomItem import ClassroomItem
from app.db.models.ClassroomItemAssignment import ClassroomItemAssignment
from app.db.models.ClassroomItemDocument import ClassroomItemDocument
from app.db.models.FeatureClassroom import FeatureClassroom
from app.db.models.Conversation import Conversation
from app.db.models.ConversationMessage import ConversationMessage
from app.db.models.PendingLogSync import PendingLogSync

# app/support/ is an isolated package (see 02-architecture-decisions.md §9.1) but its
# models still register on the same shared Base/metadata (§9.4) — import them here too.
from app.support.ingestion.models import IngestionTask
from app.support.adapter.gmail.models import (
    GmailMailbox,
    GmailOutboxMessage,
    GmailSentReply,
    GmailWatch,
)
from app.support.adapter.imap.models import (
    ImapMailbox,
    ImapOutboxMessage,
    ImapSentReply,
    ImapThreadMessage,
)
from app.support.adapter.mailtrap.models import (
    MailtrapLastInboundMessage,
    MailtrapMailbox,
    MailtrapSentReply,
)


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

config.set_main_option("sqlalchemy.url", settings.database_url)


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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
