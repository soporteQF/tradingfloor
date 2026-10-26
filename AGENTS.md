# AGENTS.md — NEXUS QUANT FLOOR

> Reglas locales del proyecto. Prioridad sobre `~/.config/opencode/AGENTS.md`.

---

## 1. CLASIFICACIÓN DEL PROYECTO

**Tipo:** Quant Research/Execution Platform — UI/DB/Endpoints/Auth/Deploy local  
**Stack:** Python/FastAPI + React/Three.js + DuckDB/KuzuDB/SQLite-vec + Ollama + Redis + Celery  
**Infra:** Laptop (Control Plane) + Oracle ARM Free Tier (Data Plane) — $0/mes  
**Objetivo:** Fábrica de alpha personalizada para futuros (NQ, ES, YM, GC) en cuentas fondeo (Lucid/Tradeify/MFF/Topstep)

---

## 2. REGLAS INQUEBRANTABLES

| Regla | Descripción |
|-------|-------------|
| **CERO SECRETOS EN CÓDIGO** | Todo en `.env` / variables de entorno. `.env.example` obligatorio. |
| **SOLO LAPTOP + ORACLE ARM** | Nada de cloud pagado. Hetzner solo como fallback documentado. |
| **PAPER TRADING 100% HASTA VALIDACIÓN** | Live solo tras: backtest riguroso + paper 20+ trades + approval Chief. |
| **BACKTEST RIGUROSO OBLIGATORIO** | Walk-forward + purged K-fold + Monte Carlo + fingerprint + OOS lock. Sin excepciones. |
| **KNOWLEDGE GRAPH = VERDAD ÚNICA** | Todo aprendizaje persiste en KuzuDB. Agentes consultan ANTES de actuar. |
| **8 AGENTES FUSIONADOS** | Discovery, Validation, Execution, Guardian, Regime, Alpha, Evolution, Chief. |
| **EVENT BUS = REDIS STREAMS** | No LangGraph channels. Event-driven, replayable, observable. |
| **CPU-ONLY** | `num_gpu_layers=0` en Ollama. TEI CPU para embeddings. Vectorbt/Numba para backtests. |
| **TIMEZONE AMERICA/NEW_YORK** | Todos los timestamps en ET. Market hours: 09:30-16:00 ET. |
| **PROP FIRM RULES = HARD GUARDS** | Daily loss, trailing DD, consistency, scaling plan — inquebrantables pre-trade. |

---

## 3. GATES DE CALIDAD (Definition of Done por fase)

| Fase | Gate | Criterio | Verificación |
|------|------|----------|--------------|
| **Sprint 0.1** | Infra up | `docker compose -f docker-compose.laptop.yml up -d` → todos healthy | `docker ps` + health checks |
| **Sprint 0.2** | Data layer | Datos 1m/15m/1h NQ,ES,YM,GC en DuckDB + Parquet | `SELECT count(*) FROM ticks_1m` |
| **Sprint 0.3** | 3D Floor MVP | 14 salas navegables, Chief chat, mini-mapa, reduced-motion | Navegación teclado + mouse, 30fps iGPU |
| **Sprint 0.4** | LangGraph skeleton | Chief → 3 Leads → Coordination Hub → resultado | Task delegada → completada → log en KG |
| **Sprint 0.5** | Discovery loop v0 | Pattern Mine → Hypothesis → Backtest → Pass/Fail | 1 hipótesis generada → validada → log |
| **Sprint 0.6** | Alpha Library | KuzuDB schema + write/read API + graph viz 3D | Error/insight escrito → visible en Alpha Library |
| **Sprint 0.7** | Daily Report | Chief genera reporte 18:00 ET → UI notification | Reporte diario en Chief UI |
| **Sprint 1** | Paper trading | Estrategia válida → paper shadow → A/B vs baseline | P&L stream + execution quality metrics |
| **Sprint 2** | Live readiness | Risk guards prop firm + drift detector + benchmark semanal | Benchmark: agent > baseline 20% |

