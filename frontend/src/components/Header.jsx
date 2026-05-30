import { useEffect, useState } from 'react'
import { Activity, Cpu, Database, Wifi, WifiOff } from 'lucide-react'
import { getHealth } from '../api'
import { ModeSwitcher } from './ModeSwitcher'

export function Header({ buildingCount = 0, mode, onModeChange }) {
  const [health, setHealth]   = useState(null)
  const [online, setOnline]   = useState(null)

  useEffect(() => {
    const check = async () => {
      const h = await getHealth()
      setHealth(h)
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
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginRight: '8px' }}>
        <div style={{
          width: 22, height: 22,
          background: 'var(--nv-green)',
          borderRadius: '4px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '10px', fontWeight: 900, color: '#000',
        }}>UF</div>
        <span style={{ fontWeight: 700, fontSize: '14px', letterSpacing: '-0.02em' }}>
          Urban<span style={{ color: 'var(--cyan)' }}>Forge</span>
        </span>
      </div>

      <div style={{ width: 1, height: 20, background: 'var(--border)' }} />

      {/* Status indicators */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>

        {/* Backend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <div style={{
            width: 5, height: 5, borderRadius: '50%',
            background: online ? '#4ade80' : 'var(--text-3)',
            boxShadow: online ? '0 0 6px #4ade80' : 'none',
            transition: 'all 0.3s',
          }} />
          {online
            ? <Wifi size={11} color="var(--text-3)" />
            : <WifiOff size={11} color="var(--text-3)" />}
          <span style={{ fontSize: '11px', color: 'var(--text-2)' }}>
            {online ? 'Backend live' : 'Backend offline'}
          </span>
        </div>

        {/* DGX Spark */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Cpu size={11} color="var(--cyan)" />
          <span style={{ fontSize: '11px', color: 'var(--text-2)' }}>DGX Spark</span>
          <span className="tag tag-cyan" style={{ fontSize: '9px', padding: '1px 5px' }}>NeMoTron</span>
        </div>

        {/* Models */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Activity size={11} color="var(--text-2)" />
          <span style={{ fontSize: '11px', color: 'var(--text-2)' }}>3 XGBoost models</span>
        </div>

        {/* Spatial layers */}
        {health?.spatial_layers && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Database size={11} color="var(--text-2)" />
            <span style={{ fontSize: '11px', color: 'var(--text-2)' }}>
              {Object.values(health.spatial_layers).filter(Boolean).length} / {Object.keys(health.spatial_layers).length} data layers
            </span>
          </div>
        )}
      </div>

      {/* Right: mode switcher + building count + hackathon badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginLeft: 'auto' }}>
        <ModeSwitcher mode={mode} onChange={onModeChange} />
        {buildingCount > 0 && (
          <span style={{ fontSize: '11px', color: 'var(--text-2)' }}>
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--cyan)', fontWeight: 600 }}>{buildingCount}</span> buildings
          </span>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <div style={{ width: 8, height: 8, borderRadius: '1px', background: 'var(--nv-green)' }} />
          <span style={{ fontSize: '10px', color: 'var(--text-3)', fontWeight: 600, letterSpacing: '0.05em' }}>
            NVIDIA HACKATHON 2026
          </span>
        </div>
      </div>
    </header>
  )
}
