"""Operational commands: `python -m app.cli <command>`."""

import argparse
import asyncio
import json
import sys

from app.db import get_engine, session_factory
from app.main import app
from app.models import Role
from app.services.users import get_or_create_user


def export_openapi() -> None:
    """Print the OpenAPI schema; the web TS client is generated from this file."""
    json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


async def make_admin(email: str) -> None:
    """Grant the admin role (creating the user if needed). The only way to become admin (AC-M1-03.3)."""
    async with session_factory()() as db:
        user = await get_or_create_user(db, email)
        user.role = Role.ADMIN
        await db.commit()
        print(f"{user.email} is now admin (id={user.id})")
    await get_engine().dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export-openapi", help="print OpenAPI JSON to stdout")
    admin = sub.add_parser("make-admin", help="grant admin role to an email")
    admin.add_argument("email")
    args = parser.parse_args()
    if args.command == "export-openapi":
        export_openapi()
    elif args.command == "make-admin":
        asyncio.run(make_admin(args.email))


if __name__ == "__main__":
    main()
