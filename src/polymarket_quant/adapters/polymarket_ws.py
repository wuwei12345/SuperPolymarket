from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any


MARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


class MarketWebSocketClient:
    def __init__(
        self,
        url: str = MARKET_WS_URL,
        connector: Callable[[str], Any] | None = None,
    ) -> None:
        self.url = url
        self.connector = connector

    def build_subscription_payload(self, token_ids: list[str]) -> dict[str, object]:
        return {
            "assets_ids": token_ids,
            "type": "market",
            "custom_feature_enabled": True,
        }

    async def subscribe(self, token_ids: list[str]) -> AsyncIterator[dict[str, Any]]:
        connector = self.connector or _default_connector
        async with connector(self.url) as websocket:
            await websocket.send(json.dumps(self.build_subscription_payload(token_ids)))
            async for message in websocket:
                if not message:
                    continue
                if isinstance(message, bytes):
                    message = message.decode("utf-8")
                payload = json.loads(message)
                if isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, dict):
                            yield item
                elif isinstance(payload, dict):
                    yield payload


def _default_connector(url: str) -> Any:
    import websockets

    return websockets.connect(url)
