#!/usr/bin/env bash
# setup_laptop.sh — Bootstrap NEXUS QUANT FLOOR on Laptop (Windows/WSL2)
# Ejecutar desde: C:\Users\Asus\Desktop\proyecto\TradingFloor\nexus-quant-floor

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  NEXUS QUANT FLOOR — Laptop Setup (Control Plane)           ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# ─── Colors ───
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log() { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $*"; }
ok() { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err() { echo -e "${RED}✗${NC} $*"; }

# ─── Pre-flight checks ───
check_wsl2() {
    if [[ ! -f /proc/version ]] || ! grep -qi microsoft /proc/version; then
        warn "No se detecta WSL2. Se asume Docker Desktop en Windows."
        return 1
    fi
    ok "WSL2 detectado"
    return 0
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        err "Docker no instalado. Instala Docker Desktop (Windows) + WSL2 backend."
        return 1
    fi
    if ! docker compose version &> /dev/null; then
        err "Docker Compose v2 no disponible."
        return 1
    fi
    ok "Docker $(docker --version) + Compose $(docker compose version)"
    return 0
}

check_ram() {
    local total_ram_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local total_ram_gb=$((total_ram_kb / 1024 / 1024))
    if [[ $total_ram_gb -lt 15 ]]; then
        warn "RAM detectada: ${total_ram_gb}GB (recomendado 16GB+). Ajusta memory_limits en docker-compose."
    else
        ok "RAM: ${total_ram_gb}GB"
    fi
}

# ─── Main setup ───
main() {
    log "Iniciando setup en: $PROJECT_ROOT"
    cd "$PROJECT_ROOT"

    # 1. Checks
    check_wsl2 || true
    check_docker || exit 1
    check_ram

    # 2. .env from example
    if [[ ! -f .env ]]; then
        if [[ -f .env.example ]]; then
            cp .env.example .env
            ok ".env creado desde .env.example — EDITA TUS CLAVES"
        else
            warn ".env.example no encontrado, creando .env vacío"
            touch .env
        fi
    else
        ok ".env ya existe"
    fi

    # 3. Data directories
    mkdir -p data/raw/cme_datamine/{NQ,ES,YM,GC}/{1m,15m,1h}
    mkdir -p data/processed
    mkdir -p data/knowledge_graph
    ok "Directorios de datos creados"

    # 4. Pull base images (laptop profile)
    log "Descargando imágenes base (laptop)..."
    docker compose -f docker-compose.laptop.yml pull redis ollama embeddings 2>/dev/null || true
    ok "Imágenes base descargadas"

    # 5. Build custom images
    log "Construyendo imágenes custom..."
    docker compose -f docker-compose.laptop.yml build --parallel fastapi_app threejs_floor chief_ui 2>/dev/null || true
    ok "Imágenes custom construidas"

    # 6. Start core services
    log "Levantando servicios core (redis, ollama, embeddings)..."
    docker compose -f docker-compose.laptop.yml up -d redis ollama embeddings
    
    # Wait for health
    log "Esperando health checks..."
    sleep 10
    docker compose -f docker-compose.laptop.yml ps

    # 7. Pull Ollama models (8b only for laptop)
    log "Descargando modelos Ollama (8b-q4)..."
    docker compose -f docker-compose.laptop.yml --profile setup up ollama-pull
    ok "Modelos descargados"

    # 8. Start all laptop services
    log "Levantando todos los servicios laptop..."
    docker compose -f docker-compose.laptop.yml up -d fastapi_app threejs_floor chief_ui
    
    # 9. Optional: Jupyter
    read -p "¿Levantar JupyterLab para research? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker compose -f docker-compose.laptop.yml --profile research up -d jupyter
        ok "JupyterLab en http://localhost:8888"
    fi

    # 10. Optional: Tailscale
    if grep -q "TAILSCALE_AUTHKEY=" .env 2>/dev/null && [[ -n $(grep "TAILSCALE_AUTHKEY=" .env | cut -d'=' -f2) ]]; then
        log "Conectando Tailscale..."
        docker compose -f docker-compose.laptop.yml --profile vpn up -d tailscale
        ok "Tailscale conectado"
    else
        warn "TAILSCALE_AUTHKEY no configurado en .env — VPN no activada"
    fi

    # 11. Summary
    echo
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  SETUP COMPLETADO — ENDPOINTS                               ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  FastAPI (Chief + API):     http://localhost:8000           ║"
    echo "║  Chief of Staff WS:         ws://localhost:8001             ║"
    echo "║  3D Trading Floor:          http://localhost:3000           ║"
    echo "║  Chief of Staff UI:         http://localhost:3001           ║"
    echo "║  Ollama API:                http://localhost:11434          ║"
    echo "║  Embeddings (TEI):          http://localhost:8080           ║"
    echo "║  Redis:                     localhost:6379                  ║"
    echo "║  JupyterLab (opcional):     http://localhost:8888           ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo
    echo "Próximos pasos:"
    echo "  1. Edita .env con tus claves (TRADOVATE, RITHMIC, FRED, OANDA, TAILSCALE)"
    echo "  2. Abre http://localhost:3000 — 3D Floor"
    echo "  3. Abre http://localhost:3001 — Chief of Staff UI"
    echo "  4. Ejecuta: ./scripts/setup_oracle.sh (en Oracle VPS) cuando tengas cuenta"
}

main "$@"