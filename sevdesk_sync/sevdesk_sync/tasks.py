"""Scheduled and on-demand entry points for the sevDesk price sync."""

from __future__ import annotations

import frappe
from frappe.utils import now_datetime

from .erpnext_source import get_price_list_items
from .price_sync import sync_prices
from .sevdesk_client import SevDeskClient


def scheduled_sync() -> None:
    """Called daily by Frappe's scheduler, see ``scheduler_events`` in hooks.py."""
    run_sync()


@frappe.whitelist()
def run_sync_now() -> str:
    """Manually trigger a sync, e.g. from the bench console (``bench execute``)."""
    frappe.only_for("System Manager")
    return run_sync()


def run_sync() -> str:
    settings = frappe.get_single("SevDesk Sync Settings")

    erpnext_items = get_price_list_items(settings.erpnext_price_list)
    sevdesk_client = SevDeskClient(
        settings.sevdesk_base_url,
        settings.get_password("sevdesk_api_token"),
    )

    results = sync_prices(
        erpnext_items,
        sevdesk_client,
        default_tax_rate=settings.default_tax_rate or None,
        default_unity_id=settings.sevdesk_default_unity_id or None,
        dry_run=bool(settings.dry_run),
    )

    created = sum(1 for result in results if result.action == "created")
    updated = sum(1 for result in results if result.action == "updated")
    unchanged = sum(1 for result in results if result.action == "unchanged")
    summary = (
        f"{created} created, {updated} updated, {unchanged} already in sync"
        f"{' (dry-run)' if settings.dry_run else ''}"
    )

    settings.db_set("last_sync_on", now_datetime())
    settings.db_set("last_sync_summary", summary)

    frappe.logger("sevdesk_sync").info(summary)
    return summary
