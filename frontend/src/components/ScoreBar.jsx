import { useEffect, useRef } from 'react'

function scoreColor(score) {
  if (score <= 30) return 'var(--score-low)'
  if (score <= 60) return 'var(--score-mid)'
  if (score <= 85) return 'var(--score-high)'
  return 'var(--score-crit)'
}

function scoreLabel(score) {
  if (score <= 30) return 'Low'
  if (score <= 60) return 'Moderate'
  if (score <= 85) return 'Significant'
  return 'High'
}

export function ScoreBar({ icon: Icon, label, score, description, animate = true }) {
  const barRef = useRef(null)

  useEffect(() => {
    if (!barRef.current || !animate) return
    // Animate bar width in after mount
    const t = setTimeout(() => {
      if (barRef.current) barRef.current.style.width = `${score}%`
    }, 80)
    return () => clearTimeout(t)
  }, [score, animate])

  const color = scoreColor(score)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {Icon && <Icon size={13} color="var(--text-2)" strokeWidth={1.5} />}
        <span style={{ flex: 1, fontWeight: 500, fontSize: '12px', color: 'var(--text)' }}>{label}</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: '13px', fontWeight: 600, color }}>
          {score}
        </span>
        <span className="tag" style={{
          fontSize: '9px',
          color,
          borderColor: color + '55',
          background: color + '18',
          padding: '1px 5px',
        }}>
          {scoreLabel(score)}
        </span>
      </div>

      {/* Bar */}
      <div style={{ height: '3px', background: 'var(--border-2)', borderRadius: '2px', overflow: 'hidden' }}>
        <div
          ref={barRef}
          style={{
            height: '100%',
            width: animate ? '0%' : `${score}%`,
            background: color,
            borderRadius: '2px',
            transition: 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
            boxShadow: `0 0 8px ${color}66`,
          }}
        />
      </div>

      {/* Description */}
      {description && (
        <p style={{ fontSize: '11px', color: 'var(--text-2)', lineHeight: '1.6', margin: 0 }}>
          {description}
        </p>
      )}
    </div>
  )
}
