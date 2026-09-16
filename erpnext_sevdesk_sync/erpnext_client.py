"""Minimal client for the parts of the ERPNext (Frappe) REST API we need."""

from __future__ import annotations

import logging
from typing import Dict, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


class ERPNextError(RuntimeError):
    """Raised when the ERPNext API returns an error response."""


class ERPNextClient:
    """Talks to a Frappe/ERPNext site's REST API using an API key/secret pair."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_secret: str,
        session: Optional[requests.Session] = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"token {api_key}:{api_secret}",
                "Accept": "application/json",
            }
        )

    def get_price_list_rates(self, price_list: str) -> Dict[str, float]:
        """Return ``{item_code: price_list_rate}`` for the given selling price list.

        The Item Price rates in ERPNext are assumed to be gross (VAT-included)
        prices, as is common for a "Standard Selling" price list aimed at
        end-customer invoices.
        """
        prices: Dict[str, float] = {}
        page_length = 200
        start = 0

        while True:
            params = {
                "filters": (
                    '[["price_list","=","%s"],["selling","=",1]]' % price_list
                ),
                "fields": '["item_code","price_list_rate"]',
                "limit_start": start,
                "limit_page_length": page_length,
            }
            response = self._session.get(
                f"{self._base_url}/api/resource/{quote('Item Price')}",
                params=params,
                timeout=self._timeout,
            )
            if response.status_code != 200:
                raise ERPNextError(
                    f"ERPNext request failed with status {response.status_code}: "
                    f"{response.text}"
                )

            batch = response.json().get("data", [])
            for row in batch:
                item_code = row.get("item_code")
                rate = row.get("price_list_rate")
                if item_code is None or rate is None:
                    continue
                prices[item_code] = float(rate)

            if len(batch) < page_length:
                break
            start += page_length

        logger.info(
            "Fetched %d item price(s) from ERPNext price list %r",
            len(prices),
            price_list,
        )
        return prices
