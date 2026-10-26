/** Manages all HTML overlays */

import { ZoneKey, ZONES, CHIEF_CENTER, ZONE_KEYS } from '../data/floorConfig.js';

// Local mock data (same as prototype)
const LIVE_DATA = {
  regime: 'trend_up',
  killSwitch: false,
  nightlyProgress: 0.8,
  nightlyState: 'running',
  pnl: 12847,
  tradesToday: 47,
  guards: [
    { name: 'Daily Loss', current: 234, limit: 1500, ok: true },
    { name: 'Trailing DD', current: 8.2, limit: 15, ok: true },
    { name: 'Contracts', current: 3, limit: 10, ok: true },
    { name: 'Correlation', current: 0.34, limit: 0.5, ok: true },
    { name: 'Loss Streak', current: 0, limit: 3, ok: true },
    { name: 'Trade Freq', current: 12, limit: 50, ok: true },
    { name: 'Strategy DD', current: 4.1, limit: 10, ok: true },
    { name: 'Cooldown', current: 0, limit: 1, ok: true },
  ],
  zoneMetrics: {
    research:    { patterns: 847, hypotheses: 12, queue: 5, active: 3 },
    validation:  { folds: '3/8', passed: 2, failed: 1, mcRunning: true },
    execution:   { signals: 4, pending: 1, fills: 3, slipBps: 1.2 },
    guardian:    { alerts: 0, cooldown: false, overrides: 0 },
    regime:      { state: 'trend_up', confidence: 0.87, nextChange: '~45min' },
    alpha:       { strategies: 8, insights: 23, errors: 41, queries: 7 },
  },
};

export class OverlayManager {
  private elements: Map<string, HTMLElement> = new Map();
  private currentZone: ZoneKey | 'chief' | null = null;
  private statusUpdateCallback?: (status: any) => void;
  private commandCallback?: (type: string, data: any) => void;

  constructor() {
    this.initElements();
    this.setupEventListeners();
    this.initMockData();
  }

  private initElements(): void {
    // Cache all overlay elements
    const ids = [
      'regimeBadge', 'killBadge', 'killDot', 'nightlyProgress', 'nightlyPct', 'etClock',
      'minimap', 'minimapCanvas', 'zonePanel', 'zonePanelTitle', 'zonePanelColor',
      'zonePanelContent', 'zonePanelActions', 'chatMessages', 'chatInput',
      'reducedMotionToggle', 'loading', 'loadStatus', 'loadError',
    ];
    ids.forEach(id => {
      const el = document.getElementById(id);
      if (el) this.elements.set(id, el);
    });
  }

  private setupEventListeners(): void {
    // Chat input
    const chatInput = this.elements.get('chatInput');
    if (chatInput) {
      chatInput.addEventListener('keydown', (e: KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendChat();
        }
      });
    }

    // Reduced motion toggle
    const reducedToggle = this.elements.get('reducedMotionToggle') as HTMLInputElement;
    if (reducedToggle) {
      reducedToggle.addEventListener('change', (e: Event) => {
        const target = e.target as HTMLInputElement;
        window.dispatchEvent(new CustomEvent('reduced-motion', { detail: { enabled: target.checked } }));
      });
    }

    // Zone panel close
    const zoneClose = document.querySelector('.zone-close');
    if (zoneClose) {
      zoneClose.addEventListener('click', () => this.closeZonePanel());
    }

