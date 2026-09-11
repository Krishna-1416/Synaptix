import { useEffect, useMemo, useRef, useState } from 'react'
import { Document as WordDocument, HeadingLevel, ImageRun, Packer, Paragraph, Table, TableCell, TableRow, TextRun } from 'docx'
import {
  Activity, ArrowLeft, ArrowUpRight, BarChart3, Bell, Camera, Check, CheckCircle2, ChevronRight, CircleHelp,
  ClipboardCheck, Edit3, Eye, FileText, History, ImagePlus, Layers, LayoutDashboard, LoaderCircle,
  LockKeyhole, LogOut, Mail, Menu, Moon, Save, ScanLine, Search, Settings, ShieldCheck,
  SlidersHorizontal, StopCircle, Sun, SwitchCamera, UploadCloud, UserRound, X, XCircle,
  ExternalLink, Send, Paperclip, BookOpen, AlertTriangle, Download
} from 'lucide-react'
import { api, demoInspections } from './api'
import { demoStats } from './demoData'

const navItems = [
  { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
  { id: 'scan', label: 'New inspection', icon: ImagePlus },
  { id: 'history', label: 'Inspection history', icon: History },
  { id: 'enforcement', label: 'Enforcement', icon: ShieldCheck }
]

const statusMeta = {
  PASS: { label: 'Compliant', className: 'pass', icon: Check },
  FAIL: { label: 'Non-compliant', className: 'fail', icon: X },
  REVIEW: { label: 'Needs review', className: 'review', icon: CircleHelp }
}

let activeInspectionProgress = { extract: 'pending', check: 'pending', decide: 'pending', message: '' }

function normalizeStats(stats = {}) {
  return {
    total: stats.total ?? stats.total_inspections ?? stats.inspections_count ?? demoStats.total_inspections,
    pass: stats.compliant ?? stats.passed ?? stats.pass_count ?? stats.compliant_count ?? demoStats.compliant,
    fail: stats.non_compliant ?? stats.failed ?? stats.fail_count ?? stats.violations_count ?? demoStats.non_compliant,
    review: stats.review ?? stats.review_count ?? demoStats.review,
    rate: stats.compliance_rate ?? stats.compliance_rate_pct ?? stats.complianceRate ?? demoStats.compliance_rate,
    alerts: stats.recent_alerts ?? stats.alerts ?? stats.total_violations_flagged ?? demoStats.recent_alerts
  }
}

function formatDate(value) {
  if (!value) return 'Date unavailable'
  return new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function isAdmin(user) {
  return ['admin', 'administrator'].includes(String(user?.role || '').toLowerCase())
}

function displayRole(user) {
  return isAdmin(user) ? 'Administrator' : 'User'
}

function initials(user) {
  return (user?.full_name || 'User').split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()
}

function percentage(value, fallback = null) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? Math.max(0, Math.min(100, Math.round(numeric <= 1 ? numeric * 100 : numeric))) : fallback
}

function inspectionOwnerId(user) {
  return user?.id || user?.user_id || user?.email || 'demo-user'
}

function createDemoInspection({ file, productName, category, user }) {
  const imageUrl = URL.createObjectURL(file)
  const sample = demoInspections.find((inspection) => inspection.compliance?.status === 'FAIL') || demoInspections[0]
  return {
    ...sample,
    inspection_id: `SYN-${Date.now().toString().slice(-6)}`,
    user_id: inspectionOwnerId(user),
    created_at: new Date().toISOString(),
    image_url: imageUrl,
    product: { name: productName || sample.product?.name, category: category || sample.product?.category }
  }
}

function asRule(item) {
  return typeof item === 'string' ? { name: item } : { name: item?.name || item?.label || item?.rule || item?.rule_id, reason: item?.reason || item?.message }
}

function inspectionRules(inspection) {
  const compliance = inspection?.compliance || {}
  const outcomes = inspection?.rule_results || compliance.rule_results || []
  if (Array.isArray(outcomes) && outcomes.length) {
    return outcomes.reduce((summary, outcome) => {
      const state = String(outcome.status || outcome.result || '').toUpperCase()
      const rule = asRule(outcome)
      if (!rule.name) return summary
      if (state === 'PASS') summary.obeyed.push(rule)
      else if (state === 'FAIL') summary.notObeyed.push(rule)
      else summary.review.push(rule)
      return summary
    }, { obeyed: [], notObeyed: [], review: [] })
  }
  const obeyed = (inspection?.rules_obeyed || []).map(asRule).filter((rule) => rule.name)
  const unresolved = (inspection?.rules_review || compliance.rules_review || []).map(asRule).filter((rule) => rule.name)
  const violations = (inspection?.rules_not_obeyed || compliance.violations || []).map(asRule).filter((rule) => rule.name)
  return { obeyed, notObeyed: compliance.status === 'REVIEW' ? [] : violations, review: compliance.status === 'REVIEW' ? (unresolved.length ? unresolved : violations) : unresolved }
}

function inspectionScore(inspection, rules) {
  const value = inspection?.compliance?.score ?? inspection?.compliance?.percentage ?? inspection?.compliance_percentage
  const direct = percentage(value)
  if (direct != null) return direct
  const hasRuleOutcomes = Array.isArray(inspection?.rule_results) || Array.isArray(inspection?.compliance?.rule_results) || Array.isArray(inspection?.rules_obeyed) || Array.isArray(inspection?.rules_not_obeyed) || Array.isArray(inspection?.rules_review)
  if (!hasRuleOutcomes) return null
  const total = rules.obeyed.length + rules.notObeyed.length + rules.review.length
  return total ? Math.round((rules.obeyed.length / total) * 100) : null
}

function inspectionConfidence(inspection) {
  const direct = percentage(inspection?.compliance?.confidence ?? inspection?.confidence ?? inspection?.confidence_percentage)
  if (direct != null) return direct
  const values = (inspection?.ocr_raw?.texts || []).map((item) => Number(item.confidence)).filter(Number.isFinite)
  return values.length ? Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 100) : null
}

function StatusBadge({ status }) {
  const meta = statusMeta[status] || statusMeta.REVIEW
  const Icon = meta.icon
  return <span className={`status-badge ${meta.className}`}><Icon size={13} strokeWidth={2.5} />{meta.label}</span>
}

function ThemeToggle({ theme, onToggle, compact = false }) {
  const isDark = theme === 'dark'
  return <button className={`theme-toggle ${compact ? 'compact' : ''}`} onClick={onToggle} aria-label={`Switch to ${isDark ? 'light' : 'dark'} mode`}><span className="theme-toggle-icon">{isDark ? <Sun size={15} /> : <Moon size={15} />}</span>{!compact && <span>{isDark ? 'Light mode' : 'Dark mode'}</span>}</button>
}

function EntryFlow({ onAuthenticated, theme, onToggleTheme }) {
  const [screen, setScreen] = useState('splash')
  useEffect(() => {
    const timer = window.setTimeout(() => setScreen('welcome'), 1700)
    return () => window.clearTimeout(timer)
  }, [])
  if (screen === 'splash') return <Splash />
  if (screen === 'welcome') return <Welcome onNext={() => setScreen('portal')} theme={theme} onToggleTheme={onToggleTheme} />
  if (screen === 'portal') return <PortalSelection onSelect={() => setScreen('login')} onBack={() => setScreen('welcome')} theme={theme} onToggleTheme={onToggleTheme} />
  return <Auth onBack={() => setScreen('portal')} onAuthenticated={onAuthenticated} theme={theme} onToggleTheme={onToggleTheme} />
}

function Splash() {
  return <div className="entry-screen splash-screen"><div className="splash-orbit orbit-one" /><div className="splash-orbit orbit-two" /><div className="splash-content"><div className="splash-mark"><ShieldCheck size={31} /></div><div className="splash-wordmark">synaptix<span>field intelligence</span></div><div className="splash-loader"><i /><i /><i /></div></div><div className="splash-foot">SIH26034 · LEGAL METROLOGY OPERATIONS</div></div>
}

function EntryHeader({ theme, onToggleTheme, onBack }) {
  return <header className="entry-header"><div className="entry-brand"><span className="entry-brand-mark"><ShieldCheck size={17} /></span><strong>synaptix</strong></div><div className="entry-header-actions">{onBack && <button className="entry-back" onClick={onBack}><ArrowLeft size={15} /> Back</button>}<ThemeToggle theme={theme} onToggle={onToggleTheme} compact /></div></header>
}

