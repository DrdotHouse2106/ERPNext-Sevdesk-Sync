"""Scheduled and on-demand entry points for the sevDesk price sync."""

from __future__ import annotations

import frappe
from frappe.utils import now_datetime

from .erpnext_source import get_price_list_items
from .price_sync import sync_prices
from .sevdesk_client import SevDeskClient


def scheduled_sync() -> None:
    """Called daily by Frappe's scheduler, see ``scheduler_events`` in hooks.py."""
    settings = frappe.get_single("SevDesk Sync Settings")
    if not settings.enabled:
        frappe.logger("sevdesk_sync").info(
            "Synchronisierung ist deaktiviert (Synchronisierung aktiv = Nein), "
            "automatischer Lauf wird übersprungen."
        )
        return
    run_sync()


@frappe.whitelist()
def run_sync_now() -> str:
    """Manually trigger a sync, e.g. from the bench console or the settings page button."""
    frappe.only_for("System Manager")
    return run_sync()


@frappe.whitelist()
def run_dry_run() -> str:
    """Manually trigger a dry run, regardless of the stored "Trockenlauf" setting.

    Does not update "Letzte Synchronisierung", since it's only a test.
    """
    frappe.only_for("System Manager")
    return run_sync(force_dry_run=True, persist=False)


@frappe.whitelist()
def test_connection() -> str:
    """Verify that the configured sevDesk base URL and API token work."""
    frappe.only_for("System Manager")
    settings = frappe.get_single("SevDesk Sync Settings")
    sevdesk_client = SevDeskClient(
        settings.sevdesk_base_url,
        settings.get_password("sevdesk_api_token"),
    )
    sevdesk_client.test_connection()
    return "Verbindung zu sevDesk erfolgreich hergestellt."


def run_sync(*, force_dry_run: bool = False, persist: bool = True) -> str:
    settings = frappe.get_single("SevDesk Sync Settings")
    dry_run = True if force_dry_run else bool(settings.dry_run)

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
        dry_run=dry_run,
    )

    created = sum(1 for result in results if result.action == "created")
    updated = sum(1 for result in results if result.action == "updated")
    unchanged = sum(1 for result in results if result.action == "unchanged")
    summary = (
        f"{created} angelegt, {updated} aktualisiert, {unchanged} bereits synchron"
        f"{' (Trockenlauf)' if dry_run else ''}"
    )

    if persist:
        settings.db_set("last_sync_on", now_datetime())
        settings.db_set("last_sync_summary", summary)

    frappe.logger("sevdesk_sync").info(summary)
    return summary
