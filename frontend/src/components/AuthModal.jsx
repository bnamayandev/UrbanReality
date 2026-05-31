import { useState } from 'react'
import { X, Building2, User, Loader2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function AuthModal({ onClose }) {
  const { signIn, signUp } = useAuth()

  const [tab,      setTab]      = useState('login')   // 'login' | 'signup'
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [role,     setRole]     = useState('public')  // 'public' | 'org_admin'
  const [orgName,  setOrgName]  = useState('')
  const [busy,     setBusy]     = useState(false)
  const [error,    setError]    = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (tab === 'login') {
        await signIn(email, password)
      } else {
        if (role !== 'public' && !orgName.trim()) {
          setError('Organization name is required.')
          setBusy(false)
          return
        }
        await signUp(email, password, role, orgName.trim() || undefined)
      }
      onClose()
    } catch (err) {
      setError(err.message || 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={styles.modal}>
        {/* Close */}
        <button style={styles.closeBtn} onClick={onClose}><X size={16} /></button>

        {/* Tab switcher */}
        <div style={styles.tabs}>
          {['login', 'signup'].map(t => (
            <button
              key={t}
              style={{ ...styles.tab, ...(tab === t ? styles.tabActive : {}) }}
              onClick={() => { setTab(t); setError('') }}
            >
              {t === 'login' ? 'Log in' : 'Sign up'}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@example.com"
            style={styles.input}
          />

          <label style={styles.label}>Password</label>
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="••••••••"
            style={styles.input}
          />

          {/* Role selector — only on signup */}
          {tab === 'signup' && (
            <>
              <label style={styles.label}>Account type</label>
              <div style={styles.roleRow}>
                <button
                  type="button"
                  onClick={() => setRole('public')}
                  style={{ ...styles.roleBtn, ...(role === 'public' ? styles.roleBtnActive : {}) }}
                >
                  <User size={14} style={{ marginRight: 6 }} />
                  General public
                </button>
                <button
                  type="button"
                  onClick={() => setRole('org_admin')}
                  style={{ ...styles.roleBtn, ...(role === 'org_admin' ? styles.roleBtnActive : {}) }}
                >
                  <Building2 size={14} style={{ marginRight: 6 }} />
                  Builder / Org
                </button>
              </div>

              {role === 'org_admin' && (
                <>
                  <label style={styles.label}>Organization name</label>
                  <input
                    type="text"
                    required
                    value={orgName}
                    onChange={e => setOrgName(e.target.value)}
                    placeholder="e.g. Maple Construction Inc."
                    style={styles.input}
                  />
                  <p style={styles.hint}>
                    Creates a new org or joins an existing one with this exact name.
                  </p>
                </>
              )}
            </>
          )}

          {error && <p style={styles.errorMsg}>{error}</p>}

          <button type="submit" disabled={busy} style={styles.submitBtn}>
            {busy
              ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
              : tab === 'login' ? 'Log in' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  )
}

const styles = {
  overlay: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,0.7)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000,
  },
  modal: {
    background: 'var(--bg-3)',
    border: '1px solid var(--border-2)',
    borderRadius: 10,
    padding: '28px 28px 24px',
    width: 360,
    position: 'relative',
  },
  closeBtn: {
    position: 'absolute', top: 12, right: 12,
    background: 'none', border: 'none',
    color: 'var(--text-2)', cursor: 'pointer',
    display: 'flex', alignItems: 'center',
  },
  tabs: {
    display: 'flex', gap: 4,
    marginBottom: 20,
    borderBottom: '1px solid var(--border)',
    paddingBottom: 12,
  },
  tab: {
    background: 'none', border: 'none',
    color: 'var(--text-2)', cursor: 'pointer',
    fontSize: 14, fontWeight: 500, paddingBottom: 4,
    borderBottom: '2px solid transparent',
  },
  tabActive: {
    color: 'var(--cyan)',
    borderBottom: '2px solid var(--cyan)',
  },
  form: { display: 'flex', flexDirection: 'column', gap: 10 },
  label: {
    fontSize: 10, fontWeight: 600,
    textTransform: 'uppercase', letterSpacing: '0.1em',
    color: 'var(--text-2)',
  },
  input: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 6, padding: '8px 10px',
    color: 'var(--text)', fontSize: 13, width: '100%',
    outline: 'none',
  },
  roleRow: { display: 'flex', gap: 8 },
  roleBtn: {
    flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 6, padding: '8px 12px',
    color: 'var(--text-2)', cursor: 'pointer', fontSize: 12,
  },
  roleBtnActive: {
    border: '1px solid var(--cyan)',
    color: 'var(--cyan)',
    background: 'var(--cyan-dim)',
  },
  hint: { fontSize: 11, color: 'var(--text-3)', marginTop: -4 },
  errorMsg: { color: '#f87171', fontSize: 12, marginTop: -4 },
  submitBtn: {
    marginTop: 6,
    background: 'var(--cyan)',
    color: '#000', fontWeight: 600, fontSize: 13,
    border: 'none', borderRadius: 6,
    padding: '10px', cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
}
