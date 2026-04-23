from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from polymarket_quant.domain.operator import (
    ConnectionComponent,
    ConnectionState,
    ConnectionStatus,
    GlobalMode,
)
from polymarket_quant.services.operator_queries import OperatorQueryService
from polymarket_quant.services.operator_runtime_registry import OperatorRuntimeRegistry
from polymarket_quant.ui.contracts import OPERATOR_CONSOLE_DETAIL_PANES
from polymarket_quant.ui.operator_console_app import (
    build_mode_preflight,
    confirm_mode_switch,
)


def instant() -> datetime:
    return datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc)


def healthy_connections() -> list[ConnectionState]:
    return [
        ConnectionState(
            component=ConnectionComponent.DB,
            status=ConnectionStatus.HEALTHY,
            updated_at=instant(),
        ),
        ConnectionState(
            component=ConnectionComponent.MARKET_DATA_WS,
            status=ConnectionStatus.HEALTHY,
            updated_at=instant(),
        ),
        ConnectionState(
            component=ConnectionComponent.EXECUTION,
            status=ConnectionStatus.HEALTHY,
            updated_at=instant(),
        ),
        ConnectionState(
            component=ConnectionComponent.RISK,
            status=ConnectionStatus.HEALTHY,
            updated_at=instant(),
        ),
    ]


def test_mode_switch_requires_preflight_and_confirmation(tmp_path: Path) -> None:
    registry = OperatorRuntimeRegistry(global_mode=GlobalMode.REPLAY)
    blocked_service = OperatorQueryService(
        tmp_path,
        runtime_registry=registry,
        connections_provider=lambda: [
            ConnectionState(
                component=ConnectionComponent.DB,
                status=ConnectionStatus.DOWN,
                updated_at=instant(),
            ),
            ConnectionState(
                component=ConnectionComponent.MARKET_DATA_WS,
                status=ConnectionStatus.DOWN,
                updated_at=instant(),
            ),
        ],
    )

    blocked_preflight = build_mode_preflight(blocked_service, target_mode="paper")
    assert blocked_preflight.allowed is False
    assert any("DB is down" in blocker for blocker in blocked_preflight.blockers)
    assert confirm_mode_switch(blocked_service, blocked_preflight, confirmed=True) is False
    assert registry.get_global_mode() == GlobalMode.REPLAY

    allowed_service = OperatorQueryService(
        tmp_path,
        runtime_registry=registry,
        connections_provider=healthy_connections,
    )
    allowed_preflight = build_mode_preflight(
        allowed_service,
        target_mode="live-disabled",
    )
    assert allowed_preflight.allowed is True
    assert any("live-disabled" in warning for warning in allowed_preflight.warnings)
    assert confirm_mode_switch(allowed_service, allowed_preflight, confirmed=False) is False
    assert registry.get_global_mode() == GlobalMode.REPLAY
    assert confirm_mode_switch(allowed_service, allowed_preflight, confirmed=True) is True
    assert registry.get_global_mode() == GlobalMode.LIVE_DISABLED


def test_runs_artifacts_surface_is_not_a_homepage_default_pane() -> None:
    source = Path("src/polymarket_quant/ui/operator_console_app.py").read_text()

    assert "operator.runs_artifacts" in source
    assert "operator.runs_artifacts_caption" in source
    assert OPERATOR_CONSOLE_DETAIL_PANES == ["Positions / Orders", "PnL / Exposure"]
    assert "Runs / Artifacts" not in OPERATOR_CONSOLE_DETAIL_PANES


def test_readme_documents_phase5_operator_console() -> None:
    readme = Path("README.md").read_text()

    assert "## Phase 5 Operator Console" in readme
    assert "streamlit run src/polymarket_quant/ui/operator_console_app.py" in readme
    assert "preflight" in readme
    assert "confirm" in readme
    assert "live-disabled" in readme
