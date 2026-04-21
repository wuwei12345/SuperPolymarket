from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from polymarket_quant.domain.strategy import RunManifest, StrategyEvent, StrategySignal
from polymarket_quant.services.run_artifacts import RunArtifactBundleWriter
from polymarket_quant.services.strategy_runtime import StrategyRuntime


@dataclass
class ReplayRunResult:
    processed_events: int
    clock_ticks: list[datetime] = field(default_factory=list)
    signals: list[StrategySignal] = field(default_factory=list)


class ReplayRuntime:
    def __init__(
        self,
        runtime: StrategyRuntime,
        *,
        time_step: timedelta,
        artifact_writer: RunArtifactBundleWriter | None = None,
        manifest: RunManifest | None = None,
    ) -> None:
        if time_step <= timedelta(0):
            raise ValueError("time_step must be positive")
        self.runtime = runtime
        self.time_step = time_step
        self.artifact_writer = artifact_writer
        self.manifest = manifest

    def run(self, events: list[StrategyEvent]) -> ReplayRunResult:
        ordered_events = sorted(events, key=lambda event: event.ts)
        if not ordered_events:
            raise ValueError("replay requires at least one event")

        first_ts = ordered_events[0].ts
        last_ts = ordered_events[-1].ts
        emitted_signals = list(self.runtime.on_init(first_ts))
        clock_ticks: list[datetime] = []
        next_tick = self._align_first_tick(first_ts)

        for event in ordered_events:
            while next_tick < event.ts:
                emitted_signals.extend(self.runtime.on_clock(next_tick))
                clock_ticks.append(next_tick)
                next_tick += self.time_step
            emitted_signals.extend(self.runtime.on_event(event))

        while next_tick <= last_ts:
            emitted_signals.extend(self.runtime.on_clock(next_tick))
            clock_ticks.append(next_tick)
            next_tick += self.time_step

        emitted_signals.extend(self.runtime.on_finish(last_ts))
        if self.artifact_writer is not None and self.manifest is not None:
            self.artifact_writer.write_bundle(
                self.manifest,
                signals=emitted_signals,
                strategy_log="",
                framework_log="",
            )
        return ReplayRunResult(
            processed_events=len(ordered_events),
            clock_ticks=clock_ticks,
            signals=emitted_signals,
        )

    def _align_first_tick(self, timestamp: datetime) -> datetime:
        epoch = datetime.fromtimestamp(0, tz=timestamp.tzinfo)
        elapsed = timestamp - epoch
        intervals = elapsed // self.time_step
        return epoch + (intervals + 1) * self.time_step
