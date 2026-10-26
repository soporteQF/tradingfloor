import { useState, useRef, useEffect } from 'react'
import { Send, Mic, MicOff, Bot, User, Zap, Shield, RotateCcw } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

interface Props {
  onSendCommand: (cmd: any) => void
}

const QUICK_ACTIONS = [
  { label: 'Run nightly now', cmd: { type: 'run_nightly_now' }, icon: RotateCcw },
  { label: 'Kill switch', cmd: { type: 'kill_switch', reason: 'Manual via chat' }, icon: Zap, variant: 'danger' },
  { label: 'Pause nightly', cmd: { type: 'pause_loop' }, icon: Shield },
  { label: 'Resume nightly', cmd: { type: 'resume_loop' }, icon: RotateCcw },
]

export default function ChatPanel({ onSendCommand }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: 'Chief of Staff ready. Nightly loop, paper strategies, and Guardian are monitored. How can I help?', timestamp: new Date() },
  ])
  const [input, setInput] = useState('')
  const [isListening, setIsListening] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    if (!input.trim()) return
    const userMsg = input.trim()
    setMessages(prev => [...prev, { role: 'user', content: userMsg, timestamp: new Date() }])
    setInput('')

    // Simple command parsing
    const lower = userMsg.toLowerCase()
    if (lower.includes('kill') || lower.includes('emergency')) {
      onSendCommand({ type: 'kill_switch', reason: 'Via chat' })
      setMessages(prev => [...prev, { role: 'assistant', content: '🚨 Kill switch activated. All positions will be flattened.', timestamp: new Date() }])
    } else if (lower.includes('run nightly') || lower.includes('nightly now')) {
      onSendCommand({ type: 'run_nightly_now' })
      setMessages(prev => [...prev, { role: 'assistant', content: '🔄 Nightly loop triggered. Running Research → Validation → KG.', timestamp: new Date() }])
    } else if (lower.includes('pause')) {
      onSendCommand({ type: 'pause_loop' })
      setMessages(prev => [...prev, { role: 'assistant', content: '⏸️ Nightly loop paused.', timestamp: new Date() }])
    } else if (lower.includes('resume') || lower.includes('continue')) {
      onSendCommand({ type: 'resume_loop' })
      setMessages(prev => [...prev, { role: 'assistant', content: '▶️ Nightly loop resumed.', timestamp: new Date() }])
    } else if (lower.includes('status') || lower.includes('estado')) {
      setMessages(prev => [...prev, { role: 'assistant', content: '📊 Use the Overview tab for full status. What specific metric do you need?', timestamp: new Date() }])
    } else {
      setMessages(prev => [...prev, { role: 'assistant', content: `Understood. I can execute: kill switch, run nightly, pause/resume. Or ask me about strategies, alerts, performance.`, timestamp: new Date() }])
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleQuickAction = (action: typeof QUICK_ACTIONS[0]) => {
    onSendCommand(action.cmd)
    setMessages(prev => [...prev, { role: 'user', content: action.label, timestamp: new Date() }])
    if (action.cmd.type === 'kill_switch') {
      setMessages(prev => [...prev, { role: 'assistant', content: '🚨 Kill switch activated via quick action.', timestamp: new Date() }])
    } else if (action.cmd.type === 'run_nightly_now') {
      setMessages(prev => [...prev, { role: 'assistant', content: '🔄 Nightly loop triggered via quick action.', timestamp: new Date() }])
    }
  }

  return (
    <div className="chat" style={{ height: 'calc(100vh - 140px)' }}>
      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`chat-message ${msg.role}`}>
            <div className={`chat-avatar ${msg.role === 'assistant' ? 'chief' : 'user'}`}>
              {msg.role === 'assistant' ? <Bot className="w-5 h-5" /> : <User className="w-5 h-5" />}
            </div>
            <div className="chat-bubble">{msg.content}</div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <div className="chat-input-row">
          <input
            type="text"
            className="chat-input"
            placeholder="Type command or ask Chief..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button className="btn btn-primary" onClick={handleSend} disabled={!input.trim()}>
            <Send className="w-4 h-4" />
          </button>
          <button className="btn btn-ghost" onClick={() => { setIsListening(!isListening); }} aria-label={isListening ? 'Stop listening' : 'Start voice input'}>
            {isListening ? <MicOff className="w-5 h-5" style={{ color: 'var(--danger)' }} /> : <Mic className="w-5 h-5" />}
          </button>
        </div>
        <div className="quick-actions">
          {QUICK_ACTIONS.map((action, idx) => (
            <button key={idx} className="quick-action" onClick={() => handleQuickAction(action)} style={{ borderColor: action.variant === 'danger' ? 'var(--danger)' : 'var(--border)' }}>
              <action.icon className="w-3 h-3" style={{ marginRight: '4px', color: action.variant === 'danger' ? 'var(--danger)' : 'inherit' }} />
              {action.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}