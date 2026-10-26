"""Tests del Alpha Librarian."""

from __future__ import annotations

import pytest
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.alpha import (
    AlphaLibrarian, AlphaQuery, AlphaResult, QueryType,
    PlaybookEntry, CausalPath, DriftReport, RegimeStats,
    create_alpha_librarian, query_playbook, query_causal, query_drift, query_regime_stats,
)
from knowledge_graph.client import KnowledgeGraph
from contracts import (
    StrategyDNA, ErrorNode, InsightNode, EntryRule, ExitRule,
    SizingRule, ValidationMetrics, StrategyStatus, Hypothesis, ValidationResult
)
import uuid


@pytest.fixture
def kg_with_data(tmp_path):
    """KG poblado con datos de prueba."""
    db_path = str(tmp_path / "test_alpha_kuzu.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    kg = KnowledgeGraph(db_path)
    # _init_schema se llama en __init__

    # StrategyDNA válida
    s1 = StrategyDNA(
        id=str(uuid.uuid4()),
        hypothesis_id="h1",
        symbol="NQ",
        timeframe="5m",
        entry=EntryRule(kind="ema_cross", params={"ema_fast": 9, "ema_slow": 21}),
        exit=ExitRule(kind="atr_trailing", params={"atr_mult": 2.0}),
        sizing=SizingRule(kind="fixed_contracts", params={"contracts": 1}),
        regime_gates=["trend_up"],
        performance=ValidationMetrics(sharpe=1.8, max_drawdown=0.12, trades=150),
        fingerprint="ema_cross|atr_trailing|NQ|5m|trend_up",
        status=StrategyStatus.VALIDATED,
    )
    kg.write_strategy(s1)

    # StrategyDNA en range_low_vol (diferente entry/exit)
    s2 = StrategyDNA(
        id=str(uuid.uuid4()),
        hypothesis_id="h2",
        symbol="NQ",
        timeframe="15m",
        entry=EntryRule(kind="rsi_extreme", params={"rsi_period": 14, "rsi_low": 30}),
        exit=ExitRule(kind="opposite_signal", params={}),
        sizing=SizingRule(kind="fixed_contracts", params={"contracts": 1}),
        regime_gates=["range_low_vol"],
        performance=ValidationMetrics(sharpe=1.4, max_drawdown=0.08, trades=200),
        fingerprint="rsi_extreme|opposite_signal|NQ|15m|range_low_vol",
        status=StrategyStatus.VALIDATED,
    )
    kg.write_strategy(s2)

    # StrategyDNA ES
    s3 = StrategyDNA(
        id=str(uuid.uuid4()),
        hypothesis_id="h3",
        symbol="ES",
        timeframe="5m",
        entry=EntryRule(kind="ema_cross", params={"ema_fast": 9, "ema_slow": 21}),
        exit=ExitRule(kind="atr_trailing", params={"atr_mult": 2.0}),
        sizing=SizingRule(kind="fixed_contracts", params={"contracts": 1}),
        regime_gates=["trend_up"],
        performance=ValidationMetrics(sharpe=1.2, max_drawdown=0.18, trades=100),
        fingerprint="ema_cross|atr_trailing|ES|5m|trend_up",
        status=StrategyStatus.VALIDATED,
    )
    kg.write_strategy(s3)

    # ErrorNode
    e1 = ErrorNode(
        kind="overfit",
        root_cause="Strategy overfit to in-sample: Sharpe 3.0 IS vs -0.5 OOS",
        symbol="NQ",
        regime="trend_up",
        strategy_id=s1.id,
        evidence={"entry_kind": "ema_cross", "exit_kind": "atr_trailing"},
        confidence=0.9,
        source_agent="validation",
    )
    kg.write_error(e1)

    # InsightNode que previno el error
    i1 = InsightNode(
        kind="param_stability",
        description="Use walk-forward with purged K-fold; penalize param sensitivity",
        symbol="NQ",
        timeframe="5m",
        confidence=0.85,
        source_agent="validation",
        error_id=e1.id,
    )
    kg.write_insight(i1)

    # Link error to insight
    kg.link_error_insight(e1.id, i1.id)

    # Insight standalone
    i2 = InsightNode(
        kind="regime_filter",
        description="EMA trend only works in trend_up/trend_down; fails in range",
        symbol="NQ",
        timeframe="5m",
        confidence=0.9,
        source_agent="research",
    )
    kg.write_insight(i2)

    # Add HypothesisRecord data for regime stats
    hyp1 = Hypothesis(
        id="h1",
        symbol="NQ",
        timeframe="5m",
        entry=EntryRule(kind="ema_cross", params={"ema_fast": 9, "ema_slow": 21}),
        exit=ExitRule(kind="atr_trailing", params={"atr_mult": 2.0}),
    )
    res1 = ValidationResult(
        hypothesis_id="h1",
        symbol="NQ",
        passed=True,
        metrics=ValidationMetrics(sharpe=1.8, max_drawdown=0.12, trades=150),
        fingerprint="ema_cross|atr_trailing|NQ|5m|trend_up",
    )
    kg.record_hypothesis(hyp1, res1)

    hyp2 = Hypothesis(
        id="h2",
        symbol="NQ",
        timeframe="15m",
        entry=EntryRule(kind="rsi_extreme", params={"rsi_period": 14, "rsi_low": 30}),
        exit=ExitRule(kind="opposite_signal", params={}),
    )
    res2 = ValidationResult(
        hypothesis_id="h2",
        symbol="NQ",
        passed=True,
        metrics=ValidationMetrics(sharpe=1.4, max_drawdown=0.08, trades=200),
        fingerprint="rsi_extreme|opposite_signal|NQ|15m|range_low_vol",
    )
    kg.record_hypothesis(hyp2, res2)

    hyp3 = Hypothesis(
        id="h3",
        symbol="ES",
        timeframe="5m",
        entry=EntryRule(kind="ema_cross", params={"ema_fast": 9, "ema_slow": 21}),
        exit=ExitRule(kind="atr_trailing", params={"atr_mult": 2.0}),
    )
    res3 = ValidationResult(
        hypothesis_id="h3",
        symbol="ES",
        passed=False,
        metrics=ValidationMetrics(sharpe=-0.5, max_drawdown=0.5, trades=50),
        fingerprint="ema_cross|atr_trailing|ES|5m|trend_up",
    )
    kg.record_hypothesis(hyp3, res3)

    yield kg

    kg.close()


def test_alpha_librarian_creation():
    kg = KnowledgeGraph("./data/knowledge_graph/test_create.db")
    agent = AlphaLibrarian(kg=kg)
    assert agent.name == "alpha"
    kg.close()
    shutil.rmtree("./data/knowledge_graph/test_create.db", ignore_errors=True)


def test_query_playbook(kg_with_data):
    agent = AlphaLibrarian(kg=kg_with_data)

    # Playbook NQ 5m
    res = agent.query(AlphaQuery(
        query_type=QueryType.PLAYBOOK,
        symbol="NQ",
        timeframe="5m",
    ))
    assert len(res.playbook) == 1
    assert res.playbook[0].entry_kind == "ema_cross"
    assert res.playbook[0].exit_kind == "atr_trailing"
    assert res.playbook[0].sharpe == 1.8

    # Playbook NQ 15m
    res = agent.query(AlphaQuery(
        query_type=QueryType.PLAYBOOK,
        symbol="NQ",
        timeframe="15m",
    ))
    assert len(res.playbook) == 1
    assert res.playbook[0].entry_kind == "rsi_extreme"
    assert res.playbook[0].exit_kind == "opposite_signal"

    # Playbook sin filtro timeframe (debe traer ambas NQ)
    res = agent.query(AlphaQuery(
        query_type=QueryType.PLAYBOOK,
        symbol="NQ",
    ))
    assert len(res.playbook) == 2


def test_query_causal_path(kg_with_data):
    agent = AlphaLibrarian(kg=kg_with_data)

    res = agent.query(AlphaQuery(
        query_type=QueryType.CAUSAL_PATH,
        symbol="NQ",
    ))
    assert len(res.causal_paths) >= 1
    # Debe haber path con insight preventivo
    prevented = [p for p in res.causal_paths if p.prevented]
    assert len(prevented) >= 1
    assert prevented[0].error_kind == "overfit"
    assert prevented[0].insight_kind == "param_stability"


def test_query_drift_report(kg_with_data):
    agent = AlphaLibrarian(kg=kg_with_data)

    # Drift report no implementado aún (params no en KG)
    res = agent.query(AlphaQuery(
        query_type=QueryType.DRIFT_REPORT,
        strategy_id="any",
    ))
    assert len(res.drift_reports) == 0
    assert "params no almacenados" in res.summary


def test_query_regime_stats(kg_with_data):
    agent = AlphaLibrarian(kg=kg_with_data)

    res = agent.query(AlphaQuery(
        query_type=QueryType.REGIME_STATS,
        symbol="NQ",
    ))
    assert len(res.regime_stats) == 2  # ema_cross+atr_trailing y rsi_extreme+opposite_signal
    combos = {(s.entry_kind, s.exit_kind) for s in res.regime_stats}
    assert ("ema_cross", "atr_trailing") in combos
    assert ("rsi_extreme", "opposite_signal") in combos


def test_query_strategy_performance(kg_with_data):
    agent = AlphaLibrarian(kg=kg_with_data)

    res = agent.query(AlphaQuery(
        query_type=QueryType.STRATEGY_PERFORMANCE,
        symbol="NQ",
    ))
    assert len(res.strategy_performance) == 2
    assert res.strategy_performance[0]["sharpe"] >= res.strategy_performance[1]["sharpe"]


def test_query_error_analysis(kg_with_data):
    agent = AlphaLibrarian(kg=kg_with_data)

    res = agent.query(AlphaQuery(
        query_type=QueryType.ERROR_ANALYSIS,
        symbol="NQ",
        lookback_days=30,
    ))
    assert len(res.error_analysis) >= 1
    assert res.error_analysis[0]["kind"] == "overfit"


def test_query_insight_lookup(kg_with_data):
    agent = AlphaLibrarian(kg=kg_with_data)

    res = agent.query(AlphaQuery(
        query_type=QueryType.INSIGHT_LOOKUP,
        symbol="NQ",
    ))
    assert len(res.insights) >= 2
    kinds = [i["kind"] for i in res.insights]
    assert "param_stability" in kinds
    assert "regime_filter" in kinds


def test_factory_helpers(kg_with_data):
    """Test one-liner helpers."""
    res = query_playbook(kg_with_data, symbol="NQ", timeframe="5m")
    assert len(res.playbook) == 1

    res = query_causal(kg_with_data, symbol="NQ")
    assert len(res.causal_paths) >= 1

    # Drift
    res = query_drift(kg_with_data, "any")
    assert len(res.drift_reports) == 0

    res = query_regime_stats(kg_with_data, symbol="NQ")
    assert len(res.regime_stats) == 2


def test_summary_generation(kg_with_data):
    agent = AlphaLibrarian(kg=kg_with_data)

    res = agent.query(AlphaQuery(query_type=QueryType.PLAYBOOK, symbol="NQ"))
    assert "Playbook:" in res.summary
    assert "ema_cross+atr_trailing" in res.summary

    res = agent.query(AlphaQuery(query_type=QueryType.CAUSAL_PATH, symbol="NQ"))
    assert "Rutas causales:" in res.summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])