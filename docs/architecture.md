# ADR-001: Stack Decision — NEXUS QUANT FLOOR

**Fecha:** 2026-10-25  
**Estado:** Aceptado  
**Decisores:** Usuario único (single-tenant)

---

## Contexto

Plataforma cuantitativa personal para futuros (NQ, ES, YM, GC) en cuentas fondeo (Lucid, Tradeify, MFF, Topstep). Requisitos:
- 100% local/self-hosted, $0/mes infra
- Laptop 16GB RAM, GPU integrada (iGPU)
- Paper trading 100% hasta validación robusta
- 3D trading floor (14 salas) + agentes autónomos
- Backtesting riguroso, knowledge graph, behavioral alpha
- Timezone: America/New_York

---

## Decisión

### Arquitectura: Control Plane / Data Plane Split

| Plano | Hardware | Componentes | RAM estimada |
|-------|----------|-------------|--------------|
| **Control Plane** | Laptop (Windows/WSL2) | 3D Floor, Chief of Staff UI, JupyterLab, FastAPI Gateway, Redis, SQLite-vec, Ollama 8b-q4 | ~6 GB |
| **Data Plane** | Oracle Cloud Free Tier (ARM Ampere, 24GB, 200GB NVMe) | Celery Workers, DuckDB, KuzuDB, Ollama 70b (batch), vectorbt, Data Ingestion 24/7, Evolution Engine | ~16 GB |

**Comunicación:** Tailscale VPN + Redis Streams (event bus) + HTTP/gRPC

---

### Stack Tecnológico Locked

| Capa | Tecnología | Versión | Justificación |
|------|------------|---------|---------------|
| **Language** | Python | 3.11+ | Ecosistema quant maduro, type hints |
| **API Framework** | FastAPI | 0.109+ | Async, OpenAPI, performance |
| **Orchestration** | LangGraph | 0.2+ | Stateful agents, checkpointing, human-in-loop |
| **Event Bus** | Redis Streams | 7.2+ | Persistente, replayable, consumer groups |
| **Task Queue** | Celery | 5.3+ | Distributed workers, beat scheduler |
| **Cache/State** | Redis | 7.2+ | Streams, pub/sub, session |
| **Analytics DB** | DuckDB | 1.1+ | Columnar, embedded, vectorized, Parquet native |
| **Knowledge Graph** | KuzuDB | 0.8+ | Embedded graph, Cypher, ACID, mmap |
| **Vector Search** | SQLite-vec | 0.1.6+ | HNSW, embedded, zero-config |
| **Metadata DB** | SQLite | 3.45+ | Config, audit, lightweight |
| **Local LLMs** | Ollama | 0.3+ | llama3.1:8b-q4 (daily), 70b-q4 (batch), qwen2.5-coder, bge-small |
| **Embeddings Server** | TEI (text-embeddings-inference) | 1.5+ | CPU-optimized, batched, fast |
| **Backtesting** | vectorbt + NAUTILUS | latest | Institutional, vectorized, walk-forward |
| **ML/Stats** | scikit-learn, hmmlearn, river, DEAP, Optuna | latest | Pattern mining, regime, evolution, optimization |
| **Microstructure** | Rust (tokio) | 1.78+ | High-freq L2 parsing, gRPC |
| **3D Frontend** | React Three Fiber + Drei + GSAP | latest | React-native 3D, animation, physics |
| **UI Framework** | React 18 + TypeScript + Tailwind + shadcn/ui | latest | Professional, accessible, dark mode |
| **Charts** | AG Charts / Recharts | latest | Financial charts, real-time |
| **Containerization** | Docker Compose | v2.24+ | Local orchestration, multi-arch |
| **VPN** | Tailscale | latest | Mesh VPN, NAT traversal, free personal |
| **CI/CD** | GitHub Actions | free tier | Nocturnal benchmarks, lint, test |

---

### Modelos Ollama (CPU-only, quantized)

