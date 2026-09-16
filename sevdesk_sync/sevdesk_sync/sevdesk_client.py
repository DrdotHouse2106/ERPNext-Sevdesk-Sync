"""Minimal client for the parts of the sevDesk REST API we need."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class SevDeskError(RuntimeError):
    """Raised when the sevDesk API returns an error response."""


class SevDeskClient:
    """Talks to the sevDesk REST API (Part / Artikel endpoint) using an API token."""

    def __init__(
        self,
        base_url: str,
        api_token: str,
        session: Optional[requests.Session] = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Authorization": api_token,
                "Accept": "application/json",
            }
        )

    def get_parts_by_number(self) -> Dict[str, Dict[str, Any]]:
        """Return ``{partNumber: part}`` for all sevDesk parts that have a part number.

        The part number is expected to match the ERPNext ``item_code`` so
        items can be paired up between the two systems.
        """
        parts: Dict[str, Dict[str, Any]] = {}
        limit = 100
        offset = 0

        while True:
            response = self._session.get(
                f"{self._base_url}/Part",
                params={"limit": limit, "offset": offset},
                timeout=self._timeout,
            )
            if response.status_code != 200:
                raise SevDeskError(
                    f"sevDesk request failed with status {response.status_code}: "
                    f"{response.text}"
                )

            batch = response.json().get("objects", [])
            for part in batch:
                part_number = part.get("partNumber")
                if part_number:
                    parts[part_number] = part

            if len(batch) < limit:
                break
            offset += limit

        logger.info("Fetched %d sevDesk part(s) with a part number", len(parts))
        return parts

    def update_part_price(
        self,
        part_id: str,
        *,
        net_price: float,
        gross_price: float,
        tax_rate: float,
    ) -> None:
        """Update a sevDesk part's net and gross sales price."""
        response = self._session.put(
            f"{self._base_url}/Part/{part_id}",
            json={
                "price": round(net_price, 2),
                "priceGross": round(gross_price, 2),
                "taxRate": tax_rate,
            },
            timeout=self._timeout,
        )
        if response.status_code != 200:
            raise SevDeskError(
                f"sevDesk update for part {part_id} failed with status "
                f"{response.status_code}: {response.text}"
            )
