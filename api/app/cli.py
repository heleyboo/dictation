"""Operational commands: `python -m app.cli <command>`."""

import argparse
import json
import sys

from app.main import app


def export_openapi() -> None:
    """Print the OpenAPI schema; the web TS client is generated from this file."""
    json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export-openapi", help="print OpenAPI JSON to stdout")
    args = parser.parse_args()
    if args.command == "export-openapi":
        export_openapi()


if __name__ == "__main__":
    main()