| Modelo | Quant | RAM | Uso | Config |
|--------|-------|-----|-----|--------|
| `llama3.1:8b-instruct-q4_K_M` | Q4_K_M | 4.7 GB | Daily driver (hypothesis, root cause, report, behavioral) | `num_threads=4`, `batch=512`, `ctx=8192` |
| `llama3.1:70b-instruct-q4_K_M` | Q4_K_M | 38 GB | **Solo Oracle**: weekly deep dive, complex synthesis | `num_threads=8`, `batch=256`, `ctx=4096` |
| `qwen2.5-coder:7b-instruct-q4_K_M` | Q4_K_M | 4.2 GB | Code gen: DSL→Python, mutations, scaffolding | `num_threads=4`, `batch=512`, `ctx=32768` |
| `bge-small-en-v1.5` | FP32 | 0.13 GB | Embeddings (384-dim) — via TEI | batch=64, float32 |

---

### Data Sources (Todos Gratis/Free-Tier)

| Fuente | Tipo | Acceso | Símbolos | Frecuencia |
|--------|------|--------|----------|------------|
| **CME Datamine** | Historical | HTTP/S3 (gratis registro) | NQ, ES, YM, GC | 1m, 15m, 1h — backfill |
| **Tradovate** | Live Paper | WebSocket/REST (demo gratis) | Futuros CME | Tick, 1s, 1m — primary |
| **Rithmic** | Live Paper | WebSocket (demo gratis) | Futuros CME | L2, tick — microstructure |
| **IBKR** | Live Paper | WebSocket/REST (demo gratis) | Futuros + FX | Fallback |
| **FRED** | Macro | REST (gratis API key) | Yields, CPI, FED, etc. | Daily |
| **COT** | Macro | CFTC (gratis) | Posiciones grandes | Weekly |
| **OANDA** | FX | REST/WS (demo gratis) | EURUSD, DXY, majors | 1m — correlaciones |

---

### Alternativas Descartadas

| Alternativa | Por qué NO |
|-------------|------------|
| **Solo Laptop** | RAM/CPU insuficiente para backtests paralelos, 24/7 ingestion, 70B, microstructure |
| **Hetzner CX42 (€16/mes)** | Oracle Free Tier da 24GB RAM + 200GB NVMe + 4 ARM cores = **gratis para siempre** |
| **AWS/GCP/Azure Free Tier** | 12 meses only, 1 GB RAM (t2.micro), no 24/7 garantizado |
| **LangGraph Channels** | Overhead innecesario; sistema es event-driven paralelo, no workflow lineal |
| **12 agentes separados** | Fusionados a 8: menos handoffs, menos tokens, mismo coverage |
| **GPU/CUDA** | Hardware no disponible (iGPU laptop, ARM sin GPU en Oracle) |
| **TimescaleDB / InfluxDB** | Overhead; DuckDB + Parquet + KuzuDB cubren analytics + graph + vector |
| **Neo4j** | Requiere server separado; KuzuDB es embedded, ACID, Cypher-compatible |
| **Weaviate / Qdrant / Pinecone** | Overhead; SQLite-vec es embedded, HNSW, zero-config, suficiente para <1M vecs |

---

### Consecuencias

**Positivas:**
- $0/mes infra perpetuo
- 24GB RAM dedicados para workloads pesados
- Separación clara: UI estable en laptop, compute escalable en cloud
- Stack 100% open source, sin vendor lock-in
- ARM64 nativo en Oracle (Ollama, DuckDB, KuzuDB, TEI, Rust tienen wheels/binarios ARM)

**Negativas:**
- Dependencia de Oracle Free Tier (riesgo: aprobación cuenta, cancelación futuro)
- Latencia laptop↔Oracle ~20-120ms (mitigado: async, batch, local cache)
- ARM64 edge cases raros (mitigado: multi-arch images, compilación nativa)
- Complejidad operativa: 2 entornos, Tailscale, sync de datos

**Mitigación:** Fallback documentado a Hetzner CX42 (€16/mes, x86, 5 min migración con mismo docker-compose).

---

## Referencias

- `docker-compose.laptop.yml` — Control plane
- `docker-compose.oracle.yml` — Data plane (ARM64)
- `docker-compose.hetzner.yml` — Fallback x86
- `setup_laptop.sh` / `setup_oracle.sh` / `migrate_to_oracle.sh`
- `AGENTS.md` — Reglas, gates, bitácora