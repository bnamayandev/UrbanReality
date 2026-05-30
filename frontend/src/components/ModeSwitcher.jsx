import { Building2, Users } from 'lucide-react'

export function ModeSwitcher({ mode, onChange }) {
  return (
    <div style={{
      display: 'flex',
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '6px',
      padding: '3px',
      gap: '2px',
    }}>
      <ModeBtn
        active={mode === 'builder'}
        onClick={() => onChange('builder')}
        icon={<Building2 size={12} />}
        label="Developer"
        title="Developer / Architect mode — place and analyze buildings"
      />
      <ModeBtn
        active={mode === 'citizen'}
        onClick={() => onChange('citizen')}
        icon={<Users size={12} />}
        label="Citizen"
        title="Citizen mode — explore existing developments"
      />
    </div>
  )
}

function ModeBtn({ active, onClick, icon, label, title }) {
  return (
    <button
      title={title}
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: '5px',
        padding: '4px 10px',
        border: 'none',
        borderRadius: '4px',
        cursor: 'pointer',
        fontSize: '11px',
        fontWeight: active ? 600 : 400,
        fontFamily: 'var(--font)',
        transition: 'all 0.15s',
        background: active ? 'var(--cyan)' : 'transparent',
        color: active ? '#000' : 'var(--text-2)',
      }}
    >
      {icon}
      {label}
    </button>
  )
}