    // Keyboard shortcuts
    window.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      switch (e.key.toLowerCase()) {
        case 'm': this.toggleMinimap(); break;
        case 'r': this.toggleReducedMotion(); break;
        case ' ': e.preventDefault(); this.focusChief(); break;
        case 'escape': this.closeZonePanel(); break;
      }
    });

    // Window resize
    window.addEventListener('resize', () => this.updateMinimap());
  }

  private initMockData(): void {
    // Hide loading screen
    const loading = this.elements.get('loading');
    if (loading) loading.style.display = 'none';

    // Initial mock status
    this.updateTopBar({
      regime: 'trend_up',
      killSwitch: false,
      nightlyProgress: 0.8,
      nightlyState: 'running',
      pnl: 12847,
      tradesToday: 47,
    });

    // Initial chat messages
    this.addChatMessage('chief', 'Chief of Staff online. Floor operational. All systems nominal.');
    this.addChatMessage('chief', 'Commands: "run nightly", "kill switch", "pause", "resume", "status"');

    // Start clock
    this.updateClock();
    setInterval(() => this.updateClock(), 1000);

    // Start live updates (mock)
    this.startLiveUpdates();
  }

  private startLiveUpdates(): void {
    setInterval(() => {
      // Mock live data updates
      const pnlChange = (Math.random() - 0.48) * 50;
      LIVE_DATA.pnl += pnlChange;
      if (Math.random() > 0.95) LIVE_DATA.tradesToday += 1;

      // Occasional regime change
      if (Math.random() < 0.001) {
        const regimes = ['trend_up', 'trend_down', 'range_low_vol', 'range_high_vol'];
        LIVE_DATA.regime = regimes[Math.floor(Math.random() * regimes.length)];
        this.updateTopBar({ regime: LIVE_DATA.regime });
        this.addChatMessage('chief', `🌊 Regime change: ${LIVE_DATA.regime.toUpperCase()}`);
      }

      // Occasional guardian alert
      if (Math.random() < 0.0005) {
        const guard = LIVE_DATA.guards[Math.floor(Math.random() * LIVE_DATA.guards.length)];
        guard.ok = false;
        this.addChatMessage('chief', `⚠️ Guardian: ${guard.name} threshold (${guard.current}/${guard.limit})`);
        setTimeout(() => { guard.ok = true; }, 5000);
      }

      // Nightly progress
      if (LIVE_DATA.nightlyState === 'running') {
        LIVE_DATA.nightlyProgress = Math.min(1, LIVE_DATA.nightlyProgress + Math.random() * 0.05);
        if (LIVE_DATA.nightlyProgress >= 1) {
          LIVE_DATA.nightlyState = 'completed';
          this.addChatMessage('chief', '✅ Nightly loop completed. Daily report generated.');
        }
      }

      this.updateTopBar({});
    }, 2000);
  }

  // Public API
  public setStatusUpdateCallback(cb: (status: any) => void): void {
    this.statusUpdateCallback = cb;
  }

  public setCommandCallback(cb: (type: string, data: any) => void): void {
    this.commandCallback = cb;
  }

  public updateFromStatus(status: any): void {
    this.updateTopBar(status);
    if (this.currentZone) this.openZonePanel(this.currentZone);
    this.statusUpdateCallback?.(status);
  }

  // Top Bar
  public updateTopBar(data: Partial<{
    regime: string;
    killSwitch: boolean;
    nightlyProgress: number;
    nightlyState: string;
    pnl: number;
    tradesToday: number;
  }>): void {
    if (data.regime !== undefined) LIVE_DATA.regime = data.regime;
    if (data.killSwitch !== undefined) LIVE_DATA.killSwitch = data.killSwitch;
    if (data.nightlyProgress !== undefined) LIVE_DATA.nightlyProgress = data.nightlyProgress;
    if (data.nightlyState !== undefined) LIVE_DATA.nightlyState = data.nightlyState;
    if (data.pnl !== undefined) LIVE_DATA.pnl = data.pnl;
    if (data.tradesToday !== undefined) LIVE_DATA.tradesToday = data.tradesToday;

    // Regime badge
    const regimeBadge = this.elements.get('regimeBadge');
    if (regimeBadge) {
      regimeBadge.className = `regime-badge regime-${LIVE_DATA.regime}`;
      regimeBadge.textContent = LIVE_DATA.regime.toUpperCase().replace('_', ' ') + ' ' +
        (LIVE_DATA.regime === 'trend_up' ? '▲' : LIVE_DATA.regime === 'trend_down' ? '▼' : '◆');
    }

    // Kill switch
    const killBadge = this.elements.get('killBadge');
    const killDot = this.elements.get('killDot');
    if (killBadge && killDot) {
      if (LIVE_DATA.killSwitch) {
        killBadge.className = 'kill-badge kill-active';
        killDot.textContent = '●';
        killBadge.childNodes[1].textContent = ' KILL ACTIVE';
      } else {
        killBadge.className = 'kill-badge kill-safe';
        killDot.textContent = '●';
        killBadge.childNodes[1].textContent = ' GUARDIAN SAFE';
      }
    }

    // Nightly progress
    const nightlyProgress = this.elements.get('nightlyProgress');
    const nightlyPct = this.elements.get('nightlyPct');
    if (nightlyProgress) nightlyProgress.style.width = `${(LIVE_DATA.nightlyProgress * 100).toFixed(0)}%`;
    if (nightlyPct) nightlyPct.textContent = `${(LIVE_DATA.nightlyProgress * 100).toFixed(0)}%`;
  }

  public updateClock(): void {
    const etClock = this.elements.get('etClock');
    if (etClock) {
      const now = new Date();
      const et = new Date(now.getTime() - 4 * 3600000); // UTC-4
      etClock.textContent = et.toLocaleTimeString('en-US', { hour12: false, timeZone: 'America/New_York' }) + ' ET';
    }
  }

  // Zone Panel
  public openZonePanel(zoneKey: ZoneKey | 'chief'): void {
    this.currentZone = zoneKey;
    const panel = this.elements.get('zonePanel');
    const title = this.elements.get('zonePanelTitle');
    const colorEl = this.elements.get('zonePanelColor');
    const content = this.elements.get('zonePanelContent');
    const actions = this.elements.get('zonePanelActions');

    if (!panel || !title || !colorEl || !content || !actions) return;

    if (zoneKey === 'chief') {
      title.textContent = 'CHIEF COMMAND CENTER';
      colorEl.style.background = '#ffcc00';
      content.innerHTML = this.buildChiefPanelContent();
      actions.innerHTML = this.buildChiefPanelActions();
    } else {
      const zone = ZONES[zoneKey];
      const metrics = LIVE_DATA.zoneMetrics[zoneKey];
      title.textContent = `${zone.emoji}  ${zone.name}`;
      colorEl.style.background = `#${zone.accent.toString(16).padStart(6, '0')}`;
      content.innerHTML = this.buildZonePanelContent(zoneKey, zone, metrics);
      actions.innerHTML = this.buildZonePanelActions(zoneKey);
    }
    panel.classList.add('open');
  }

  public closeZonePanel(): void {
    const panel = this.elements.get('zonePanel');
    if (panel) panel.classList.remove('open');
    this.currentZone = null;
  }

  private buildZonePanelContent(key: ZoneKey, zone: any, metrics: any): string {
    let html = `<div style="font-size:11px;color:#7a7a8a;margin-bottom:12px;">${zone.desc}</div>`;
    html += '<div style="display:flex;flex-direction:column;gap:6px;">';
    Object.entries(metrics).forEach(([k, v]) => {
      const label = k.charAt(0).toUpperCase() + k.slice(1).replace(/([A-Z])/g, ' $1');
      let cls = '';
      if (typeof v === 'number' && v > 0) cls = 'positive';
      if (typeof v === 'number' && v < 0) cls = 'negative';
      html += `<div class="zone-metric"><span class="metric-label">${label}</span><span class="metric-value ${cls}">${v}</span></div>`;
    });
    return html + '</div>';
  }

  private buildZonePanelActions(zoneKey: ZoneKey): string {
    return `<button class="btn btn-primary" onclick="window.overlayManager?.runZoneAction('${zoneKey}')">Run Cycle</button>
            <button class="btn btn-ghost" onclick="window.overlayManager?.viewZoneDetails('${zoneKey}')">Details</button>`;
  }

  private buildChiefPanelContent(): string {
    const activeCount = Object.entries(LIVE_DATA.zoneMetrics).filter(([, v]) => v.active).length;
    return `<div class="zone-metric"><span class="metric-label">PnL Total</span><span class="metric-value positive">$${LIVE_DATA.pnl.toLocaleString()}</span></div>
            <div class="zone-metric"><span class="metric-label">Trades Today</span><span class="metric-value">${LIVE_DATA.tradesToday}</span></div>
            <div class="zone-metric"><span class="metric-label">Nightly State</span><span class="metric-value">${LIVE_DATA.nightlyState}</span></div>
            <div class="zone-metric"><span class="metric-label">Regime</span><span class="metric-value">${LIVE_DATA.regime.toUpperCase()}</span></div>
            <div class="zone-metric"><span class="metric-label">Guardian</span><span class="metric-value ${LIVE_DATA.killSwitch ? 'negative' : 'positive'}">${LIVE_DATA.killSwitch ? 'KILL ACTIVE' : 'SAFE'}</span></div>
            <div class="zone-metric"><span class="metric-label">Active Strategies</span><span class="metric-value">${activeCount}</span></div>`;
  }

  private buildChiefPanelActions(): string {
    return `<button class="btn btn-primary" onclick="window.overlayManager?.chiefAction('run_nightly')">▶ Run Nightly Now</button>
            <button class="btn ${LIVE_DATA.killSwitch ? 'btn-ghost' : 'btn-danger'}" onclick="window.overlayManager?.chiefAction('kill_switch')">${LIVE_DATA.killSwitch ? 'Kill Active' : '🚨 Kill Switch'}</button>
            <button class="btn btn-ghost" onclick="window.overlayManager?.chiefAction('pause')">⏸ Pause Nightly</button>
            <button class="btn btn-ghost" onclick="window.overlayManager?.chiefAction('resume')">▶ Resume Nightly</button>`;
  }

  public runZoneAction(key: ZoneKey): void {
    this.addChatMessage('user', `Run ${ZONES[key].name} cycle`);
    this.addChatMessage('chief', `🔄 ${ZONES[key].name} cycle triggered. Processing...`);
    setTimeout(() => this.addChatMessage('chief', `✅ ${ZONES[key].name} cycle complete.`), 1500);
  }

  public viewZoneDetails(key: ZoneKey): void {
    this.addChatMessage('user', `Show ${ZONES[key].name} details`);
    this.addChatMessage('chief', `📊 ${ZONES[key].name} details opened in Alpha Library.`);
  }

  public chiefAction(action: string): void {
    const labels: Record<string, string> = {
      run_nightly: 'Run Nightly',
      kill_switch: 'Kill Switch',
      pause: 'Pause Nightly',
      resume: 'Resume Nightly',
    };
    this.addChatMessage('user', labels[action] || action);

    this.commandCallback?.(action, {});

    if (action === 'kill_switch') {
      LIVE_DATA.killSwitch = !LIVE_DATA.killSwitch;
      this.updateTopBar({ killSwitch: LIVE_DATA.killSwitch });
      this.addChatMessage('chief', LIVE_DATA.killSwitch ? '🚨 KILL SWITCH ACTIVATED.' : '✅ Kill switch deactivated.');
    } else if (action === 'run_nightly') {
      LIVE_DATA.nightlyState = 'running';
      this.animateNightlyProgress();
      this.addChatMessage('chief', '🌙 Nightly loop started.');
    } else if (action === 'pause') {
      LIVE_DATA.nightlyState = 'paused';
      this.addChatMessage('chief', '⏸ Nightly paused.');
    } else if (action === 'resume') {
      LIVE_DATA.nightlyState = 'running';
      this.addChatMessage('chief', '▶ Nightly resumed.');
    }
    this.openZonePanel('chief');
  }

  private animateNightlyProgress(): void {
    let p = LIVE_DATA.nightlyProgress;
    const interval = setInterval(() => {
      p += Math.random() * 0.15;
      if (p >= 1) {
        p = 1;
        clearInterval(interval);
        LIVE_DATA.nightlyState = 'completed';
        this.addChatMessage('chief', '✅ Nightly completed.');
      }
      LIVE_DATA.nightlyProgress = p;
      this.updateTopBar({ nightlyProgress: p, nightlyState: LIVE_DATA.nightlyState });
    }, 500);
  }

  // Chat
  public addChatMessage(role: 'user' | 'chief', text: string): void {
    const container = this.elements.get('chatMessages');
    if (!container) return;

    const msg = document.createElement('div');
    msg.className = `chat-msg ${role}`;
    msg.innerHTML = `<div class="chat-avatar ${role}">${role === 'chief' ? '🤖' : '👤'}</div>
                     <div class="chat-bubble">${this.escapeHtml(text)}</div>`;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
  }

  public sendChat(): void {
    const input = this.elements.get('chatInput') as HTMLInputElement;
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    this.addChatMessage('user', text);
    this.processChatCommand(text.toLowerCase());
  }

  private processChatCommand(cmd: string): void {
    if (cmd.includes('kill') || cmd.includes('emergency')) {
      this.chiefAction('kill_switch');
    } else if (cmd.includes('run nightly') || cmd.includes('nightly now')) {
      this.chiefAction('run_nightly');
    } else if (cmd.includes('pause')) {
      this.chiefAction('pause');
    } else if (cmd.includes('resume') || cmd.includes('continue')) {
      this.chiefAction('resume');
    } else if (cmd.includes('status') || cmd.includes('estado')) {
      this.addChatMessage('chief', `📊 Regime ${LIVE_DATA.regime.toUpperCase()} | PnL $${LIVE_DATA.pnl.toLocaleString()} | Trades ${LIVE_DATA.tradesToday} | Guardian ${LIVE_DATA.killSwitch ? 'KILL' : 'SAFE'} | Nightly ${LIVE_DATA.nightlyState}`);
    } else if (cmd.includes('promote') || cmd.includes('retire')) {
      this.addChatMessage('chief', 'Use the Strategies panel to promote/retire.');
    } else {
      this.addChatMessage('chief', `Commands: run nightly, kill switch, pause, resume, status`);
    }
  }

  private escapeHtml(text: string): string {
    return text.replace(/&/g, '&').replace(/</g, '<').replace(/>/g, '>');
  }

  // Minimap
  public updateMinimap(): void {
    const canvas = this.elements.get('minimapCanvas') as HTMLCanvasElement;
    if (!canvas) return;

    const ctx = canvas.getContext('2d')!;
    const scale = 2;
    canvas.width = 220 * scale;
    canvas.height = 160 * scale;
    canvas.style.width = '220px';
    canvas.style.height = '160px';
    ctx.scale(scale, scale);

    const mmW = 220, mmH = 160;
    const scaleX = mmW / (80 * 64); // GRID_W * TILE_W
    const scaleY = mmH / (60 * 32); // GRID_H * TILE_H

    // Background
    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, mmW, mmH);

    // Zones
    ZONE_KEYS.forEach(key => {
      const zone = ZONES[key];
      ctx.fillStyle = `#${zone.color.toString(16).padStart(6, '0')}22`;
      ctx.strokeStyle = `#${zone.accent.toString(16).padStart(6, '0')}`;
      ctx.lineWidth = 1;
      const x = zone.x * 64 * scaleX;
      const y = zone.y * 32 * scaleY;
      const w = 16 * 64 * scaleX;
      const h = 16 * 32 * scaleY;
      ctx.fillRect(x, y, w, h);
      ctx.strokeRect(x, y, w, h);
    });

    // Chief center
    ctx.fillStyle = '#ffcc0033';
    ctx.strokeStyle = '#ffcc00';
    ctx.lineWidth = 2;
    const cx = CHIEF_CENTER.x * 64 * scaleX;
    const cy = CHIEF_CENTER.y * 32 * scaleY;
    const cw = CHIEF_CENTER.size * 64 * scaleX;
    const ch = CHIEF_CENTER.size * 32 * scaleY;
    ctx.fillRect(cx, cy, cw, ch);
    ctx.strokeRect(cx, cy, cw, ch);

    // Corridor
    ctx.fillStyle = '#00d4aa11';
    ctx.fillRect(0, 24 * 32 * scaleY, mmW, 4 * 32 * scaleY);
  }

  public toggleMinimap(): void {
    const minimap = this.elements.get('minimap');
    if (minimap) {
      minimap.style.display = minimap.style.display === 'none' ? 'block' : 'none';
    }
  }

  public toggleReducedMotion(): void {
    const toggle = this.elements.get('reducedMotionToggle') as HTMLInputElement;
    if (toggle) {
      toggle.checked = !toggle.checked;
      window.dispatchEvent(new CustomEvent('reduced-motion', { detail: { enabled: toggle.checked } }));
    }
  }

  public focusChief(): void {
    window.dispatchEvent(new CustomEvent('focus-chief'));
  }
}

// Global access for inline handlers
declare global {
  interface Window {
    overlayManager: OverlayManager;
  }
}