import { AlertTriangle, AlertCircle, Shield, Info } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface Props {
  alerts: any[]
}

const SEVERITY_ICONS: Record<string, React.ReactNode> = {
  critical: <AlertTriangle className="w-4 h-4" />,
  warning: <AlertCircle className="w-4 h-4" />,
  info: <Info className="w-4 h-4" />,
}

const SEVERITY_CLASSES: Record<string, string> = {
  critical: 'alert-critical',
  warning: 'alert-warning',
  info: 'alert-info',
}

export default function GuardianAlertsPanel({ alerts }: Props) {
  if (alerts.length === 0) {
    return (
      <section className="section">
        <div className="section-title"><h2>Guardian Alerts</h2><span className="count">0</span></div>
        <div className="empty" style={{ padding: '60px 16px' }}>
          <Shield className="w-16 h-16 mx-auto" style={{ opacity: 0.3 }} />
          <p>Sin alertas de Guardian</p>
          <p style={{ fontSize: '12px', marginTop: '8px', opacity: 0.6 }}>Los límites de riesgo están bajo control</p>
        </div>
      </section>
    )
  }

  return (
    <section className="section">
      <div className="section-title"><h2>Guardian Alerts</h2><span className="count">{alerts.length}</span></div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}>
        {alerts.slice().reverse().map((alert, idx) => (
          <div key={idx} className={`alert ${SEVERITY_CLASSES[alert.severity] || 'alert-warning'}`}>
            <div className="alert-icon" style={{ color: 'inherit' }}>
              {SEVERITY_ICONS[alert.severity] || SEVERITY_ICONS.warning}
            </div>
            <div className="alert-content">
              <div className="alert-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{alert.guard_name.replace(/_/g, ' ')}</span>
                <span style={{ fontSize: '10px', opacity: 0.7, fontWeight: 500, textTransform: 'uppercase' }}>
                  {alert.action}
                </span>
                {alert.symbol && (
                  <span style={{ fontSize: '10px', color: 'var(--accent)', fontWeight: 600 }}>
                    {alert.symbol}
                  </span>
                )}
              </div>
              <div className="alert-message">{alert.message}</div>
            </div>
            <div className="alert-time">{formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true })}</div>
          </div>
        ))}
      </div>
    </section>
  )
}