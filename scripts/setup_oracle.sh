#!/usr/bin/env bash
# setup_oracle.sh — Provision Oracle Cloud Free Tier ARM64 for NEXUS Data Plane
# Ejecutar EN la instancia Oracle (SSH) tras crear la VM

set -euo pipefail

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  NEXUS QUANT FLOOR — Oracle ARM64 Setup (Data Plane)        ║"
echo "╚══════════════════════════════════════════════════════════════╝"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log() { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $*"; }
ok() { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err() { echo -e "${RED}✗${NC} $*"; }

# ─── Root check ───
if [[ $EUID -ne 0 ]]; then
    err "Ejecutar como root (sudo -i)"
    exit 1
fi

# ─── Detect Oracle Cloud ───
if [[ -f /sys/class/dmi/id/product_name ]] && grep -qi "oracle" /sys/class/dmi/id/product_name; then
    ok "Oracle Cloud detectado"
else
    warn "No se detecta Oracle Cloud — continuando anyway"
fi

# ─── System prep ───
log "Actualizando sistema e instalando dependencias..."
apt-get update -qq && apt-get install -y -qq \
    docker.io docker-compose-v2 \
    git curl wget jq htop iotop nethogs \
    build-essential pkg-config libssl-dev \
    python3.11 python3.11-venv python3.11-dev \
    2>/dev/null | tail -5

# Docker permissions
usermod -aG docker ubuntu 2>/dev/null || true
usermod -aG docker opc 2>/dev/null || true

# ─── Mount block volume (200GB NVMe) ───
log "Configurando block volume (200GB)..."
if lsblk | grep -q "nvme1n1"; then
    DEVICE="/dev/nvme1n1"
elif lsblk | grep -q "sdb"; then
    DEVICE="/dev/sdb"
else
    warn "Block volume no detectado automáticamente. Monta manualmente en /data"
    DEVICE=""
fi

if [[ -n "$DEVICE" ]]; then
    if ! blkid "$DEVICE" &>/dev/null; then
        mkfs.ext4 "$DEVICE"
        ok "Formateado $DEVICE como ext4"
    fi
    mkdir -p /data
    echo "$DEVICE /data ext4 defaults,nofail 0 2" >> /etc/fstab
    mount -a
    ok "Block volume montado en /data"
fi

# ─── Data directories ───
mkdir -p /data/raw/cme_datamine/{NQ,ES,YM,GC}/{1m,15m,1h}
mkdir -p /data/processed
mkdir -p /data/knowledge_graph
chown -R 1000:1000 /data 2>/dev/null || true
ok "Directorios de datos creados en /data"

# ─── Clone repo ───
log "Clonando repositorio..."
cd /opt
if [[ ! -d nexus-quant-floor ]]; then
    git clone https://github.com/TU_USUARIO/nexus-quant-floor.git 2>/dev/null || {
        warn "Repo no accesible vía HTTPS. Usa SSH o clona manualmente."
        mkdir -p nexus-quant-floor
    }
fi
cd nexus-quant-floor
chown -R 1000:1000 /opt/nexus-quant-floor 2>/dev/null || true

# ─── .env ───
if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        cp .env.example .env
        warn ".env creado — EDITA CON TUS CLAVES REALES"
    else
        touch .env
    fi
fi

# ─── Docker Compose ───
log "Descargando imágenes ARM64..."
docker compose -f docker-compose.oracle.yml pull 2>/dev/null | tail -3

log "Construyendo imágenes custom ARM64..."
docker compose -f docker-compose.oracle.yml build --parallel 2>/dev/null | tail -5

# ─── Start core ───
log "Levantando servicios core..."
docker compose -f docker-compose.oracle.yml up -d redis ollama embeddings

log "Esperando health checks..."
sleep 15

# ─── Pull models ───
log "Descargando modelos Ollama (8b + 70b)..."
docker compose -f docker-compose.oracle.yml --profile setup up ollama-pull

# ─── Start all workers ───
log "Levantando workers + ingestion + monitoring..."
docker compose -f docker-compose.oracle.yml up -d \
    worker-discovery worker-validation worker-deployment worker-learning \
    celery-beat data-ingestion prometheus grafana

# ─── Tailscale ───
if grep -q "TAILSCALE_AUTHKEY=" .env 2>/dev/null && [[ -n $(grep "TAILSCALE_AUTHKEY=" .env | cut -d'=' -f2) ]]; then
    log "Conectando Tailscale..."
    docker compose -f docker-compose.oracle.yml up -d tailscale
    ok "Tailscale conectado — verifica en laptop: tailscale status"
else
    warn "TAILSCALE_AUTHKEY no configurado — configúralo en .env y ejecuta: docker compose -f docker-compose.oracle.yml up -d tailscale"
fi

# ─── Firewall (Oracle security lists + iptables) ───
log "Configurando firewall local..."
ufw allow 22/tcp    # SSH
ufw allow 6379/tcp  # Redis (solo Tailscale)
ufw allow 8000/tcp  # FastAPI (si expuesto)
ufw allow 8080/tcp  # Embeddings
ufw allow 11434/tcp # Ollama
ufw allow 50051/tcp # Microstructure gRPC
ufw allow 9090/tcp  # Prometheus
ufw allow 3002/tcp  # Grafana
ufw --force enable 2>/dev/null || true
ok "Firewall configurado (puertos solo accesibles vía Tailscale)"

# ─── Summary ───
echo
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ORACLE SETUP COMPLETADO — ENDPOINTS (vía Tailscale)        ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Redis:               <tailscale-ip>:6379                   ║"
echo "║  Ollama:              <tailscale-ip>:11434                  ║"
echo "║  Embeddings (TEI):    <tailscale-ip>:8080                   ║"
echo "║  Microstructure gRPC: <tailscale-ip>:50051                  ║"
echo "║  Prometheus:          <tailscale-ip>:9090                   ║"
echo "║  Grafana:             <tailscale-ip>:3002 (admin/<pass>)    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo
echo "En laptop (.env):"
echo "  REDIS_URL=redis://<tailscale-ip-oracle>:6379"
echo "  OLLAMA_URL=http://<tailscale-ip-oracle>:11434"
echo "  EMBEDDINGS_URL=http://<tailscale-ip-oracle>:8080"
echo
echo "Luego en laptop: ./scripts/migrate_to_oracle.sh"