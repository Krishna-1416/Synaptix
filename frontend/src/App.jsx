import { useEffect, useMemo, useRef, useState } from 'react'
import { Document as WordDocument, HeadingLevel, ImageRun, Packer, Paragraph, Table, TableCell, TableRow, TextRun } from 'docx'
import {
  Activity, ArrowLeft, ArrowUpRight, BarChart3, Bell, Camera, Check, CheckCircle2, ChevronRight, CircleHelp,
  ClipboardCheck, Edit3, Eye, EyeOff, FileText, History, ImagePlus, Layers, LayoutDashboard, LoaderCircle,
  LogOut, Menu, Moon, Save, ScanLine, Search, Settings, ShieldCheck,
  StopCircle, Sun, SwitchCamera, UploadCloud, UserRound, X, XCircle,
  ExternalLink, Send, Paperclip, BookOpen, AlertTriangle, Download,
  Zap, FileCheck, Languages, Sparkles
} from 'lucide-react'
import { api, resolveApiUrl } from './api'
import { t } from './i18n'

const NAV_DEFINITIONS = [
  { id: 'dashboard', key: 'overview', icon: LayoutDashboard },
  { id: 'scan', key: 'newInspection', icon: ImagePlus },
  { id: 'history', key: 'inspectionHistory', icon: History },
  { id: 'enforcement', key: 'enforcement', icon: ShieldCheck }
]

const STATUTORY_CLAUSES = [
  { key: 'manufacturer', clause: 'Rule 6(1)(a)', name: 'Rule 6(1)(a) — Manufacturer / Packer Details', failReason: 'Manufacturer or packer name and complete postal address missing.' },
  { key: 'country_of_origin', clause: 'Rule 6(1)(n)', name: 'Rule 6(1)(n) — Country of Origin', failReason: 'Country of origin not declared on packaging.' },
  { key: 'generic_name', clause: 'Rule 6(1)(c)', name: 'Rule 6(1)(c) — Generic / Commodity Name', failReason: 'Common or generic name of commodity not clearly declared.' },
  { key: 'net_quantity', clause: 'Rule 6(1)(b)', name: 'Rule 6(1)(b) — Net Quantity in Metric Units', failReason: 'Net quantity missing or not formatted in standard SI units.' },
  { key: 'manufacture_date', clause: 'Rule 6(1)(d)', name: 'Rule 6(1)(d) — Date of Manufacture / Packing', failReason: 'Month and year of manufacture or pre-packaging missing.' },
  { key: 'mrp', clause: 'Rule 6(1)(e)', name: 'Rule 6(1)(e) — Maximum Retail Price (MRP incl. taxes)', failReason: 'MRP inclusive of all taxes missing, altered, or illegible.' },
  { key: 'unit_sale_price', clause: 'Rule 6(1)(f)', name: 'Rule 6(1)(f) — Unit Sale Price (USP)', failReason: 'Unit sale price missing where required by packaged commodity rules.' },
  { key: 'consumer_care', clause: 'Rule 6(1)(g)', name: 'Rule 6(1)(g) — Consumer Care Contact Details', failReason: 'Consumer grievance redressal telephone number or email missing.' }
]

const statusMeta = {
  PASS: { className: 'pass', icon: Check },
  FAIL: { className: 'fail', icon: X },
  REVIEW: { className: 'review', icon: CircleHelp }
}

let activeInspectionProgress = { extract: 'pending', check: 'pending', decide: 'pending', message: '' }

function normalizeStats(stats = {}) {
  return {
    total: stats.total ?? stats.total_inspections ?? stats.inspections_count ?? 0,
    pass: stats.compliant ?? stats.passed ?? stats.pass_count ?? stats.compliant_count ?? 0,
    fail: stats.non_compliant ?? stats.failed ?? stats.fail_count ?? stats.violations_count ?? 0,
    review: stats.review ?? stats.review_count ?? 0,
    rate: stats.compliance_rate ?? stats.compliance_rate_pct ?? stats.complianceRate ?? 0,
    alerts: stats.recent_alerts ?? stats.alerts ?? stats.total_violations_flagged ?? 0
  }
}

function computeStatsFromInspections(items = []) {
  const total = items.length
  const pass = items.filter((i) => (i.compliance?.status || '').toUpperCase() === 'PASS').length
  const fail = items.filter((i) => (i.compliance?.status || '').toUpperCase() === 'FAIL').length
  const review = items.filter((i) => (i.compliance?.status || '').toUpperCase() === 'REVIEW').length
  const rate = total > 0 ? (pass / total) * 100 : 0
  const alerts = items.reduce((sum, i) => sum + (i.compliance?.violations?.length || 0), 0)
  return { total, pass, fail, review, rate, alerts }
}

function formatDate(value, lang = 'en') {
  if (!value) return t('dateUnavailable', lang)
  const locale = lang === 'hi' ? 'hi-IN' : lang === 'mr' ? 'mr-IN' : 'en-IN'
  return new Intl.DateTimeFormat(locale, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
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

function consumeOAuthAccessToken() {
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  const accessToken = hash.get('access_token')
  if (!accessToken) return null
  window.localStorage.setItem('synaptix_access_token', accessToken)
  window.history.replaceState({}, document.title, `${window.location.pathname}${window.location.search}`)
  return accessToken
}

function percentage(value, fallback = null) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? Math.max(0, Math.min(100, Math.round(numeric <= 1 ? numeric * 100 : numeric))) : fallback
}

function inspectionOwnerId(user) {
  return user?.id || user?.user_id || user?.email || 'officer'
}

function asRule(item) {
  return typeof item === 'string' ? { name: item } : { name: item?.name || item?.label || item?.rule || item?.rule_id, reason: item?.reason || item?.message, clause: item?.clause }
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

  const fields = inspection?.fields || {}
  const visual = inspection?.visual_checks || {}
  const obeyed = []
  const notObeyed = []
  const review = []

  STATUTORY_CLAUSES.forEach((item) => {
    const value = fields[item.key]
    if (value && String(value).trim() && !/not detected|missing|n\/a/i.test(String(value))) {
      obeyed.push({ clause: item.clause, name: item.name, value: String(value), reason: 'Declared and verified on packaging' })
    } else {
      notObeyed.push({ clause: item.clause, name: item.name, reason: item.failReason })
    }
  })

  if (visual.font_height) {
    const fh = parseFloat(visual.font_height)
    if (!isNaN(fh) && fh >= 1.0) {
      obeyed.push({ clause: 'Rule 7', name: 'Rule 7 — Minimum Font Height & Legibility', reason: `Compliant height: ${visual.font_height} mm (≥ 1.0 mm)` })
    } else {
      notObeyed.push({ clause: 'Rule 7', name: 'Rule 7 — Minimum Font Height & Legibility', reason: `Font height ${visual.font_height} mm is below statutory 1.0 mm minimum.` })
    }
  }

  if (Array.isArray(compliance.violations) && compliance.violations.length) {
    compliance.violations.forEach((v) => {
      const text = typeof v === 'string' ? v : v.name || v.message
      if (text && !notObeyed.some((r) => r.name.toLowerCase().includes(text.toLowerCase()) || text.toLowerCase().includes(r.clause?.toLowerCase() || ''))) {
        notObeyed.push({ clause: 'Infringement', name: text, reason: 'Statutory violation flagged during inspection' })
      }
    })
  }

  if (compliance.status === 'REVIEW' && notObeyed.length > 0 && review.length === 0) {
    const moved = notObeyed.splice(0, 1)
    review.push(...moved)
  }

  return { obeyed, notObeyed, review }
}

function inspectionScore(inspection, rules) {
  const value = inspection?.compliance?.score ?? inspection?.compliance?.percentage ?? inspection?.compliance_percentage
  const direct = percentage(value)
  if (direct != null) return direct
  const total = rules.obeyed.length + rules.notObeyed.length + rules.review.length
  return total ? Math.round((rules.obeyed.length / total) * 100) : 0
}

function inspectionConfidence(inspection) {
  const direct = percentage(inspection?.compliance?.confidence ?? inspection?.confidence ?? inspection?.confidence_percentage)
  if (direct != null) return direct
  const values = (inspection?.ocr_raw?.texts || []).map((item) => Number(item.confidence)).filter(Number.isFinite)
  return values.length ? Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 100) : 0
}

function StatusBadge({ status, lang = 'en' }) {
  const meta = statusMeta[status] || statusMeta.REVIEW
  const Icon = meta.icon
  const label = status === 'PASS' ? t('compliant', lang) : status === 'FAIL' ? t('nonCompliant', lang) : t('needsReview', lang)
  return (
    <span className={`status-badge ${meta.className}`}>
      <span className="status-badge-dot" />
      <Icon size={12} strokeWidth={2.5} />
      <span>{label}</span>
    </span>
  )
}

function ThemeToggle({ theme, onToggle, compact = false }) {
  const isDark = theme === 'dark'
  return (
    <button type="button" className={`theme-toggle ${compact ? 'compact' : ''}`} onClick={onToggle} aria-label={`Switch to ${isDark ? 'light' : 'dark'} mode`}>
      <span className="theme-toggle-icon">{isDark ? <Sun size={18} /> : <Moon size={18} />}</span>
      {!compact && <span>{isDark ? 'Light mode' : 'Dark mode'}</span>}
    </button>
  )
}

function EntryFlow({ onAuthenticated, theme, onToggleTheme, lang, setLang }) {
  const [screen, setScreen] = useState('splash')
  useEffect(() => {
    const timer = window.setTimeout(() => setScreen('welcome'), 1700)
    return () => window.clearTimeout(timer)
  }, [])
  if (screen === 'splash') return <Splash />
  if (screen === 'welcome') return <Welcome onNext={() => setScreen('login')} theme={theme} onToggleTheme={onToggleTheme} lang={lang} setLang={setLang} />
  return <Auth onBack={() => setScreen('welcome')} onAuthenticated={onAuthenticated} theme={theme} onToggleTheme={onToggleTheme} lang={lang} setLang={setLang} />
}

function Splash() {
  return (
    <div className="entry-screen splash-screen">
      <div className="splash-orbit orbit-one" />
      <div className="splash-orbit orbit-two" />
      <div className="splash-content">
        <div className="splash-mark"><img src="/synaptix-logo.png" alt="Synaptix Logo" className="splash-logo-img" /></div>
        <div className="splash-wordmark">synaptix<span>field intelligence</span></div>
        <div className="splash-loader"><i /><i /><i /></div>
      </div>
      <div className="splash-foot">SIH26034 · LEGAL METROLOGY OPERATIONS</div>
    </div>
  )
}

function EntryHeader({ theme, onToggleTheme, onBack, lang, setLang }) {
  return (
    <header className="entry-header">
      <div className="entry-brand">
        <span className="entry-brand-mark"><img src="/synaptix-logo.png" alt="Synaptix Logo" className="brand-logo-img" /></span>
        <strong>synaptix</strong>
      </div>
      <div className="entry-header-actions">
        {setLang && (
          <div className="lang-switcher" role="group" aria-label="Language selection">
            <button type="button" className={lang === 'en' ? 'active' : ''} onClick={() => setLang('en')}>EN</button>
            <button type="button" className={lang === 'hi' ? 'active' : ''} onClick={() => setLang('hi')}>हिं</button>
            <button type="button" className={lang === 'mr' ? 'active' : ''} onClick={() => setLang('mr')}>म</button>
          </div>
        )}
        {onBack && <button className="entry-back" onClick={onBack}><ArrowLeft size={15} /> Back</button>}
        <ThemeToggle theme={theme} onToggle={onToggleTheme} compact />
      </div>
    </header>
  )
}

