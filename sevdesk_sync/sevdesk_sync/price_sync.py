"""Core sync logic: ERPNext gross prices -> sevDesk net prices."""

from __future__ import annotations

import dataclasses
import logging
from typing import Dict, List, Optional

from .sevdesk_client import SevDeskClient

logger = logging.getLogger(__name__)

#: Prices within this many currency units are considered already in sync,
#: to avoid re-writing sevDesk parts because of floating point rounding.
DEFAULT_PRICE_TOLERANCE = 0.005


@dataclasses.dataclass(frozen=True)
class SyncResult:
    item_code: str
    gross_price: float
    net_price: float
    tax_rate: float
    updated: bool


def gross_to_net(gross_price: float, tax_rate: float) -> float:
    """Convert a VAT-included (gross) price to a VAT-excluded (net) price."""
    return gross_price / (1 + tax_rate / 100)


def sync_prices(
    erpnext_prices: Dict[str, float],
    sevdesk_client: SevDeskClient,
    *,
    default_tax_rate: Optional[float] = None,
    dry_run: bool = False,
    price_tolerance: float = DEFAULT_PRICE_TOLERANCE,
) -> List[SyncResult]:
    """Sync gross ERPNext prices to sevDesk as net prices.

    ``erpnext_prices`` maps ERPNext ``item_code`` to its gross price list
    rate. Items are matched to sevDesk parts on ``item_code`` against
    sevDesk's ``partNumber``. The tax rate used for the gross-to-net
    conversion is taken from the existing sevDesk part (so it stays
    consistent with how sevDesk itself classifies the part); ``default_tax_rate``
    is only used as a fallback when a part has no tax rate set yet.
    """
    sevdesk_parts = sevdesk_client.get_parts_by_number()

    results: List[SyncResult] = []
    skipped: List[str] = []

    for item_code, gross_price in erpnext_prices.items():
        part = sevdesk_parts.get(item_code)
        if part is None:
            skipped.append(item_code)
            continue

        tax_rate = part.get("taxRate")
        if tax_rate is None:
            tax_rate = default_tax_rate
        if tax_rate is None:
            logger.warning(
                "Skipping %s: no tax rate on the sevDesk part and no "
                "DEFAULT_TAX_RATE configured",
                item_code,
            )
            skipped.append(item_code)
            continue
        tax_rate = float(tax_rate)

        net_price = gross_to_net(gross_price, tax_rate)
        current_net = part.get("price")
        already_in_sync = (
            current_net is not None
            and abs(float(current_net) - net_price) < price_tolerance
        )

        updated = False
        if already_in_sync:
            logger.debug("%s already in sync (net %.2f)", item_code, net_price)
        elif dry_run:
            logger.info(
                "[dry-run] Would update %s: net %.2f -> %.2f (gross %.2f, tax %.2f%%)",
                item_code,
                float(current_net) if current_net is not None else 0.0,
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
                "Updated %s: net %.2f -> %.2f (gross %.2f, tax %.2f%%)",
                item_code,
                float(current_net) if current_net is not None else 0.0,
                net_price,
                gross_price,
                tax_rate,
            )
            updated = True

        results.append(SyncResult(item_code, gross_price, net_price, tax_rate, updated))

    if skipped:
        logger.warning(
            "%d ERPNext item(s) had no matching sevDesk part (by part number) "
            "or no usable tax rate and were skipped: %s",
            len(skipped),
            ", ".join(sorted(skipped)),
        )

    return results
