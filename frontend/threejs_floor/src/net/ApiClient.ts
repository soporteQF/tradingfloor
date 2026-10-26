/** API client for Chief of Staff backend */

export interface ChiefStatus {
  nightly: {
    state: 'running' | 'paused' | 'stopped' | 'error';
    last_run: string | null;
    next_run: string | null;
    hypotheses_generated: number;
    hypotheses_passed: number;
    hypotheses_rejected: number;
    last_error: string | null;
  };
  paper_strategies: Record<string, PaperStrategy>;
  guardian_alerts: GuardianAlert[];
  guardian_status: GuardianStatus;
}

export interface PaperStrategy {
  strategy_id: string;
  name: string;
  symbol: string;
  timeframe: string;
  regime: string;
  state: string;
  equity: number;
  unrealized_pnl: number;
  realized_pnl: number;
  trades_today: number;
  win_rate: number;
  avg_fill_slippage_bps: number;
  last_signal: string | null;
  last_fill: string | null;
  guard_alerts: string[];
}

export interface GuardianAlert {
  timestamp: string;
  guard_name: string;
  action: string;
  message: string;
  severity: string;
  strategy_id: string | null;
  symbol: string | null;
}

export interface GuardianStatus {
  kill_switch: boolean;
  loss_streak: number;
  trades_today: number;
  daily_pnl: number;
  trailing_dd: number;
  limits: Record<string, any>;
}

export interface CommandRequest {
  type: string;
  strategy_id?: string;
  target_state?: string;
  reason?: string;
  user?: string;
}

export interface CommandResponse {
  status: string;
  command: string;
}

class ApiClient {
  private baseUrl: string;
  private cache: Map<string, { data: any; timestamp: number }> = new Map();
  private cacheTtl = 1000; // 1 second
  private abortControllers: Map<string, AbortController> = new Map();