---

## 4. BITÁCORA (project-kickoff.md)

```markdown
# Project Kickoff Log — NEXUS QUANT FLOOR

## 2026-10-25 — Inicio
- Clasificación declarada: Quant Research/Execution Platform
- Stack decision: Python/FastAPI + React/Three.js + DuckDB/KuzuDB/SQLite-vec + Ollama + Redis/Celery
- Infra: Laptop (Control Plane) + Oracle ARM Free Tier (Data Plane)
- Prop firms: Lucid (activa), Tradeify, MFF, Topstep — paper only
- Broker: Tradovate (via Lucid) + Rithmic (opcional L2)
- Symbols: NQ, ES, YM, GC + FX macro (EURUSD, DXY)
- Timezone: America/New_York
- Journal: híbrido (voz + texto estructurado)

## Gates completados
- [ ] Sprint 0.1 — Infra up
- [ ] Sprint 0.2 — Data layer
- [ ] Sprint 0.3 — 3D Floor MVP
- [ ] Sprint 0.4 — LangGraph skeleton
- [ ] Sprint 0.5 — Discovery loop v0
- [ ] Sprint 0.6 — Alpha Library
- [ ] Sprint 0.7 — Daily Report
- [ ] Sprint 1 — Paper trading
- [ ] Sprint 2 — Live readiness

## Decisiones clave (ADR)
- ADR-001: Control/Data plane split (Laptop + Oracle ARM)
- ADR-002: 8 agentes fusionados (no 12)
- ADR-003: Redis Streams event bus (no LangGraph channels)
- ADR-004: Kelly + HRP capital allocation
- ADR-005: CPU-only optimization (num_gpu_layers=0)
- ADR-006: Benchmark obligatorio semanal vs baselines
```

---

## 5. COMANDOS DE VERIFICACIÓN (verification-loop)

```bash
# Ejecutar ANTES de afirmar "hecho"
cd C:\Users\Asus\Desktop\proyecto\TradingFloor\nexus-quant-floor

# 1. Lint + typecheck
docker compose -f docker-compose.laptop.yml exec fastapi_app ruff check .
docker compose -f docker-compose.laptop.yml exec fastapi_app mypy .

# 2. Tests
docker compose -f docker-compose.laptop.yml exec fastapi_app pytest tests/ -v

# 3. Build frontend
cd frontend/threejs_floor && npm run build
cd ../chief_of_staff_ui && npm run build

# 4. Health checks
curl -f http://localhost:8000/health
curl -f http://localhost:3000/health

# 5. Verificación tabla
# Completar verification-loop.md con resultados
```

---

## 6. SKIP JUSTIFICADOS

| Ítem | Justificación |
|------|---------------|
| Multi-user / multi-account | Single-tenant v1. Fuera de alcance. |
| Options / crypto / equities cash | Solo futuros + FX correlaciones v1. |
| HFT / colocation / ultra-low latency | Free tier data feeds no lo permiten. |
| Compliance/regulatory reporting | Solo funding account rules (prop firms). |
| Mobile app nativo | Responsive web basta (3D floor + Chief UI). |
| GPU acceleration | Hardware no disponible (iGPU + ARM CPU). |
| Cloud managed services | $0/mes requirement. Self-hosted only. |

---

## 7. ESCALACIÓN

| Problema | Acción |
|----------|--------|
| Build/test fail | `engineering-build-error-resolver` — un error a la vez |
| Arquitectura duda | `engineering-software-architect` |
| Backend performance | `engineering-backend-architect` |
| DB optimization | `engineering-database-optimizer` |
| UX/3D issues | `design-ux-architect` |
| Behavioral/psychology | `trading-psychiatrist` |
| Security review | `security-appsec-engineer` |
| E2E critical flows | `testing-e2e-runner` |
| Code review final | `engineering-code-reviewer` |