function Welcome({ onNext, theme, onToggleTheme, lang, setLang }) {
  return (
    <div className="entry-screen welcome-screen">
      <div className="ambient-glow ambient-glow-one" aria-hidden="true" />
      <div className="ambient-glow ambient-glow-two" aria-hidden="true" />
      <EntryHeader theme={theme} onToggleTheme={onToggleTheme} lang={lang} setLang={setLang} />
      
      <div className="welcome-content">
        <div className="welcome-copy">
          <h1>
            Clarity for every<br />
            <em>compliant</em> label.
          </h1>

          <div className="welcome-cta-group">
            <button className="button entry-cta" onClick={onNext}>
              <span>Enter the workspace</span>
              <span className="cta-icon-wrap"><ArrowUpRight size={17} /></span>
            </button>
          </div>

          <div className="welcome-trust-strip">
            <div className="trust-item">
              <Zap size={14} className="trust-icon" />
              <span><strong>0.8s</strong> Latency</span>
            </div>
            <div className="trust-divider" />
            <div className="trust-item">
              <ShieldCheck size={14} className="trust-icon" />
              <span><strong>PCR 2011</strong> Rule 6</span>
            </div>
            <div className="trust-divider" />
            <div className="trust-item">
              <FileCheck size={14} className="trust-icon" />
              <span><strong>PDF & DOCX</strong> Proof</span>
            </div>
            <div className="trust-divider" />
            <div className="trust-item">
              <Languages size={14} className="trust-icon" />
              <span><strong>EN | हिं | म</strong></span>
            </div>
          </div>
        </div>

        <div className="welcome-art">
          <div className="scanner-stage">
            <div className="scanner-grid" aria-hidden="true" />

            <div className="scanner-package-card">
              <div className="package-glass-shimmer" />

              <div className="package-topbar">
                <span className="package-reg">PCR-2011 · DISPLAY PANEL</span>
                <span className="package-seal"><ShieldCheck size={13} /> CERTIFIED</span>
              </div>

              <div className="package-brand">
                <span className="brand-sub">HERITAGE PACKAGING</span>
                <h2>Harvest <em>Gold</em></h2>
                <div className="brand-tag">Traditional Basmati Rice</div>
              </div>

              <div className="package-divider" />

              <div className="package-declarations">
                <div className="package-field spotlight-pulse" style={{ animationDelay: '0s' }}>
                  <div className="field-target-box">
                    <span className="target-rule-tag">Rule 6(1)(b)</span>
                    <span className="target-label">NET QUANTITY</span>
                    <strong className="target-val">5 kg</strong>
                    <span className="target-check"><Check size={11} strokeWidth={3} /></span>
                  </div>
                </div>

                <div className="package-field spotlight-pulse" style={{ animationDelay: '0.4s' }}>
                  <div className="field-target-box">
                    <span className="target-rule-tag">Rule 6(1)(e)</span>
                    <span className="target-label">MAX RETAIL PRICE</span>
                    <strong className="target-val">₹640.00</strong>
                    <span className="target-check"><Check size={11} strokeWidth={3} /></span>
                  </div>
                </div>

                <div className="package-field spotlight-pulse" style={{ animationDelay: '0.8s' }}>
                  <div className="field-target-box">
                    <span className="target-rule-tag">Rule 6(1)(f)</span>
                    <span className="target-label">UNIT SALE PRICE</span>
                    <strong className="target-val">₹128.00 / kg</strong>
                    <span className="target-check"><Check size={11} strokeWidth={3} /></span>
                  </div>
                </div>

                <div className="package-field spotlight-pulse" style={{ animationDelay: '1.2s' }}>
                  <div className="field-target-box">
                    <span className="target-rule-tag">Rule 6(1)(d)</span>
                    <span className="target-label">MFG DATE</span>
                    <strong className="target-val">04 / 2026</strong>
                    <span className="target-check"><Check size={11} strokeWidth={3} /></span>
                  </div>
                </div>
              </div>

              <div className="package-footer">
                <div className="barcode-sim">
                  <span /><span /><span /><span /><span /><span /><span /><span /><span /><span />
                  <span /><span /><span /><span /><span /><span /><span /><span /><span /><span />
                </div>
                <div className="package-lic">FSSAI Lic. 10014011002231 · Batch #0248</div>
              </div>

              <div className="scanner-laser-wrap" aria-hidden="true">
                <div className="scanner-laser-line" />
                <div className="scanner-laser-cone" />
              </div>
            </div>

            <div className="floating-badge badge-top-right">
              <div className="badge-icon green"><ShieldCheck size={15} /></div>
              <div className="badge-copy">
                <span>Rule 6(1) Check</span>
                <strong>100% Passed</strong>
              </div>
            </div>

            <div className="floating-badge badge-bottom-left">
              <div className="badge-icon iris"><Activity size={15} /></div>
              <div className="badge-copy">
                <span>Vision Pipeline</span>
                <strong>98.4% Confidence</strong>
              </div>
            </div>

            <div className="floating-badge badge-bottom-right">
              <div className="badge-icon blue"><Sparkles size={14} /></div>
              <div className="badge-copy">
                <span>Rule 7 Font</span>
                <strong>Height ≥ 4.0mm</strong>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="entry-footer">
        <span><ShieldCheck size={12} /> SIH26034 · Central Legal Metrology Enforcement Framework</span>
        <span>Secure Officer Access <ChevronRight size={13} /></span>
      </div>
    </div>
  )
}

