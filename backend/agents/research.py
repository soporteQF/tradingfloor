"""RESEARCH — propone hipótesis estructuradas.

Deliberadamente NO usa un LLM para generar ideas: un 8b-q4 local produce
ruido genérico. Genera un espacio de hipótesis explícito con mecanismo
declarado, y usa el Knowledge Graph para no repetir lo que ya murió.

Eso es lo que hace que "aprenda": cada ronda evita fingerprints rechazados
y baja la confianza en los tipos de entrada que más fallan.
"""

from __future__ import annotations

import itertools
import random

from contracts import (
    EntryRule,
    ExitRule,
    Hypothesis,
    Regime,
    SizingRule,
    Symbol,
    Timeframe,
)

from .base import Agent

# Mecanismo declarado por tipo de entrada (no decoración: informa el gate)
ENTRY_MECHANISM = {
    "ema_cross": "momentum: la tendencia persiste tras el cruce de medias",
    "donchian_breakout": "momentum: la ruptura de rango atrae flujo en la dirección",
    "rsi_extreme": "mean-reversion: la extensión se revierte hacia la media",
    "zscore_mean_revert": "mean-reversion: desviación estadística vuelve a la media",
    "vwap_reclaim": "microestructura: recuperar VWAP señala control del comprador/vendedor",
}

# Régimen donde el mecanismo debería funcionar mejor
ENTRY_REGIMES: dict[str, list[Regime]] = {
    "ema_cross": ["trend_up", "trend_down"],
    "donchian_breakout": ["trend_up", "trend_down"],
    "rsi_extreme": ["range_low_vol", "range_high_vol"],
    "zscore_mean_revert": ["range_low_vol", "range_high_vol"],
    "vwap_reclaim": ["range_low_vol", "range_high_vol"],
}

DEFAULT_ENTRY_PARAMS: dict[str, list[dict]] = {
    "ema_cross": [{"fast": 9, "slow": 21}, {"fast": 20, "slow": 50}],
    "donchian_breakout": [{"lookback": 20}, {"lookback": 40}],
    "rsi_extreme": [{"period": 14, "oversold": 30, "overbought": 70}],
    "zscore_mean_revert": [{"period": 20, "threshold": 2.0}],
    "vwap_reclaim": [{"period": 20}],
}

EXITS: list[ExitRule] = [
    ExitRule(kind="fixed_r", params={"stop_atr": 2.0, "r_multiple": 2.0}),
    ExitRule(kind="atr_trailing", params={"stop_atr": 2.0, "atr_mult": 2.5}),
    ExitRule(kind="time_stop", params={"bars": 20}),
    ExitRule(kind="opposite_signal", params={}),
]

# Timeframes sensatos por símbolo (evita 1m con 30 días de datos = inútil)
SYMBOL_TIMEFRAMES: dict[str, list[Timeframe]] = {
    "NQ": ["1h", "15m"],
    "ES": ["1h", "15m"],
    "YM": ["1h", "15m"],
    "GC": ["1h", "1d"],
}


class ResearchAgent(Agent):
    name = "research"
    role = "Propone hipótesis testables con mecanismo declarado y evita repetir errores."

    def __init__(self, kg=None, seed: int = 7):
        super().__init__(kg=kg)
        self.rng = random.Random(seed)

    def propose(self, symbols: list[Symbol], timeframe: Timeframe | None = None,
                max_per_symbol: int = 20) -> list[Hypothesis]:
        rejected = self.kg.failed_fingerprints() if self.kg else set()
        failures = self.kg.failure_by_entry_kind() if self.kg else {}

        # Sizing por riesgo: 0.8% del capital por trade. Sin esto, 1 contrato
        # fijo de NQ arriesga 4-8% por trade y cualquier estrategia quiebra.
        sizing = SizingRule(kind="atr_risk", params={"risk_usd": 400.0, "atr_period": 14})

        # Mapeo símbolo → contrato real que se usa para P&L (micros para cuentas pequeñas)
        CONTRACT_MAP: dict[str, str] = {
            "NQ": "MNQ", "ES": "MES", "YM": "MYM", "GC": "MGC",
        }

        out: list[Hypothesis] = []
        for symbol in symbols:
            tfs = [timeframe] if timeframe else SYMBOL_TIMEFRAMES.get(symbol, ["1h"])
            tfs = [t for t in tfs if t in SYMBOL_TIMEFRAMES.get(symbol, tfs)] or tfs

            candidates: list[Hypothesis] = []
            for tf in tfs:
                for entry_kind, param_sets in DEFAULT_ENTRY_PARAMS.items():
                    for params in param_sets:
                        for exit_rule in EXITS:
                            entry = EntryRule(kind=entry_kind, params=params)
                            hyp = Hypothesis(
                                symbol=symbol,
                                contract=CONTRACT_MAP.get(symbol),
                                timeframe=tf,
                                direction="both",
                                entry=entry,
                                exit=exit_rule,
                                sizing=sizing.model_copy(deep=True),
                                regime_gate=ENTRY_REGIMES.get(entry_kind, []),
                                rationale=(
                                    f"{symbol} {tf} · {entry_kind}: "
                                    f"{ENTRY_MECHANISM.get(entry_kind, 'mecanismo no declarado')}. "
                                    f"Salida {exit_rule.kind}. "
                                    f"Régimen esperado: {', '.join(ENTRY_REGIMES.get(entry_kind, ['any']))}. "
                                    f"Contrato P&L: {CONTRACT_MAP.get(symbol, symbol)}."
                                ),
                            )
                            candidates.append(hyp)

            # Prior: penaliza tipos de entrada con historial de fallo
            max_fail = max(failures.values(), default=1)
            for h in candidates:
                fails = failures.get(h.entry.kind, 0)
                h.prior_confidence = round(max(0.05, 0.6 - 0.4 * (fails / max_fail)), 3)

            # Descarta lo ya rechazado y ordena por prior
            fresh = [h for h in candidates if h.fingerprint_key() not in rejected]
            fresh.sort(key=lambda h: h.prior_confidence, reverse=True)

            chosen = fresh[:max_per_symbol] if fresh else []
            out.extend(chosen)

        self.log(
            "propuestas=%d (descartadas por KG=%d, tipos con fallo=%s)",
            len(out), sum(len(v) for v in []), dict(sorted(failures.items())),
        )
        self._remember({"proposed": len(out), "symbols": symbols})
        return out
