import { lazy, Suspense, useState } from 'react'
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'

const routePages = () => import('./RoutePages')
const lazyPage = (name) => lazy(() => routePages().then((module) => ({ default: module[name] })))

const Home = lazyPage('Home')
const AuthPage = lazyPage('AuthPage')
const Banks = lazyPage('Banks')
const BankDetail = lazyPage('BankDetail')
const Requests = lazyPage('Requests')
const RequestForm = lazyPage('RequestForm')
const RequestDetail = lazyPage('RequestDetail')
const Dashboard = lazyPage('Dashboard')
const Notifications = lazyPage('Notifications')
const Donor = lazyPage('Donor')
const Workspace = lazyPage('Workspace')

function Spinner({ label = 'Loading page' }) {
  return <div className="state" role="status"><span className="spinner" aria-hidden="true" /> <span>{label}…</span></div>
}

function Layout({ children }) {
  const { user, logout, isStaff } = useAuth()
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const nav = [['/', 'Home'], ['/banks', 'Find Blood Banks'], ['/requests', 'My Requests'], ['/donor', 'Donor Profile'], ['/dashboard', 'Dashboard']]
  return <div className="site-shell">
    <a className="skip" href="#main">Skip to content</a>
    <header className="header"><div className="nav-wrap">
      <Link className="brand" to="/"><span className="brand-mark" aria-hidden="true">♥</span><span>Blood<span>Connect</span></span></Link>
      <button className="menu-button" aria-label="Toggle menu" aria-expanded={open} onClick={() => setOpen(!open)}>☰</button>
      <nav className={open ? 'nav open' : 'nav'} aria-label="Primary navigation">
        {nav.map(([to, label]) => <NavLink key={to} to={to} onClick={() => setOpen(false)}>{label}</NavLink>)}
        {isStaff && <NavLink to="/workspace" onClick={() => setOpen(false)}>Bank Workspace</NavLink>}
      </nav>
      <div className="account-actions">
        {user ? <><Link className="icon-link" to="/notifications" aria-label="Notifications">◉ <span>Notifications</span></Link><button className="text-button" onClick={async () => { await logout(); navigate('/') }}>Log out</button></> : <><Link className="text-button" to="/login">Log in</Link><Link className="button small" to="/register">Create account</Link></>}
      </div>
    </div></header>
    <main id="main" tabIndex={-1}>{children}</main>
    <footer><div><Link className="brand footer-brand" to="/"><span className="brand-mark">♥</span>BloodConnect</Link><p>Helping people find verified blood-bank information and coordinate urgent requests.</p></div><div><strong>Important</strong><p>Availability can change. Always confirm directly with the blood bank or hospital. This service does not replace emergency medical services.</p></div></footer>
  </div>
}

function Protected({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Spinner label="Restoring your session" />
  return user ? children : <Navigate to="/login" state={{ from: location }} replace />
}

function NotFound() {
  return <div className="page"><div className="empty"><span className="empty-icon">○</span><h3>Page not found</h3><p><Link to="/">Return home</Link></p></div></div>
}

export default function App() {
  return <Layout><Suspense fallback={<Spinner />}><Routes>
    <Route path="/" element={<Home />} />
    <Route path="/login" element={<AuthPage />} />
    <Route path="/register" element={<AuthPage register />} />
    <Route path="/banks" element={<Banks />} />
    <Route path="/banks/:slug" element={<BankDetail />} />
    <Route path="/requests" element={<Protected><Requests /></Protected>} />
    <Route path="/requests/new" element={<Protected><RequestForm /></Protected>} />
    <Route path="/requests/:id" element={<Protected><RequestDetail /></Protected>} />
    <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
    <Route path="/notifications" element={<Protected><Notifications /></Protected>} />
    <Route path="/donor" element={<Protected><Donor /></Protected>} />
    <Route path="/workspace" element={<Protected><Workspace /></Protected>} />
    <Route path="*" element={<NotFound />} />
  </Routes></Suspense></Layout>
}
