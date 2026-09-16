"""Core sync logic: ERPNext gross prices -> sevDesk net prices.

The number in ERPNext's price list rate (labeled gross/"Brutto" there) is
carried over unchanged as the sevDesk *net* price. sevDesk's own gross price
is then derived by adding VAT on top: e.g. ERPNext 100 EUR (gross) becomes
sevDesk 100 EUR net, i.e. 119 EUR gross at 19% VAT.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Dict, List, Optional

from .sevdesk_client import SevDeskClient

logger = logging.getLogger(__name__)

#: Prices within this many currency units are considered already in sync,
#: to avoid re-writing sevDesk parts because of floating point rounding.
DEFAULT_PRICE_TOLERANCE = 0.005


@dataclasses.dataclass(frozen=True)
class SyncResult:
    item_code: str
    net_price: float
    gross_price: float
    tax_rate: float
    action: str  # "created", "updated", or "unchanged"


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
    need to be newly created in sevDesk, ``item_name``.

    Items are matched to sevDesk parts on ``item_code`` against sevDesk's
    ``partNumber``:

    - If a matching part exists, its tax rate is used to compute the sevDesk
      gross price and its price fields are updated if they differ.
    - If no matching part exists, a new one is created using
      ``default_tax_rate`` and ``default_unity_id`` (both required for
      creation; the item is skipped with a warning if either is missing).
    """
    sevdesk_parts = sevdesk_client.get_parts_by_number()

    results: List[SyncResult] = []
    skipped: List[str] = []

    for item_code, item in erpnext_items.items():
        net_price = float(item["gross_price"])
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
                skipped.append(item_code)
                continue
            tax_rate = float(tax_rate)
            gross_price = net_to_gross(net_price, tax_rate)

            current_net = part.get("price")
            already_in_sync = (
                current_net is not None
                and abs(float(current_net) - net_price) < price_tolerance
            )

            if already_in_sync:
                logger.debug("%s already in sync (net %.2f)", item_code, net_price)
                results.append(
                    SyncResult(item_code, net_price, gross_price, tax_rate, "unchanged")
                )
                continue

            if dry_run:
                logger.info(
                    "[dry-run] Would update %s: net -> %.2f (gross %.2f, tax %.2f%%)",
                    item_code,
                    net_price,
                    gross_price,
                    tax_rate,
                )
            else:
                sevdesk_client.update_part_price(
                    part["id"],
                    net_price=net_price,
                    gross_price=gross_price,
                    tax_rate=tax_rate,
                )
                logger.info(
                    "Updated %s: net -> %.2f (gross %.2f, tax %.2f%%)",
                    item_code,
                    net_price,
                    gross_price,
                    tax_rate,
                )
            results.append(
                SyncResult(item_code, net_price, gross_price, tax_rate, "updated")
            )
            continue

        # No matching sevDesk part: create one.
        if default_tax_rate is None:
            logger.warning(
                "Skipping %s: no matching sevDesk part and no default tax "
                "rate configured to create one",
                item_code,
            )
            skipped.append(item_code)
            continue
        if not default_unity_id:
            logger.warning(
                "Skipping %s: no matching sevDesk part and no default unity "
                "configured to create one",
                item_code,
            )
            skipped.append(item_code)
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

    if skipped:
        logger.warning(
            "%d ERPNext item(s) skipped (missing tax rate/unity to create, "
            "see warnings above): %s",
            len(skipped),
            ", ".join(sorted(skipped)),
        )

    return results