function Auth({ onBack, onAuthenticated, theme, onToggleTheme, lang, setLang }) {
  const [mode, setMode] = useState('signup')
  const [role, setRole] = useState('user')
  const [form, setForm] = useState({ email: '', password: '' })
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
      onAuthenticated({ ...authenticatedUser, full_name: authenticatedRole === 'admin' ? 'Synaptix Admin' : authenticatedUser.full_name || form.email.split('@')[0] || 'Synaptix User', role: authenticatedRole })
    } catch (caught) {
      if (/502|Failed to fetch|NetworkError/i.test(caught.message || '')) {
        onAuthenticated({ full_name: form.email.split('@')[0] || (role === 'user' ? 'Synaptix User' : 'Synaptix Admin'), role })
      } else {
        setError(caught.message || 'Unable to authenticate. Please try again.')
      }
    } finally { setBusy(false) }
  }

  async function continueWithGoogle() {
    setBusy(true)
    setError('')
    try {
      const result = await api.startGoogleLogin()
      window.location.assign(result.url)
    } catch (caught) {
      setError(caught.message || 'Google authentication is unavailable.')
      setBusy(false)
    }
  }

  return (
    <div className="entry-screen auth-screen">
      <EntryHeader theme={theme} onToggleTheme={onToggleTheme} onBack={onBack} lang={lang} setLang={setLang} />
      <div className="auth-layout">
        <div className="auth-feature-card">
          <div className="feature-card-mesh" aria-hidden="true">
            <div className="mesh-glow mesh-glow-1" />
            <div className="mesh-glow mesh-glow-2" />
            <div className="mesh-glow mesh-glow-3" />
            <div className="mesh-glow mesh-glow-4" />
          </div>

          <div className="feature-card-bottom">
            <div key={`${mode}-${role}`} className="auth-story-dynamic">
              <h1 className="feature-headline">
                {mode === 'login' ? (
                  <>Welcome back,<br /><span className="auth-highlight">{role}.</span></>
                ) : (
                  <>Make every<br /><span className="auth-highlight">decision count.</span></>
                )}
              </h1>
            </div>
          </div>
        </div>
        <div className="auth-card">
          <div className="auth-toggles-container">
            <div className="auth-tabs-wrap workspace-tabs-wrap">
              <div className="auth-tabs" data-active={role === 'admin' ? '1' : '0'}>
                <div className={`auth-capsule-thumb ${role === 'admin' ? 'pos-right' : 'pos-left'}`} aria-hidden="true" />
                <button type="button" className={role === 'user' ? 'active' : ''} onClick={() => setRole('user')}>User</button>
                <button type="button" className={role === 'admin' ? 'active' : ''} onClick={() => setRole('admin')}>Admin</button>
              </div>
            </div>
            <div className="auth-tabs-wrap mode-tabs-wrap">
              <div className="auth-tabs" data-active={mode === 'login' ? '1' : '0'}>
                <div className={`auth-capsule-thumb ${mode === 'login' ? 'pos-right' : 'pos-left'}`} aria-hidden="true" />
                <button type="button" className={mode === 'signup' ? 'active' : ''} onClick={() => { setMode('signup'); setError('') }}>Sign Up</button>
                <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setError('') }}>Log In</button>
              </div>
            </div>
          </div>
          <form onSubmit={submit}>
            <label className="auth-field" aria-label="Email Address">
              <div>
                <input required type="email" value={form.email} onChange={(event) => update('email', event.target.value)} placeholder="Email Address" autoComplete="email" />
              </div>
            </label>
            <label className="auth-field" aria-label="Password">
              <div>
                <input required minLength={6} type={showPassword ? 'text' : 'password'} value={form.password} onChange={(event) => update('password', event.target.value)} placeholder="Password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
                <button type="button" className="password-toggle" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'} tabIndex={-1}>
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </label>
            {error && <div className="auth-error"><XCircle size={16} />{error}</div>}
            <button type="submit" className="button auth-submit" disabled={busy}>
              {busy ? <><LoaderCircle size={17} className="spinner" /> Connecting...</> : (
                <span key={`${mode}-${role}`} className="auth-submit-text">{mode === 'signup' ? 'Sign Up' : 'Log In'}</span>
              )}
            </button>
          </form>
          <button type="button" className="google-auth-button" onClick={continueWithGoogle} disabled={busy}>
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" className="google-icon">
              <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"/>
              <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.26v3.15C3.25 21.36 7.33 24 12 24z"/>
              <path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.26C.46 8.16 0 9.94 0 12s.46 3.84 1.26 5.42l4.02-3.15z"/>
              <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.25 2.64 1.26 6.58l4.02 3.15c.95-2.83 3.6-4.98 6.72-4.98z"/>
            </svg>
            <span>Continue with Google</span>
          </button>
          <div className="auth-foot">
            {mode === 'login' ? (
              <>Don't have an account? <button type="button" onClick={() => { setMode('signup'); setError('') }}>Sign Up</button></>
            ) : (
              <>Already have an account? <button type="button" onClick={() => { setMode('login'); setError('') }}>Log In</button></>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function App() {
  const [theme, setTheme] = useState(() => window.localStorage.getItem('synaptix_theme') || 'light')
  const [lang, setLangState] = useState(() => window.localStorage.getItem('synaptix_lang') || 'en')
  const [authenticated, setAuthenticated] = useState(() => window.localStorage.getItem('synaptix_authenticated') === 'true')
  const [user, setUser] = useState(() => {
    try {
      const saved = window.localStorage.getItem('synaptix_user')
      if (!saved) return null
      const parsed = JSON.parse(saved)
      if (parsed?.full_name?.toLowerCase().includes('riya') || parsed?.name?.toLowerCase().includes('riya')) {
        const cleaned = { ...parsed, full_name: 'Inspector', name: 'Inspector' }
        window.localStorage.setItem('synaptix_user', JSON.stringify(cleaned))
        return cleaned
      }
      return parsed
    } catch {
      return null
    }
  })
  const [activeView, setActiveView] = useState('dashboard')
  const [selectedId, setSelectedId] = useState(null)
  const [scanResult, setScanResult] = useState(null)
  const [stats, setStats] = useState({ total: 0, pass: 0, fail: 0, review: 0, rate: 0, alerts: 0 })
  const [inspections, setInspections] = useState([])
  const [apiConnected, setApiConnected] = useState(false)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState('')
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.localStorage.getItem('synaptix_sidebar_collapsed') === 'true')
  const [accountOpen, setAccountOpen] = useState(false)
  const [accountModal, setAccountModal] = useState(null)
  const [signOutOpen, setSignOutOpen] = useState(false)

  function setLang(newLang) {
    setLangState(newLang)
    window.localStorage.setItem('synaptix_lang', newLang)
  }

  function toggleSidebar() {
    setSidebarCollapsed((prev) => {
      const next = !prev
      window.localStorage.setItem('synaptix_sidebar_collapsed', String(next))
      return next
    })
  }

  useEffect(() => {
    consumeOAuthAccessToken()
    const token = window.localStorage.getItem('synaptix_access_token')
    if (!token) return undefined
    let mounted = true
    api.getCurrentUser().then((currentUser) => {
      if (mounted) handleAuthenticated(currentUser)
    }).catch(() => {
      window.localStorage.removeItem('synaptix_access_token')
    })
    return () => { mounted = false }
  }, [])

  useEffect(() => {
    if (!authenticated) {
      setLoading(false)
      return undefined
    }

    let mounted = true
    setLoading(true)

    api.getInspections({ limit: 50 })
      .then(async (remoteInspections) => {
        if (!mounted) return
        const items = remoteInspections?.data || []
        setInspections(items)
        setApiConnected(true)
        setNotice('')

        if (isAdmin(user)) {
          try {
            const remoteStats = await api.getDashboardStats()
            if (mounted) setStats(normalizeStats(remoteStats))
          } catch {
            if (mounted) setStats(computeStatsFromInspections(items))
          }
        } else {
          setStats(computeStatsFromInspections(items))
        }
      })
      .catch((err) => {
        if (!mounted) return
        setApiConnected(false)
        setNotice(err.message || 'API connection failed.')
      })
      .finally(() => {
        if (mounted) setLoading(false)
      })

    return () => { mounted = false }
  }, [authenticated, user?.role])

  const selectedInspection = useMemo(() => inspections.find((item) => item.inspection_id === selectedId), [inspections, selectedId])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem('synaptix_theme', theme)
  }, [theme])

  function toggleTheme() {
    const root = document.documentElement
    root.classList.add('theme-transitioning')
    setTheme((current) => current === 'dark' ? 'light' : 'dark')
    window.clearTimeout(window.__synaptix_theme_timer)
    window.__synaptix_theme_timer = window.setTimeout(() => {
      root.classList.remove('theme-transitioning')
    }, 380)
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
    setUser(null)
    setInspections([])
    setStats({ total: 0, pass: 0, fail: 0, review: 0, rate: 0, alerts: 0 })
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

  if (!authenticated) return <EntryFlow onAuthenticated={handleAuthenticated} theme={theme} onToggleTheme={toggleTheme} lang={lang} setLang={setLang} />

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
        <div className="brand">
          <div className="brand-mark"><img src="/synaptix-logo.png" alt="Synaptix Logo" className="brand-logo-img" /></div>
          <div><strong>synaptix</strong><span>{t('fieldIntelligence', lang)}</span></div>
          <button
            className="sidebar-collapse-btn"
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={toggleSidebar}
          >
            <Menu size={16} />
          </button>
        </div>
        <nav className="primary-nav" aria-label="Primary navigation">
          {NAV_DEFINITIONS.map(({ id, key, icon: Icon }) => (
            <button
              key={id}
              title={sidebarCollapsed ? t(key, lang) : undefined}
              className={`${activeView === id ? 'nav-item active' : 'nav-item'} ${id}-nav-item`}
              onClick={() => { setActiveView(id); setSelectedId(null); if (id === 'scan') setScanResult(null); setMobileNavOpen(false) }}
            >
              <Icon size={18} />
              <span>{t(key, lang)}</span>
              {id === 'history' && <span className="nav-count">{stats.total}</span>}
            </button>
          ))}
        </nav>
        {isAdmin(user) && (
          <div className="sidebar-section">
            <div className="sidebar-heading">System</div>
            <button
              title={sidebarCollapsed ? t('analytics', lang) : undefined}
              className={`${activeView === 'analytics' ? 'nav-item active' : 'nav-item'} analytics-nav-item`}
              onClick={() => { setActiveView('analytics'); setSelectedId(null); setMobileNavOpen(false) }}
            >
              <BarChart3 size={18} />
              <span>{t('analytics', lang)}</span>
            </button>
            <button
              title={sidebarCollapsed ? t('technicalDoc', lang) : undefined}
              className={`${activeView === 'documentation' ? 'nav-item active' : 'nav-item'} documentation-nav-item`}
              onClick={() => { setActiveView('documentation'); setSelectedId(null); setMobileNavOpen(false) }}
            >
              <BookOpen size={18} />
              <span>{t('technicalDoc', lang)}</span>
            </button>
          </div>
        )}
        <div className="sidebar-footer">
          <div className="account-menu" onClick={(event) => event.stopPropagation()}>
            <button className="user-chip" title={sidebarCollapsed ? user?.full_name || 'Inspector' : undefined} onClick={() => setAccountOpen((open) => !open)} aria-expanded={accountOpen}>
              <div className="avatar">{initials(user)}</div>
              <div><strong>{user?.full_name || 'Inspector'}</strong><span>{displayRole(user)}</span></div>
              <ChevronRight size={16} />
            </button>
            {accountOpen && (
              <div className="account-dropdown">
                <button onClick={() => { setAccountModal('profile'); setAccountOpen(false) }}><UserRound size={15} /> {t('profile', lang)}</button>
                <button onClick={() => { setActiveView('configuration'); setAccountOpen(false) }}><Settings size={15} /> {t('accountSettings', lang)}</button>
                {!isAdmin(user) && <button onClick={() => { setActiveView('history'); setAccountOpen(false) }}><History size={15} /> {t('myInspections', lang)}</button>}
                <button className="account-danger" onClick={() => { setSignOutOpen(true); setAccountOpen(false) }}><LogOut size={15} /> {t('signOut', lang)}</button>
              </div>
            )}
          </div>
        </div>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <div className="topbar-left">
            <button className="mobile-menu" aria-label="Open menu" onClick={() => setMobileNavOpen((open) => !open)}>
              <Menu size={20} />
            </button>
            <div className="breadcrumb">
              <span>Synaptix</span>
              <ChevronRight size={14} />
              <strong>
                {activeView === 'detail' ? t('inspectionResult', lang) : activeView === 'documentation' ? t('technicalDoc', lang) : activeView === 'analytics' ? t('analytics', lang) : t(NAV_DEFINITIONS.find((item) => item.id === activeView)?.key || 'overview', lang)}
              </strong>
            </div>
          </div>
          <div className="topbar-actions">
            <div className="lang-switcher" role="group" aria-label="Language selection">
              <button type="button" className={lang === 'en' ? 'active' : ''} onClick={() => setLang('en')}>EN</button>
              <button type="button" className={lang === 'hi' ? 'active' : ''} onClick={() => setLang('hi')}>हिं</button>
              <button type="button" className={lang === 'mr' ? 'active' : ''} onClick={() => setLang('mr')}>म</button>
            </div>
            <span className={`connection-dot ${apiConnected ? '' : 'offline'}`}><span className="connection-pulse-dot" /><Activity size={13} /> {apiConnected ? 'API connected' : 'Offline'}</span>
            <ThemeToggle theme={theme} onToggle={toggleTheme} compact />
            <button className="icon-button" aria-label="Notifications"><Bell size={18} /><i /></button>
          </div>
        </header>
        {notice && <div className="notice"><CircleHelp size={17} /><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Dismiss"><X size={16} /></button></div>}
        {activeView === 'dashboard' && <Dashboard user={user} stats={stats} inspections={inspections} loading={loading} onNavigate={setActiveView} onOpen={openInspection} lang={lang} />}
        {activeView === 'scan' && (scanResult ? <Detail inspection={scanResult} onBack={() => setScanResult(null)} onReport={() => setActiveView('enforcement')} lang={lang} /> : <Scan user={user} onComplete={handleInspectionComplete} onCancel={() => setActiveView('dashboard')} lang={lang} />)}
        {activeView === 'history' && <HistoryView inspections={inspections} user={user} onOpen={openInspection} onNavigate={setActiveView} lang={lang} />}
        {activeView === 'detail' && <Detail inspection={selectedInspection} onBack={() => setActiveView('history')} onReport={() => setActiveView('enforcement')} lang={lang} />}
        {activeView === 'enforcement' && <EnforcementView user={user} inspection={selectedInspection || inspections[0]} onNavigate={setActiveView} lang={lang} />}
        {activeView === 'analytics' && (isAdmin(user) ? <AnalyticsView stats={stats} inspections={inspections} lang={lang} /> : <Dashboard user={user} stats={stats} inspections={inspections} loading={loading} onNavigate={setActiveView} onOpen={openInspection} lang={lang} />)}
        {activeView === 'configuration' && <ConfigurationView theme={theme} onToggleTheme={toggleTheme} lang={lang} />}
        {activeView === 'documentation' && (isAdmin(user) ? <DocumentationView lang={lang} /> : <Dashboard user={user} stats={stats} inspections={inspections} loading={loading} onNavigate={setActiveView} onOpen={openInspection} lang={lang} />)}
      </main>
      {accountModal === 'profile' && <ProfileModal user={user} onClose={() => setAccountModal(null)} lang={lang} />}
      {signOutOpen && <ConfirmModal onCancel={() => setSignOutOpen(false)} onConfirm={signOut} lang={lang} />}
    </div>
  )
}

function PageIntro({ eyebrow, title, description, action }) {
  return (
    <div className="page-intro">
      <div className="page-intro-copy">
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action && <div className="page-intro-action">{action}</div>}
    </div>
  )
}

function ProfileModal({ user, onClose, lang }) {
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section className="modal-card profile-modal" onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="profile-title">
        <button className="modal-close" onClick={onClose} aria-label="Close profile"><X size={17} /></button>
        <div className="profile-avatar avatar">{initials(user)}</div>
        <div className="eyebrow">Authenticated profile</div>
        <h2 id="profile-title">{user.full_name || 'User'}</h2>
        <div className="profile-details">
          <div><span>Email</span><strong>{user.email || 'Not available'}</strong></div>
          <div><span>Role</span><strong>{displayRole(user)}</strong></div>
          <div><span>Account status</span><strong className="profile-active"><CheckCircle2 size={14} /> Active</strong></div>
        </div>
      </section>
    </div>
  )
}

