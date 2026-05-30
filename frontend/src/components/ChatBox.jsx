import { useState, useEffect, useRef, useCallback } from 'react'
import { Send } from 'lucide-react'
import { createChatSocket } from '../api'

const SUGGESTED = [
  'What is the traffic impact?',
  'Will this raise rents nearby?',
  'How many jobs will this create?',
  'Is this height legal under zoning?',
  'What is the environmental impact?',
]

let sessionCounter = 1

export function ChatBox({ buildingId }) {
  const [messages, setMessages] = useState([
    { role: 'bot', text: 'Hello! Ask me anything about this development — traffic, rent, jobs, zoning, or environmental impact.' }
  ])
  const [input, setInput]     = useState('')
  const [sending, setSending] = useState(false)
  const [connected, setConnected] = useState(false)
  const wsRef      = useRef(null)
  const sessionId  = useRef(sessionCounter++)
  const bottomRef  = useRef(null)

  const connect = useCallback(() => {
    if (wsRef.current) wsRef.current.close()
    const ws = createChatSocket(sessionId.current)
    ws.onopen    = () => setConnected(true)
    ws.onclose   = () => setConnected(false)
    ws.onerror   = () => setConnected(false)
    ws.onmessage = (e) => {
      const { response } = JSON.parse(e.data)
      setMessages(prev => [...prev, { role: 'bot', text: response }])
      setSending(false)
    }
    wsRef.current = ws
  }, [])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = useCallback((text) => {
    const msg = (text || input).trim()
    if (!msg || sending) return
    setMessages(prev => [...prev, { role: 'user', text: msg }])
    setInput('')
    setSending(true)

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ message: msg, building_id: buildingId || undefined }))
    } else {
      // Reconnect and retry
      connect()
      setTimeout(() => {
        wsRef.current?.send(JSON.stringify({ message: msg, building_id: buildingId || undefined }))
      }, 500)
    }
  }, [input, sending, buildingId, connect])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '280px', flexShrink: 0 }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '10px 16px', borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)',
        background: 'var(--bg-2)',
      }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: connected ? 'var(--score-low)' : 'var(--text-3)',
          boxShadow: connected ? '0 0 6px var(--score-low)' : 'none',
          transition: 'all 0.3s',
        }} />
        <span className="label">NeMoTron Assistant</span>
        {!connected && <span style={{ marginLeft: 'auto', fontSize: '10px', color: 'var(--text-3)' }}>Reconnecting...</span>}
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {messages.map((m, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
            <div style={{
              maxWidth: '85%',
              padding: '7px 11px',
              borderRadius: m.role === 'user' ? '10px 10px 2px 10px' : '2px 10px 10px 10px',
              fontSize: '12px',
              lineHeight: '1.55',
              background: m.role === 'user' ? 'var(--cyan-dim)' : 'var(--surface-2)',
              border: `1px solid ${m.role === 'user' ? 'rgba(0,212,255,0.2)' : 'var(--border)'}`,
              color: 'var(--text)',
            }}>
              {m.text}
            </div>
          </div>
        ))}
        {sending && (
          <div style={{ display: 'flex', gap: '4px', padding: '4px 0', alignItems: 'center' }}>
            {[0,1,2].map(i => (
              <div key={i} style={{
                width: 5, height: 5, borderRadius: '50%',
                background: 'var(--text-3)',
                animation: `pulse 1.2s ${i * 0.2}s infinite`,
              }} />
            ))}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      {messages.length < 2 && (
        <div style={{ padding: '0 14px 8px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
          {SUGGESTED.slice(0, 3).map(s => (
            <button key={s} onClick={() => send(s)} style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: '20px',
              color: 'var(--text-2)',
              fontSize: '11px',
              padding: '3px 10px',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => { e.target.style.borderColor = 'var(--cyan)'; e.target.style.color = 'var(--cyan)' }}
            onMouseLeave={e => { e.target.style.borderColor = 'var(--border)'; e.target.style.color = 'var(--text-2)' }}>
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div style={{
        display: 'flex', gap: '8px', padding: '10px 14px',
        borderTop: '1px solid var(--border)', background: 'var(--bg-2)',
      }}>
        <input
          type="text"
          placeholder="Ask about this development..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          disabled={sending}
          style={{ flex: 1, padding: '7px 10px', fontSize: '12px' }}
        />
        <button className="btn btn-primary" onClick={() => send()} disabled={!input.trim() || sending}
          style={{ padding: '7px 12px', flexShrink: 0 }}>
          <Send size={13} />
        </button>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  )
}
