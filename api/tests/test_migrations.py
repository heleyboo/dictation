from alembic import command
from tests.conftest import alembic_config


def test_migrations_downgrade_and_upgrade_cleanly() -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
