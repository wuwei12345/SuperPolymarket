from __future__ import annotations

from decimal import Decimal

from polymarket_quant.domain.market import CanonicalMarket
from polymarket_quant.domain.market_data import ReferenceToken
from polymarket_quant.storage.market_store import MarketStore


SELECTION_REASON = "liquidity_desc_end_date_asc"


class UniverseSelector:
    def __init__(self, market_store: MarketStore, top_n: int = 50) -> None:
        if top_n < 1:
            raise ValueError("top_n must be at least 1")
        self.market_store = market_store
        self.top_n = top_n

    def select_top_tokens(self) -> list[ReferenceToken]:
        markets = sorted(self.market_store.list_markets(), key=_market_sort_key)
        tokens: list[ReferenceToken] = []
        rank = 1
        selection_reason = "liquidity_desc_end_date_asc"
        for market in markets:
            for outcome, token_id in (
                ("Yes", market.yes_token_id),
                ("No", market.no_token_id),
            ):
                tokens.append(
                    ReferenceToken(
                        token_id=token_id,
                        condition_id=market.condition_id,
                        market_id=market.market_id,
                        question=market.question,
                        outcome=outcome,
                        category=market.category,
                        liquidity=(
                            None
                            if market.liquidity is None
                            else Decimal(str(market.liquidity))
                        ),
                        end_date=market.end_date,
                        active=market.active,
                        accepting_orders=market.accepting_orders,
                        universe_rank=rank,
                        selection_reason=selection_reason,
                    )
                )
                rank += 1
                if len(tokens) >= self.top_n:
                    return tokens
        return tokens


def _market_sort_key(market: CanonicalMarket) -> tuple[float, int, object, str]:
    liquidity = market.liquidity if market.liquidity is not None else 0.0
    has_no_end_date = 1 if market.end_date is None else 0
    return (-liquidity, has_no_end_date, market.end_date or "", market.question)
