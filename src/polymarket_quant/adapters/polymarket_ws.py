from __future__ import annotations

import json
import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any


MARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


class MarketWebSocketClient:
    def __init__(
        self,
        url: str = MARKET_WS_URL,
        connector: Callable[[str], Any] | None = None,
        heartbeat_interval_seconds: float = 10.0,
    ) -> None:
        self.url = url
        self.connector = connector
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

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
            heartbeat_task = asyncio.create_task(self._heartbeat(websocket))
            try:
                async for message in websocket:
                    if not message:
                        continue
                    if isinstance(message, bytes):
                        message = message.decode("utf-8")
                    if isinstance(message, str) and message.upper() == "PONG":
                        continue
                    if isinstance(message, str) and message.lower() == "ping":
                        await websocket.send("pong")
                        continue
                    payload = json.loads(message)
                    if isinstance(payload, list):
                        for item in payload:
                            if isinstance(item, dict):
                                yield item
                    elif isinstance(payload, dict):
                        yield payload
            finally:
                heartbeat_task.cancel()

    async def _heartbeat(self, websocket: Any) -> None:
        if self.heartbeat_interval_seconds <= 0:
            return
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval_seconds)
                await websocket.send("PING")
        except asyncio.CancelledError:
            return


def _default_connector(url: str) -> Any:
    import websockets

    return websockets.connect(url, proxy=None)
