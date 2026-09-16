"""Core sync logic: ERPNext gross prices -> sevDesk net prices.

The number in ERPNext's price list rate (labeled gross/"Brutto" there) is
carried over unchanged as the sevDesk *net* price. sevDesk's own gross price
is then derived by adding VAT on top: e.g. ERPNext 100 EUR (gross) becomes
sevDesk 100 EUR net, i.e. 119 EUR gross at 19% VAT.

An ERPNext item's "Disabled" flag is mirrored to the sevDesk part's active
status: disabling an item in ERPNext deactivates the matching sevDesk part
(and re-enabling it reactivates that part), instead of touching its price.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Dict, List, Optional

from .sevdesk_client import STATUS_ACTIVE, STATUS_INACTIVE, SevDeskClient

logger = logging.getLogger(__name__)

#: Prices within this many currency units are considered already in sync,
#: to avoid re-writing sevDesk parts because of floating point rounding.
DEFAULT_PRICE_TOLERANCE = 0.005


@dataclasses.dataclass(frozen=True)
class SyncResult:
    item_code: str
    net_price: Optional[float]
    gross_price: Optional[float]
    tax_rate: Optional[float]
    action: str  # "created", "updated", "unchanged", or "skipped"
    reason: str = ""  # set (in German, for display) when action == "skipped"


def net_to_gross(net_price: float, tax_rate: float) -> float:
    """Add VAT on top of a net price to get the corresponding gross price."""
    return net_price * (1 + tax_rate / 100)


def sync_prices(
    erpnext_items: Dict[str, Dict[str, Any]],
    sevdesk_client: SevDeskClient,
    *,
    default_tax_rate: Optional[float] = None,
    default_unity_id: Optional[str] = None,
    dry_run: bool = False,
    price_tolerance: float = DEFAULT_PRICE_TOLERANCE,
) -> List[SyncResult]:
    """Sync ERPNext price list rates to sevDesk as net prices.

    ``erpnext_items`` maps ERPNext ``item_code`` to a dict with at least
    ``gross_price`` (the ERPNext price list rate) and, for items that may
    need to be newly created in sevDesk, ``item_name``. An optional
    ``disabled`` flag mirrors the ERPNext item's "Disabled" checkbox.

    Items are matched to sevDesk parts on ``item_code`` against sevDesk's
    ``partNumber``:

    - If a matching part exists, its tax rate is used to compute the sevDesk
      gross price, and its price and active status are updated if either
      differs from the target (active unless the ERPNext item is disabled).
    - If no matching part exists and the ERPNext item is not disabled, a new
      one is created using ``default_tax_rate`` and ``default_unity_id``
      (both required for creation; the item is skipped if either is
      missing). A disabled ERPNext item without a matching part is skipped
      without creating one.

    Every ERPNext item produces exactly one ``SyncResult``, including skipped
    ones (with ``action="skipped"`` and a human-readable ``reason``), so
    callers can build a full report of a run.
    """
    sevdesk_parts = sevdesk_client.get_parts_by_number()

    results: List[SyncResult] = []

    for item_code, item in erpnext_items.items():
        net_price = float(item["gross_price"])
        disabled = bool(item.get("disabled"))
        target_status = STATUS_INACTIVE if disabled else STATUS_ACTIVE
        part = sevdesk_parts.get(item_code)

        if part is not None:
            tax_rate = part.get("taxRate")
            if tax_rate is None:
                tax_rate = default_tax_rate
            if tax_rate is None:
                logger.warning(
                    "Skipping %s: no tax rate on the sevDesk part and no "
                    "default tax rate configured",
                    item_code,
                )
                results.append(
                    SyncResult(
                        item_code,
                        net_price,
                        None,
                        None,
                        "skipped",
                        reason=(
                            "Kein Steuersatz am sevDesk-Artikel und kein "
                            "Standard-Steuersatz konfiguriert"
                        ),
                    )
                )
                continue
            tax_rate = float(tax_rate)
            gross_price = net_to_gross(net_price, tax_rate)

            current_net = part.get("price")
            price_in_sync = (
                current_net is not None
                and abs(float(current_net) - net_price) < price_tolerance
            )
            current_status = part.get("status")
            status_in_sync = (
                current_status is not None and int(current_status) == target_status
            )

            if price_in_sync and status_in_sync:
                logger.debug("%s already in sync (net %.2f)", item_code, net_price)
                results.append(
                    SyncResult(item_code, net_price, gross_price, tax_rate, "unchanged")
                )
                continue

            if dry_run:
                logger.info(
                    "[dry-run] Would update %s: net -> %.2f (gross %.2f, tax %.2f%%, "
                    "status -> %s)",
                    item_code,
                    net_price,
                    gross_price,
                    tax_rate,
                    target_status,
                )
            else:
                sevdesk_client.update_part_price(
                    part["id"],
                    net_price=net_price,
                    gross_price=gross_price,
                    tax_rate=tax_rate,
                    status=target_status,
                )
                logger.info(
                    "Updated %s: net -> %.2f (gross %.2f, tax %.2f%%, status -> %s)",
                    item_code,
                    net_price,
                    gross_price,
                    tax_rate,
                    target_status,
                )
            results.append(
                SyncResult(item_code, net_price, gross_price, tax_rate, "updated")
            )
            continue

        # No matching sevDesk part.
        if disabled:
            logger.info(
                "Skipping %s: item is disabled in ERPNext, not creating a new "
                "sevDesk part for it",
                item_code,
            )
            results.append(
                SyncResult(
                    item_code,
                    net_price,
                    None,
                    None,
                    "skipped",
                    reason="Artikel ist in ERPNext deaktiviert, keine Neuanlage in sevDesk",
                )
            )
            continue

        if default_tax_rate is None:
            logger.warning(
                "Skipping %s: no matching sevDesk part and no default tax "
                "rate configured to create one",
                item_code,
            )
            results.append(
                SyncResult(
                    item_code,
                    net_price,
                    None,
                    None,
                    "skipped",
                    reason=(
                        "Kein passender sevDesk-Artikel und kein "
                        "Standard-Steuersatz zum Anlegen konfiguriert"
                    ),
                )
            )
            continue
        if not default_unity_id:
            logger.warning(
                "Skipping %s: no matching sevDesk part and no default unity "
                "configured to create one",
                item_code,
            )
            results.append(
                SyncResult(
                    item_code,
                    net_price,
                    None,
                    None,
                    "skipped",
                    reason=(
                        "Kein passender sevDesk-Artikel und keine "
                        "sevDesk-Standardeinheit zum Anlegen konfiguriert"
                    ),
                )
            )
            continue

        tax_rate = float(default_tax_rate)
        gross_price = net_to_gross(net_price, tax_rate)

        if dry_run:
            logger.info(
                "[dry-run] Would create %s: net %.2f (gross %.2f, tax %.2f%%)",
                item_code,
                net_price,
                gross_price,
                tax_rate,
            )
        else:
            sevdesk_client.create_part(
                name=item.get("item_name") or item_code,
                part_number=item_code,
                net_price=net_price,
                gross_price=gross_price,
                tax_rate=tax_rate,
                unity_id=default_unity_id,
            )
            logger.info(
                "Created %s: net %.2f (gross %.2f, tax %.2f%%)",
                item_code,
                net_price,
                gross_price,
                tax_rate,
            )
        results.append(SyncResult(item_code, net_price, gross_price, tax_rate, "created"))

    skipped_count = sum(1 for result in results if result.action == "skipped")
    if skipped_count:
        logger.warning(
            "%d ERPNext item(s) skipped (see warnings above): %s",
            skipped_count,
            ", ".join(sorted(r.item_code for r in results if r.action == "skipped")),
        )

    return results