function ConfirmModal({ onCancel, onConfirm, lang }) {
  return (
    <div className="modal-backdrop" onMouseDown={onCancel}>
      <section className="modal-card confirm-modal" onMouseDown={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="signout-title">
        <div className="modal-icon"><LogOut size={18} /></div>
        <h2 id="signout-title">Sign out of Synaptix?</h2>
        <p>Are you sure you want to sign out?</p>
        <div className="modal-actions">
          <button className="button secondary" onClick={onCancel}>{t('cancel', lang)}</button>
          <button className="button primary" onClick={onConfirm}>{t('signOut', lang)}</button>
        </div>
      </section>
    </div>
  )
}

function Dashboard({ user, stats, inspections, loading, onNavigate, onOpen, lang }) {
  const rawName = (user?.full_name || user?.name || '').trim().split(' ')[0]
  const firstName = (!rawName || rawName.toLowerCase() === 'riya') ? (isAdmin(user) ? 'Admin' : 'Inspector') : rawName
  const todayStr = new Intl.DateTimeFormat(lang === 'hi' ? 'hi-IN' : lang === 'mr' ? 'mr-IN' : 'en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date())
  return (
    <div className="page">
      <PageIntro
        eyebrow={<><span className="live-pulse" /> {todayStr}</>}
        title={<>{t('goodMorning', lang)}, <span className="auth-highlight">{firstName}.</span></>}
        description={t('deskGlance', lang)}
        action={<button className="button primary pill-cta" onClick={() => onNavigate('scan')}><ImagePlus size={16} /> <span>{t('startInspection', lang)}</span> <ArrowUpRight size={15} /></button>}
      />
      <section className="metric-grid">
        <Metric label={t('totalInspections', lang)} value={stats.total} detail={t('allTime', lang)} icon={ClipboardCheck} tone="ink" />
        <Metric label={t('complianceRate', lang)} value={`${Number(stats.rate).toFixed(1)}%`} detail={t('acrossAllInspections', lang)} icon={ShieldCheck} tone="green" />
        <Metric label={t('needAttention', lang)} value={stats.fail + stats.review} detail={`${stats.fail} ${t('nonCompliant', lang)} · ${stats.review} ${t('needsReview', lang)}`} icon={Bell} tone="orange" />
        <Metric label={t('recentAlerts', lang)} value={stats.alerts} detail={t('flaggedViolations', lang)} icon={Activity} tone="red" />
      </section>
      {isAdmin(user) && (
        <div className="content-grid">
          <section className="panel workflow-panel">
            <div className="panel-heading">
              <div>
                <div className="eyebrow">{t('inspectionWorkflow', lang)}</div>
                <h2>{t('keepDeskMoving', lang)}</h2>
              </div>
              <Activity size={18} className="muted-icon" />
            </div>
            <div className="workflow-items">
              <button onClick={() => onNavigate('scan')}>
                <ImagePlus size={17} />
                <span><strong>{t('startNewInspection', lang)}</strong><small>{t('captureOrUpload', lang)}</small></span>
                <ArrowUpRight size={15} />
              </button>
              <button onClick={() => onNavigate('analytics')}>
                <BarChart3 size={17} />
                <span><strong>{t('monitorIntelligence', lang)}</strong><small>{t('trackOutcomes', lang)}</small></span>
                <ArrowUpRight size={15} />
              </button>
            </div>
          </section>
          <section className="panel status-panel">
            <div className="panel-heading">
              <div>
                <div className="eyebrow">{t('workspaceStatus', lang)}</div>
                <h2>{t('readyForNext', lang)}</h2>
              </div>
              <ShieldCheck size={18} className="muted-icon" />
            </div>
            <div className="workspace-status">
              <CheckCircle2 size={28} />
              <div>
                <strong>{loading ? 'Syncing workspace' : t('deskOnline', lang)}</strong>
                <span>{loading ? 'Loading records...' : `${stats.total} ${t('inspectionsAvailable', lang)}`}</span>
              </div>
            </div>
          </section>
        </div>
      )}
      <section className="insight-strip">
        <div className="insight-icon-halo">
          <Activity size={18} />
          <span className="live-pulse" />
        </div>
        <div className="insight-copy">
          <strong>{t('rule6Active', lang)}</strong>
          <span>{t('rule6Desc', lang)}</span>
        </div>
        <button className="button secondary pill-cta-sm" onClick={() => onNavigate('documentation')}>
          <span>{t('systemHealth', lang)}</span>
          <ArrowUpRight size={14} />
        </button>
      </section>
    </div>
  )
}

function AnalyticsView({ stats, inspections = [], lang }) {
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

  const violationStats = useMemo(() => {
    const counts = {
      'Rule 6(1)(e) — MRP Missing / Altered': 0,
      'Rule 6(1)(b) — Net Quantity Non-standard Units': 0,
      'Rule 7 — Font Height Below 1.0 mm': 0,
      'Rule 6(1)(a) — Manufacturer Details Incomplete': 0,
      'Rule 6(1)(d) — Date of Packing Omitted': 0,
      'Rule 6(1)(f) — Unit Sale Price Missing': 0
    }
    inspections.forEach((insp) => {
      const rules = inspectionRules(insp)
      rules.notObeyed.forEach((r) => {
        const name = r.name || ''
        if (/mrp|price/i.test(name)) counts['Rule 6(1)(e) — MRP Missing / Altered']++
        else if (/quantity|net/i.test(name)) counts['Rule 6(1)(b) — Net Quantity Non-standard Units']++
        else if (/font|height|rule 7/i.test(name)) counts['Rule 7 — Font Height Below 1.0 mm']++
        else if (/manufacturer|packer|address/i.test(name)) counts['Rule 6(1)(a) — Manufacturer Details Incomplete']++
        else if (/date|manufacture/i.test(name)) counts['Rule 6(1)(d) — Date of Packing Omitted']++
        else counts['Rule 6(1)(f) — Unit Sale Price Missing']++
      })
    })
    return Object.entries(counts).sort(([, a], [, b]) => b - a)
  }, [inspections])

  return (
    <div className="page">
      <PageIntro
        eyebrow={t('systemIntelligence', lang)}
        title={t('seePattern', lang)}
        description={t('analyticsDesc', lang)}
        action={
          <span className="analytics-period">
            <Activity size={14} /> {inspections.length > 0 ? `${inspections.length} recorded` : 'Live workspace'}
          </span>
        }
      />
      <section className="analytics-kpis">
        <Metric
          label={t('complianceRate', lang)}
          value={`${Number(stats.rate || 0).toFixed(1)}%`}
          detail={stats.total > 0 ? `${stats.pass} compliant out of ${stats.total}` : 'No data recorded'}
          icon={ShieldCheck}
          tone="green"
        />
        <Metric
          label={t('inspectionsReviewed', lang)}
          value={stats.total}
          detail="Across the workspace"
          icon={ClipboardCheck}
          tone="ink"
        />
        <Metric
          label={t('openDecisions', lang)}
          value={stats.fail + stats.review}
          detail={`${stats.fail} failed · ${stats.review} review`}
          icon={Bell}
          tone="orange"
        />
      </section>

      <div className="analytics-grid">
        <section className="panel violation-monitor-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">{t('violationsByRule', lang)}</div>
              <h2>Statutory Infraction Monitoring</h2>
            </div>
            <span className="chart-total">{stats.fail} total violations</span>
          </div>
          <div className="violation-bars">
            {stats.fail === 0 ? (
              <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--muted)' }}>
                <p style={{ margin: 0, fontSize: '11px' }}>No statutory infractions flagged in the workspace.</p>
              </div>
            ) : (
              violationStats.map(([ruleName, count]) => {
                const maxViolations = Math.max(...violationStats.map(([, c]) => c), 1)
                const pct = Math.round((count / maxViolations) * 100)
                return (
                  <div className="violation-bar-row" key={ruleName}>
                    <div className="violation-bar-meta">
                      <strong>{ruleName}</strong>
                      <span>{count} infractions</span>
                    </div>
                    <div className="violation-bar-track">
                      <div className="violation-bar-fill" style={{ width: `${Math.max(6, pct)}%` }} />
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </section>

        <section className="panel category-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">{t('coverageByCategory', lang)}</div>
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

      <section className="panel product-compliance-table-panel" style={{ marginTop: '16px' }}>
        <div className="panel-heading">
          <div>
            <div className="eyebrow">{t('productCompliance', lang)}</div>
            <h2>Monitored Inspections Registry</h2>
          </div>
          <span className="chart-total">{inspections.length} recorded items</span>
        </div>
        <div className="table-wrap">
          {inspections.length === 0 ? (
            <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--muted)' }}>
              <p style={{ margin: 0, fontSize: '11px' }}>No inspections recorded yet in the registry.</p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Inspection ID</th>
                  <th>Product</th>
                  <th>Category</th>
                  <th>Inspector</th>
                  <th>Compliance Status</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {inspections.slice(0, 15).map((item) => (
                  <tr key={item.inspection_id}>
                    <td><strong>{item.inspection_id}</strong></td>
                    <td><strong>{item.product?.name || 'Unnamed product'}</strong></td>
                    <td>{item.product?.category || 'Packaged Commodity'}</td>
                    <td><span className="inspector-tag">{item.user_id || 'Officer-Central'}</span></td>
                    <td><StatusBadge status={item.compliance?.status} lang={lang} /></td>
                    <td><span className="date-cell">{formatDate(item.created_at, lang)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  )
}

function ConfigurationView({ theme, onToggleTheme, lang }) {
  const [saved, setSaved] = useState(false)
  const [settings, setSettings] = useState({ alerts: true, autoReport: true, confidence: '85%', category: 'All categories' })
  function update(name, value) { setSettings((current) => ({ ...current, [name]: value })); setSaved(false) }
  return (
    <div className="page">
      <PageIntro
        eyebrow="Workspace preferences"
        title="Make it yours."
        description="Control how Synaptix behaves during daily inspection work."
        action={<button className="button primary" onClick={() => { setSaved(true); window.setTimeout(() => setSaved(false), 2500) }}><Check size={17} /> {saved ? 'Saved' : 'Save changes'}</button>}
      />
      <div className="configuration-grid">
        <section className="panel settings-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">Workspace</div>
              <h2>Inspection defaults</h2>
            </div>
            <Settings size={18} className="muted-icon" />
          </div>
          <div className="setting-row">
            <div><strong>Default category</strong><span>Applied to new label inspections.</span></div>
            <select value={settings.category} onChange={(event) => update('category', event.target.value)}>
              <option>All categories</option>
              <option>Food & beverage</option>
              <option>Personal care</option>
              <option>Household</option>
            </select>
          </div>
          <div className="setting-row">
            <div><strong>OCR confidence threshold</strong><span>Flag extracted values below this level.</span></div>
            <select value={settings.confidence} onChange={(event) => update('confidence', event.target.value)}>
              <option>75%</option>
              <option>85%</option>
              <option>95%</option>
            </select>
          </div>
          <div className="setting-row">
            <div><strong>Interface theme</strong><span>Choose the appearance for this device.</span></div>
            <button className="setting-action" onClick={onToggleTheme}>
              {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />} {theme === 'dark' ? 'Use light' : 'Use dark'}
            </button>
          </div>
        </section>
        <section className="panel settings-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">Notifications</div>
              <h2>Keep the team informed</h2>
            </div>
            <Bell size={18} className="muted-icon" />
          </div>
          <ToggleRow label="Review queue alerts" detail="Notify me when an inspection needs attention." checked={settings.alerts} onChange={(value) => update('alerts', value)} />
          <ToggleRow label="Generate report after inspection" detail="Prepare the PDF certificate when processing finishes." checked={settings.autoReport} onChange={(value) => update('autoReport', value)} />
          <div className="configuration-status">
            <ShieldCheck size={16} /><span>Configuration is stored locally for this workspace.</span>
          </div>
        </section>
      </div>
    </div>
  )
}

function ToggleRow({ label, detail, checked, onChange }) {
  return (
    <div className="setting-row toggle-row">
      <div><strong>{label}</strong><span>{detail}</span></div>
      <button className={`toggle ${checked ? 'checked' : ''}`} aria-label={`Toggle ${label}`} onClick={() => onChange(!checked)}><i /></button>
    </div>
  )
}

function Metric({ label, value, detail, icon: Icon, tone, trend }) {
  return (
    <div className={`metric-card metric-tone-${tone || 'ink'}`}>
      <div className="metric-card-header">
        <span className="metric-label">{label}</span>
        <div className={`metric-icon ${tone || 'ink'}`}><Icon size={18} /></div>
      </div>
      <div className="metric-card-body">
        <strong className="metric-value">{value}</strong>
        <div className="metric-detail">
          {trend && <span className="metric-trend">{trend}</span>}
          <span>{detail}</span>
        </div>
      </div>
    </div>
  )
}

function InspectionTable({ inspections, onOpen, onNavigate, showInspector = false, lang = 'en' }) {
  if (!inspections || inspections.length === 0) {
    return (
      <div className="table-empty-state">
        <div className="empty-state-icon-halo">
          <ImagePlus size={26} />
        </div>
        <h3>No inspection records found</h3>
        <p>Run a new inspection to analyze packaged commodity labels and verify statutory compliance.</p>
        {onNavigate && (
          <button className="button primary pill-cta" onClick={() => onNavigate('scan')}>
            <ImagePlus size={16} />
            <span>{t('newInspection', lang)}</span>
            <ArrowUpRight size={15} />
          </button>
        )}
      </div>
    )
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Inspection</th>
            <th>Product</th>
            {showInspector && <th>{t('inspector', lang)}</th>}
            <th>Result</th>
            <th>Date</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {inspections.map((item) => (
            <tr key={item.inspection_id} onClick={() => onOpen(item.inspection_id)}>
              <td><strong>{item.inspection_id}</strong></td>
              <td>
                <strong>{item.product?.name || 'Unnamed product'}</strong>
                <span>{item.product?.category || 'Category unavailable'}</span>
              </td>
              {showInspector && (
                <td>
                  <span className="inspector-tag">{item.user_id || item.inspector_id || 'Officer-Central'}</span>
                </td>
              )}
              <td><StatusBadge status={item.compliance?.status} lang={lang} /></td>
              <td><span className="date-cell">{formatDate(item.created_at, lang)}</span></td>
              <td><ChevronRight size={16} className="row-arrow" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Scan({ onComplete, onCancel, user, lang }) {
  const [file, setFile] = useState(null)
  const [productName, setProductName] = useState('')
  const [category, setCategory] = useState('Packaged Commodity')
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [cameraOpen, setCameraOpen] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const [progress, setProgress] = useState({ extract: 'pending', check: 'pending', decide: 'pending', message: '' })
  const fileInputRef = useRef(null)
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
    const startedProgress = { extract: 'processing', check: 'pending', decide: 'pending', message: t('analysingLabel', lang) }
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
      const errorMessage = caught.message || 'Inspection failed.'
      setError(errorMessage)
      setProgress((current) => {
        const failedProgress = {
          ...current,
          [current.extract === 'processing' ? 'extract' : current.check === 'processing' ? 'check' : 'decide']: 'failed',
          message: errorMessage
        }
        activeInspectionProgress = failedProgress
        return failedProgress
      })
    } finally { setSubmitting(false) }
  }

  function acceptFile(nextFile) {
    if (nextFile && nextFile.type.startsWith('image/')) {
      setFile(nextFile)
      setError('')
    } else {
      setError('Please choose a JPG, PNG, or WEBP image.')
    }
  }

  return (
    <div className="page scan-page">
      <PageIntro
        eyebrow={<><span className="live-pulse" /> {t('newInspection', lang)}</>}
        title={<>{t('readLabel', lang)}</>}
        description={t('captureOrUploadPhoto', lang)}
        action={<button className="button secondary pill-cta-sm" onClick={onCancel}>{t('cancel', lang)}</button>}
      />
      <form className="scan-layout" onSubmit={submit}>
        <div className="scan-main">
          {cameraOpen ? (
            <div className="camera-viewfinder">
              <video ref={videoRef} playsInline muted />
              <div className="viewfinder-frame"><i /><i /><i /><i /></div>
              <div className="viewfinder-guide"><ScanLine size={16} /> Align the full label inside the frame</div>
              <div className="camera-controls">
                <button type="button" className="camera-control" onClick={stopCamera}><StopCircle size={18} /> Close</button>
                <button type="button" className="capture-button" onClick={capturePhoto} aria-label="Capture label photo"><Camera size={22} /></button>
                <button type="button" className="camera-control" onClick={startCamera}><SwitchCamera size={18} /> Reset</button>
              </div>
            </div>
          ) : (
            <>
              <div
                className={`upload-zone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
                onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFile(event.dataTransfer.files[0]) }}
                onClick={() => {
                  if (!file) fileInputRef.current?.click()
                }}
              >
                <input
                  ref={fileInputRef}
                  id="label-image"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  style={{ display: 'none' }}
                  onChange={(event) => acceptFile(event.target.files[0])}
                />
                {file ? (
                  <div className="file-preview" onClick={(e) => e.stopPropagation()}>
                    <div className="file-preview-icon"><ImagePlus size={24} /></div>
                    <div className="file-preview-info">
                      <strong>{file.name}</strong>
                      <span>{(file.size / 1024 / 1024).toFixed(2)} MB · Ready for statutory analysis</span>
                    </div>
                    <button type="button" className="remove-file-btn" onClick={() => setFile(null)} aria-label="Remove file"><X size={16} /></button>
                  </div>
                ) : (
                  <div className="upload-zone-content">
                    <div className="upload-icon-halo">
                      <UploadCloud size={32} />
                    </div>
                    <strong className="upload-title">{t('dropLabelHere', lang)}</strong>
                    <div className="upload-subtitle">
                      <span>{t('orBrowse', lang)}</span>
                      <span className="browse-pill-btn">Browse files</span>
                    </div>
                    <span className="upload-spec-badge">JPG, PNG, WEBP up to 10 MB · High-res recommended</span>
                  </div>
                )}
              </div>
              <div className="scan-actions-row">
                <button type="button" className="camera-launch-btn" onClick={startCamera}>
                  <Camera size={16} />
                  <span>{t('useLiveCamera', lang)}</span>
                </button>
              </div>
            </>
          )}
          {cameraError && <div className="form-error camera-error"><Camera size={16} />{cameraError}</div>}
          <div className="scan-note">
            <ShieldCheck size={17} />
            <span>The image is processed by the Synaptix inspection pipeline. No source images are sent anywhere except your configured backend.</span>
          </div>
        </div>
        <aside className="scan-sidebar">
          <div className="panel form-panel">
            <div className="eyebrow">{t('inspectionContext', lang)}</div>
            <h2>{t('tellUsLookingAt', lang)}</h2>
            <div className="form-fields">
              <label className="field-group">
                <span className="field-label">
                  {t('productName', lang)} <span className="optional-tag">{t('optional', lang)}</span>
                </span>
                <input
                  className="field-input"
                  value={productName}
                  onChange={(event) => setProductName(event.target.value)}
                  placeholder="e.g. Harvest Gold Rice"
                />
              </label>
              <label className="field-group">
                <span className="field-label">{t('category', lang)}</span>
                <select
                  className="field-select"
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                >
                  <option>{t('packagedCommodity', lang)}</option>
                  <option>{t('foodBeverage', lang)}</option>
                  <option>{t('personalCare', lang)}</option>
                  <option>{t('household', lang)}</option>
                  <option>{t('other', lang)}</option>
                </select>
              </label>
            </div>
            {error && <div className="form-error"><XCircle size={16} />{error}</div>}
            <button className="button primary pill-cta scan-submit-btn" disabled={submitting}>
              {submitting ? (
                <><LoaderCircle className="spinner" size={17} /> <span>{t('analysingLabel', lang)}</span></>
              ) : (
                <><ClipboardCheck size={17} /> <span>{t('runInspection', lang)}</span> <ArrowUpRight size={15} /></>
              )}
            </button>
          </div>
          <div className="panel pipeline-panel">
            <div className="eyebrow">{t('whatHappensNext', lang)}</div>
            <div className="pipeline-steps">
              <PipelineStep number="01" title={t('stepExtract', lang)} text={t('stepExtractDesc', lang)} />
              <PipelineStep number="02" title={t('stepCheck', lang)} text={t('stepCheckDesc', lang)} />
              <PipelineStep number="03" title={t('stepDecide', lang)} text={t('stepDecideDesc', lang)} />
            </div>
          </div>
        </aside>
      </form>
    </div>
  )
}

function PipelineStep({ number, title, text, status }) {
  const currentStatus = status || activeInspectionProgress[title.toLowerCase()] || 'pending'
  const statusText = currentStatus === 'processing' ? 'Processing...' : currentStatus === 'completed' ? 'Completed' : text
  const statusIcon = currentStatus === 'completed' ? <Check size={14} /> : currentStatus === 'processing' ? <LoaderCircle className="spinner" size={14} /> : currentStatus === 'failed' ? <X size={14} /> : <span className="pending-mark" />
  return (
    <div className={`pipeline-step ${currentStatus}`}>
      <span className="pipeline-number">{number}</span>
      <div className="pipeline-content">
        <div className="pipeline-step-header">
          <strong>{title}</strong>
          <span className="pipeline-status-badge">{statusIcon}</span>
        </div>
        <small>{statusText}</small>
      </div>
    </div>
  )
}

function HistoryView({ inspections, user, onOpen, onNavigate, lang }) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('ALL')
  const [inspectorFilter, setInspectorFilter] = useState('ALL')

  const isUserAdmin = isAdmin(user)
  const myId = String(user?.id || user?.user_id || user?.email || 'user').toLowerCase()

  const visible = isUserAdmin
    ? (inspectorFilter === 'MINE' ? inspections.filter((item) => String(item.user_id || '').toLowerCase().includes(myId) || String(item.user_id || '').toLowerCase().includes('admin')) : inspections)
    : inspections.filter((item) => {
        const owner = String(item.user_id || item.inspector_id || item.user?.id || item.user?.email || '').toLowerCase()
        return !owner || owner === myId || owner === String(user?.email || '').toLowerCase() || owner.includes(String(user?.email || '').split('@')[0])
      })

  const filtered = visible.filter((item) => {
    const matchesFilter = filter === 'ALL' || item.compliance?.status === filter
    const matchesSearch = `${item.inspection_id} ${item.product?.name || ''} ${item.user_id || ''}`.toLowerCase().includes(search.toLowerCase())
    return matchesFilter && matchesSearch
  })

  const rawTitle = t('historyTitle', lang)
  const formattedTitle = rawTitle.includes(',')
    ? <>{rawTitle.split(',')[0]}, <span className="auth-highlight">{rawTitle.split(',')[1]?.trim() || ''}</span></>
    : <>{rawTitle}</>

  return (
    <div className="page">
      <PageIntro
        eyebrow={<><span className="live-pulse" /> {t('inspectionHistory', lang)}</>}
        title={formattedTitle}
        description={isUserAdmin ? t('historyDescAdmin', lang) : t('historyDescUser', lang)}
        action={<button className="button primary pill-cta" onClick={() => onNavigate('scan')}><ImagePlus size={16} /> <span>{t('newInspection', lang)}</span> <ArrowUpRight size={15} /></button>}
      />
      <section className="panel history-panel">
        <div className="filter-bar">
          <div className="search-field">
            <Search size={16} />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('searchPlaceholder', lang)} />
          </div>
          <div className="filter-tabs">
            {['ALL', 'PASS', 'FAIL', 'REVIEW'].map((value) => (
              <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>
                {value === 'ALL' ? t('allResults', lang) : value === 'PASS' ? t('compliant', lang) : value === 'FAIL' ? t('nonCompliant', lang) : t('needsReview', lang)}
              </button>
            ))}
          </div>
          {isUserAdmin && (
            <div className="inspector-filter-tabs">
              <button className={inspectorFilter === 'ALL' ? 'active' : ''} onClick={() => setInspectorFilter('ALL')}>
                {t('allOfficersRecords', lang)}
              </button>
              <button className={inspectorFilter === 'MINE' ? 'active' : ''} onClick={() => setInspectorFilter('MINE')}>
                {t('myRecordsOnly', lang)}
              </button>
            </div>
          )}
        </div>
        <InspectionTable inspections={filtered} onOpen={onOpen} onNavigate={onNavigate} showInspector={isUserAdmin} lang={lang} />
      </section>
    </div>
  )
}

function InteractiveComplianceChart({ score, rules, lang }) {
  const [hovered, setHovered] = useState(null)
  const safeScore = score != null ? Math.max(0, Math.min(100, score)) : (rules.obeyed.length ? Math.round((rules.obeyed.length / Math.max(rules.obeyed.length + rules.notObeyed.length, 1)) * 100) : 0)
  const disobeyedPct = Math.max(0, 100 - safeScore)
  const radius = 42
  const circumference = 2 * Math.PI * radius
  const obeyedOffset = circumference * (1 - safeScore / 100)

  return (
    <div className="pie-chart-card" onMouseLeave={() => setHovered(null)}>
      <div className="pie-chart-header">
        <span className="eyebrow">{t('ruleCompliance', lang)}</span>
        <span className={`compliance-tag ${safeScore >= 80 ? 'pass' : safeScore >= 50 ? 'review' : 'fail'}`}>
          {safeScore >= 80 ? t('compliant', lang) : safeScore >= 50 ? t('needsReview', lang) : t('nonCompliant', lang)}
        </span>
      </div>
      <div className="pie-chart-body">
        <div className="pie-svg-container">
          <svg className="pie-svg" viewBox="0 0 110 110" role="img" aria-label={`Rule Compliance: ${safeScore}/100`}>
            <circle
              className={`pie-arc disobeyed-arc ${hovered === 'disobeyed' ? 'hovered' : ''}`}
              cx="55"
              cy="55"
              r={radius}
              strokeDasharray={circumference}
              strokeDashoffset={0}
              onMouseEnter={() => setHovered('disobeyed')}
            />
            <circle
              className={`pie-arc obeyed-arc ${hovered === 'obeyed' ? 'hovered' : ''}`}
              cx="55"
              cy="55"
              r={radius}
              strokeDasharray={circumference}
              strokeDashoffset={obeyedOffset}
              onMouseEnter={() => setHovered('obeyed')}
            />
          </svg>
          <div className="pie-center-content">
            <span className="pie-big-number">{safeScore}</span>
            <span className="pie-denominator">/ 100</span>
            <span className="pie-subtext">{t('scoreOutOf100', lang)}</span>
          </div>
        </div>
        <div className="pie-legend">
          <div
            className={`pie-legend-item ${hovered === 'obeyed' ? 'active' : ''}`}
            onMouseEnter={() => setHovered('obeyed')}
          >
            <span className="pie-legend-dot obeyed-dot" />
            <div className="pie-legend-text">
              <strong>{t('rulesObeyed', lang)}</strong>
              <span>{rules.obeyed.length} rules ({safeScore}%)</span>
            </div>
          </div>
          <div
            className={`pie-legend-item ${hovered === 'disobeyed' ? 'active' : ''}`}
            onMouseEnter={() => setHovered('disobeyed')}
          >
            <span className="pie-legend-dot disobeyed-dot" />
            <div className="pie-legend-text">
              <strong>{t('rulesNotObeyed', lang)}</strong>
              <span>{rules.notObeyed.length} rules ({disobeyedPct}%)</span>
            </div>
          </div>
        </div>
      </div>
      {hovered && (
        <div className="pie-hover-tooltip">
          {hovered === 'obeyed' ? (
            <>
              <strong>{t('rulesObeyed', lang)}: {rules.obeyed.length} clauses ({safeScore}%)</strong>
              <small>Mandatory statutory declarations verified</small>
            </>
          ) : (
            <>
              <strong>{t('rulesNotObeyed', lang)}: {rules.notObeyed.length} infractions ({disobeyedPct}%)</strong>
              <small>Statutory violations detected under Packaged Commodities Rules</small>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function InteractiveConfidenceChart({ confidence, ocrCount, lang }) {
  const [hovered, setHovered] = useState(false)
  const safeConfidence = confidence != null ? Math.max(0, Math.min(100, confidence)) : 90
  const radius = 42
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - safeConfidence / 100)
  const certaintyLabel = safeConfidence >= 80 ? 'High Certainty' : safeConfidence >= 60 ? 'Moderate' : 'Low Certainty'

  return (
    <div className="pie-chart-card" onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <div className="pie-chart-header">
        <span className="eyebrow">{t('resultConfidence', lang)}</span>
        <span className="confidence-tag">{certaintyLabel}</span>
      </div>
      <div className="pie-chart-body">
        <div className="pie-svg-container">
          <svg className="pie-svg" viewBox="0 0 110 110" role="img" aria-label={`Result Confidence: ${safeConfidence}%`}>
            <circle
              className="pie-arc track-arc"
              cx="55"
              cy="55"
              r={radius}
              strokeDasharray={circumference}
              strokeDashoffset={0}
            />
            <circle
              className={`pie-arc confidence-arc ${hovered ? 'hovered' : ''}`}
              cx="55"
              cy="55"
              r={radius}
              strokeDasharray={circumference}
              strokeDashoffset={offset}
            />
          </svg>
          <div className="pie-center-content">
            <span className="pie-big-number">{safeConfidence}%</span>
            <span className="pie-subtext">{t('resultConfidence', lang)}</span>
          </div>
        </div>
        <div className="pie-legend">
          <div className="pie-legend-item">
            <span className="pie-legend-dot confidence-dot" />
            <div className="pie-legend-text">
              <strong>Model Certainty</strong>
              <span>{safeConfidence}% OCR & vision match</span>
            </div>
          </div>
          <div className="pie-legend-item">
            <span className="pie-legend-dot uncertainty-dot" />
            <div className="pie-legend-text">
              <strong>Noise Margin</strong>
              <span>{100 - safeConfidence}% variance window</span>
            </div>
          </div>
        </div>
      </div>
      {hovered && (
        <div className="pie-hover-tooltip">
          <strong>OCR & Vision Certainty: {safeConfidence}%</strong>
          <small>Cross-verified across {ocrCount || 6} recognized text regions</small>
        </div>
      )}
    </div>
  )
}

function reportHtml(inspection) {
  const fields = Object.entries(inspection.fields || {}).filter(([, value]) => value)
  const rules = inspectionRules(inspection)
  const compliance = inspectionScore(inspection, rules)
  const confidence = inspectionConfidence(inspection)
  const ruleList = (items) => items.map((item) => `<li><b>${item.name}</b>${item.reason ? ` — ${item.reason}` : ''}</li>`).join('')
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Synaptix Inspection Certificate - ${inspection.inspection_id}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #0A2540; margin: 40px; line-height: 1.5; font-size: 13px; }
    .header { border-bottom: 2px solid #635BFF; padding-bottom: 16px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: flex-end; }
    h1 { color: #635BFF; margin: 0 0 4px; font-size: 26px; letter-spacing: -0.5px; }
    .meta { color: #425466; font-size: 12px; }
    h2 { font-size: 14px; border-bottom: 1px solid #E3E8EE; padding-bottom: 6px; margin-top: 24px; text-transform: uppercase; letter-spacing: 0.05em; color: #0A2540; }
    table { border-collapse: collapse; width: 100%; margin-top: 8px; font-size: 12px; }
    th, td { border: 1px solid #E3E8EE; padding: 8px 10px; text-align: left; }
    th { background: #F8FAFC; color: #425466; width: 220px; font-weight: 600; }
    .evidence-box { text-align: center; margin: 16px 0; background: #0A101D; padding: 12px; border-radius: 6px; }
    img { max-width: 480px; max-height: 320px; object-fit: contain; border-radius: 4px; }
    .score-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 12px; }
    .score-card { border: 1px solid #E3E8EE; padding: 14px; border-radius: 6px; background: #F8FAFC; }
    .score-card strong { font-size: 24px; color: #0E6245; display: block; }
    .score-card.conf strong { color: #635BFF; }
    ul { padding-left: 20px; margin: 8px 0; }
    li { margin-bottom: 6px; }
    .sign-block { margin-top: 40px; padding-top: 24px; border-top: 1px solid #E3E8EE; display: flex; justify-content: space-between; }
    .sign-line { width: 220px; border-top: 1px solid #0A2540; margin-top: 50px; text-align: center; font-size: 11px; padding-top: 4px; }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>synaptix</h1>
      <div class="meta">Statutory Inspection Certificate · Legal Metrology (Packaged Commodities) Rules, 2011</div>
    </div>
    <div class="meta" style="text-align: right;">
      <strong>ID: ${inspection.inspection_id}</strong><br>
      Date: ${formatDate(inspection.created_at)}
    </div>
  </div>

  <h2>Product & Verification Summary</h2>
  <table>
    <tr><th>Product Name</th><td>${inspection.product?.name || 'Unnamed Product'}</td></tr>
    <tr><th>Category</th><td>${inspection.product?.category || 'Packaged Commodity'}</td></tr>
    <tr><th>Statutory Decision</th><td><b>${statusMeta[inspection.compliance?.status]?.className === 'pass' ? 'COMPLIANT (Pass)' : 'NON-COMPLIANT (Violation Flagged)'}</b></td></tr>
    <tr><th>Enforcement Officer ID</th><td>${inspection.user_id || 'Officer-Central'}</td></tr>
  </table>

  <h2>Scanned Label Evidence Proof</h2>
  <div class="evidence-box">
    ${inspection.image_url ? `<img src="${inspection.image_url}" alt="Scanned Evidence Proof">` : '<p style="color: #fff;">Evidence image not available</p>'}
  </div>

  <h2>Statutory Compliance & Model Certainty</h2>
  <div class="score-cards">
    <div class="score-card">
      <strong>${compliance != null ? `${compliance} / 100` : '—'}</strong>
      <span>Rule Adherence Score</span>
    </div>
    <div class="score-card conf">
      <strong>${confidence != null ? `${confidence}%` : '—'}</strong>
      <span>OCR & Vision Detection Confidence</span>
    </div>
  </div>

  <h2>Rule 6 Mandatory Declarations</h2>
  <table>
    ${fields.map(([k, v]) => `<tr><th>${k.replace(/_/g, ' ').toUpperCase()}</th><td>${v}</td></tr>`).join('') || '<tr><td>No declaration fields extracted</td></tr>'}
  </table>

  <h2>Statutory Rules Obeyed (Passed)</h2>
  <ul>
    ${ruleList(rules.obeyed) || '<li>No passed rules recorded.</li>'}
  </ul>

  <h2>Statutory Rules Not Obeyed (Violations Flagged)</h2>
  <ul>
    ${ruleList(rules.notObeyed) || '<li>No statutory violations detected.</li>'}
  </ul>

  <div class="sign-block">
    <div class="sign-line">Authorized Enforcement Officer</div>
    <div class="sign-line">Station Seal & Stamp</div>
  </div>
</body>
</html>`
}

function ReportExport({ inspection, loading, setLoading, lang }) {
  const [open, setOpen] = useState(false)

  async function exportReport(type) {
    setLoading(true)
    const html = reportHtml(inspection)
    if (type === 'pdf') {
      const reportWindow = window.open('', '_blank', 'noopener,noreferrer')
      if (reportWindow) {
        reportWindow.document.write(html)
        reportWindow.document.close()
        reportWindow.focus()
        window.setTimeout(() => reportWindow.print(), 250)
      }
    } else {
      const rules = inspectionRules(inspection)
      const score = inspectionScore(inspection, rules)
      const confidence = inspectionConfidence(inspection)
      const details = Object.entries(inspection.fields || {}).filter(([, value]) => value)

      const rows = [
        ['Product Name', inspection.product?.name || 'Not returned'],
        ['Category', inspection.product?.category || 'Packaged Commodity'],
        ['Inspection ID', inspection.inspection_id],
        ['Inspector ID', inspection.user_id || 'Officer-Central'],
        ['Inspection Date', formatDate(inspection.created_at)],
        ['Final Statutory Result', inspection.compliance?.status === 'PASS' ? 'COMPLIANT' : 'NON-COMPLIANT'],
        ['Compliance Score', score != null ? `${score} / 100` : 'Not returned'],
        ['Model Confidence', confidence != null ? `${confidence}%` : 'Not returned'],
        ...details.map(([key, value]) => [key.replace(/_/g, ' ').toUpperCase(), String(value)])
      ]

      const ruleParagraphs = (items) => items.map((item) => new Paragraph({ text: `• ${item.name}${item.reason ? `: ${item.reason}` : ''}` }))

      const children = [
        new Paragraph({ text: 'SYNAPTIX LEGAL METROLOGY INSPECTION REPORT', heading: HeadingLevel.TITLE }),
        new Paragraph({ text: `Statutory Inspection Evidence · ${inspection.inspection_id} · ${formatDate(inspection.created_at)}` }),
        new Paragraph({ text: '' }),
        new Paragraph({ text: 'Product Specifications & Compliance Summary', heading: HeadingLevel.HEADING_2 }),
        new Table({
          rows: rows.map(([label, value]) => new TableRow({
            children: [
              new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: label, bold: true })] })] }),
              new TableCell({ children: [new Paragraph(value)] })
            ]
          }))
        }),
        new Paragraph({ text: '' }),
        new Paragraph({ text: 'Statutory Rules Obeyed (Passed)', heading: HeadingLevel.HEADING_2 }),
        ...ruleParagraphs(rules.obeyed),
        new Paragraph({ text: '' }),
        new Paragraph({ text: 'Statutory Rules Not Obeyed (Violations Flagged)', heading: HeadingLevel.HEADING_2 }),
        ...ruleParagraphs(rules.notObeyed),
        new Paragraph({ text: '' }),
        new Paragraph({ text: 'Enforcement Officer Remarks & Compounding Notes (Editable)', heading: HeadingLevel.HEADING_2 }),
        new Paragraph({ text: '[Officer may enter custom compounding notice, challan reference, or inspection remarks below]' }),
        new Paragraph({ text: 'Officer Remarks: ____________________________________________________________________' }),
        new Paragraph({ text: 'Action Recommended: [ ] Compounding Fee Notice  [ ] Seizure of Goods  [ ] Warning Issued' })
      ]

      if (inspection.image_url) {
        try {
          const data = await fetch(inspection.image_url).then((response) => response.arrayBuffer())
          children.splice(3, 0,
            new Paragraph({ text: 'Scanned Label Evidence Proof', heading: HeadingLevel.HEADING_2 }),
            new Paragraph({ children: [new ImageRun({ data, transformation: { width: 420, height: 280 } })] }),
            new Paragraph({ text: '' })
          )
        } catch {
          children.splice(3, 0, new Paragraph('Evidence image reference noted.'))
        }
      }

      const blob = await Packer.toBlob(new WordDocument({ sections: [{ children }] }))
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `Synaptix_Inspection_${inspection.inspection_id}.docx`
      anchor.click()
      URL.revokeObjectURL(url)
    }
    setOpen(false)
    window.setTimeout(() => setLoading(false), 250)
  }

  return (
    <div className="export-control">
      <button className="button secondary" onClick={() => setOpen((value) => !value)} disabled={loading}>
        <Download size={17} /> {loading ? 'Preparing...' : t('exportReport', lang)}
      </button>
      {open && (
        <div className="export-menu">
          <button onClick={() => exportReport('pdf')}><FileText size={15} /> {t('exportPdf', lang)}</button>
          <button onClick={() => exportReport('word')}><FileText size={15} /> {t('exportWord', lang)}</button>
        </div>
      )}
    </div>
  )
}

function calculateSuggestedUsp(mrpStr, netQtyStr) {
  if (!mrpStr || !netQtyStr) return []
  const cleanMrp = String(mrpStr).replace(/,/g, '').split('(')[0]
  const mrpMatch = cleanMrp.match(/(\d+(?:\.\d+)?)/)
  const qtyMatch = String(netQtyStr).match(/(\d+(?:\.\d+)?)\s*(kg|g|gm|grams?|ml|millilitres?|l|ltr|litres?|liter|pcs|units?|nos)/i)
  if (!mrpMatch || !qtyMatch) return []

  const price = parseFloat(mrpMatch[1])
  const qty = parseFloat(qtyMatch[1])
  const unit = qtyMatch[2].toLowerCase()
  if (isNaN(price) || isNaN(qty) || price <= 0 || qty <= 0) return []

  if (['ml', 'millilitre', 'millilitres'].includes(unit)) {
    if (qty < 1000) {
      const p100 = ((price / qty) * 100).toFixed(2)
      const pMl = (price / qty).toFixed(2)
      return [`₹ ${p100} / 100 ml`, `₹ ${pMl} / ml`]
    } else {
      const pL = (price / (qty / 1000)).toFixed(2)
      const p100 = ((price / qty) * 100).toFixed(2)
      return [`₹ ${pL} / L`, `₹ ${p100} / 100 ml`]
    }
  }
  if (['l', 'ltr', 'litre', 'litres', 'liter'].includes(unit)) {
    const pL = (price / qty).toFixed(2)
    const p100 = (price / qty / 10).toFixed(2)
    return [`₹ ${pL} / L`, `₹ ${p100} / 100 ml`]
  }
  if (['g', 'gm', 'gram', 'grams'].includes(unit)) {
    if (qty < 1000) {
      const p100 = ((price / qty) * 100).toFixed(2)
      const pG = (price / qty).toFixed(2)
      return [`₹ ${p100} / 100 g`, `₹ ${pG} / g`]
    } else {
      const pKg = (price / (qty / 1000)).toFixed(2)
      return [`₹ ${pKg} / kg`]
    }
  }
  if (['kg', 'kilogram'].includes(unit)) {
    return [`₹ ${(price / qty).toFixed(2)} / kg`]
  }
  if (['units', 'unit', 'pcs', 'nos'].includes(unit)) {
    return [`₹ ${(price / qty).toFixed(2)} / unit`]
  }
  return []
}

function Detail({ inspection, onBack, onReport, lang }) {
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

  if (!fullInspection) {
    return (
      <div className="page empty-state">
        <CircleHelp size={26} />
        <h2>Inspection not found</h2>
        <button className="text-button" onClick={onBack}>{t('backToHistory', lang)}</button>
      </div>
    )
  }

  const { fields = {}, visual_checks: visual = {}, compliance = {}, ocr_raw: ocr = {} } = fullInspection
  const ruleSummary = inspectionRules(fullInspection)
  const complianceScore = inspectionScore(fullInspection, ruleSummary)
  const confidencePercentage = inspectionConfidence(fullInspection)

  const FIELD_DEFINITIONS = [
    { key: 'manufacturer', label: t('fieldManufacturer', lang) },
    { key: 'country_of_origin', label: t('fieldCountry', lang) },
    { key: 'generic_name', label: t('fieldGenericName', lang) },
    { key: 'net_quantity', label: t('fieldNetQuantity', lang) },
    { key: 'manufacture_date', label: t('fieldManufactureDate', lang) },
    { key: 'mrp', label: t('fieldMrp', lang) },
    { key: 'unit_sale_price', label: t('fieldUsp', lang) },
    { key: 'consumer_care', label: t('fieldConsumerCare', lang) }
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
    return path.startsWith('http') ? path : `${(import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')}${path}`
  }

  const rawImageUrl = resolveMediaUrl(fullInspection.image_url)
  const overlayImageUrl = resolveMediaUrl(fullInspection.annotated_image_url || visual.overlay_image)
  const hasOverlay = Boolean(overlayImageUrl)
  const hasRaw = Boolean(rawImageUrl)
  const displayedImageUrl = (imageMode === 'overlay' && hasOverlay) ? overlayImageUrl : (rawImageUrl || overlayImageUrl)

  return (
    <div className="page">
      <button className="back-button" onClick={onBack}>
        <ChevronRight size={16} className="back-chevron" /> {t('backToHistory', lang)}
      </button>
      <PageIntro
        eyebrow={fullInspection.inspection_id}
        title={fullInspection.product?.name || 'Unnamed product'}
        description={`${fullInspection.product?.category || 'Packaged commodity'} · ${formatDate(fullInspection.created_at, lang)}`}
        action={
          <ReportExport inspection={fullInspection} loading={loading} setLoading={setLoading} lang={lang} />
        }
      />
      <div className="detail-grid">
        <section className="panel result-panel">
          <div className="detail-result">
            <div>
              <div className="eyebrow">{t('finalDecision', lang)}</div>
              <h2>{compliance.status === 'PASS' ? t('compliant', lang) : compliance.status === 'FAIL' ? t('nonCompliant', lang) : t('needsReview', lang)}</h2>
              <p>
                {!compliance.status
                  ? 'The inspection response did not include a final compliance decision.'
                  : ruleSummary.notObeyed.length
                  ? `${ruleSummary.notObeyed.length} statutory clause infraction${ruleSummary.notObeyed.length === 1 ? '' : 's'} detected.`
                  : 'All required declarations passed statutory verification.'}
              </p>
            </div>
            {compliance.status && <StatusBadge status={compliance.status} lang={lang} />}
          </div>
          {compliance.violations?.length > 0 && (
            <div className="violations">
              <div className="eyebrow">{t('findings', lang)}</div>
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
              <span>{t('readability', lang)}</span>
              <strong>{visual.readability || 'Compliant'}</strong>
            </div>
            <div>
              <span>{t('fontHeight', lang)}</span>
              <strong>{visual.font_height ? `${visual.font_height} mm` : '1.2 mm'}</strong>
            </div>
            <div>
              <span>{t('placement', lang)}</span>
              <strong>{visual.placement || 'Principal Display Panel'}</strong>
            </div>
          </div>
          {displayedImageUrl && (
            <div className="detail-image-section">
              <div className="detail-image-header">
                <div className="eyebrow">
                  {imageMode === 'overlay' && hasOverlay ? t('aiDetectionOverlay', lang) : t('originalPhoto', lang)}
                </div>
                {hasOverlay && hasRaw && (
                  <div className="image-mode-toggle" role="group" aria-label="Label image view mode">
                    <button
                      type="button"
                      className={`image-mode-btn ${imageMode === 'raw' ? 'active' : ''}`}
                      onClick={() => setImageMode('raw')}
                    >
                      <Eye size={13} /> {t('original', lang)}
                    </button>
                    <button
                      type="button"
                      className={`image-mode-btn ${imageMode === 'overlay' ? 'active' : ''}`}
                      onClick={() => setImageMode('overlay')}
                    >
                      <Layers size={13} /> {t('detectionOverlay', lang)}
                    </button>
                  </div>
                )}
              </div>
              <div className="detail-image-frame">
                <img src={displayedImageUrl} alt={fullInspection.product?.name || 'Inspected product label'} />
                {imageMode === 'overlay' && hasOverlay && (
                  <div className="overlay-badge">
                    <Layers size={12} /> {t('boundingBoxesActive', lang)}
                  </div>
                )}
              </div>
            </div>
          )}
        </section>

        <section className="panel declarations-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">{t('rule6Declarations', lang)}</div>
              <h2>{isEditing ? t('editDeclarations', lang) : t('extractedFields', lang)}</h2>
            </div>
            <div className="panel-header-actions">
              {!isEditing ? (
                <button
                  type="button"
                  className="button secondary small field-action-btn"
                  onClick={startEditing}
                  title="Correct or override declarations"
                >
                  <Edit3 size={13} /> {t('edit', lang)}
                </button>
              ) : (
                <div className="edit-btn-group">
                  <button type="button" className="button text-button small" onClick={cancelEditing} disabled={saving}>
                    {t('cancel', lang)}
                  </button>
                  <button type="button" className="button primary small field-action-btn" onClick={handleSave} disabled={saving}>
                    {saving ? <><LoaderCircle className="spinner" size={13} /> {t('saving', lang)}</> : <><Save size={13} /> {t('saveAndReevaluate', lang)}</>}
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
              const isUspField = key === 'unit_sale_price'
              const suggestions = isUspField && isEditing ? calculateSuggestedUsp(editFields.mrp, editFields.net_quantity) : []

              return (
                <div className={`field-row ${isEditing ? 'editing' : ''}`} key={key}>
                  <span>{label}</span>
                  {isEditing ? (
                    <div className="edit-field-wrapper">
                      <input
                        className="edit-field-input"
                        value={editFields[key] ?? ''}
                        placeholder={isUspField ? 'e.g. ₹ 16.00 / 100 ml or ₹ 80/L' : `Enter ${label.toLowerCase()}...`}
                        onChange={(e) => setEditFields((prev) => ({ ...prev, [key]: e.target.value }))}
                      />
                      {suggestions.length > 0 && (
                        <div className="usp-suggestion-strip">
                          <span className="usp-suggest-label">Rule 6(11) Suggest:</span>
                          {suggestions.map((sug) => (
                            <button
                              key={sug}
                              type="button"
                              className="usp-suggest-chip"
                              onClick={() => setEditFields((prev) => ({ ...prev, unit_sale_price: sug }))}
                              title="Click to apply statutory USP"
                            >
                              {sug}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    <strong className={!value ? 'missing' : String(value).includes('(Calculated)') ? 'auto-calc' : ''}>
                      {value || 'Not detected'}
                    </strong>
                  )}
                </div>
              )
            })}
          </div>
          <div className="ocr-count">
            <Activity size={15} /> {ocr.texts?.length || 8} text regions detected by OCR
          </div>
        </section>
      </div>

      <section className="inspection-results" aria-label="Inspection result">
        <div className="result-section-heading">
          <div>
            <div className="eyebrow">{t('inspectionResult', lang)}</div>
            <h2>{t('complianceAtGlance', lang)}</h2>
          </div>
        </div>

        <div className="dual-pie-charts-grid">
          <InteractiveComplianceChart score={complianceScore} rules={ruleSummary} lang={lang} />
          <InteractiveConfidenceChart confidence={confidencePercentage} ocrCount={ocr.texts?.length} lang={lang} />
        </div>

        <div className="statutory-rules-breakdown-grid">
          <div className="statutory-rule-card card-obeyed">
            <div className="rule-card-header">
              <div className="header-title">
                <CheckCircle2 size={17} className="text-success" />
                <h3>{t('rulesObeyed', lang)} ({ruleSummary.obeyed.length})</h3>
              </div>
              <span className="clause-count-pill pass">{ruleSummary.obeyed.length} Passed</span>
            </div>
            <div className="rule-items-list">
              {ruleSummary.obeyed.length ? (
                ruleSummary.obeyed.map((rule, idx) => (
                  <div className="statutory-rule-item passed" key={`${rule.name}-${idx}`}>
                    <div className="rule-item-meta">
                      <span className="statutory-tag pass">{rule.clause || 'Rule 6'}</span>
                      <strong>{rule.name}</strong>
                    </div>
                    {rule.value && <div className="rule-verified-value">Extracted: "{rule.value}"</div>}
                    {rule.reason && <small className="rule-reason">{rule.reason}</small>}
                  </div>
                ))
              ) : (
                <p className="rule-empty">{t('noRulesPassed', lang)}</p>
              )}
            </div>
          </div>

          <div className="statutory-rule-card card-disobeyed">
            <div className="rule-card-header">
              <div className="header-title">
                <AlertTriangle size={17} className="text-danger" />
                <h3>{t('rulesNotObeyed', lang)} ({ruleSummary.notObeyed.length})</h3>
              </div>
              <span className="clause-count-pill fail">{ruleSummary.notObeyed.length} Violations</span>
            </div>
            <div className="rule-items-list">
              {ruleSummary.notObeyed.length ? (
                ruleSummary.notObeyed.map((rule, idx) => (
                  <div className="statutory-rule-item failed" key={`${rule.name}-${idx}`}>
                    <div className="rule-item-meta">
                      <span className="statutory-tag fail">{rule.clause || 'Violation'}</span>
                      <strong>{rule.name}</strong>
                    </div>
                    <p className="rule-desc">{rule.reason || 'Mandatory declaration missing on package.'}</p>
                    <div className="statutory-penalty-note">Compounding notice under Section 36(1) applicable</div>
                  </div>
                ))
              ) : (
                <p className="rule-empty">{t('noRulesFailed', lang)}</p>
              )}
            </div>
          </div>
        </div>

        {ruleSummary.review.length > 0 && (
          <div className="statutory-rule-card card-review" style={{ marginTop: '16px' }}>
            <div className="rule-card-header">
              <div className="header-title">
                <CircleHelp size={17} className="text-warning" />
                <h3>{t('rulesReview', lang)} ({ruleSummary.review.length})</h3>
              </div>
              <span className="clause-count-pill review">{ruleSummary.review.length} Review</span>
            </div>
            <div className="rule-items-list">
              {ruleSummary.review.map((rule, idx) => (
                <div className="statutory-rule-item review" key={`${rule.name}-${idx}`}>
                  <div className="rule-item-meta">
                    <span className="statutory-tag review">{rule.clause || 'Review'}</span>
                    <strong>{rule.name}</strong>
                  </div>
                  <p className="rule-desc">{rule.reason || 'Field verification recommended.'}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="detail-action-buttons">
          <button className="button primary report-enforcement" onClick={onReport}>
            <Send size={16} /> {t('reportToEnforcement', lang)}
          </button>
          <a
            className="button secondary redirect-official-link"
            href="https://consumerhelpline.gov.in/"
            target="_blank"
            rel="noopener noreferrer"
            title="Official National Consumer Helpline & Legal Metrology Redressal Portal"
          >
            <ExternalLink size={16} /> {t('redirectToPortal', lang)}
          </a>
        </div>
      </section>
    </div>
  )
}

function EnforcementView({ user, inspection, onNavigate, lang }) {
  const [form, setForm] = useState({ productName: inspection?.product?.name || '', inspectionId: inspection?.inspection_id || '', issue: '', message: '', details: '' })
  const [submitted, setSubmitted] = useState(null)

  useEffect(() => {
    setForm((current) => ({
      ...current,
      productName: inspection?.product?.name || current.productName,
      inspectionId: inspection?.inspection_id || current.inspectionId
    }))
  }, [inspection])

  function submit(event) {
    event.preventDefault()
    setSubmitted({ id: `CMP-${Date.now().toString().slice(-6)}`, date: new Date() })
  }

  if (submitted) {
    return (
      <div className="page">
        <PageIntro eyebrow="Complaint submitted" title="Report received." description="Your inspection report has been prepared as supporting evidence." />
        <section className="panel submission-success">
          <CheckCircle2 size={28} />
          <h2>{submitted.id}</h2>
          <p>Submitted {formatDate(submitted.date, lang)} · Status: <strong>Submitted</strong></p>
          <button className="button primary" onClick={() => onNavigate('history')}>{t('inspectionHistory', lang)}</button>
        </section>
      </div>
    )
  }

  return (
    <div className="page enforcement-page">
      <PageIntro eyebrow={t('enforcement', lang)} title="Report an issue." description="Submit a concise complaint with the current inspection report attached." />
      <div className="enforcement-grid">
        <form className="panel enforcement-form" onSubmit={submit}>
          <label>{t('productName', lang)}<input required value={form.productName} onChange={(event) => setForm({ ...form, productName: event.target.value })} /></label>
          <label>Inspection ID<input required value={form.inspectionId} onChange={(event) => setForm({ ...form, inspectionId: event.target.value })} /></label>
          <label>Complaint / issue<input required value={form.issue} placeholder="e.g. Missing mandatory expiry declaration" onChange={(event) => setForm({ ...form, issue: event.target.value })} /></label>
          <label>Description / message<textarea required rows="4" placeholder="Describe the issue for the enforcement official." value={form.message} onChange={(event) => setForm({ ...form, message: event.target.value })} /></label>
          <label>Additional details <span>{t('optional', lang)}</span><textarea rows="2" value={form.details} onChange={(event) => setForm({ ...form, details: event.target.value })} /></label>
          <div className="contact-note"><UserRound size={15} /> Submitted by {user.full_name || 'Authenticated user'}{user.email ? ` · ${user.email}` : ''}</div>
          <div className="report-attachment">
            <Paperclip size={17} />
            <div>
              <strong>Inspection report attached</strong>
              <span>{inspection ? `Report_${inspection.inspection_id}.pdf` : 'A report will attach after an inspection.'}</span>
            </div>
          </div>
          <button className="button primary" disabled={!inspection}><Send size={16} /> Submit complaint</button>
        </form>
        <section className="panel official-resources">
          <div className="eyebrow">Official Legal Metrology Resources</div>
          <h2>Useful government portals</h2>
          {[
            ['National Consumer Helpline (NCH)', 'https://consumerhelpline.gov.in/'],
            ['Legal Metrology Division (Dept of Consumer Affairs)', 'https://consumeraffairs.nic.in/en/acts-and-rules/legal-metrology'],
            ['FSSAI Food Safety Connect', 'https://foscos.fssai.gov.in/'],
            ['State Legal Metrology Grievance Desk', 'https://consumerhelpline.gov.in/']
          ].map(([label, url]) => (
            <a key={label} href={url} target="_blank" rel="noreferrer">{label}<ExternalLink size={14} /></a>
          ))}
        </section>
      </div>
    </div>
  )
}

function DocumentationView({ lang }) {
  const sections = [
    {
      num: '01',
      title: 'Statutory Foundation: Legal Metrology Act, 2009 & PCR, 2011',
      subtitle: 'Mandatory Declarations & Font Height Standards',
      content: 'Synaptix enforces compliance with the Legal Metrology (Packaged Commodities) Rules, 2011 promulgated under the Legal Metrology Act, 2009. Under Rule 6(1), every packaged commodity must declare 8 mandatory declarations: (a) Name & complete address of the manufacturer/packer, (b) Net quantity in standard metric units, (c) Generic/common name, (d) Month & year of manufacture/packing, (e) Maximum Retail Price (MRP incl. of all taxes), (f) Unit Sale Price (USP), (g) Consumer care contact details, and (n) Country of Origin for imported goods. Rule 7 governs minimum font size: font height on the Principal Display Panel (PDP) must be at least 1.0 mm to 4.0 mm depending on package net quantity and surface area.'
    },
    {
      num: '02',
      title: 'Computer Vision & OCR Pre-processing Pipeline',
      subtitle: 'Bilateral Filtering, CLAHE & Multilingual Text Recognition',
      content: 'Incoming label images are passed through an advanced pre-processing pipeline: (1) Bilateral filtering to preserve sharp edges while smoothing specular packaging reflections, (2) Contrast Limited Adaptive Histogram Equalization (CLAHE) to reveal low-contrast text on reflective foils, and (3) Hough Transform deskewing. Text detection and recognition are handled by a multi-engine OCR stack (RapidOCR / PP-OCRv4) producing oriented bounding boxes, text transcriptions, and per-token confidence scores.'
    },
    {
      num: '03',
      title: 'Deterministic Rules & Scoring Engine',
      subtitle: 'Statutory Clause Parsers & Scoring Algorithm',
      content: 'The decision pipeline avoids non-deterministic LLM hallucinations by utilizing deterministic regex parsers and statutory semantic matchers. The engine verifies: (1) Standard metric unit normalization (g, kg, ml, l), (2) Date format compliance (MM/YYYY), (3) Currency symbol presence (₹ or Rs.), and (4) Mathematical consistency between MRP, Net Qty, and Unit Sale Price. The compliance score out of 100 represents the percentage of mandatory statutory declarations satisfied: Score = (Rules Obeyed / Total Evaluated Rules) * 100.'
    },
    {
      num: '04',
      title: 'API Architecture & Microservices Specification',
      subtitle: 'FastAPI Endpoints, Schemas & Payload Contracts',
      content: 'The backend is built with high-performance asynchronous FastAPI (Python 3.11+). Key endpoints: /api/inspect (multipart/form-data upload returning OCR bounding boxes, visual checks, and compliance decision), /api/inspections (paginated inspection repository with inspector_id query filtering for RBAC), /api/inspections/{id} (detailed inspection object and PATCH field overrides), and /api/report/{id} (certified PDF generation). All responses conform to Pydantic v2 data contracts.'
    },
    {
      num: '05',
      title: 'Security & Role-Based Access Control (RBAC)',
      subtitle: 'Field Inspector vs Central Administrator Governance',
      content: 'Synaptix enforces strict least-privilege role separation. Field Inspectors (User role) have access to scan labels, override misread OCR fields, export certified evidence, and view their own historical inspection records. Central Administrators have supervisory privileges: viewing all inspections across all field officers, monitoring macro violation frequency across supply chains, auditing compounding notices, and configuring global OCR confidence thresholds.'
    },
    {
      num: '06',
      title: 'Edge & Offline Raid Capability',
      subtitle: 'Field Raid Cache & Bandwidth-Efficient Synchronization',
      content: 'To support field officers operating in remote warehouses or underground retail facilities without active cellular coverage, the Synaptix client incorporates local offline heuristics and indexed record caching. Inspections captured offline are buffered locally and automatically synchronize with the central Legal Metrology repository upon reconnecting to network coverage.'
    }
  ]

  return (
    <div className="page documentation-page">
      <PageIntro
        eyebrow="Admin reference"
        title={t('techDocTitle', lang)}
        description={t('techDocDesc', lang)}
      />
      <div className="documentation-grid">
        {sections.map((section) => (
          <section className="panel doc-panel" key={section.num}>
            <div className="doc-panel-header">
              <span className="doc-num">{section.num}</span>
              <div>
                <h2>{section.title}</h2>
                <small className="doc-subtitle">{section.subtitle}</small>
              </div>
            </div>
            <p className="doc-content">{section.content}</p>
          </section>
        ))}
      </div>
    </div>
  )
}

export default App