  constructor(baseUrl: string = '/api') {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const controller = new AbortController();
    const key = `${options.method || 'GET'}:${endpoint}`;
    this.abortControllers.set(key, controller);

    try {
      const res = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error(`API ${res.status}: ${await res.text()}`);
      }

      return res.json();
    } finally {
      this.abortControllers.delete(key);
    }
  }

  private getCached<T>(key: string): T | null {
    const entry = this.cache.get(key);
    if (entry && Date.now() - entry.timestamp < this.cacheTtl) {
      return entry.data;
    }
    return null;
  }

  private setCache(key: string, data: any): void {
    this.cache.set(key, { data, timestamp: Date.now() });
  }

  /** Get full Chief status */
  async getStatus(): Promise<ChiefStatus> {
    const cached = this.getCached('status');
    if (cached) return cached;

    const data = await this.request<ChiefStatus>('/chief/status');
    this.setCache('status', data);
    return data;
  }

  /** Send command to Chief */
  async sendCommand(cmd: CommandRequest): Promise<CommandResponse> {
    return this.request<CommandResponse>('/chief/command', {
      method: 'POST',
      body: JSON.stringify(cmd),
    });
  }

  /** Get Guardian status */
  async getGuardianStatus(): Promise<GuardianStatus> {
    return this.request<GuardianStatus>('/chief/guardian/status');
  }

  /** Activate kill switch */
  async activateKillSwitch(reason: string = 'Manual via UI'): Promise<CommandResponse> {
    return this.request<CommandResponse>('/chief/guardian/kill-switch', {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  }

  /** Override guard for strategy */
  async overrideGuard(strategyId: string, reason: string = 'Manual override'): Promise<CommandResponse> {
    return this.request<CommandResponse>('/chief/guardian/override', {
      method: 'POST',
      body: JSON.stringify({ strategy_id: strategyId, reason }),
    });
  }

  /** Get nightly status */
  async getNightlyStatus(): Promise<ChiefStatus['nightly']> {
    return this.request<ChiefStatus['nightly']>('/chief/nightly/status');
  }

  /** Trigger nightly loop */
  async runNightlyNow(): Promise<CommandResponse> {
    return this.request<CommandResponse>('/chief/nightly/run', { method: 'POST' });
  }

  /** Pause nightly loop */
  async pauseNightly(): Promise<CommandResponse> {
    return this.request<CommandResponse>('/chief/nightly/pause', { method: 'POST' });
  }

  /** Resume nightly loop */
  async resumeNightly(): Promise<CommandResponse> {
    return this.request<CommandResponse>('/chief/nightly/resume', { method: 'POST' });
  }

  /** Get paper strategies */
  async getPaperStrategies(): Promise<Record<string, PaperStrategy>> {
    return this.request<Record<string, PaperStrategy>>('/chief/strategies');
  }

  /** Promote strategy to paper */
  async promoteStrategy(strategyId: string, reason: string = 'Promoted by Chief'): Promise<CommandResponse> {
    return this.request<CommandResponse>(`/chief/strategies/${strategyId}/promote`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  }

  /** Retire strategy */
  async retireStrategy(strategyId: string, reason: string = 'Retired by Chief'): Promise<CommandResponse> {
    return this.request<CommandResponse>(`/chief/strategies/${strategyId}/retire`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  }

  /** Get guardian alerts */
  async getAlerts(limit: number = 50): Promise<GuardianAlert[]> {
    return this.request<GuardianAlert[]>(`/chief/alerts?limit=${limit}`);
  }

  /** Health check */
  async healthCheck(): Promise<{ status: string; chief_initialized: boolean; guardian_initialized: boolean }> {
    return this.request('/health');
  }

  /** Clear cache */
  clearCache(): void {
    this.cache.clear();
  }

  /** Abort all pending requests */
  abortAll(): void {
    for (const controller of this.abortControllers.values()) {
      controller.abort();
    }
    this.abortControllers.clear();
  }
}

// Singleton instance
export const api = new ApiClient();

// Mock data fallback for development (when backend not running)
export const mockApi = {
  async getStatus(): Promise<ChiefStatus> {
    // Simulate network delay
    await new Promise(r => setTimeout(r, 50));
    return {
      nightly: {
        state: 'running',
        last_run: new Date(Date.now() - 3600000).toISOString(),
        next_run: new Date(Date.now() + 82800000).toISOString(),
        hypotheses_generated: 847,
        hypotheses_passed: 12,
        hypotheses_rejected: 835,
        last_error: null,
      },
      paper_strategies: {
        'strat_1': {
          strategy_id: 'strat_1',
          name: 'ema_trend_nq_5m',
          symbol: 'NQ',
          timeframe: '5m',
          regime: 'trend_up',
          state: 'paper',
          equity: 52847,
          unrealized_pnl: 1234,
          realized_pnl: -456,
          trades_today: 23,
          win_rate: 0.61,
          avg_fill_slippage_bps: 1.2,
          last_signal: 'LONG 2 MNQ @ 15420',
          last_fill: 'LONG 2 @ 15421',
          guard_alerts: [],
        },
        'strat_2': {
          strategy_id: 'strat_2',
          name: 'mean_rev_nq_15m',
          symbol: 'NQ',
          timeframe: '15m',
          regime: 'range_low_vol',
          state: 'validated',
          equity: 0,
          unrealized_pnl: 0,
          realized_pnl: 0,
          trades_today: 0,
          win_rate: 0,
          avg_fill_slippage_bps: 0,
          last_signal: null,
          last_fill: null,
          guard_alerts: [],
        },
      },
      guardian_alerts: [],
      guardian_status: {
        kill_switch: false,
        loss_streak: 0,
        trades_today: 47,
        daily_pnl: 1234.56,
        trailing_dd: 2.1,
        limits: {
          max_daily_loss: 1500,
          max_trailing_dd: 2500,
          max_contracts_per_symbol: 10,
          max_total_contracts: 20,
        },
      },
    };
  },

  async sendCommand(cmd: CommandRequest): Promise<CommandResponse> {
    await new Promise(r => setTimeout(r, 50));
    return { status: 'accepted', command: cmd.type };
  },

  async getGuardianStatus() {
    return mockApi.getStatus().then(s => s.guardian_status);
  },

  async activateKillSwitch(reason: string) {
    return { status: 'activated', command: 'kill_switch' };
  },

  async getNightlyStatus() {
    return mockApi.getStatus().then(s => s.nightly);
  },

  async runNightlyNow() {
    return { status: 'triggered', command: 'run_nightly_now' };
  },

  async pauseNightly() {
    return { status: 'paused', command: 'pause_loop' };
  },

  async resumeNightly() {
    return { status: 'resumed', command: 'resume_loop' };
  },

  async getPaperStrategies() {
    return mockApi.getStatus().then(s => s.paper_strategies);
  },

  async promoteStrategy(strategyId: string, reason: string) {
    return { status: 'promoted', command: 'promote' };
  },

  async retireStrategy(strategyId: string, reason: string) {
    return { status: 'retired', command: 'retire' };
  },

  async getAlerts(limit: number) {
    return [];
  },

  async healthCheck() {
    return { status: 'healthy', chief_initialized: true, guardian_initialized: true };
  },
};

// Auto-detect: use mock if backend not reachable OR in Codespaces
let useMock = false;

function isCodespace(): boolean {
  if (typeof window === 'undefined') return false;
  const host = window.location.hostname;
  return host.includes('github.dev') || host.includes('app.github.dev');
}

export async function getApiClient(): Promise<ApiClient> {
  // Force mock in Codespaces (no backend available)
  if (isCodespace()) {
    console.log('Codespace detected, using mock API');
    useMock = true;
    return mockApi as any;
  }

  if (useMock) return api; // Return mock interface

  try {
    await api.healthCheck();
    useMock = false;
    return api;
  } catch {
    console.warn('Backend not reachable, using mock API');
    useMock = true;
    return mockApi as any;
  }
}

export function setUseMock(mock: boolean): void {
  useMock = mock;
}