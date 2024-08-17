from asyncio import Future
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any

import httpx
import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class HTTPClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.Client(base_url=self.base_url)
        self.executor = ThreadPoolExecutor(max_workers=10)

    def get(self, endpoint: str, params: Dict[str, Any] = None) -> Future:
        logger.info(f"GET request to {endpoint} with params {params}")
        return self.executor.submit(self._get, endpoint, params)

    def _get(self, endpoint: str, params: Dict[str, Any] = None) -> httpx.Response:
        response = self.client.get(endpoint, params=params)
        response.raise_for_status()
        return response

    def post(self, endpoint: str, data: BaseModel) -> Future:
        logger.info(f"POST request to {endpoint} with data {data}")
        return self.executor.submit(self._post, endpoint, data)

    def _post(self, endpoint: str, data: BaseModel) -> httpx.Response:
        response = self.client.post(endpoint, json=data.dict())
        response.raise_for_status()
        return response

    def close(self) -> None:
        logger.info("Closing HTTP client and executor")
        self.client.close()
        self.executor.shutdown()