"""Scheduled and on-demand entry points for the sevDesk price sync."""

from __future__ import annotations

from typing import Any, Dict, List

import frappe
from frappe.utils import now_datetime

from .erpnext_source import get_price_list_items
from .price_sync import SyncResult, sync_prices
from .sevdesk_client import SevDeskClient

#: German labels for SyncResult.action, used for the "Aktion" select field on
#: SevDesk Sync Log Item.
_ACTION_LABELS = {
    "created": "Angelegt",
    "updated": "Aktualisiert",
    "skipped": "Übersprungen",
}


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
def run_sync_now() -> Dict[str, Any]:
    """Manually trigger a real sync, e.g. from the settings page button."""
    frappe.only_for("System Manager")
    return run_sync()


@frappe.whitelist()
def run_dry_run() -> Dict[str, Any]:
    """Manually trigger a dry run, regardless of the stored "Trockenlauf" setting.

    Does not update "Letzte Synchronisierung" on the settings doc, since it's
    only a test — but the run is still recorded in SevDesk Sync Log for review.
    """
    frappe.only_for("System Manager")
    return run_sync(force_dry_run=True, persist_settings=False)


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


def run_sync(*, force_dry_run: bool = False, persist_settings: bool = True) -> Dict[str, Any]:
    settings = frappe.get_single("SevDesk Sync Settings")
    dry_run = True if force_dry_run else bool(settings.dry_run)

    excluded_item_groups = [row.item_group for row in settings.excluded_item_groups]
    erpnext_items = get_price_list_items(
        settings.erpnext_price_list,
        excluded_item_groups=excluded_item_groups,
        required_field=settings.sync_only_if_field_filled or None,
    )
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

    created = [r for r in results if r.action == "created"]
    updated = [r for r in results if r.action == "updated"]
    unchanged = [r for r in results if r.action == "unchanged"]
    skipped = [r for r in results if r.action == "skipped"]

    summary = (
        f"{len(created)} angelegt, {len(updated)} aktualisiert, "
        f"{len(unchanged)} bereits synchron"
        f"{f', {len(skipped)} übersprungen' if skipped else ''}"
        f"{' (Trockenlauf)' if dry_run else ''}"
    )

    sync_time = now_datetime()
    log_name = _save_sync_log(
        sync_time=sync_time,
        dry_run=dry_run,
        summary=summary,
        counts=(len(created), len(updated), len(unchanged), len(skipped)),
        items=[*created, *updated, *skipped],
    )

    if persist_settings:
        settings.db_set("last_sync_on", sync_time)
        settings.db_set("last_sync_summary", summary)

    frappe.logger("sevdesk_sync").info(summary)
    return {"summary": summary, "log": log_name}


def _save_sync_log(
    *,
    sync_time,
    dry_run: bool,
    summary: str,
    counts: tuple,
    items: List[SyncResult],
) -> str:
    """Persist one SevDesk Sync Log record plus its SevDesk Sync Log Item rows.

    Item rows are bulk-inserted (bypassing normal Document hooks) since a
    single run can touch thousands of items and this is a plain audit trail,
    not data that needs controller validation.
    """
    created_count, updated_count, unchanged_count, skipped_count = counts

    log = frappe.get_doc(
        {
            "doctype": "SevDesk Sync Log",
            "sync_time": sync_time,
            "dry_run": 1 if dry_run else 0,
            "created_count": created_count,
            "updated_count": updated_count,
            "unchanged_count": unchanged_count,
            "skipped_count": skipped_count,
            "summary": summary,
        }
    )
    log.insert(ignore_permissions=True)

    if items:
        now = frappe.utils.now()
        user = frappe.session.user
        fields = [
            "name",
            "sync_log",
            "item_code",
            "action",
            "net_price",
            "gross_price",
            "tax_rate",
            "reason",
            "owner",
            "creation",
            "modified",
            "modified_by",
        ]
        values = [
            [
                frappe.generate_hash(length=10),
                log.name,
                result.item_code,
                _ACTION_LABELS[result.action],
                result.net_price,
                result.gross_price,
                result.tax_rate,
                result.reason,
                user,
                now,
                now,
                user,
            ]
            for result in items
        ]
        frappe.db.bulk_insert("SevDesk Sync Log Item", fields=fields, values=values)

    return log.name
