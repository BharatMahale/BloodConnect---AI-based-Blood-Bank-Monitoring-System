import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, sessionStore } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => sessionStore.get()?.user || null)
  const [loading, setLoading] = useState(Boolean(sessionStore.get()?.access))

  const restore = useCallback(async () => {
    if (!sessionStore.get()?.access) { setLoading(false); return }
    try {
      const current = await api('auth/me/')
      const session = sessionStore.get()
      if (session) sessionStore.set({ ...session, user: current })
      setUser(current)
    } catch (error) {
      if (!error.isNetworkError && (error.status === 401 || error.status === 403)) setUser(null)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { restore(); const handler = () => { if (!sessionStore.get()) setUser(null) }; window.addEventListener('bloodconnect:session', handler); return () => window.removeEventListener('bloodconnect:session', handler) }, [restore])

  const authenticate = (data) => {
    const tokens = data.tokens || data
    const nextUser = data.user
    sessionStore.set({ access: tokens.access, refresh: tokens.refresh, user: nextUser })
    setUser(nextUser)
  }
  const logout = async () => {
    const session = sessionStore.get()
    try { if (session?.refresh) await api('auth/logout/', { method: 'POST', body: JSON.stringify({ refresh: session.refresh }) }) } catch { /* local logout remains available */ }
    sessionStore.set(null); setUser(null)
  }
  const value = useMemo(() => ({ user, loading, authenticate, logout, refreshUser: restore, isStaff: Boolean(user?.roles?.some((r) => ['ADMIN', 'BLOOD_BANK_STAFF'].includes(r))) }), [user, loading, restore])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
