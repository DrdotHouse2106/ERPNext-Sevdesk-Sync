"""ERPNext-side data access for the sevDesk sync.

Runs inside the Frappe process, so item prices are read directly via the
Frappe ORM instead of an external REST call.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

import frappe


def get_price_list_items(
    price_list: str,
    excluded_item_groups: Optional[Iterable[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Return ``{item_code: {"item_name": ..., "gross_price": ..., "disabled": ...}}``.

    ``gross_price`` is the Item Price ``price_list_rate`` for the given
    selling price list, assumed to include VAT (gross), as is common for a
    "Standard Selling" price list aimed at end-customer invoices.
    ``item_name`` is included for parts that still need to be created in
    sevDesk. ``disabled`` reflects the ERPNext Item's "Disabled" checkbox and
    is used to deactivate (or reactivate) the matching sevDesk part.

    Items whose Item Group (exact match, not including sub-groups) is in
    ``excluded_item_groups`` are left out entirely.
    """
    rows = frappe.get_all(
        "Item Price",
        filters={"price_list": price_list, "selling": 1},
        fields=[
            "item_code",
            "price_list_rate",
            "item_code.item_name as item_name",
            "item_code.item_group as item_group",
            "item_code.disabled as disabled",
        ],
    )

    excluded = set(excluded_item_groups or [])

    items: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        item_code = row.get("item_code")
        rate = row.get("price_list_rate")
        if not item_code or rate is None:
            continue
        if excluded and row.get("item_group") in excluded:
            continue
        items[item_code] = {
            "item_name": row.get("item_name") or item_code,
            "gross_price": float(rate),
            "disabled": bool(row.get("disabled")),
        }
    return items
