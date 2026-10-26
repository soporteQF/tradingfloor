// ═══════════════════════════════════════════════════════════
// NEXUS QUANT FLOOR — KuzuDB schema (memoria colectiva)
// ═══════════════════════════════════════════════════════════
//
// Nodos: Error, Insight, Strategy, HypothesisRecord
// Edges: CAUSES, DERIVED_FROM, VALIDATED_BY
//
// Regla: los agentes consultan ANTES de actuar. Si una hipótesis
// comparte fingerprint con un Error de tipo overfit/no_edge, no se
// vuelve a proponer.

CREATE NODE TABLE IF NOT EXISTS Error(
    id           STRING,
    kind         STRING,
    strategy_id  STRING,
    symbol       STRING,
    regime       STRING,
    root_cause   STRING,
    evidence     STRING,
    created_at   STRING,
    PRIMARY KEY (id)
);

CREATE NODE TABLE IF NOT EXISTS Insight(
    id           STRING,
    kind         STRING,
    note         STRING,
    regime       STRING,
    symbol       STRING,
    confidence   DOUBLE,
    source_agent STRING,
    created_at   STRING,
    PRIMARY KEY (id)
);

CREATE NODE TABLE IF NOT EXISTS Strategy(
    id           STRING,
    hypothesis_id STRING,
    symbol       STRING,
    timeframe    STRING,
    entry_kind   STRING,
    exit_kind    STRING,
    fingerprint  STRING,
    status       STRING,
    sharpe       DOUBLE,
    max_drawdown DOUBLE,
    trades       INT64,
    created_at   STRING,
    PRIMARY KEY (id)
);

// Registro de toda hipótesis evaluada (viva o muerta) para no repetirla.
CREATE NODE TABLE IF NOT EXISTS HypothesisRecord(
    id           STRING,
    fingerprint  STRING,
    symbol       STRING,
    timeframe    STRING,
    entry_kind   STRING,
    exit_kind    STRING,
    passed       BOOLEAN,
    sharpe       DOUBLE,
    created_at   STRING,
    PRIMARY KEY (id)
);

CREATE REL TABLE IF NOT EXISTS CAUSES(
    FROM Error TO Insight,
    kind STRING,
    created_at STRING
);

CREATE REL TABLE IF NOT EXISTS DERIVED_FROM(
    FROM Strategy TO HypothesisRecord,
    created_at STRING
);

CREATE REL TABLE IF NOT EXISTS VALIDATED_BY(
    FROM HypothesisRecord TO Insight,
    created_at STRING
);

// Índices para lookups en tiempo real
CREATE INDEX IF NOT EXISTS idx_error_kind ON Error(kind);
CREATE INDEX IF NOT EXISTS idx_error_symbol ON Error(symbol);
CREATE INDEX IF NOT EXISTS idx_insight_symbol ON Insight(symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_status ON Strategy(status);
CREATE INDEX IF NOT EXISTS idx_hyp_fingerprint ON HypothesisRecord(fingerprint);
