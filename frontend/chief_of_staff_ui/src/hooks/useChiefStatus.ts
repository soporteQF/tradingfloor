import { useEffect, useState, useCallback } from 'react'

interface ChiefStatus {
  nightly: NightlyStatus | null
  paper_strategies: Record<string, PaperStrategy>
  guardian_alerts: GuardianAlert[]
  guardian_status: GuardianStatus | null
}

interface NightlyStatus {
  state: 'running' | 'paused' | 'stopped' | 'error'
  last_run: string | null
  next_run: string | null
  hypotheses_generated: number
  hypotheses_passed: number
  hypotheses_rejected: number
  last_error: string | null
}

interface PaperStrategy {
  strategy_id: string
  name: string
  symbol: string
  timeframe: string
  regime: string
  state: string
  equity: number
  unrealized_pnl: number
  realized_pnl: number
  trades_today: number
  win_rate: number
  avg_fill_slippage_bps: number
  last_signal: string | null
  last_fill: string | null
  guard_alerts: string[]
}

interface GuardianAlert {
  timestamp: string
  guard_name: string
  action: string
  message: string
  severity: string
  strategy_id: string | null
  symbol: string | null
}

interface GuardianStatus {
  kill_switch: boolean
  loss_streak: number
  trades_today: number
  daily_pnl: number
  trailing_dd: number
  limits: Record<string, any>
}

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000'

export function useChiefStatus(_ttsEnabled: boolean) {
  const [status, setStatus] = useState<ChiefStatus>({
    nightly: null,
    paper_strategies: {},
    guardian_alerts: [],
    guardian_status: null,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/chief/status`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setStatus(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 3000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const sendCommand = useCallback(async (cmd: any) => {
    try {
      const res = await fetch(`${API_BASE}/api/chief/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cmd),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      // Optimistic update - will be refreshed by interval
      await fetchStatus()
    } catch (e) {
      console.error('Command failed:', e)
      alert(`Command failed: ${e instanceof Error ? e.message : 'Unknown error'}`)
    }
  }, [fetchStatus])

  return { status, loading, error, sendCommand, refresh: fetchStatus }
}