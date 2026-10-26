import { useState } from 'react'
import { Menu, X, Bot, AlertTriangle, Activity, Zap, RotateCcw, Volume2, VolumeX } from 'lucide-react'
import { useChiefStatus } from './hooks/useChiefStatus'
import NightlyLoopCard from './components/NightlyLoopCard'
import PaperStrategiesPanel from './components/PaperStrategiesPanel'
import GuardianAlertsPanel from './components/GuardianAlertsPanel'
import GuardianStatusCard from './components/GuardianStatusCard'
import ChatPanel from './components/ChatPanel'
import ConfirmModal from './components/ConfirmModal'

type Tab = 'overview' | 'strategies' | 'alerts' | 'chat'

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'overview', label: 'Overview', icon: <Activity className="w-4 h-4" /> },
  { id: 'strategies', label: 'Strategies', icon: <Zap className="w-4 h-4" /> },
  { id: 'alerts', label: 'Alerts', icon: <AlertTriangle className="w-4 h-4" /> },
  { id: 'chat', label: 'Chief', icon: <Bot className="w-4 h-4" /> },
]

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [modal, setModal] = useState<{ type: string; data?: any } | null>(null)
  const [ttsEnabled, setTtsEnabled] = useState(true)

  const { status, sendCommand, refresh } = useChiefStatus(ttsEnabled)

  const handleCommand = (type: string, data?: any) => {
    if (type === 'kill_switch' || type === 'retire') {
      setModal({ type, data })
    } else {
      sendCommand({ type, ...data })
    }
  }

  const confirmModal = () => {
    if (!modal) return null
    const { type, data } = modal
    if (type === 'kill_switch') {
      return (
        <ConfirmModal
          title="Activar Kill Switch"
          message="Esto aplanará TODAS las posiciones abiertas y bloqueará nueva operativa. ¿Confirmar?"
          onConfirm={() => { sendCommand({ type: 'kill_switch', reason: 'Manual by Chief' }); setModal(null); }}
          onCancel={() => setModal(null)}
          confirmText="Activar Kill Switch"
          confirmVariant="danger"
        />
      )
    }
    if (type === 'retire') {
      return (
        <ConfirmModal
          title={`Retirar ${data?.name || 'estrategia'}`}
          message={`¿Seguro que quieres retirar "${data?.name}"? Se cerrarán posiciones y no volverá a operar.`}
          onConfirm={() => { sendCommand({ type: 'retire', strategy_id: data?.strategy_id, reason: 'Retired by Chief' }); setModal(null); }}
          onCancel={() => setModal(null)}
          confirmText="Retirar"
          confirmVariant="danger"
        />
      )
    }
    return null
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <button className="btn btn-ghost btn-icon" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle sidebar">
            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          <div className="logo">
            <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="50" cy="50" r="45" stroke="currentColor" strokeWidth="2"/>
              <path d="M30 50 L45 65 L70 35" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span className="logo-text">CHIEF OF STAFF</span>
          </div>
          <span className={`badge ${status?.nightly?.state === 'running' ? 'badge-running' : status?.nightly?.state === 'paused' ? 'badge-paused' : status?.nightly?.state === 'error' ? 'badge-error' : 'badge-stopped'}`}>
            {status?.nightly?.state || 'stopped'}
          </span>
        </div>
        <div className="header-right">
          <button className="btn btn-ghost btn-icon" onClick={() => setTtsEnabled(!ttsEnabled)} aria-label={ttsEnabled ? 'Desactivar voz' : 'Activar voz'}>
            {ttsEnabled ? <Volume2 className="w-5 h-5" /> : <VolumeX className="w-5 h-5" />}
          </button>
          <button className="btn btn-ghost btn-icon" onClick={() => refresh()} aria-label="Actualizar">
            <RotateCcw className="w-5 h-5" />
          </button>
        </div>
      </header>

      <div className="main">
        <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
          <nav style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`btn btn-ghost ${activeTab === tab.id ? 'btn-primary' : ''}`}
                style={{ justifyContent: 'flex-start', borderRadius: 'var(--radius)' }}
              >
                {tab.icon}
                <span style={{ marginLeft: '8px' }}>{tab.label}</span>
              </button>
            ))}
          </nav>
        </aside>

        <main className="content">
          {activeTab === 'overview' && (
            <>
              <NightlyLoopCard status={status?.nightly} onRunNow={() => handleCommand('run_nightly_now')} onPause={() => handleCommand('pause_loop')} onResume={() => handleCommand('resume_loop')} />
              <GuardianStatusCard guardian={status?.guardian_status} onKillSwitch={() => handleCommand('kill_switch')} />
              <section className="section">
                <div className="section-title"><h2>Paper Strategies</h2><span className="count">{Object.keys(status?.paper_strategies || {}).length} active</span></div>
                {Object.keys(status?.paper_strategies || {}).length === 0 ? (
                  <div className="empty"><Activity className="w-12 h-12 mx-auto" />No hay estrategias en paper trading</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {Object.values(status?.paper_strategies || {}).slice(0, 3).map(s => (
                      <PaperStrategyCard key={s.strategy_id} strategy={s} onPromote={() => handleCommand('promote', { strategy_id: s.strategy_id })} onRetire={() => handleCommand('retire', { strategy_id: s.strategy_id, name: s.name })} />
                    ))}
                    {Object.keys(status?.paper_strategies || {}).length > 3 && (
                      <button className="btn btn-ghost" onClick={() => setActiveTab('strategies')} style={{ marginTop: '8px', width: '100%' }}>
                        Ver todas las {Object.keys(status?.paper_strategies || {}).length} estrategias →
                      </button>
                    )}
                  </div>
                )}
              </section>
            </>
          )}

          {activeTab === 'strategies' && <PaperStrategiesPanel strategies={status?.paper_strategies || {}} onPromote={handleCommand} onRetire={handleCommand} />}

          {activeTab === 'alerts' && <GuardianAlertsPanel alerts={status?.guardian_alerts || []} />}

          {activeTab === 'chat' && <ChatPanel onSendCommand={handleCommand} />}

          {confirmModal()}
        </main>
      </div>

      {sidebarOpen && (
        <div className="modal-overlay" onClick={() => setSidebarOpen(false)} style={{ background: 'transparent' }} />
      )}
    </div>
  )
}

