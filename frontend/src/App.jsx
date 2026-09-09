import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, ArrowLeft, ArrowUpRight, BarChart3, Bell, Camera, Check, ChevronRight, CircleHelp,
  ClipboardCheck, FileText, History, ImagePlus, LayoutDashboard, LoaderCircle,
  LockKeyhole, LogOut, Mail, Menu, Moon, ScanLine, Search, Settings, ShieldCheck,
  SlidersHorizontal, StopCircle, Sun, SwitchCamera, UploadCloud, UserRound, X, XCircle
} from 'lucide-react'
import { api, demoInspections } from './api'
import { demoStats } from './demoData'

const navItems = [
  { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
  { id: 'scan', label: 'New inspection', icon: ImagePlus },
  { id: 'history', label: 'Inspection history', icon: History }
]

const statusMeta = {
  PASS: { label: 'Compliant', className: 'pass', icon: Check },
  FAIL: { label: 'Non-compliant', className: 'fail', icon: X },
  REVIEW: { label: 'Needs review', className: 'review', icon: CircleHelp }
}

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
      onAuthenticated({ ...(result.user || {}), full_name: result.user?.full_name || form.fullName || (role === 'user' ? 'Synaptix User' : 'Synaptix Admin'), role })
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
  const [stats, setStats] = useState(normalizeStats())
  const [inspections, setInspections] = useState(demoInspections)
  const [isDemo, setIsDemo] = useState(true)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState('')
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.localStorage.getItem('synaptix_sidebar_collapsed') === 'true')

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
    setUser(nextUser)
    setAuthenticated(true)
    window.localStorage.setItem('synaptix_authenticated', 'true')
    window.localStorage.setItem('synaptix_user', JSON.stringify(nextUser))
  }

  if (!authenticated) return <EntryFlow onAuthenticated={handleAuthenticated} theme={theme} onToggleTheme={toggleTheme} />

  function openInspection(id) {
    setSelectedId(id)
    setActiveView('detail')
  }

  function handleInspectionComplete(result) {
    setInspections((current) => [result, ...current.filter((item) => item.inspection_id !== result.inspection_id)])
    setSelectedId(result.inspection_id)
    setActiveView('detail')
    setIsDemo(false)
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''} ${mobileNavOpen ? 'open' : ''}`}>
        <div className="brand"><div className="brand-mark"><ShieldCheck size={20} /></div><div><strong>synaptix</strong><span>field intelligence</span></div></div>
        <div className="workspace-label">Workspace <span>LIVE</span></div>
        <nav className="primary-nav" aria-label="Primary navigation">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              title={sidebarCollapsed ? label : undefined}
              className={`${activeView === id ? 'nav-item active' : 'nav-item'} ${id === 'dashboard' ? 'overview-nav-item' : `${id}-nav-item`}`}
              onClick={() => { setActiveView(id); setSelectedId(null); setMobileNavOpen(false) }}
            >
              <Icon size={18} />
              <span>{label}</span>
              {id === 'history' && <span className="nav-count">{stats.total}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-section">
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
            title={sidebarCollapsed ? 'Configuration' : undefined}
            className={`${activeView === 'configuration' ? 'nav-item active' : 'nav-item'} configuration-nav-item`}
            onClick={() => { setActiveView('configuration'); setSelectedId(null); setMobileNavOpen(false) }}
          >
            <Settings size={18} />
            <span>Configuration</span>
          </button>
        </div>
        <div className="sidebar-footer">
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
          <div className="user-chip" title={sidebarCollapsed ? user.full_name || 'Riya Kapoor' : undefined}>
            <div className="avatar">{(user.full_name || 'RK').split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()}</div>
            <div><strong>{user.full_name || 'Riya Kapoor'}</strong><span>{user.role === 'admin' ? 'Administrator' : 'User account'}</span></div>
            <ChevronRight size={16} />
          </div>
          <button
            className="logout"
            title={sidebarCollapsed ? 'Sign out' : undefined}
            onClick={() => { setAuthenticated(false); window.localStorage.removeItem('synaptix_authenticated'); window.localStorage.removeItem('synaptix_user') }}
          >
            <LogOut size={16} /> Sign out
          </button>
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
              <strong>{activeView === 'detail' ? 'Inspection detail' : activeView === 'configuration' ? 'Configuration' : activeView === 'analytics' ? 'Analytics' : navItems.find((item) => item.id === activeView)?.label || 'Overview'}</strong>
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
        {activeView === 'scan' && <Scan onComplete={handleInspectionComplete} onCancel={() => setActiveView('dashboard')} />}
        {activeView === 'history' && <HistoryView inspections={inspections} onOpen={openInspection} onNavigate={setActiveView} />}
        {activeView === 'detail' && <Detail inspection={selectedInspection} onBack={() => setActiveView('history')} />}
        {activeView === 'analytics' && <AnalyticsView stats={stats} inspections={inspections} />}
        {activeView === 'configuration' && <ConfigurationView theme={theme} onToggleTheme={toggleTheme} />}
      </main>
    </div>
  )
}

function PageIntro({ eyebrow, title, description, action }) {
  return <div className="page-intro"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>
}

function Dashboard({ user, stats, inspections, loading, onNavigate, onOpen }) {
  const firstName = (user?.full_name || 'Riya').split(' ')[0]
  const todayStr = new Intl.DateTimeFormat('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date())
  return <div className="page"><PageIntro eyebrow={todayStr} title={`Good morning, ${firstName}.`} description="Your compliance desk at a glance." action={<button className="button primary" onClick={() => onNavigate('scan')}><ImagePlus size={17} /> Start inspection</button>} />
    <section className="metric-grid"><Metric label="Total inspections" value={stats.total} detail="All time" icon={ClipboardCheck} tone="ink" /><Metric label="Compliance rate" value={`${Number(stats.rate).toFixed(1)}%`} detail="Across all inspections" icon={ShieldCheck} tone="green" /><Metric label="Need attention" value={stats.fail + stats.review} detail={`${stats.fail} failed · ${stats.review} review`} icon={Bell} tone="orange" /><Metric label="Recent alerts" value={stats.alerts} detail="Flagged violations" icon={Activity} tone="red" /></section>
    <div className="content-grid"><section className="panel recent-panel"><div className="panel-heading"><div><div className="eyebrow">Latest activity</div><h2>Recent inspections</h2></div><button className="text-button" onClick={() => onNavigate('history')}>View all <ArrowUpRight size={15} /></button></div>{loading ? <LoadingRows /> : <InspectionTable inspections={inspections.slice(0, 4)} onOpen={onOpen} />}</section><section className="panel distribution-panel"><div className="panel-heading"><div><div className="eyebrow">Compliance pulse</div><h2>Decision split</h2></div><SlidersHorizontal size={18} className="muted-icon" /></div><div className="donut-wrap"><div className="donut" style={{ '--pass': `${stats.total ? stats.pass / stats.total * 100 : 0}%`, '--fail': `${stats.total ? stats.fail / stats.total * 100 : 0}%` }}><div><strong>{Number(stats.rate).toFixed(0)}%</strong><span>compliant</span></div></div></div><div className="legend"><Legend color="green" label="Compliant" value={stats.pass} /><Legend color="red" label="Non-compliant" value={stats.fail} /><Legend color="yellow" label="Needs review" value={stats.review} /></div></section></div>
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

function Scan({ onComplete, onCancel }) {
  const [file, setFile] = useState(null)
  const [productName, setProductName] = useState('')
  const [category, setCategory] = useState('Packaged Commodity')
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [cameraOpen, setCameraOpen] = useState(false)
  const [cameraError, setCameraError] = useState('')
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
  async function submit(event) { event.preventDefault(); if (!file) return setError('Choose an image or capture a label first.'); setSubmitting(true); setError(''); try { onComplete(await api.inspect({ file, productName, category })) } catch (caught) { setError(caught.message) } finally { setSubmitting(false) } }
  function acceptFile(nextFile) { if (nextFile && nextFile.type.startsWith('image/')) { setFile(nextFile); setError('') } else setError('Please choose a JPG, PNG, or WEBP image.') }
  return <div className="page scan-page"><PageIntro eyebrow="New inspection" title="Read the label." description="Capture a live package image or upload a clear photo for analysis." action={<button className="text-button" onClick={onCancel}>Cancel</button>} /><form className="scan-layout" onSubmit={submit}><div className="scan-main">{cameraOpen ? <div className="camera-viewfinder"><video ref={videoRef} playsInline muted /><div className="viewfinder-frame"><i /><i /><i /><i /></div><div className="viewfinder-guide"><ScanLine size={16} /> Align the full label inside the frame</div><div className="camera-controls"><button type="button" className="camera-control" onClick={stopCamera}><StopCircle size={18} /> Close</button><button type="button" className="capture-button" onClick={capturePhoto} aria-label="Capture label photo"><Camera size={22} /></button><button type="button" className="camera-control" onClick={startCamera}><SwitchCamera size={18} /> Reset</button></div></div> : <><div className={`upload-zone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFile(event.dataTransfer.files[0]) }}><input id="label-image" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => acceptFile(event.target.files[0])} />{file ? <div className="file-preview"><ImagePlus size={25} /><div><strong>{file.name}</strong><span>{(file.size / 1024 / 1024).toFixed(2)} MB · ready for analysis</span></div><button type="button" className="remove-file" onClick={() => setFile(null)} aria-label="Remove file"><X size={17} /></button></div> : <label htmlFor="label-image"><div className="upload-icon"><UploadCloud size={24} /></div><strong>Drop the product label here</strong><span>or <u>browse files</u> · JPG, PNG or WEBP up to 10 MB</span></label>}</div><button type="button" className="camera-launch" onClick={startCamera}><Camera size={17} /> Use live camera</button></>}{cameraError && <div className="form-error camera-error"><Camera size={16} />{cameraError}</div>}<div className="scan-note"><ShieldCheck size={17} /><span>The image is processed by the Synaptix inspection pipeline. No source images are sent anywhere except your configured backend.</span></div></div><aside className="scan-sidebar"><div className="panel form-panel"><div className="eyebrow">Inspection context</div><h2>Tell us what we are looking at.</h2><label>Product name <span>Optional</span><input value={productName} onChange={(event) => setProductName(event.target.value)} placeholder="e.g. Harvest Gold Rice" /></label><label>Category<select value={category} onChange={(event) => setCategory(event.target.value)}><option>Packaged Commodity</option><option>Food & beverage</option><option>Personal care</option><option>Household</option><option>Other</option></select></label>{error && <div className="form-error"><XCircle size={16} />{error}</div>}<button className="button primary wide" disabled={submitting}>{submitting ? <><LoaderCircle className="spinner" size={17} /> Analysing label...</> : <><ClipboardCheck size={17} /> Run inspection</>}</button></div><div className="pipeline-list"><div className="eyebrow">What happens next</div><PipelineStep number="01" title="Extract" text="OCR finds mandatory declarations." /><PipelineStep number="02" title="Check" text="Visual rules assess readability." /><PipelineStep number="03" title="Decide" text="Rule 6 produces the result." /></div></aside></form></div>
}
function PipelineStep({ number, title, text }) { return <div className="pipeline-step"><span>{number}</span><div><strong>{title}</strong><small>{text}</small></div></div> }

