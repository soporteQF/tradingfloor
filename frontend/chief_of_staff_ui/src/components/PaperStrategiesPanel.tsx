import { Zap, CheckCircle, RotateCcw, MinusCircle } from 'lucide-react'

interface Props {
  strategies: Record<string, any>
  onPromote: (cmd: any) => void
  onRetire: (cmd: any) => void
}

const STATE_STYLES: Record<string, { dot: string; label: string; color: string }> = {
  paper: { dot: 'status-running', label: 'PAPER', color: 'var(--accent)' },
  validated: { dot: 'status-paused', label: 'VALIDATED', color: 'var(--warning)' },
  proposed: { dot: 'status-stopped', label: 'PROPOSED', color: 'var(--fg-muted)' },
  live: { dot: 'status-running', label: 'LIVE', color: 'var(--accent)' },
  retired: { dot: 'status-stopped', label: 'RETIRED', color: 'var(--fg-muted)' },
  rejected: { dot: 'status-error', label: 'REJECTED', color: 'var(--danger)' },
}

function getPnlColor(pnl: number) {
  if (pnl > 0) return 'positive'
  if (pnl < 0) return 'negative'
  return ''
}

export default function PaperStrategiesPanel({ strategies, onPromote, onRetire }: Props) {
  const stratList = Object.values(strategies)

  if (stratList.length === 0) {
    return (
      <section className="section">
        <div className="section-title"><h2>Paper Strategies</h2><span className="count">0 active</span></div>
        <div className="empty" style={{ padding: '60px 16px' }}>
          <Zap className="w-16 h-16 mx-auto" style={{ opacity: 0.3 }} />
          <p>No hay estrategias en paper trading</p>
          <p style={{ fontSize: '12px', marginTop: '8px', opacity: 0.6 }}>Las estrategias validadas aparecerán aquí</p>
        </div>
      </section>
    )
  }

  return (
    <section className="section">
      <div className="section-title"><h2>Paper Strategies</h2><span className="count">{stratList.length} total</span></div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {stratList.map((s: any) => {
          const stateInfo = STATE_STYLES[s.state] || STATE_STYLES.proposed
          const pnl = (s.unrealized_pnl || 0) + (s.realized_pnl || 0)
          const pnlClass = getPnlColor(pnl)
          const canPromote = s.state === 'validated'

          return (
            <div key={s.strategy_id} className="card" style={{ borderLeft: `4px solid ${stateInfo.color}` }}>
              <div className="card-title">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
                  <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {s.name}
                    <span className={`status-dot ${stateInfo.dot}`} style={{ width: '10px', height: '10px' }} />
                  </h3>
                </div>
                <span style={{ fontSize: '10px', fontWeight: 600, color: stateInfo.color, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {stateInfo.label}
                </span>
              </div>
              <div className="card-meta">
                <span>{s.symbol} {s.timeframe}</span>
                <span>{s.regime}</span>
                <span>{s.trades_today} trades</span>
              </div>
              <div className="metric"><span className="metric-label">Equity</span><span className="metric-value mono">${(s.equity || 0).toLocaleString()}</span></div>
              <div className="metric"><span className="metric-label">PnL Total</span><span className={`metric-value mono ${pnlClass}`}>{pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}</span></div>
              <div className="metric"><span className="metric-label">Win Rate</span><span className="metric-value mono">{(s.win_rate * 100).toFixed(1)}%</span></div>
              <div className="metric"><span className="metric-label">Avg Slippage</span><span className="metric-value mono">{s.avg_fill_slippage_bps?.toFixed(1) || 0} bps</span></div>
              {s.last_signal && <div className="metric"><span className="metric-label">Last Signal</span><span className="metric-value mono mono" style={{ color: 'var(--fg-muted)' }}>{s.last_signal}</span></div>}
              {s.last_fill && <div className="metric"><span className="metric-label">Last Fill</span><span className="metric-value mono" style={{ color: 'var(--fg-muted)' }}>{s.last_fill}</span></div>}
              <div style={{ display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
                {canPromote && (
                  <button className="btn btn-primary" style={{ flex: 1, minWidth: '120px' }} onClick={() => onPromote({ type: 'promote', strategy_id: s.strategy_id })}>
                    <CheckCircle className="w-4 h-4" /> Promover a Paper
                  </button>
                )}
                {s.state === 'paper' && (
                  <button className="btn btn-ghost" style={{ flex: 1, minWidth: '120px' }} onClick={() => onRetire({ type: 'retire', strategy_id: s.strategy_id, name: s.name })}>
                    <RotateCcw className="w-4 h-4" /> Retirar
                  </button>
                )}
                {s.state === 'retired' && (
                  <button className="btn btn-ghost" style={{ flex: 1, minWidth: '120px', opacity: 0.5 }} disabled>
                    <MinusCircle className="w-4 h-4" /> Retirada
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}