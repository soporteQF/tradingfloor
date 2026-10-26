import { Activity, Play, Pause, RotateCcw, Clock, CheckCircle, XCircle, AlertTriangle } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface Props {
  status: any
  onRunNow: () => void
  onPause: () => void
  onResume: () => void
}

export default function NightlyLoopCard({ status, onRunNow, onPause, onResume }: Props) {
  if (!status) return null

  const state = status.state || 'stopped'
  const lastRun = status.last_run ? formatDistanceToNow(new Date(status.last_run), { addSuffix: true }) : 'Never'

  return (
    <section className="section">
      <div className="section-title">
        <h2>Nightly Loop</h2>
        <span className="count">{status.hypotheses_generated} generated</span>
      </div>
      <div className={`loop-status ${state}`}>
        <div className="loop-status-icon">
          {state === 'running' && <Activity className="w-6 h-6 animate-pulse" />}
          {state === 'paused' && <Pause className="w-6 h-6" />}
          {state === 'stopped' && <Play className="w-6 h-6" />}
          {state === 'error' && <AlertTriangle className="w-6 h-6" />}
        </div>
        <div className="loop-status-info">
          <div className="loop-status-title">
            {state === 'running' && 'Ejecutando...'}
            {state === 'paused' && 'Pausado'}
            {state === 'stopped' && 'Detenido'}
            {state === 'error' && 'Error'}
          </div>
          <div className="loop-status-stats">
            <span className="loop-status-stat"><strong>{status.hypotheses_generated}</strong> hipótesis</span>
            <span className="loop-status-stat"><CheckCircle className="w-3 h-3 positive" /><strong>{status.hypotheses_passed}</strong> passed</span>
            <span className="loop-status-stat"><XCircle className="w-3 h-3 negative" /><strong>{status.hypotheses_rejected}</strong> rejected</span>
            <span className="loop-status-stat"><Clock className="w-3 h-3" />Última: {lastRun}</span>
          </div>
          {status.last_error && (
            <div style={{ marginTop: '8px', padding: '8px', background: 'var(--danger-dim)', borderRadius: 'var(--radius-sm)', fontSize: '11px', color: 'var(--danger)' }}>
              <AlertTriangle className="w-3 h-3 inline" style={{ marginRight: '4px' }} />
              {status.last_error}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {state !== 'running' && (
            <button className="btn btn-primary" onClick={onRunNow}><Play className="w-4 h-4" /> Ejecutar ahora</button>
          )}
          {state === 'running' && (
            <button className="btn btn-ghost" onClick={onPause}><Pause className="w-4 h-4" /> Pausar</button>
          )}
          {state === 'paused' && (
            <button className="btn btn-primary" onClick={onResume}><RotateCcw className="w-4 h-4" /> Reanudar</button>
          )}
        </div>
      </div>
    </section>
  )
}