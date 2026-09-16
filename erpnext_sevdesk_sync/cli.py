"""Command line entrypoint for the ERPNext -> sevDesk price sync."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional

from .config import Config, ConfigError
from .env_file import load_env_file
from .erpnext_client import ERPNextClient
from .price_sync import sync_prices
from .sevdesk_client import SevDeskClient

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erpnext-sevdesk-sync",
        description=(
            "Sync gross prices from an ERPNext price list to sevDesk as net prices."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and log the changes without writing anything to sevDesk.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to a .env file to load before reading configuration (default: .env).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    load_env_file(args.env_file)

    try:
        config = Config.from_env()
    except ConfigError as exc:
        logger.error(str(exc))
        return 2

    dry_run = config.dry_run or args.dry_run

    erpnext_client = ERPNextClient(
        config.erpnext_url,
        config.erpnext_api_key,
        config.erpnext_api_secret,
    )
    sevdesk_client = SevDeskClient(config.sevdesk_base_url, config.sevdesk_api_token)

    results = sync_prices(
        erpnext_client,
        sevdesk_client,
        price_list=config.erpnext_price_list,
        default_tax_rate=config.default_tax_rate,
        dry_run=dry_run,
    )

    updated = sum(1 for result in results if result.updated)
    unchanged = len(results) - updated
    logger.info(
        "Sync complete: %d updated, %d already in sync%s",
        updated,
        unchanged,
        " (dry-run)" if dry_run else "",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
