"""ERPNext-side data access for the sevDesk sync.

Runs inside the Frappe process, so item prices are read directly via the
Frappe ORM instead of an external REST call.
"""

from __future__ import annotations

from typing import Dict

import frappe


def get_price_list_rates(price_list: str) -> Dict[str, float]:
    """Return ``{item_code: price_list_rate}`` for the given selling price list.

    The rates are assumed to be gross (VAT-included) prices, as is common for
    a "Standard Selling" price list aimed at end-customer invoices.
    """
    rows = frappe.get_all(
        "Item Price",
        filters={"price_list": price_list, "selling": 1},
        fields=["item_code", "price_list_rate"],
    )
    return {
        row.get("item_code"): float(row.get("price_list_rate"))
        for row in rows
        if row.get("item_code") and row.get("price_list_rate") is not None
    }