function PaperStrategyCard({ strategy, onPromote, onRetire }: { strategy: any; onPromote: () => void; onRetire: () => void }) {
  const pnl = (strategy.unrealized_pnl || 0) + (strategy.realized_pnl || 0)
  const pnlClass = pnl >= 0 ? 'positive' : 'negative'
  return (
    <div className="card">
      <div className="card-title">
        <h3>{strategy.name}</h3>
        <span className={`status-dot ${strategy.state === 'paper' ? 'status-running' : strategy.state === 'validated' ? 'status-paused' : 'status-stopped'}`} />
      </div>
      <div className="card-meta">
        <span>{strategy.symbol} {strategy.timeframe}</span>
        <span>{strategy.regime}</span>
        <span>{strategy.trades_today} trades</span>
      </div>
      <div className="metric"><span className="metric-label">Equity</span><span className="metric-value mono">${strategy.equity.toLocaleString()}</span></div>
      <div className="metric"><span className="metric-label">PnL</span><span className={`metric-value mono ${pnlClass}`}>{pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}</span></div>
      <div className="metric"><span className="metric-label">Win Rate</span><span className="metric-value mono">{(strategy.win_rate * 100).toFixed(1)}%</span></div>
      <div className="metric"><span className="metric-label">Slippage</span><span className="metric-value mono">{strategy.avg_fill_slippage_bps?.toFixed(1) || 0} bps</span></div>
      <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
        <button className="btn btn-primary" style={{ flex: 1 }} onClick={onPromote} disabled={strategy.state === 'paper'}>Promover a Paper</button>
        <button className="btn btn-danger" style={{ flex: 1 }} onClick={onRetire}>Retirar</button>
      </div>
    </div>
  )
}

export default App