function HistoryView({ inspections, onOpen, onNavigate }) { const [search, setSearch] = useState(''); const [filter, setFilter] = useState('ALL'); const filtered = inspections.filter((item) => (filter === 'ALL' || item.compliance?.status === filter) && `${item.inspection_id} ${item.product?.name || ''}`.toLowerCase().includes(search.toLowerCase())); return <div className="page"><PageIntro eyebrow="Inspection repository" title="History, with context." description="Search every label that has moved through the compliance pipeline." action={<button className="button primary" onClick={() => onNavigate('scan')}><ImagePlus size={17} /> New inspection</button>} /><section className="panel history-panel"><div className="filter-bar"><div className="search-field"><Search size={17} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search ID or product name" /></div><div className="filter-tabs">{['ALL', 'PASS', 'FAIL', 'REVIEW'].map((value) => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{value === 'ALL' ? 'All results' : statusMeta[value].label}</button>)}</div></div><InspectionTable inspections={filtered} onOpen={onOpen} /></section></div> }

<<<<<<< HEAD
function getFieldLabel(text) {
  const value = text.toLowerCase()
  if (/mrp|maximum retail|rs\.?\s*\d|₹/.test(value)) return 'MRP'
  if (/net|\b\d+(\.\d+)?\s*(kg|g|ml|l|mg)\b/.test(value)) return 'Net Qty'
  if (/manufactur|packed by|brand/.test(value)) return 'Manufacturer'
  if (/origin|made in|country/.test(value)) return 'Origin'
  if (/date|mfg|exp|best before/.test(value)) return 'Date'
  if (/care|consumer|helpline|contact|phone/.test(value)) return 'Consumer Care'
  return 'Detected text'
}

function LabelVisualizer({ inspection, ocr, fields }) {
  const imageRef = useRef(null)
  const [dimensions, setDimensions] = useState({ width: 1, height: 1 })
  const imageUrl = inspection.image_url || inspection.image?.url
  const texts = ocr.texts || []
  function boxStyle(bbox = []) {
    const [x1 = 0, y1 = 0, x2 = 0, y2 = 0] = bbox
    const unit = Math.max(...bbox) <= 1 ? 'ratio' : 'pixel'
    const left = unit === 'ratio' ? x1 * 100 : x1 / dimensions.width * 100
    const top = unit === 'ratio' ? y1 * 100 : y1 / dimensions.height * 100
    const boxWidth = x2 > x1 ? x2 - x1 : x2
    const boxHeight = y2 > y1 ? y2 - y1 : y2
    const width = unit === 'ratio' ? Math.max(boxWidth * 100, 5) : Math.max(boxWidth / dimensions.width * 100, 5)
    const height = unit === 'ratio' ? Math.max(boxHeight * 100, 4) : Math.max(boxHeight / dimensions.height * 100, 4)
    return { left: `${left}%`, top: `${top}%`, width: `${width}%`, height: `${height}%` }
  }
  const required = [['MRP', fields.mrp], ['Net Qty', fields.net_quantity], ['Manufacturer', fields.manufacturer], ['Consumer Care', fields.consumer_care]]
  if (!imageUrl) return <section className="panel visualizer-panel visualizer-empty"><div className="visualizer-heading"><div><div className="eyebrow">Validation visualizer</div><h2>Label evidence</h2></div><ScanLine size={18} className="muted-icon" /></div><div className="visualizer-placeholder"><ImagePlus size={25} /><strong>Source image unavailable</strong><span>Bounding boxes will appear here when the backend returns `image_url` and OCR coordinates.</span></div></section>
  return <section className="panel visualizer-panel"><div className="visualizer-heading"><div><div className="eyebrow">Validation visualizer</div><h2>Label evidence</h2><p>OCR regions and declaration checks over the scanned image.</p></div><span className="visualizer-legend"><i className="box-pass" /> Detected <i className="box-missing" /> Missing</span></div><div className="visualizer-stage"><img ref={imageRef} src={imageUrl} alt="Scanned product label" onLoad={(event) => setDimensions({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} />{texts.filter((item) => item.bbox?.length >= 4).map((item, index) => <div className={`bbox ${item.text ? 'detected' : 'missing'}`} style={boxStyle(item.bbox)} key={`${item.text}-${index}`}><span>{getFieldLabel(item.text)}</span></div>)}</div><div className="visualizer-fields">{required.map(([label, value]) => <div className={`visualizer-field ${value ? 'found' : 'missing'}`} key={label}>{value ? <Check size={14} /> : <CircleHelp size={14} />}<span>{label}</span><strong>{value || 'Not detected'}</strong></div>)}</div></section>
}

function Detail({ inspection, onBack }) { const [loading, setLoading] = useState(false); const [fullInspection, setFullInspection] = useState(inspection); useEffect(() => { if (!inspection) return; api.getInspection(inspection.inspection_id).then(setFullInspection).catch(() => {}) }, [inspection]); if (!fullInspection) return <div className="page empty-state"><CircleHelp size={26} /><h2>Inspection not found</h2><button className="text-button" onClick={onBack}>Back to history</button></div>; const { fields = {}, visual_checks: visual = {}, compliance = {}, ocr_raw: ocr = {} } = fullInspection; async function download() { setLoading(true); try { await api.downloadReport(fullInspection.inspection_id) } catch (error) { window.alert(error.message) } finally { setLoading(false) } } return <div className="page"><button className="back-button" onClick={onBack}><ChevronRight size={16} className="back-chevron" /> Back to history</button><PageIntro eyebrow={fullInspection.inspection_id} title={fullInspection.product?.name || 'Unnamed product'} description={`${fullInspection.product?.category || 'Packaged commodity'} · inspected ${formatDate(fullInspection.created_at)}`} action={<button className="button secondary" onClick={download} disabled={loading}><FileText size={17} /> {loading ? 'Preparing...' : 'Download certificate'}</button>} /><LabelVisualizer inspection={fullInspection} ocr={ocr} fields={fields} /><div className="detail-grid"><section className="panel result-panel"><div className="detail-result"><div><div className="eyebrow">Final decision</div><h2>{statusMeta[compliance.status]?.label || 'Needs review'}</h2><p>{compliance.violations?.length ? `${compliance.violations.length} declaration issue${compliance.violations.length === 1 ? '' : 's'} detected.` : 'All required declarations passed the current checks.'}</p></div><StatusBadge status={compliance.status} /></div>{compliance.violations?.length > 0 && <div className="violations"><div className="eyebrow">Findings</div>{compliance.violations.map((violation) => <div className="violation" key={violation}><XCircle size={16} />{violation}</div>)}</div>}<div className="visual-summary"><div><span>Readability</span><strong>{visual.readability || 'Not assessed'}</strong></div><div><span>Font height</span><strong>{visual.font_height ? `${visual.font_height} mm` : 'Not assessed'}</strong></div><div><span>Placement</span><strong>{visual.placement || 'Not assessed'}</strong></div></div></section><section className="panel declarations-panel"><div className="panel-heading"><div><div className="eyebrow">Rule 6 declarations</div><h2>Extracted fields</h2></div><ClipboardCheck size={18} className="muted-icon" /></div><div className="field-list">{[['Manufacturer', fields.manufacturer], ['Country of origin', fields.country_of_origin], ['Net quantity', fields.net_quantity], ['Manufacture date', fields.manufacture_date], ['Maximum retail price', fields.mrp], ['Consumer care', fields.consumer_care]].map(([label, value]) => <div className="field-row" key={label}><span>{label}</span><strong className={!value ? 'missing' : ''}>{value || 'Not detected'}</strong></div>)}</div><div className="ocr-count"><Activity size={15} /> {ocr.texts?.length || 0} text regions detected by OCR</div></section></div></div> }
=======
function Detail({ inspection, onBack }) {
  const [loading, setLoading] = useState(false)
  const [fullInspection, setFullInspection] = useState(inspection)
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

  async function download() {
    setLoading(true)
    try {
      await api.downloadReport(fullInspection.inspection_id)
    } catch (error) {
      window.alert(error.message)
    } finally {
      setLoading(false)
    }
  }

  const rawUrl = fullInspection.image_url
  const imageUrl = rawUrl ? (rawUrl.startsWith('http') ? rawUrl : `${(import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')}${rawUrl}`) : null

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
          <button className="button secondary" onClick={download} disabled={loading}>
            <FileText size={17} /> {loading ? 'Preparing...' : 'Download certificate'}
          </button>
        }
      />
      <div className="detail-grid">
        <section className="panel result-panel">
          <div className="detail-result">
            <div>
              <div className="eyebrow">Final decision</div>
              <h2>{statusMeta[compliance.status]?.label || 'Needs review'}</h2>
              <p>
                {compliance.violations?.length
                  ? `${compliance.violations.length} declaration issue${compliance.violations.length === 1 ? '' : 's'} detected.`
                  : 'All required declarations passed the current checks.'}
              </p>
            </div>
            <StatusBadge status={compliance.status} />
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
          {imageUrl && (
            <div className="detail-image-section">
              <div className="eyebrow">Inspected label photo</div>
              <div className="detail-image-frame">
                <img src={imageUrl} alt={fullInspection.product?.name || 'Inspected product label'} />
              </div>
            </div>
          )}
        </section>
        <section className="panel declarations-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">Rule 6 declarations</div>
              <h2>Extracted fields</h2>
            </div>
            <ClipboardCheck size={18} className="muted-icon" />
          </div>
          <div className="field-list">
            {[
              ['Manufacturer', fields.manufacturer],
              ['Country of origin', fields.country_of_origin],
              ['Net quantity', fields.net_quantity],
              ['Manufacture date', fields.manufacture_date],
              ['Maximum retail price', fields.mrp],
              ['Consumer care', fields.consumer_care],
            ].map(([label, value]) => (
              <div className="field-row" key={label}>
                <span>{label}</span>
                <strong className={!value ? 'missing' : ''}>{value || 'Not detected'}</strong>
              </div>
            ))}
          </div>
          <div className="ocr-count">
            <Activity size={15} /> {ocr.texts?.length || 0} text regions detected by OCR
          </div>
        </section>
      </div>
    </div>
  )
}
>>>>>>> origin/main

export default App