function Welcome({ onNext, theme, onToggleTheme }) {
  return <div className="entry-screen welcome-screen"><EntryHeader theme={theme} onToggleTheme={onToggleTheme} /><div className="welcome-content"><div className="welcome-copy"><div className="entry-eyebrow"><span /> INSPECTION INTELLIGENCE / 01</div><h1>Clarity for every<br /><em>compliant</em> label.</h1><p>Synaptix turns a package photograph into a clear, defensible compliance decision for the officers who keep commerce honest.</p><button className="button entry-cta" onClick={onNext}>Enter the workspace <ArrowUpRight size={17} /></button><div className="welcome-meta"><span><ShieldCheck size={15} /> Rule 6 aware</span><span><Activity size={15} /> OCR + vision pipeline</span></div></div><div className="welcome-art"><div className="art-grid" /><div className="label-card"><div className="label-card-top"><span>PRODUCT LABEL</span><ShieldCheck size={17} /></div><div className="label-card-title">Harvest<br /><strong>Gold</strong></div><div className="label-card-line" /><div className="label-card-details"><span>NET QTY</span><strong>5 kg</strong><span>MRP</span><strong>Rs. 640.00</strong></div><div className="scan-line" /></div><div className="art-note note-one"><span>01</span><strong>OCR extraction</strong><small>Every declaration, found.</small></div><div className="art-note note-two"><span>02</span><strong>Rule validation</strong><small>Every decision, traceable.</small></div></div></div><div className="entry-footer"><span>Built for enforcement teams</span><span>Scroll to inspect <ChevronRight size={14} /></span></div></div>
}

function PortalSelection({ onSelect, onBack, theme, onToggleTheme }) {
  return <div className="entry-screen portal-screen"><EntryHeader theme={theme} onToggleTheme={onToggleTheme} onBack={onBack} /><div className="portal-layout"><div className="portal-content"><div className="entry-eyebrow"><span /> YOUR WORKSPACE / 02</div><h1>Choose your<br /><em>workspace.</em></h1><p className="portal-intro">Open the Synaptix workspace for your inspection work.</p><div className="portal-grid"><button className="portal-card selected" onClick={onSelect}><div className="portal-card-icon"><ShieldCheck size={23} /></div><div className="portal-card-copy"><span>For field teams</span><h2>Inspector portal</h2><p>Scan labels, review declarations, and issue compliance certificates.</p></div><span className="portal-arrow"><ArrowUpRight size={18} /></span><div className="portal-card-caption">Recommended for you</div></button></div><div className="portal-help"><CircleHelp size={16} /><span>Your account will open the inspection workspace automatically.</span></div></div><PortalVisual /></div></div>
}

function PortalVisual() {
  return <div className="portal-visual" aria-hidden="true"><div className="visual-orbit visual-orbit-one" /><div className="visual-orbit visual-orbit-two" /><div className="inspection-sheet"><div className="sheet-header"><span>LABEL / 0248</span><ShieldCheck size={16} /></div><div className="sheet-brand">Harvest <em>Gold</em></div><div className="sheet-copy"><i /><i /><i /></div><div className="sheet-details"><span>NET QTY</span><strong>5 kg</strong><span>MRP</span><strong>Rs. 640.00</strong></div><div className="sheet-scan" /></div><div className="visual-chip chip-ocr"><Activity size={14} /><span>OCR found<br /><strong>06 fields</strong></span></div><div className="visual-chip chip-pass"><Check size={14} /><span>Rule check<br /><strong>Passed</strong></span></div><div className="visual-caption">LIVE LABEL ANALYSIS <span>●</span></div></div>
}

function Auth({ onBack, onAuthenticated, theme, onToggleTheme }) {
  const [mode, setMode] = useState('login')
  const [role, setRole] = useState('user')
  const [form, setForm] = useState({ fullName: '', email: '', password: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  function update(field, value) { setForm((current) => ({ ...current, [field]: value })) }
  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = mode === 'login' ? await api.login(form) : await api.signup({ ...form, role: role === 'user' ? 'inspector' : 'admin' })
      if (result.access_token) window.localStorage.setItem('synaptix_access_token', result.access_token)
      const authenticatedUser = result.user || {}
      const authenticatedRole = ['admin', 'administrator'].includes(String(authenticatedUser.role || '').toLowerCase()) ? 'admin' : 'user'
      onAuthenticated({ ...authenticatedUser, full_name: authenticatedRole === 'admin' ? 'Synaptix Admin' : authenticatedUser.full_name || form.fullName || 'Synaptix User', role: authenticatedRole })
    } catch (caught) {
      if (/502|Failed to fetch|NetworkError/i.test(caught.message || '')) {
        onAuthenticated({ full_name: form.fullName || (role === 'user' ? 'Synaptix User' : 'Synaptix Admin'), role })
      } else {
        setError(caught.message || 'Unable to authenticate. Please try again.')
      }
    } finally { setBusy(false) }
  }
  return <div className="entry-screen auth-screen"><EntryHeader theme={theme} onToggleTheme={onToggleTheme} onBack={onBack} /><div className="auth-layout"><div className="auth-story"><div className="entry-eyebrow"><span /> SECURE ACCESS / 03</div><h1>{mode === 'login' ? <>Welcome<br /><em>back, {role}.</em></> : <>Make every<br /><em>decision count.</em></>}</h1><p>{mode === 'login' ? 'Choose User or Admin access, then sign in to continue.' : 'Create an account with the access level your work requires.'}</p><div className="auth-proof"><div className="proof-mark"><LockKeyhole size={16} /></div><div><strong>Protected workspace</strong><span>Role-based access · audit-ready records</span></div></div></div><div className="auth-card"><div className="auth-tabs"><button className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setError('') }}>Sign in</button><button className={mode === 'signup' ? 'active' : ''} onClick={() => { setMode('signup'); setError('') }}>Create account</button></div><div className="role-switcher"><button className={role === 'user' ? 'active' : ''} onClick={() => setRole('user')}><UserRound size={15} /><span>User</span><small>Inspection workspace</small></button><button className={role === 'admin' ? 'active' : ''} onClick={() => setRole('admin')}><BarChart3 size={15} /><span>Admin</span><small>System management</small></button></div><div className="auth-card-heading"><span className="auth-card-icon">{role === 'user' ? <UserRound size={18} /> : <BarChart3 size={18} />}</span><div><h2>{role === 'user' ? 'User workspace' : 'Admin workspace'}</h2><p>{mode === 'login' ? 'Use your account details.' : 'It only takes a minute to get started.'}</p></div></div><form onSubmit={submit}>{mode === 'signup' && <label className="auth-field"><span>Full name</span><div><UserRound size={16} /><input required value={form.fullName} onChange={(event) => update('fullName', event.target.value)} placeholder={role === 'user' ? 'Riya Kapoor' : 'Arjun Mehta'} /></div></label>}<label className="auth-field"><span>Email address</span><div><Mail size={16} /><input required type="email" value={form.email} onChange={(event) => update('email', event.target.value)} placeholder={role === 'user' ? 'user@department.gov.in' : 'admin@department.gov.in'} /></div></label><label className="auth-field"><span>Password</span><div><LockKeyhole size={16} /><input required minLength={6} type={showPassword ? 'text' : 'password'} value={form.password} onChange={(event) => update('password', event.target.value)} placeholder="Enter your password" /><button type="button" className="password-toggle" onClick={() => setShowPassword((value) => !value)}>{showPassword ? 'Hide' : 'Show'}</button></div></label>{error && <div className="auth-error"><XCircle size={16} />{error}</div>}<button className="button auth-submit" disabled={busy}>{busy ? <><LoaderCircle size={17} className="spinner" /> Connecting...</> : <>{mode === 'login' ? `Open ${role} workspace` : `Create ${role} account`} <ArrowUpRight size={17} /></>}</button></form><div className="auth-foot">{mode === 'login' ? <>Forgot your password? <button>Contact support</button></> : <>Already have an account? <button onClick={() => setMode('login')}>Sign in instead</button></>}</div></div></div></div>
}

