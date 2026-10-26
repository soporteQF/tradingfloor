"""Contratos compartidos del NEXUS QUANT FLOOR.

Estos modelos son el idioma común entre agentes. Todo agente que propone,
valida o registra algo usa ESTOS schemas. Sin ellos, los agentes no pueden
hacer handoff y el debate es teatro.

Versionado: si cambias un campo, sube CONTRACTS_VERSION.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

CONTRACTS_VERSION = "1.0.0"

# ─────────────────────────────────────────────────────────────
# Enums / aliases
# ─────────────────────────────────────────────────────────────

Symbol = Literal["NQ", "ES", "YM", "GC"]
Timeframe = Literal["1m", "5m", "15m", "1h", "1d"]

Regime = Literal["trend_up", "trend_down", "range_low_vol", "range_high_vol"]

Direction = Literal["long", "short", "both"]


class StrategyStatus(str, Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    REJECTED = "rejected"
    PAPER = "paper"
    LIVE = "live"
    RETIRED = "retired"


# ─────────────────────────────────────────────────────────────
# Barra OHLCV
# ─────────────────────────────────────────────────────────────


class Bar(BaseModel):
    symbol: Symbol
    timeframe: Timeframe
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


# ─────────────────────────────────────────────────────────────
# Reglas de estrategia (el DSL mínimo)
# ─────────────────────────────────────────────────────────────


class EntryRule(BaseModel):
    kind: Literal[
        "ema_cross",
        "donchian_breakout",
        "rsi_extreme",
        "zscore_mean_revert",
        "vwap_reclaim",
    ]
    params: dict[str, float] = Field(default_factory=dict)


class ExitRule(BaseModel):
    kind: Literal["atr_trailing", "fixed_r", "time_stop", "opposite_signal"]
    params: dict[str, float] = Field(default_factory=dict)


class SizingRule(BaseModel):
    kind: Literal["fixed_contracts", "vol_target", "atr_risk"]
    params: dict[str, float] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# Hipótesis
# ─────────────────────────────────────────────────────────────


class Hypothesis(BaseModel):
    """Lo que Research entrega y Validation consume."""

    id: str = Field(default_factory=lambda: f"hyp_{uuid4().hex[:12]}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_agent: str = "research"

    symbol: Symbol
    timeframe: Timeframe
    direction: Direction = "both"

    # Contrato usado para el P&L. Permite operar el mismo subyacente con
    # micros (MNQ) cuando la cuenta no soporta el full-size (NQ).
    contract: str | None = None

    entry: EntryRule
    exit: ExitRule
    sizing: SizingRule = Field(default_factory=lambda: SizingRule(kind="fixed_contracts", params={"contracts": 1}))

    regime_gate: list[Regime] = Field(default_factory=list)
    rationale: str = ""

    # Estimación declarada por el agente que propone (no es resultado)
    prior_confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    def fingerprint_key(self) -> str:
        """Identidad estructural de la hipótesis (sin id ni timestamps)."""
        return "|".join(
            [
                self.symbol,
                self.contract or self.symbol,
                self.timeframe,
                self.direction,
                self.entry.kind,
                ",".join(f"{k}={v}" for k, v in sorted(self.entry.params.items())),
                self.exit.kind,
                ",".join(f"{k}={v}" for k, v in sorted(self.exit.params.items())),
                self.sizing.kind,
                ",".join(f"{k}={v}" for k, v in sorted(self.sizing.params.items())),
                ",".join(sorted(self.regime_gate)),
            ]
        )


# ─────────────────────────────────────────────────────────────
# Resultado de validación (el veredicto del árbitro)
# ─────────────────────────────────────────────────────────────


class ValidationCheck(BaseModel):
    name: str
    passed: bool
    value: float | str
    threshold: float | str
    detail: str = ""


class ValidationMetrics(BaseModel):
    trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    max_drawdown: float = 0.0
    total_return: float = 0.0
    avg_trade: float = 0.0
    exposure: float = 0.0
    net_sharpe: float = 0.0


class ValidationResult(BaseModel):
    hypothesis_id: str
    symbol: Symbol
    passed: bool
    metrics: ValidationMetrics
    checks: list[ValidationCheck] = Field(default_factory=list)
    param_bounds: dict[str, tuple[float, float]] = Field(default_factory=dict)
    fingerprint: str = ""
    failure_reasons: list[str] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage: Literal["walkforward", "oob", "paper"] = "walkforward"


# ─────────────────────────────────────────────────────────────
# Estrategia (DNA)
# ─────────────────────────────────────────────────────────────


class StrategyDNA(BaseModel):
    id: str = Field(default_factory=lambda: f"dna_{uuid4().hex[:12]}")
    hypothesis_id: str
    version: str = "0.1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    symbol: Symbol
    contract: str | None = None      # Contrato para P&L (p.ej. "MNQ" vs "NQ")
    timeframe: Timeframe
    entry: EntryRule
    exit: ExitRule
    sizing: SizingRule
    regime_gates: list[Regime] = Field(default_factory=list)

    performance: ValidationMetrics = Field(default_factory=ValidationMetrics)
    fingerprint: str = ""
    status: StrategyStatus = StrategyStatus.PROPOSED


# ─────────────────────────────────────────────────────────────
# Nodos de conocimiento
# ─────────────────────────────────────────────────────────────


class ErrorKind(str, Enum):
    OVERFIT = "overfit"
    NO_EDGE = "no_edge"
    PARAM_UNSTABLE = "param_unstable"
    REGIME_MISMATCH = "regime_mismatch"
    EXECUTION_DECAY = "execution_decay"
    RISK_BREACH = "risk_breach"
    BEHAVIORAL = "behavioral"
    DATA_QUALITY = "data_quality"
    UNKNOWN = "unknown"


class ErrorNode(BaseModel):
    id: str = Field(default_factory=lambda: f"err_{uuid4().hex[:12]}")
    kind: ErrorKind
    strategy_id: str | None = None
    symbol: Symbol | None = None
    regime: Regime | None = None
    root_cause: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InsightNode(BaseModel):
    id: str = Field(default_factory=lambda: f"ins_{uuid4().hex[:12]}")
    kind: str
    description: str
    regime: Regime | None = None
    symbol: Symbol | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_agent: str = "unknown"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────
# Reporte diario
# ─────────────────────────────────────────────────────────────


class HypothesisOutcome(BaseModel):
    hypothesis_id: str
    symbol: Symbol
    entry_kind: str
    exit_kind: str
    passed: bool
    sharpe: float
    max_drawdown: float
    trades: int
    reasons: list[str] = Field(default_factory=list)


class DailyReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cycle_id: str
    proposals: int = 0
    validated: int = 0
    rejected: int = 0
    winners: list[str] = Field(default_factory=list)
    outcomes: list[HypothesisOutcome] = Field(default_factory=list)
    errors_logged: int = 0
    insights_logged: int = 0
    data_quality_ok: bool = True
    notes: list[str] = Field(default_factory=list)
