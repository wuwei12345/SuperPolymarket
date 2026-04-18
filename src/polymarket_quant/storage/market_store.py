from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from polymarket_quant.domain.market import CanonicalMarket


class MarketStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def init_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS markets (
                    condition_id TEXT PRIMARY KEY,
                    market_id TEXT,
                    question TEXT NOT NULL,
                    category TEXT,
                    liquidity REAL,
                    end_date TEXT,
                    yes_token_id TEXT NOT NULL,
                    no_token_id TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    accepting_orders INTEGER NOT NULL,
                    restricted INTEGER,
                    source_map TEXT NOT NULL,
                    raw_gamma TEXT,
                    raw_clob TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def upsert_markets(self, markets: Sequence[CanonicalMarket]) -> int:
        rows = [self._to_row(market) for market in markets if market.is_phase1_valid()]
        if not rows:
            return 0

        self.init_schema()
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO markets (
                    condition_id,
                    market_id,
                    question,
                    category,
                    liquidity,
                    end_date,
                    yes_token_id,
                    no_token_id,
                    active,
                    accepting_orders,
                    restricted,
                    source_map,
                    raw_gamma,
                    raw_clob,
                    updated_at
                ) VALUES (
                    :condition_id,
                    :market_id,
                    :question,
                    :category,
                    :liquidity,
                    :end_date,
                    :yes_token_id,
                    :no_token_id,
                    :active,
                    :accepting_orders,
                    :restricted,
                    :source_map,
                    :raw_gamma,
                    :raw_clob,
                    :updated_at
                )
                ON CONFLICT(condition_id) DO UPDATE SET
                    market_id = excluded.market_id,
                    question = excluded.question,
                    category = excluded.category,
                    liquidity = excluded.liquidity,
                    end_date = excluded.end_date,
                    yes_token_id = excluded.yes_token_id,
                    no_token_id = excluded.no_token_id,
                    active = excluded.active,
                    accepting_orders = excluded.accepting_orders,
                    restricted = excluded.restricted,
                    source_map = excluded.source_map,
                    raw_gamma = excluded.raw_gamma,
                    raw_clob = excluded.raw_clob,
                    updated_at = excluded.updated_at
                """,
                rows,
            )
        return len(rows)

    def list_markets(
        self,
        category: str | None = None,
        min_liquidity: float | None = None,
        restricted: bool | None = None,
    ) -> list[CanonicalMarket]:
        self.init_schema()
        clauses = ["active = 1", "accepting_orders = 1"]
        params: dict[str, object] = {}

        if category:
            clauses.append("category = :category")
            params["category"] = category
        if min_liquidity is not None:
            clauses.append("COALESCE(liquidity, 0) >= :min_liquidity")
            params["min_liquidity"] = min_liquidity
        if restricted is not None:
            clauses.append("restricted = :restricted")
            params["restricted"] = int(restricted)

        sql = f"""
            SELECT *
            FROM markets
            WHERE {' AND '.join(clauses)}
            ORDER BY liquidity DESC, end_date ASC, question ASC
        """
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_json(value: object | None) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=True, sort_keys=True)

    @classmethod
    def _to_row(cls, market: CanonicalMarket) -> dict[str, object | None]:
        dumped = market.model_dump(mode="json")
        return {
            "condition_id": market.condition_id,
            "market_id": market.market_id,
            "question": market.question,
            "category": market.category,
            "liquidity": market.liquidity,
            "end_date": dumped["end_date"],
            "yes_token_id": market.yes_token_id,
            "no_token_id": market.no_token_id,
            "active": int(market.active),
            "accepting_orders": int(market.accepting_orders),
            "restricted": None if market.restricted is None else int(market.restricted),
            "source_map": cls._to_json(dumped["source_map"]),
            "raw_gamma": cls._to_json(dumped["raw_gamma"]),
            "raw_clob": cls._to_json(dumped["raw_clob"]),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _from_row(row: sqlite3.Row) -> CanonicalMarket:
        restricted = row["restricted"]
        return CanonicalMarket(
            market_id=row["market_id"],
            question=row["question"],
            category=row["category"],
            liquidity=row["liquidity"],
            end_date=row["end_date"],
            condition_id=row["condition_id"],
            yes_token_id=row["yes_token_id"],
            no_token_id=row["no_token_id"],
            active=bool(row["active"]),
            accepting_orders=bool(row["accepting_orders"]),
            restricted=None if restricted is None else bool(restricted),
            source_map=json.loads(row["source_map"]),
            raw_gamma=None if row["raw_gamma"] is None else json.loads(row["raw_gamma"]),
            raw_clob=None if row["raw_clob"] is None else json.loads(row["raw_clob"]),
        )