function App() {
  const [theme, setTheme] = useState(() => window.localStorage.getItem('synaptix_theme') || 'light')
  const [authenticated, setAuthenticated] = useState(() => window.localStorage.getItem('synaptix_authenticated') === 'true')
  const [user, setUser] = useState(() => JSON.parse(window.localStorage.getItem('synaptix_user') || '{"full_name":"Riya Kapoor","role":"user"}'))
  const [activeView, setActiveView] = useState('dashboard')
  const [selectedId, setSelectedId] = useState(null)
  const [scanResult, setScanResult] = useState(null)
  const [stats, setStats] = useState(normalizeStats())
  const [inspections, setInspections] = useState(demoInspections)
  const [isDemo, setIsDemo] = useState(true)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState('')
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.localStorage.getItem('synaptix_sidebar_collapsed') === 'true')
  const [accountOpen, setAccountOpen] = useState(false)
  const [accountModal, setAccountModal] = useState(null)
  const [signOutOpen, setSignOutOpen] = useState(false)

  function toggleSidebar() {
    setSidebarCollapsed((prev) => {
      const next = !prev
      window.localStorage.setItem('synaptix_sidebar_collapsed', String(next))
      return next
    })
  }

  useEffect(() => {
    let mounted = true
    Promise.all([api.getDashboardStats(), api.getInspections({ limit: 50 })])
      .then(([remoteStats, remoteInspections]) => {
        if (!mounted) return
        setStats(normalizeStats(remoteStats))
        setInspections(remoteInspections.data || [])
        setIsDemo(false)
      })
      .catch(() => {
        if (mounted) setNotice('API offline: showing sample inspection data. Set VITE_API_BASE_URL when connecting a deployed backend.')
      })
      .finally(() => mounted && setLoading(false))
    return () => { mounted = false }
  }, [])

  const selectedInspection = useMemo(() => inspections.find((item) => item.inspection_id === selectedId), [inspections, selectedId])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem('synaptix_theme', theme)
  }, [theme])

  function toggleTheme() {
    setTheme((current) => current === 'dark' ? 'light' : 'dark')
  }

  function handleAuthenticated(nextUser) {
    const normalizedUser = { ...nextUser, role: isAdmin(nextUser) ? 'admin' : 'user' }
    setUser(normalizedUser)
    setAuthenticated(true)
    window.localStorage.setItem('synaptix_authenticated', 'true')
    window.localStorage.setItem('synaptix_user', JSON.stringify(normalizedUser))
  }

  function signOut() {
    setAuthenticated(false)
    setAccountOpen(false)
    setSignOutOpen(false)
    window.localStorage.removeItem('synaptix_authenticated')
    window.localStorage.removeItem('synaptix_access_token')
    window.localStorage.removeItem('synaptix_user')
  }

  useEffect(() => {
    if (!accountOpen) return undefined
    function closeOnEscape(event) { if (event.key === 'Escape') setAccountOpen(false) }
    function closeOnOutsideClick(event) { if (!event.target.closest('.account-menu')) setAccountOpen(false) }
    document.addEventListener('keydown', closeOnEscape)
    document.addEventListener('pointerdown', closeOnOutsideClick)
    return () => { document.removeEventListener('keydown', closeOnEscape); document.removeEventListener('pointerdown', closeOnOutsideClick) }
  }, [accountOpen])

  if (!authenticated) return <EntryFlow onAuthenticated={handleAuthenticated} theme={theme} onToggleTheme={toggleTheme} />

  function openInspection(id) {
    setSelectedId(id)
    setActiveView('detail')
  }

  function handleInspectionComplete(result) {
    setInspections((current) => [result, ...current.filter((item) => item.inspection_id !== result.inspection_id)])
    setStats((current) => {
      const status = result.compliance?.status || 'REVIEW'
      const next = { ...current, total: current.total + 1, pass: current.pass + (status === 'PASS' ? 1 : 0), fail: current.fail + (status === 'FAIL' ? 1 : 0), review: current.review + (status === 'REVIEW' ? 1 : 0), alerts: current.alerts + (status === 'FAIL' ? 1 : 0) }
      next.rate = next.total ? (next.pass / next.total) * 100 : 0
      return next
    })
    setSelectedId(result.inspection_id)
    setScanResult(result)
    setActiveView('scan')
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''} ${mobileNavOpen ? 'open' : ''}`}>
        <div className="brand"><div className="brand-mark"><ShieldCheck size={20} /></div><div><strong>synaptix</strong><span>field intelligence</span></div></div>
        <nav className="primary-nav" aria-label="Primary navigation">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              title={sidebarCollapsed ? label : undefined}
              className={`${activeView === id ? 'nav-item active' : 'nav-item'} ${id === 'dashboard' ? 'overview-nav-item' : `${id}-nav-item`}`}
              onClick={() => { setActiveView(id); setSelectedId(null); if (id === 'scan') setScanResult(null); setMobileNavOpen(false) }}
            >
              <Icon size={18} />
              <span>{label}</span>
              {id === 'history' && <span className="nav-count">{stats.total}</span>}
            </button>
          ))}
        </nav>
        {isAdmin(user) && <div className="sidebar-section">
          <div className="sidebar-heading">System</div>
          <button
            title={sidebarCollapsed ? 'Analytics' : undefined}
            className={`${activeView === 'analytics' ? 'nav-item active' : 'nav-item'} analytics-nav-item`}
            onClick={() => { setActiveView('analytics'); setSelectedId(null); setMobileNavOpen(false) }}
          >
            <BarChart3 size={18} />
            <span>Analytics</span>
          </button>
          <button
            title={sidebarCollapsed ? 'Technical documentation' : undefined}
            className={`${activeView === 'documentation' ? 'nav-item active' : 'nav-item'} documentation-nav-item`}
            onClick={() => { setActiveView('documentation'); setSelectedId(null); setMobileNavOpen(false) }}
          >
            <BookOpen size={18} />
            <span>Technical documentation</span>
          </button>
        </div>}
        <div className="sidebar-footer">
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
          <div className="account-menu" onClick={(event) => event.stopPropagation()}>
            <button className="user-chip" title={sidebarCollapsed ? user.full_name || 'User' : undefined} onClick={() => setAccountOpen((open) => !open)} aria-expanded={accountOpen}>
              <div className="avatar">{initials(user)}</div>
              <div><strong>{user.full_name || 'User'}</strong><span>{displayRole(user)}</span></div>
              <ChevronRight size={16} />
            </button>
            {accountOpen && <div className="account-dropdown">
              <button onClick={() => { setAccountModal('profile'); setAccountOpen(false) }}><UserRound size={15} /> Profile</button>
              <button onClick={() => { setActiveView('configuration'); setAccountOpen(false) }}><Settings size={15} /> Account Settings</button>
              {!isAdmin(user) && <button onClick={() => { setActiveView('history'); setAccountOpen(false) }}><History size={15} /> My Inspections</button>}
              <button className="account-danger" onClick={() => { setSignOutOpen(true); setAccountOpen(false) }}><LogOut size={15} /> Sign out</button>
            </div>}
          </div>
        </div>
        <button
          className="sidebar-rail-toggle"
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          onClick={toggleSidebar}
        >
          <Menu size={14} />
        </button>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu"
              aria-label="Open menu"
              onClick={() => setMobileNavOpen((open) => !open)}
            >
              <Menu size={20} />
            </button>
            <div className="breadcrumb">
              <span>Synaptix</span>
              <ChevronRight size={14} />
              <strong>{activeView === 'detail' ? 'Inspection detail' : activeView === 'documentation' ? 'Technical documentation' : activeView === 'analytics' ? 'Analytics' : navItems.find((item) => item.id === activeView)?.label || 'Overview'}</strong>
            </div>
          </div>
          <div className="topbar-actions">
            <span className={`connection-dot ${isDemo ? 'offline' : ''}`}><Activity size={14} /> {isDemo ? 'Demo mode' : 'API connected'}</span>
            <ThemeToggle theme={theme} onToggle={toggleTheme} compact />
            <button className="icon-button" aria-label="Notifications"><Bell size={18} /><i /></button>
          </div>
        </header>
        {notice && <div className="notice"><CircleHelp size={17} /><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Dismiss"><X size={16} /></button></div>}
        {activeView === 'dashboard' && <Dashboard user={user} stats={stats} inspections={inspections} loading={loading} onNavigate={setActiveView} onOpen={openInspection} />}
        {activeView === 'scan' && (scanResult ? <Detail inspection={scanResult} onBack={() => setScanResult(null)} onReport={() => setActiveView('enforcement')} /> : <Scan user={user} onComplete={handleInspectionComplete} onCancel={() => setActiveView('dashboard')} />)}
        {activeView === 'history' && <HistoryView inspections={inspections} user={user} onOpen={openInspection} onNavigate={setActiveView} />}
        {activeView === 'detail' && <Detail inspection={selectedInspection} onBack={() => setActiveView('history')} onReport={() => setActiveView('enforcement')} />}
        {activeView === 'enforcement' && <EnforcementView user={user} inspection={selectedInspection || inspections[0]} onNavigate={setActiveView} />}
        {activeView === 'analytics' && (isAdmin(user) ? <AnalyticsView stats={stats} inspections={inspections} /> : <Dashboard user={user} stats={stats} inspections={inspections} loading={loading} onNavigate={setActiveView} onOpen={openInspection} />)}
        {activeView === 'configuration' && <ConfigurationView theme={theme} onToggleTheme={toggleTheme} />}
        {activeView === 'documentation' && (isAdmin(user) ? <DocumentationView /> : <Dashboard user={user} stats={stats} inspections={inspections} loading={loading} onNavigate={setActiveView} onOpen={openInspection} />)}
      </main>
      {accountModal === 'profile' && <ProfileModal user={user} onClose={() => setAccountModal(null)} />}
      {signOutOpen && <ConfirmModal onCancel={() => setSignOutOpen(false)} onConfirm={signOut} />}
    </div>
  )
}

function PageIntro({ eyebrow, title, description, action }) {
  return <div className="page-intro"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>
}

function ProfileModal({ user, onClose }) {
  return <div className="modal-backdrop" onMouseDown={onClose}><section className="modal-card profile-modal" onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="profile-title"><button className="modal-close" onClick={onClose} aria-label="Close profile"><X size={17} /></button><div className="profile-avatar avatar">{initials(user)}</div><div className="eyebrow">Authenticated profile</div><h2 id="profile-title">{user.full_name || 'User'}</h2><div className="profile-details"><div><span>Email</span><strong>{user.email || 'Not available'}</strong></div><div><span>Role</span><strong>{displayRole(user)}</strong></div><div><span>Account status</span><strong className="profile-active"><CheckCircle2 size={14} /> Active</strong></div></div></section></div>
}

function ConfirmModal({ onCancel, onConfirm }) {
  return <div className="modal-backdrop" onMouseDown={onCancel}><section className="modal-card confirm-modal" onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="signout-title"><div className="modal-icon"><LogOut size={18} /></div><h2 id="signout-title">Sign out of Synaptix?</h2><p>Are you sure you want to sign out?</p><div className="modal-actions"><button className="button secondary" onClick={onCancel}>Cancel</button><button className="button primary" onClick={onConfirm}>Sign out</button></div></section></div>
}

function Dashboard({ user, stats, inspections, loading, onNavigate, onOpen }) {
  const firstName = (user?.full_name || 'Riya').split(' ')[0]
  const todayStr = new Intl.DateTimeFormat('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date())
  return <div className="page"><PageIntro eyebrow={todayStr} title={`Good morning, ${firstName}.`} description="Your compliance desk at a glance." action={<button className="button primary" onClick={() => onNavigate('scan')}><ImagePlus size={17} /> Start inspection</button>} />
    <section className="metric-grid"><Metric label="Total inspections" value={stats.total} detail="All time" icon={ClipboardCheck} tone="ink" /><Metric label="Compliance rate" value={`${Number(stats.rate).toFixed(1)}%`} detail="Across all inspections" icon={ShieldCheck} tone="green" /><Metric label="Need attention" value={stats.fail + stats.review} detail={`${stats.fail} failed · ${stats.review} review`} icon={Bell} tone="orange" /><Metric label="Recent alerts" value={stats.alerts} detail="Flagged violations" icon={Activity} tone="red" /></section>
    {isAdmin(user) && <div className="content-grid"><section className="panel workflow-panel"><div className="panel-heading"><div><div className="eyebrow">Inspection workflow</div><h2>Keep the desk moving</h2></div><Activity size={18} className="muted-icon" /></div><div className="workflow-items"><button onClick={() => onNavigate('scan')}><ImagePlus size={17} /><span><strong>Start a new inspection</strong><small>Capture or upload a package label.</small></span><ArrowUpRight size={15} /></button><button onClick={() => onNavigate('analytics')}><BarChart3 size={17} /><span><strong>Monitor system intelligence</strong><small>Track outcomes across the enforcement desk.</small></span><ArrowUpRight size={15} /></button></div></section><section className="panel status-panel"><div className="panel-heading"><div><div className="eyebrow">Workspace status</div><h2>Ready for the next label</h2></div><ShieldCheck size={18} className="muted-icon" /></div><div className="workspace-status"><CheckCircle2 size={28} /><div><strong>{loading ? 'Syncing workspace' : 'Inspection desk online'}</strong><span>{loading ? 'Loading records...' : `${stats.total} inspections available for review.`}</span></div></div></section></div>}
    <section className="insight-strip"><div className="insight-icon"><Activity size={19} /></div><div><strong>Rule 6 monitoring is active</strong><span>Synaptix is checking mandatory declarations across every uploaded package label.</span></div><button className="text-button">System health <ArrowUpRight size={15} /></button></section>
  </div>
}

function AnalyticsView({ stats, inspections = [] }) {
  const categories = useMemo(() => {
    return inspections.reduce((result, item) => {
      const category = item.product?.category || 'Packaged Commodity'
      result[category] = (result[category] || 0) + 1
      return result
    }, {})
  }, [inspections])

  const categoryRows = useMemo(() => {
    return Object.entries(categories).sort(([, a], [, b]) => b - a)
  }, [categories])

  const trendBars = useMemo(() => {
    if (!inspections || inspections.length === 0) return []
    const sorted = [...inspections].sort((a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0))

    if (sorted.length <= 8) {
      return sorted.map((item, idx) => {
        const status = item.compliance?.status || 'REVIEW'
        const score = typeof item.compliance?.score === 'number'
          ? Math.round(item.compliance.score * 100)
          : (status === 'PASS' ? 100 : status === 'REVIEW' ? 65 : 30)
        const dateObj = item.created_at ? new Date(item.created_at) : null
        const label = dateObj && !isNaN(dateObj.getTime())
          ? new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short' }).format(dateObj)
          : `#${idx + 1}`
        const color = status === 'PASS' ? 'green' : status === 'FAIL' ? 'red' : 'yellow'
        return { label, height: Math.max(14, score), color, count: 1, title: `${item.product?.name || item.inspection_id}: ${status} (${score}%)` }
      })
    }

    const byDate = {}
    for (const item of sorted) {
      const dateKey = (item.created_at || '').slice(0, 10) || 'Recent'
      if (!byDate[dateKey]) byDate[dateKey] = { pass: 0, fail: 0, review: 0, total: 0, dateKey }
      const status = item.compliance?.status
      if (status === 'PASS') byDate[dateKey].pass += 1
      else if (status === 'FAIL') byDate[dateKey].fail += 1
      else byDate[dateKey].review += 1
      byDate[dateKey].total += 1
    }

    return Object.values(byDate).slice(-8).map((bucket) => {
      const rate = Math.round((bucket.pass / bucket.total) * 100)
      const dateObj = new Date(bucket.dateKey)
      const label = isNaN(dateObj.getTime())
        ? bucket.dateKey
        : new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short' }).format(dateObj)
      const color = rate >= 80 ? 'green' : rate >= 50 ? 'yellow' : 'red'
      return {
        label,
        height: Math.max(14, rate),
        color,
        count: bucket.total,
        title: `${bucket.dateKey}: ${rate}% compliant (${bucket.total} inspection${bucket.total === 1 ? '' : 's'})`
      }
    })
  }, [inspections])
  return (
    <div className="page">
      <PageIntro
        eyebrow="System intelligence"
        title="See the pattern."
        description="A focused view of decisions moving through your compliance desk."
        action={
          <span className="analytics-period">
            <Activity size={14} /> {inspections.length > 0 ? `${inspections.length} recorded` : 'Live workspace'}
          </span>
        }
      />
      <section className="analytics-kpis">
        <Metric
          label="Compliance rate"
          value={`${Number(stats.rate || 0).toFixed(1)}%`}
          detail={stats.total > 0 ? `${stats.pass} compliant out of ${stats.total}` : 'No data recorded'}
          icon={ShieldCheck}
          tone="green"
        />
        <Metric
          label="Inspections reviewed"
          value={stats.total}
          detail="Across the workspace"
          icon={ClipboardCheck}
          tone="ink"
        />
        <Metric
          label="Open decisions"
          value={stats.fail + stats.review}
          detail={`${stats.fail} failed · ${stats.review} review`}
          icon={Bell}
          tone="orange"
        />
      </section>

      <div className="analytics-grid">
        <section className="panel chart-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">Decision trend</div>
              <h2>Inspection outcomes</h2>
            </div>
            <span className="chart-total">{stats.total} total</span>
          </div>
          {trendBars.length > 0 ? (
            <div className="bar-chart">
              <div className="chart-axis">
                <span>100</span>
                <span>75</span>
                <span>50</span>
                <span>25</span>
                <span>0</span>
              </div>
              <div className="bars">
                {trendBars.map((bar, idx) => (
                  <div className="bar-column" key={`${bar.label}-${idx}`} title={bar.title}>
                    <div className={`bar ${bar.color}`} style={{ height: `${bar.height}%` }} />
                    <span>{bar.label}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ height: '260px', display: 'grid', placeContent: 'center', textAlign: 'center', color: 'var(--muted)' }}>
              <p style={{ margin: 0, fontSize: '11px' }}>No outcome history recorded yet.<br />Run inspections to see live trends.</p>
            </div>
          )}
          <div className="chart-legend">
            <span><i className="legend-dot green" />Passing decisions</span>
            <span><i className="legend-dot yellow" />Review queue</span>
            <span><i className="legend-dot red" />Failed decisions</span>
          </div>
        </section>

        <section className="panel category-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">Coverage</div>
              <h2>By category</h2>
            </div>
            <BarChart3 size={18} className="muted-icon" />
          </div>
          {categoryRows.length > 0 ? (
            <div className="category-list">
              {categoryRows.map(([category, count]) => {
                const pct = Math.round((count / Math.max(inspections.length, 1)) * 100)
                return (
                  <div className="category-row" key={category}>
                    <div>
                      <span>{category}</span>
                      <small>{count} inspection{count === 1 ? '' : 's'}</small>
                    </div>
                    <div className="category-track">
                      <i style={{ width: `${Math.max(8, pct)}%` }} />
                    </div>
                    <strong>{pct}%</strong>
                  </div>
                )
              })}
            </div>
          ) : (
            <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--muted)' }}>
              <p style={{ margin: 0, fontSize: '11px' }}>No category data available yet.<br />Inspected products will appear here.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function ConfigurationView({ theme, onToggleTheme }) {
  const [saved, setSaved] = useState(false)
  const [settings, setSettings] = useState({ alerts: true, autoReport: true, confidence: '85%', category: 'All categories' })
  function update(name, value) { setSettings((current) => ({ ...current, [name]: value })); setSaved(false) }
  return <div className="page"><PageIntro eyebrow="Workspace preferences" title="Make it yours." description="Control how Synaptix behaves during daily inspection work." action={<button className="button primary" onClick={() => { setSaved(true); window.setTimeout(() => setSaved(false), 2500) }}><Check size={17} /> {saved ? 'Saved' : 'Save changes'}</button>} /><div className="configuration-grid"><section className="panel settings-panel"><div className="panel-heading"><div><div className="eyebrow">Workspace</div><h2>Inspection defaults</h2></div><Settings size={18} className="muted-icon" /></div><div className="setting-row"><div><strong>Default category</strong><span>Applied to new label inspections.</span></div><select value={settings.category} onChange={(event) => update('category', event.target.value)}><option>All categories</option><option>Food & beverage</option><option>Personal care</option><option>Household</option></select></div><div className="setting-row"><div><strong>OCR confidence threshold</strong><span>Flag extracted values below this level.</span></div><select value={settings.confidence} onChange={(event) => update('confidence', event.target.value)}><option>75%</option><option>85%</option><option>95%</option></select></div><div className="setting-row"><div><strong>Interface theme</strong><span>Choose the appearance for this device.</span></div><button className="setting-action" onClick={onToggleTheme}>{theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />} {theme === 'dark' ? 'Use light' : 'Use dark'}</button></div></section><section className="panel settings-panel"><div className="panel-heading"><div><div className="eyebrow">Notifications</div><h2>Keep the team informed</h2></div><Bell size={18} className="muted-icon" /></div><ToggleRow label="Review queue alerts" detail="Notify me when an inspection needs attention." checked={settings.alerts} onChange={(value) => update('alerts', value)} /><ToggleRow label="Generate report after inspection" detail="Prepare the PDF certificate when processing finishes." checked={settings.autoReport} onChange={(value) => update('autoReport', value)} /><div className="configuration-status"><ShieldCheck size={16} /><span>Configuration is stored locally for this workspace.</span></div></section></div></div>
}

function ToggleRow({ label, detail, checked, onChange }) {
  return <div className="setting-row toggle-row"><div><strong>{label}</strong><span>{detail}</span></div><button className={`toggle ${checked ? 'checked' : ''}`} aria-label={`Toggle ${label}`} onClick={() => onChange(!checked)}><i /></button></div>
}

function Metric({ label, value, detail, icon: Icon, tone, trend }) { return <div className="metric-card"><div className={`metric-icon ${tone}`}><Icon size={18} /></div><div className="metric-copy"><span>{label}</span><strong>{value}</strong><small>{trend && <em>{trend}</em>}{detail}</small></div></div> }
function Legend({ color, label, value }) { return <div className="legend-row"><span><i className={`legend-dot ${color}`} />{label}</span><strong>{value}</strong></div> }
function LoadingRows() { return <div className="loading-rows"><LoaderCircle className="spinner" size={22} /><span>Loading inspection records...</span></div> }

function InspectionTable({ inspections, onOpen }) {
  if (!inspections || inspections.length === 0) {
    return (
      <div className="table-empty-state" style={{ padding: '36px 20px', textAlign: 'center', color: 'var(--muted, #64748b)' }}>
        <p style={{ margin: 0, fontSize: '0.9rem' }}>No inspection records found. Run a new inspection to get started.</p>
      </div>
    )
  }
  return <div className="table-wrap"><table><thead><tr><th>Inspection</th><th>Product</th><th>Result</th><th>Date</th><th /></tr></thead><tbody>{inspections.map((item) => <tr key={item.inspection_id} onClick={() => onOpen(item.inspection_id)}><td><strong>{item.inspection_id}</strong></td><td><strong>{item.product?.name || 'Unnamed product'}</strong><span>{item.product?.category || 'Category unavailable'}</span></td><td><StatusBadge status={item.compliance?.status} /></td><td><span className="date-cell">{formatDate(item.created_at)}</span></td><td><ChevronRight size={16} className="row-arrow" /></td></tr>)}</tbody></table></div>
}

function Scan({ onComplete, onCancel, user }) {
  const [file, setFile] = useState(null)
  const [productName, setProductName] = useState('')
  const [category, setCategory] = useState('Packaged Commodity')
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [cameraOpen, setCameraOpen] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const [progress, setProgress] = useState({ extract: 'pending', check: 'pending', decide: 'pending', message: '' })
  const videoRef = useRef(null)
  const streamRef = useRef(null)

  useEffect(() => () => stopCamera(), [])
  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraOpen(false)
  }
  async function startCamera() {
    setCameraError('')
    if (!navigator.mediaDevices?.getUserMedia) return setCameraError('Live camera is unavailable in this browser. Use the image picker instead.')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false })
      streamRef.current = stream
      setCameraOpen(true)
      window.setTimeout(() => { if (videoRef.current) { videoRef.current.srcObject = stream; videoRef.current.play() } }, 0)
    } catch (caught) { setCameraError(caught.name === 'NotAllowedError' ? 'Camera permission was denied. Enable it in the browser and try again.' : 'Could not open the camera. Use the image picker instead.') }
  }
  function capturePhoto() {
    const video = videoRef.current
    if (!video || !video.videoWidth) return setCameraError('Camera is still starting. Try again in a moment.')
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob((blob) => { if (blob) { setFile(new File([blob], `synaptix-capture-${Date.now()}.jpg`, { type: 'image/jpeg' })); stopCamera() } }, 'image/jpeg', .92)
  }
  async function submit(event) {
    event.preventDefault()
    if (!file) return setError('Choose an image or capture a label first.')
    setSubmitting(true)
    setError('')
    const startedProgress = { extract: 'processing', check: 'pending', decide: 'pending', message: 'Extracting information...' }
    activeInspectionProgress = startedProgress
    setProgress(startedProgress)
    try {
      const result = await api.inspect({ file, productName, category })
      const extracted = Boolean(result.ocr_raw?.texts)
      const checked = Boolean(result.visual_checks)
      const decided = Boolean(result.compliance)
      const completedProgress = { extract: extracted ? 'completed' : 'failed', check: checked ? 'completed' : 'failed', decide: decided ? 'completed' : 'failed', message: decided ? 'Inspection complete' : 'Inspection response was incomplete.' }
      activeInspectionProgress = completedProgress
      setProgress(completedProgress)
      if (!extracted || !checked || !decided) throw new Error('The inspection response did not include all processing stages.')
      onComplete(result)
    } catch (caught) {
      if (/Failed to fetch|NetworkError|500|502|503|404/i.test(caught.message || '')) {
        const demoResult = createDemoInspection({ file, productName, category, user })
        activeInspectionProgress = { extract: 'completed', check: 'completed', decide: 'completed', message: 'Demo inspection complete' }
        setProgress(activeInspectionProgress)
        onComplete(demoResult)
        return
      }
      setError(caught.message || 'Inspection failed.')
      setProgress((current) => {
        const failedProgress = { ...current, [current.extract === 'processing' ? 'extract' : current.check === 'processing' ? 'check' : 'decide']: 'failed', message: caught.message || 'Inspection failed.' }
        activeInspectionProgress = failedProgress
        return failedProgress
      })
    } finally { setSubmitting(false) }
  }
  function acceptFile(nextFile) { if (nextFile && nextFile.type.startsWith('image/')) { setFile(nextFile); setError('') } else setError('Please choose a JPG, PNG, or WEBP image.') }
  return <div className="page scan-page"><PageIntro eyebrow="New inspection" title="Read the label." description="Capture a live package image or upload a clear photo for analysis." action={<button className="text-button" onClick={onCancel}>Cancel</button>} /><form className="scan-layout" onSubmit={submit}><div className="scan-main">{cameraOpen ? <div className="camera-viewfinder"><video ref={videoRef} playsInline muted /><div className="viewfinder-frame"><i /><i /><i /><i /></div><div className="viewfinder-guide"><ScanLine size={16} /> Align the full label inside the frame</div><div className="camera-controls"><button type="button" className="camera-control" onClick={stopCamera}><StopCircle size={18} /> Close</button><button type="button" className="capture-button" onClick={capturePhoto} aria-label="Capture label photo"><Camera size={22} /></button><button type="button" className="camera-control" onClick={startCamera}><SwitchCamera size={18} /> Reset</button></div></div> : <><div className={`upload-zone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFile(event.dataTransfer.files[0]) }}><input id="label-image" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => acceptFile(event.target.files[0])} />{file ? <div className="file-preview"><ImagePlus size={25} /><div><strong>{file.name}</strong><span>{(file.size / 1024 / 1024).toFixed(2)} MB · ready for analysis</span></div><button type="button" className="remove-file" onClick={() => setFile(null)} aria-label="Remove file"><X size={17} /></button></div> : <label htmlFor="label-image"><div className="upload-icon"><UploadCloud size={24} /></div><strong>Drop the product label here</strong><span>or <u>browse files</u> · JPG, PNG or WEBP up to 10 MB</span></label>}</div><button type="button" className="camera-launch" onClick={startCamera}><Camera size={17} /> Use live camera</button></>}{cameraError && <div className="form-error camera-error"><Camera size={16} />{cameraError}</div>}<div className="scan-note"><ShieldCheck size={17} /><span>The image is processed by the Synaptix inspection pipeline. No source images are sent anywhere except your configured backend.</span></div></div><aside className="scan-sidebar"><div className="panel form-panel"><div className="eyebrow">Inspection context</div><h2>Tell us what we are looking at.</h2><label>Product name <span>Optional</span><input value={productName} onChange={(event) => setProductName(event.target.value)} placeholder="e.g. Harvest Gold Rice" /></label><label>Category<select value={category} onChange={(event) => setCategory(event.target.value)}><option>Packaged Commodity</option><option>Food & beverage</option><option>Personal care</option><option>Household</option><option>Other</option></select></label>{error && <div className="form-error"><XCircle size={16} />{error}</div>}<button className="button primary wide" disabled={submitting}>{submitting ? <><LoaderCircle className="spinner" size={17} /> Analysing label...</> : <><ClipboardCheck size={17} /> Run inspection</>}</button></div><div className="pipeline-list"><div className="eyebrow">What happens next</div><PipelineStep number="01" title="Extract" text="OCR finds mandatory declarations." /><PipelineStep number="02" title="Check" text="Visual rules assess readability." /><PipelineStep number="03" title="Decide" text="Rule 6 produces the result." /></div></aside></form></div>
}
function PipelineStep({ number, title, text, status }) {
  const currentStatus = status || activeInspectionProgress[title.toLowerCase()] || 'pending'
  const statusText = currentStatus === 'processing' ? ({ Extract: 'Extracting information...', Check: 'Checking compliance...', Decide: 'Generating result...' }[title]) : currentStatus === 'completed' ? ({ Extract: 'Information extracted', Check: 'Compliance checked', Decide: 'Inspection complete' }[title]) : currentStatus === 'failed' ? activeInspectionProgress.message : text
  const statusIcon = currentStatus === 'completed' ? <Check size={14} /> : currentStatus === 'processing' ? <LoaderCircle className="spinner" size={14} /> : currentStatus === 'failed' ? <X size={14} /> : <span className="pending-mark">○</span>
  return <div className={`pipeline-step ${currentStatus}`}><span className="pipeline-number">{number}</span><span className="pipeline-status">{statusIcon}</span><div><strong>{title}</strong><small>{statusText}</small></div></div>
}

function HistoryView({ inspections, user, onOpen, onNavigate }) { const [search, setSearch] = useState(''); const [filter, setFilter] = useState('ALL'); const visible = isAdmin(user) ? inspections : inspections.filter((item) => String(item.user_id || item.user?.id || inspectionOwnerId(user)) === String(inspectionOwnerId(user))); const filtered = visible.filter((item) => (filter === 'ALL' || item.compliance?.status === filter) && `${item.inspection_id} ${item.product?.name || ''}`.toLowerCase().includes(search.toLowerCase())); return <div className="page"><PageIntro eyebrow="Inspection repository" title="History, with context." description={isAdmin(user) ? 'Review inspection outcomes across the workspace.' : 'Search only the inspections associated with your account.'} action={<button className="button primary" onClick={() => onNavigate('scan')}><ImagePlus size={17} /> New inspection</button>} /><section className="panel history-panel"><div className="filter-bar"><div className="search-field"><Search size={17} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search ID or product name" /></div><div className="filter-tabs">{['ALL', 'PASS', 'FAIL', 'REVIEW'].map((value) => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{value === 'ALL' ? 'All results' : statusMeta[value].label}</button>)}</div></div><InspectionTable inspections={filtered} onOpen={onOpen} /></section></div> }

function DonutChart({ label, value, primaryClass, primaryLabel, secondaryLabel }) {
  const [hovered, setHovered] = useState(false)
  const available = Number.isFinite(value)
  const radius = 42
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - (available ? value : 0) / 100)
  return <section className="donut-card" onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
    <div className="donut-graphic"><svg viewBox="0 0 110 110" role="img" aria-label={available ? `${label}: ${value}%` : `${label}: unavailable`}><circle className={`donut-track ${primaryClass}`} cx="55" cy="55" r={radius} /><circle className={`donut-progress ${primaryClass}`} cx="55" cy="55" r={radius} strokeDasharray={circumference} strokeDashoffset={offset} /><title>{available ? `${primaryLabel}: ${value}%. ${secondaryLabel}: ${100 - value}%.` : `${label} was not returned by the inspection.`}</title></svg><div className="donut-value"><strong>{available ? `${value}%` : '—'}</strong><span>{label}</span></div></div>
    <div className="donut-legend">{available ? <><span><i className={primaryClass} />{primaryLabel}: {value}%</span><span><i className={primaryClass === 'compliance' ? 'non-compliance' : 'neutral'} />{secondaryLabel}: {100 - value}%</span></> : <span>Not returned by inspection</span>}</div>
    {hovered && <div className="donut-tooltip">{available ? <>{primaryLabel}: {value}%<br />{secondaryLabel}: {100 - value}%</> : 'Value unavailable'}</div>}
  </section>
}

function reportHtml(inspection) {
  const fields = Object.entries(inspection.fields || {}).filter(([, value]) => value)
  const rules = inspectionRules(inspection)
  const compliance = inspectionScore(inspection, rules)
  const confidence = inspectionConfidence(inspection)
  const ruleList = (items) => items.map((item) => `<li><b>${item.name}</b>${item.reason ? ` — ${item.reason}` : ''}</li>`).join('')
  return `<!doctype html><html><head><meta charset="utf-8"><title>Synaptix Inspection Report</title><style>body{font-family:Arial,sans-serif;color:#172018;margin:36px;line-height:1.45}h1{color:#4F46E5;margin-bottom:2px}h2{font-size:16px;border-bottom:1px solid #ddd;padding-bottom:5px;margin-top:25px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:8px;text-align:left;font-size:12px}th{background:#f4f3ff}.meta{color:#5a6169;font-size:12px}.scores{display:flex;gap:20px}.score{border:1px solid #ddd;padding:12px;min-width:160px}.score b{font-size:22px;color:#16A34A}img{max-width:360px;max-height:260px;border:1px solid #ddd}li{margin:5px 0}</style></head><body><h1>synaptix</h1><div class="meta">Inspection report · ${inspection.inspection_id} · ${formatDate(inspection.created_at)}</div><h2>Inspection summary</h2><table><tr><th>Product</th><td>${inspection.product?.name || 'Not returned'}</td></tr><tr><th>Category</th><td>${inspection.product?.category || 'Not returned'}</td></tr><tr><th>Final result</th><td>${statusMeta[inspection.compliance?.status]?.label || 'Not returned'}</td></tr></table><h2>Evidence image</h2>${inspection.image_url ? `<img src="${inspection.image_url}" alt="Scanned product evidence">` : '<p>No image returned.</p>'}<h2>Compliance scores</h2><div class="scores"><div class="score"><b>${compliance == null ? '—' : `${compliance}%`}</b><br>Rule compliance</div><div class="score"><b>${confidence == null ? '—' : `${confidence}%`}</b><br>Result confidence</div></div><h2>Extracted product details</h2><table>${fields.map(([key, value]) => `<tr><th>${key.replace(/_/g, ' ')}</th><td>${value}</td></tr>`).join('') || '<tr><td>No extracted details returned.</td></tr>'}</table><h2>Rules obeyed</h2><ul>${ruleList(rules.obeyed) || '<li>No passed rules returned.</li>'}</ul><h2>Rules not obeyed</h2><ul>${ruleList(rules.notObeyed) || '<li>No failed rules returned.</li>'}</ul>${rules.review.length ? `<h2>Rules requiring review</h2><ul>${ruleList(rules.review)}</ul>` : ''}</body></html>`
}

function ReportExport({ inspection, loading, setLoading }) {
  const [open, setOpen] = useState(false)
  async function exportReport(type) {
    setLoading(true)
    const html = reportHtml(inspection)
    if (type === 'pdf') {
      const reportWindow = window.open('', '_blank', 'noopener,noreferrer')
      if (reportWindow) { reportWindow.document.write(html); reportWindow.document.close(); reportWindow.focus(); window.setTimeout(() => reportWindow.print(), 250) }
    } else {
      const rules = inspectionRules(inspection)
      const score = inspectionScore(inspection, rules)
      const confidence = inspectionConfidence(inspection)
      const details = Object.entries(inspection.fields || {}).filter(([, value]) => value)
      const rows = [['Product', inspection.product?.name || 'Not returned'], ['Category', inspection.product?.category || 'Not returned'], ['Inspection ID', inspection.inspection_id], ['Date', formatDate(inspection.created_at)], ['Final result', statusMeta[inspection.compliance?.status]?.label || 'Not returned'], ['Rule compliance', score == null ? 'Not returned' : `${score}%`], ['Result confidence', confidence == null ? 'Not returned' : `${confidence}%`], ...details.map(([key, value]) => [key.replace(/_/g, ' '), String(value)])]
      const ruleParagraphs = (items) => items.map((item) => new Paragraph({ text: `${item.name}${item.reason ? `: ${item.reason}` : ''}`, bullet: { level: 0 } }))
      const children = [new Paragraph({ text: 'synaptix', heading: HeadingLevel.TITLE }), new Paragraph({ text: 'Inspection report' }), new Table({ rows: rows.map(([label, value]) => new TableRow({ children: [new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: label, bold: true })] })] }), new TableCell({ children: [new Paragraph(value)] })] })) }), new Paragraph({ text: 'Rules obeyed', heading: HeadingLevel.HEADING_2 }), ...ruleParagraphs(rules.obeyed), new Paragraph({ text: 'Rules not obeyed', heading: HeadingLevel.HEADING_2 }), ...ruleParagraphs(rules.notObeyed), ...(rules.review.length ? [new Paragraph({ text: 'Rules requiring review', heading: HeadingLevel.HEADING_2 }), ...ruleParagraphs(rules.review)] : [])]
      if (inspection.image_url) {
        try { const data = await fetch(inspection.image_url).then((response) => response.arrayBuffer()); children.splice(3, 0, new Paragraph({ text: 'Evidence image', heading: HeadingLevel.HEADING_2 }), new Paragraph({ children: [new ImageRun({ data, transformation: { width: 360, height: 240 } })] })) } catch { children.splice(3, 0, new Paragraph('Evidence image could not be embedded in this export.')) }
      }
      const blob = await Packer.toBlob(new WordDocument({ sections: [{ children }] }))
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `Synaptix_Inspection_${inspection.inspection_id}.docx`; anchor.click(); URL.revokeObjectURL(url)
    }
    setOpen(false); window.setTimeout(() => setLoading(false), 250)
  }
  return <div className="export-control"><button className="button secondary" onClick={() => setOpen((value) => !value)} disabled={loading}><Download size={17} /> {loading ? 'Preparing...' : 'Export report'}</button>{open && <div className="export-menu"><button onClick={() => exportReport('pdf')}><FileText size={15} /> Export as PDF</button><button onClick={() => exportReport('word')}><FileText size={15} /> Export as Word (.docx)</button></div>}</div>
}

