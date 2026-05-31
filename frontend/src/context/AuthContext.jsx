import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { registerUser, getMe, setAuthToken } from '../api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session,  setSession]  = useState(null)   // Supabase session
  const [profile,  setProfile]  = useState(null)   // { id, email, role, org_id, org_name }
  const [loading,  setLoading]  = useState(true)

  // Load any existing session on mount and subscribe to auth changes
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      _applySession(data.session)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      _applySession(s)
    })
    return () => subscription.unsubscribe()
  }, [])

  async function _applySession(s) {
    setSession(s)
    if (s?.access_token) {
      setAuthToken(s.access_token)
      try {
        const me = await getMe()
        setProfile(me)
      } catch {
        // User exists in Supabase but not yet in app DB (mid-registration) — ignore
        setProfile(null)
      }
    } else {
      setAuthToken(null)
      setProfile(null)
    }
    setLoading(false)
  }

  async function signIn(email, password) {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
    return data
  }

  async function signUp(email, password, role, orgName) {
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) throw error

    // Register user in the app database after Supabase signup
    const appUser = await registerUser({
      id:       data.user.id,
      email:    data.user.email,
      role:     role || 'public',
      org_name: orgName || undefined,
    })
    setProfile(appUser)
    return data
  }

  async function signOut() {
    await supabase.auth.signOut()
    setProfile(null)
    setSession(null)
    setAuthToken(null)
  }

  const isOrgUser = profile?.role === 'org_member' || profile?.role === 'org_admin'

  return (
    <AuthContext.Provider value={{ session, profile, loading, isOrgUser, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
