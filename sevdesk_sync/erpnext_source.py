"""ERPNext-side data access for the sevDesk sync.

Runs inside the Frappe process, so item prices are read directly via the
Frappe ORM instead of an external REST call.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional

import frappe

#: Frappe fieldnames are snake_case identifiers; this guards the dynamic
#: ``required_field`` against being interpolated into anything but a plain
#: column reference.
_FIELDNAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def get_price_list_items(
    price_list: str,
    excluded_item_groups: Optional[Iterable[str]] = None,
    required_field: Optional[str] = None,
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

    If ``required_field`` (an Item fieldname, e.g. a custom field) is given,
    only items where that field has a truthy value are included; items where
    it is empty are left out entirely, same as an excluded item group.
    """
    fields = [
        "item_code",
        "price_list_rate",
        "item_code.item_name as item_name",
        "item_code.item_group as item_group",
        "item_code.disabled as disabled",
    ]
    if required_field:
        if not _FIELDNAME_RE.match(required_field):
            raise ValueError(
                f"Invalid Item fieldname for 'Nur syncen, wenn Feld befüllt ist': "
                f"{required_field!r}"
            )
        fields.append(f"item_code.{required_field} as required_field_value")

    rows = frappe.get_all(
        "Item Price",
        filters={"price_list": price_list, "selling": 1},
        fields=fields,
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
        if required_field and not row.get("required_field_value"):
            continue
        items[item_code] = {
            "item_name": row.get("item_name") or item_code,
            "gross_price": float(rate),
            "disabled": bool(row.get("disabled")),
        }
    return items
