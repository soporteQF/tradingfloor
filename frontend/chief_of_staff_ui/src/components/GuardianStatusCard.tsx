import { Shield, AlertTriangle, DollarSign, Target, XCircle, TrendingDown } from 'lucide-react'

interface Props {
  guardian: any
  onKillSwitch: () => void
}

export default function GuardianStatusCard({ guardian, onKillSwitch }: Props) {
  if (!guardian) return null

  const killActive = guardian.kill_switch

  return (
    <section className="section">
      <div className="section-title"><h2>Guardian</h2></div>
      <div className="guardian-status">
        <div className={`guardian-kill ${killActive ? 'active' : 'inactive'}`}>
          <Shield className="w-4 h-4" />
          <span style={{ fontWeight: 600 }}>
            {killActive ? 'KILL SWITCH ACTIVO' : 'Guardian Activo'}
          </span>
          {killActive && (
            <span style={{ marginLeft: '8px', fontSize: '11px', opacity: 0.8 }}>
              Todas las posiciones se aplanarán
            </span>
          )}
        </div>
        <div className="guardian-metrics">
          <span className="guardian-metric"><Target className="w-3 h-3" /><strong>{guardian.trades_today}</strong> trades hoy</span>
          <span className="guardian-metric"><DollarSign className="w-3 h-3" /><strong>{guardian.daily_pnl >= 0 ? '+' : ''}{guardian.daily_pnl.toFixed(2)}</strong> PnL diario</span>
          <span className="guardian-metric"><TrendingDown className="w-3 h-3" /><strong>{guardian.trailing_dd.toFixed(2)}</strong> Trailing DD</span>
          <span className="guardian-metric"><XCircle className="w-3 h-3" /><strong>{guardian.loss_streak}</strong> Loss streak</span>
        </div>
        {!killActive && (
          <button className="btn btn-danger" onClick={onKillSwitch} style={{ marginLeft: 'auto' }}>
            <AlertTriangle className="w-4 h-4" /> Kill Switch
          </button>
        )}
      </div>
    </section>
  )
}