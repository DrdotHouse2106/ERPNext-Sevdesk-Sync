"""ERPNext-side data access for the sevDesk sync.

Runs inside the Frappe process, so item prices are read directly via the
Frappe ORM instead of an external REST call.
"""

from __future__ import annotations

from typing import Any, Dict

import frappe


def get_price_list_items(price_list: str) -> Dict[str, Dict[str, Any]]:
    """Return ``{item_code: {"item_name": ..., "gross_price": ...}}``.

    ``gross_price`` is the Item Price ``price_list_rate`` for the given
    selling price list, assumed to include VAT (gross), as is common for a
    "Standard Selling" price list aimed at end-customer invoices.
    ``item_name`` is included for parts that still need to be created in
    sevDesk.
    """
    rows = frappe.get_all(
        "Item Price",
        filters={"price_list": price_list, "selling": 1},
        fields=["item_code", "price_list_rate", "item_code.item_name as item_name"],
    )

    items: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        item_code = row.get("item_code")
        rate = row.get("price_list_rate")
        if not item_code or rate is None:
            continue
        items[item_code] = {
            "item_name": row.get("item_name") or item_code,
            "gross_price": float(rate),
        }
    return items