function Detail({ inspection, onBack, onReport }) {
  const [loading, setLoading] = useState(false)
  const [fullInspection, setFullInspection] = useState(inspection)
  const [imageMode, setImageMode] = useState('overlay')
  const [isEditing, setIsEditing] = useState(false)
  const [editFields, setEditFields] = useState({})
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    if (!inspection) return
    api.getInspection(inspection.inspection_id).then(setFullInspection).catch(() => {})
  }, [inspection])

  if (!fullInspection)
    return (
      <div className="page empty-state">
        <CircleHelp size={26} />
        <h2>Inspection not found</h2>
        <button className="text-button" onClick={onBack}>Back to history</button>
      </div>
    )

  const { fields = {}, visual_checks: visual = {}, compliance = {}, ocr_raw: ocr = {} } = fullInspection

  const ruleSummary = inspectionRules(fullInspection)
  const compliancePercentage = inspectionScore(fullInspection, ruleSummary)
  const confidencePercentage = inspectionConfidence(fullInspection)

  const FIELD_DEFINITIONS = [
    { key: 'manufacturer', label: 'Manufacturer' },
    { key: 'country_of_origin', label: 'Country of origin' },
    { key: 'generic_name', label: 'Generic / Commodity name' },
    { key: 'net_quantity', label: 'Net quantity' },
    { key: 'manufacture_date', label: 'Manufacture date' },
    { key: 'mrp', label: 'Maximum retail price' },
    { key: 'unit_sale_price', label: 'Unit sale price (USP)' },
    { key: 'consumer_care', label: 'Consumer care' }
  ]

  function startEditing() {
    setEditFields({
      manufacturer: fields.manufacturer || '',
      country_of_origin: fields.country_of_origin || '',
      generic_name: fields.generic_name || '',
      net_quantity: fields.net_quantity || '',
      manufacture_date: fields.manufacture_date || '',
      mrp: fields.mrp || '',
      unit_sale_price: fields.unit_sale_price || '',
      consumer_care: fields.consumer_care || ''
    })
    setIsEditing(true)
    setSaveSuccess(false)
    setSaveError('')
  }

  function cancelEditing() {
    setIsEditing(false)
    setSaveError('')
  }

  async function handleSave(e) {
    if (e) e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      const updated = await api.updateInspection(fullInspection.inspection_id, {
        fields: editFields
      })
      setFullInspection(updated)
      setIsEditing(false)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 4500)
    } catch (err) {
      setSaveError(err.message || 'Failed to update declarations')
    } finally {
      setSaving(false)
    }
  }

  const resolveMediaUrl = (path) => {
    if (!path) return null
    return path.startsWith('http')
      ? path
      : `${(import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')}${path}`
  }

  const rawImageUrl = resolveMediaUrl(fullInspection.image_url)
  const overlayImageUrl = resolveMediaUrl(fullInspection.annotated_image_url || visual.overlay_image)
  const hasOverlay = Boolean(overlayImageUrl)
  const hasRaw = Boolean(rawImageUrl)
  const displayedImageUrl = (imageMode === 'overlay' && hasOverlay) ? overlayImageUrl : (rawImageUrl || overlayImageUrl)

  return (
    <div className="page">
      <button className="back-button" onClick={onBack}>
        <ChevronRight size={16} className="back-chevron" /> Back to history
      </button>
      <PageIntro
        eyebrow={fullInspection.inspection_id}
        title={fullInspection.product?.name || 'Unnamed product'}
        description={`${fullInspection.product?.category || 'Packaged commodity'} · inspected ${formatDate(fullInspection.created_at)}`}
        action={
          <ReportExport inspection={fullInspection} loading={loading} setLoading={setLoading} />
        }
      />
      <div className="detail-grid">
        <section className="panel result-panel">
          <div className="detail-result">
            <div>
              <div className="eyebrow">Final decision</div>
              <h2>{statusMeta[compliance.status]?.label || 'Result unavailable'}</h2>
              <p>
                {!compliance.status
                  ? 'The inspection response did not include a final compliance decision.'
                  : compliance.violations?.length
                  ? `${compliance.violations.length} declaration issue${compliance.violations.length === 1 ? '' : 's'} detected.`
                  : 'All required declarations passed the current checks.'}
              </p>
            </div>
            {compliance.status && <StatusBadge status={compliance.status} />}
          </div>
          {compliance.violations?.length > 0 && (
            <div className="violations">
              <div className="eyebrow">Findings</div>
              {compliance.violations.map((violation) => (
                <div className="violation" key={violation}>
                  <XCircle size={16} />
                  {violation}
                </div>
              ))}
            </div>
          )}
          <div className="visual-summary">
            <div>
              <span>Readability</span>
              <strong>{visual.readability || 'Not assessed'}</strong>
            </div>
            <div>
              <span>Font height</span>
              <strong>{visual.font_height ? `${visual.font_height} mm` : 'Not assessed'}</strong>
            </div>
            <div>
              <span>Placement</span>
              <strong>{visual.placement || 'Not assessed'}</strong>
            </div>
          </div>
          {displayedImageUrl && (
            <div className="detail-image-section">
              <div className="detail-image-header">
                <div className="eyebrow">
                  {imageMode === 'overlay' && hasOverlay ? 'AI Detection Overlay' : 'Original Label Photo'}
                </div>
                {hasOverlay && hasRaw && (
                  <div className="image-mode-toggle" role="group" aria-label="Label image view mode">
                    <button
                      type="button"
                      className={`image-mode-btn ${imageMode === 'raw' ? 'active' : ''}`}
                      onClick={() => setImageMode('raw')}
                    >
                      <Eye size={13} /> Original
                    </button>
                    <button
                      type="button"
                      className={`image-mode-btn ${imageMode === 'overlay' ? 'active' : ''}`}
                      onClick={() => setImageMode('overlay')}
                    >
                      <Layers size={13} /> Detection Overlay
                    </button>
                  </div>
                )}
              </div>
              <div className="detail-image-frame">
                <img
                  src={displayedImageUrl}
                  alt={fullInspection.product?.name || 'Inspected product label'}
                />
                {imageMode === 'overlay' && hasOverlay && (
                  <div className="overlay-badge">
                    <Layers size={12} /> Bounding Boxes Active
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
        <section className="panel declarations-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">Rule 6 declarations</div>
              <h2>{isEditing ? 'Edit declarations' : 'Extracted fields'}</h2>
            </div>
            <div className="panel-header-actions">
              {!isEditing ? (
                <button
                  type="button"
                  className="button secondary small field-action-btn"
                  onClick={startEditing}
                  title="Correct or override misread declarations"
                >
                  <Edit3 size={13} /> Edit
                </button>
              ) : (
                <div className="edit-btn-group">
                  <button
                    type="button"
                    className="button text-button small"
                    onClick={cancelEditing}
                    disabled={saving}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="button primary small field-action-btn"
                    onClick={handleSave}
                    disabled={saving}
                  >
                    {saving ? (
                      <>
                        <LoaderCircle className="spinner" size={13} /> Saving...
                      </>
                    ) : (
                      <>
                        <Save size={13} /> Save & Re-evaluate
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>

          {saveSuccess && (
            <div className="form-success banner">
              <CheckCircle2 size={16} /> Declarations updated! Rules re-evaluated in real time.
            </div>
          )}
          {saveError && (
            <div className="form-error banner">
              <XCircle size={16} /> {saveError}
            </div>
          )}

          <div className="field-list">
            {FIELD_DEFINITIONS.map(({ key, label }) => {
              const value = fields[key]
              return (
                <div className={`field-row ${isEditing ? 'editing' : ''}`} key={key}>
                  <span>{label}</span>
                  {isEditing ? (
                    <input
                      className="edit-field-input"
                      value={editFields[key] ?? ''}
                      placeholder={`Enter ${label.toLowerCase()}...`}
                      onChange={(e) =>
                        setEditFields((prev) => ({ ...prev, [key]: e.target.value }))
                      }
                    />
                  ) : (
                    <strong className={!value ? 'missing' : ''}>
                      {value || 'Not detected'}
                    </strong>
                  )}
                </div>
              )
            })}
          </div>
          <div className="ocr-count">
            <Activity size={15} /> {ocr.texts?.length || 0} text regions detected by OCR
          </div>
        </section>
      </div>
      <section className="inspection-results" aria-label="Inspection result">
        <div className="result-section-heading"><div><div className="eyebrow">Inspection result</div><h2>Compliance at a glance</h2></div></div>
        <div className="result-charts">
          <DonutChart label="Rule Compliance" value={compliancePercentage} primaryClass="compliance" primaryLabel="Compliant" secondaryLabel="Non-compliant" />
          <DonutChart label="Result Confidence" value={confidencePercentage} primaryClass="confidence" primaryLabel="Confidence" secondaryLabel="Uncertainty" />
        </div>
        <div className="rule-results">
          <div className="rule-group obeyed"><div className="eyebrow">Rules obeyed</div>{ruleSummary.obeyed.length ? ruleSummary.obeyed.map((rule, index) => <div className="rule-result" key={`${rule.name}-${index}`}><CheckCircle2 size={17} /><span>{rule.name}</span>{rule.reason && <small>{rule.reason}</small>}</div>) : <p>No passed rules returned.</p>}</div>
          <div className="rule-group not-obeyed"><div className="eyebrow">Rules not obeyed</div>{ruleSummary.notObeyed.length ? ruleSummary.notObeyed.map((rule, index) => <div className="rule-result" key={`${rule.name}-${index}`}><AlertTriangle size={17} /><span>{rule.name}</span>{rule.reason && <small>{rule.reason}</small>}</div>) : <p>No failed rules returned.</p>}</div>
        </div>
        {ruleSummary.review.length > 0 && <div className="rule-group review-rules"><div className="eyebrow">Rules requiring review</div>{ruleSummary.review.map((rule, index) => <div className="rule-result" key={`${rule.name}-${index}`}><CircleHelp size={17} /><span>{rule.name}</span>{rule.reason && <small>{rule.reason}</small>}</div>)}</div>}
        <button className="button primary report-enforcement" onClick={onReport}><Send size={16} /> Report to Enforcement Official</button>
      </section>
    </div>
  )
}

function EnforcementView({ user, inspection, onNavigate }) {
  const [form, setForm] = useState({ productName: inspection?.product?.name || '', inspectionId: inspection?.inspection_id || '', issue: '', message: '', details: '' })
  const [submitted, setSubmitted] = useState(null)
  useEffect(() => setForm((current) => ({ ...current, productName: inspection?.product?.name || current.productName, inspectionId: inspection?.inspection_id || current.inspectionId })), [inspection])
  function submit(event) { event.preventDefault(); setSubmitted({ id: `CMP-${Date.now().toString().slice(-6)}`, date: new Date() }) }
  if (submitted) return <div className="page"><PageIntro eyebrow="Complaint submitted" title="Report received." description="Your inspection report has been prepared as supporting evidence." /><section className="panel submission-success"><CheckCircle2 size={28} /><h2>{submitted.id}</h2><p>Submitted {formatDate(submitted.date)} · Status: <strong>Submitted</strong></p><button className="button primary" onClick={() => onNavigate('history')}>View inspection history</button></section></div>
  return <div className="page enforcement-page"><PageIntro eyebrow="Enforcement" title="Report an issue." description="Submit a concise complaint with the current inspection report attached." /><div className="enforcement-grid"><form className="panel enforcement-form" onSubmit={submit}><label>Product name<input required value={form.productName} onChange={(event) => setForm({ ...form, productName: event.target.value })} /></label><label>Inspection ID<input required value={form.inspectionId} onChange={(event) => setForm({ ...form, inspectionId: event.target.value })} /></label><label>Complaint / issue<input required value={form.issue} placeholder="e.g. Missing mandatory expiry declaration" onChange={(event) => setForm({ ...form, issue: event.target.value })} /></label><label>Description / message<textarea required rows="4" placeholder="Describe the issue for the enforcement official." value={form.message} onChange={(event) => setForm({ ...form, message: event.target.value })} /></label><label>Additional details <span>Optional</span><textarea rows="2" value={form.details} onChange={(event) => setForm({ ...form, details: event.target.value })} /></label><div className="contact-note"><UserRound size={15} /> Submitted by {user.full_name || 'Authenticated user'}{user.email ? ` · ${user.email}` : ''}</div><div className="report-attachment"><Paperclip size={17} /><div><strong>Inspection report attached</strong><span>{inspection ? `Report_${inspection.inspection_id}.pdf` : 'A report will attach after an inspection.'}</span></div></div><button className="button primary" disabled={!inspection}><Send size={16} /> Submit complaint</button></form><section className="panel official-resources"><div className="eyebrow">Official Food Safety Resources</div><h2>Useful government links</h2>{[['FSSAI', 'https://www.fssai.gov.in/'], ['Food Safety Connect / FoSCoS', 'https://foscos.fssai.gov.in/'], ['National Consumer Helpline', 'https://consumerhelpline.gov.in/'], ['FSSAI State Helpdesk', 'https://www.fssai.gov.in/states/helpdesk']].map(([label, url]) => <a key={url} href={url} target="_blank" rel="noreferrer">{label}<ExternalLink size={14} /></a>)}</section></div></div>
}

function DocumentationView() {
  const sections = [['Project overview', 'Synaptix converts package-label evidence into traceable compliance decisions for enforcement teams.'], ['System architecture', 'React workspace → API service → OCR / vision pipeline → rule validation → report output.'], ['Frontend architecture', 'Single Vite React application with role-aware views, shared UI primitives, theme tokens and API abstraction.'], ['Backend / API architecture', 'Authenticated API calls retrieve dashboard data, inspections and reports; offline mode supplies a safe demo fallback.'], ['OCR / vision pipeline', 'Image evidence is processed for extracted declarations and visual readability checks.'], ['Rule validation & compliance logic', 'Extracted fields and visual checks are evaluated into passed rules, violations, a compliance percentage and confidence.'], ['Data flow', 'Capture → inspection → result → report / enforcement complaint.'], ['Authentication and roles', 'Users are restricted to their own inspection records; administrators can monitor all records and analytics.'], ['Report generation', 'Reports include evidence, extracted details, decision metrics and rule findings.'], ['Deployment configuration', 'Set VITE_API_BASE_URL to connect the workspace to a deployed backend.']]
  return <div className="page documentation-page"><PageIntro eyebrow="Admin reference" title="Technical documentation." description="A concise implementation reference for the Synaptix workspace." /> <div className="documentation-list">{sections.map(([title, copy], index) => <section className="panel" key={title}><span>{String(index + 1).padStart(2, '0')}</span><div><h2>{title}</h2><p>{copy}</p></div></section>)}</div></div>
}

export default App
