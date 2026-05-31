import { useEffect, useState } from 'react'
import { getHealth } from '../api'
import { ModeSwitcher } from './ModeSwitcher'

export function Header({ buildingCount = 0, mode, onModeChange, onLoginClick }) {
  const [online, setOnline] = useState(null)

  useEffect(() => {
    const check = async () => {
      const h = await getHealth()
      setOnline(h !== null)
    }
    check()
    const interval = setInterval(check, 15000)
    return () => clearInterval(interval)
  }, [])

  return (
    <header style={{
      height: 44,
      background: 'var(--bg-3)',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 16px',
      gap: '16px',
      flexShrink: 0,
      zIndex: 20,
    }}>
      {/* Logo — clicking reloads back to main screen */}
      <div
        onClick={() => window.location.reload()}
        style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}
      >
        <div style={{
          width: 26, height: 26,
          background: 'var(--nv-green)',
          borderRadius: '4px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '12px', fontWeight: 900, color: '#000',
        }}>UF</div>
        <span style={{ fontWeight: 700, fontSize: '15px', letterSpacing: '-0.02em' }}>
          Urban<span style={{ color: 'var(--cyan)' }}>Forge</span>
        </span>
        {/* Online dot */}
        <div style={{
          width: 5, height: 5, borderRadius: '50%',
          background: online ? '#4ade80' : 'var(--text-3)',
          boxShadow: online ? '0 0 6px #4ade80' : 'none',
          transition: 'all 0.3s',
        }} />
      </div>

      <div style={{ width: 1, height: 20, background: 'var(--border)' }} />

      {/* NVIDIA / Antler badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        <div style={{ width: 8, height: 8, borderRadius: '1px', background: 'var(--nv-green)' }} />
        <span style={{ fontSize: '10px', color: 'var(--text-3)', fontWeight: 600, letterSpacing: '0.04em' }}>
          NVIDIA / Antler Hackathon 2026
        </span>
      </div>

      {/* Flex spacer */}
      <div style={{ flex: 1 }} />

      {/* Right: building count, mode switcher, login */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {buildingCount > 0 && (
          <span style={{ fontSize: '11px', color: 'var(--text-2)' }}>
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)', fontWeight: 600 }}>{buildingCount}</span> buildings
          </span>
        )}
        <ModeSwitcher mode={mode} onChange={onModeChange} />
        <LoginButton onClick={onLoginClick} />
      </div>
    </header>
  )
}

function LoginButton({ onClick }) {
  const [hovered, setHovered] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        padding: '5px 14px',
        fontSize: '11px',
        fontWeight: 600,
        border: `1px solid ${hovered ? 'var(--cyan)' : 'var(--border-2)'}`,
        borderRadius: 'var(--radius)',
        background: 'transparent',
        color: hovered ? 'var(--cyan)' : 'var(--text-2)',
        cursor: 'pointer',
        transition: 'border-color 0.15s, color 0.15s',
      }}
    >
      Login
    </button>
  )
}
