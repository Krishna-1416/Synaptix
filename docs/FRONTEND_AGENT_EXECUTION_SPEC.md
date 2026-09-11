# Frontend Architectural Modernization & RBAC Execution Spec
**Target System:** Synaptix Frontend (`frontend/src/`)  
**Audience:** Autonomous AI Coding Agents & Senior Frontend Engineers  
**Standards:** `/senior-frontend` · Modular React · Zero-Slop UX · Enterprise RBAC · High-Performance Canvas/SVG  
**Build Tooling:** Vite + React 19 + Vanilla CSS Variables

---

## 1. Executive Summary & Objective

Currently, the Synaptix frontend operates as a single **819-line monolithic file** (`frontend/src/App.jsx`) where all components (Authentication, Dashboard, Scan/Camera, History, Detail, Analytics, Configuration) and states reside together. Furthermore, while the login screen offers a visual toggle between **User (Inspector)** and **Admin**, both roles currently render identical capabilities under the hood.

This document serves as the **authoritative, prescriptive implementation specification** for an AI Agent to execute a complete architectural modernization across 5 progressive, non-breaking phases:

1. **Phase 1: Component Modularization & Monolith Decomposition**
2. **Phase 2: Enterprise Role-Based Access Control (RBAC)**
3. **Phase 3: Two-Way Interactive SVG/Canvas Bounding Box Visualizer**
4. **Phase 4: Field Inspector Ergonomics & Keyboard Shortcuts**
5. **Phase 5: Resilient State Architecture & Optimistic Data Layer**

---

## 2. Target File Structure

The AI agent must restructure `frontend/src/` into the following modular layout:

```
frontend/src/
├── api.js                                # Existing API client
├── demoData.js                           # Existing mock fallback data
├── main.jsx                              # Application entry point
├── styles.css                            # Global styles & design tokens
│
├── context/
│   └── AuthContext.jsx                   # Centralized user, role, token & session state
│
├── hooks/
│   ├── useTheme.js                       # Light/Dark mode state & DOM sync
│   ├── useInspections.js                 # Inspection queries, filtering & caching
│   ├── useInspectorShortcuts.js          # Hotkeys (Space, E, Ctrl+Enter, Esc, P)
│   └── useInteractiveBBoxes.js           # SVG coordinate scaling & hover sync
│
├── components/
│   ├── common/
│   │   ├── StatusBadge.jsx               # Compliant (Pass), Non-compliant (Fail), Review
│   │   ├── MetricCard.jsx                # Metric stat card with tone & trend
│   │   ├── PageIntro.jsx                 # Standard page header with eyebrow & action
│   │   ├── ThemeToggle.jsx               # Sun/Moon pill button
│   │   └── LoadingRows.jsx               # Skeleton/Spinner loader
│   ├── layout/
│   │   ├── AppShell.jsx                  # Main wrapper with sidebar and topbar
│   │   ├── Sidebar.jsx                   # Collapsible desktop rail + mobile slide-over
│   │   └── Topbar.jsx                    # Breadcrumbs, connection status & notifications
│   └── visualizer/
│       ├── ImageOverlay.jsx              # Raster detection overlay toggle
│       └── InteractiveBBoxViewer.jsx     # High-performance responsive SVG bbox viewer
│
└── features/
    ├── auth/
    │   ├── EntryFlow.jsx                 # Splash -> Welcome -> Portal -> Auth router
    │   ├── Splash.jsx                    # Brand animated splash screen
    │   ├── Welcome.jsx                   # Value proposition landing
    │   ├── PortalSelection.jsx           # Workspace selection card
    │   └── AuthModal.jsx                 # Role-aware login/signup form
    ├── dashboard/
    │   ├── Dashboard.jsx                 # Role-aware overview desk
    │   ├── ComplianceDonut.jsx           # Pure CSS/SVG donut chart
    │   └── RecentInspections.jsx         # Recent activity widget
    ├── inspection/
    │   ├── Scan.jsx                      # Drag-and-drop & live camera capture
    │   ├── HistoryView.jsx               # Searchable, filterable repository table
    │   ├── InspectionTable.jsx           # Reusable inspection table
    │   ├── Detail.jsx                    # Inspection audit workspace
    │   └── DeclarationsTable.jsx         # Rule 6 editable declarations table
    ├── analytics/
    │   ├── AnalyticsView.jsx             # Decision trends & category distribution
    │   └── TrendBarChart.jsx             # Chronological compliance outcome chart
    └── admin/
        ├── AuditLogView.jsx              # [ADMIN ONLY] Inspector override history log
        ├── RuleTuningView.jsx            # [ADMIN ONLY] Legal Metrology engine thresholds
        └── ConfigurationView.jsx         # Workspace preferences & alert settings
```

---

## 3. Phase-by-Phase Agent Instructions

### Phase 1: Modularization & Monolith Decomposition

> [!IMPORTANT]
> **Safety Rule**: Do not break the build. After extracting each component, run `npm run build` inside `frontend/` to ensure zero compilation or syntax regressions.

#### Step 1.1: Create `src/context/AuthContext.jsx`
Extract authentication logic from `App.jsx` into a standard React Context:
- **State**: `user` (`{ id, full_name, email, role: 'inspector' | 'admin' }`), `authenticated` (boolean), `token`.
- **Methods**: `login({ email, password, role })`, `signup(...)`, `logout()`, `switchRole(role)`.
- **Persistence**: Persist `synaptix_user` and `synaptix_authenticated` to `window.localStorage`.

#### Step 1.2: Extract Layout Components (`src/components/layout/`)
1. **`Sidebar.jsx`**: Extract sidebar markup, collapse toggle button (`.sidebar-rail-toggle`), mobile drawer state, navigation links, and bottom user profile chip.
   - **Role Gate**: If `user.role === 'admin'`, display the **Audit Logs** and **System Tuning** links in the System section.
2. **`Topbar.jsx`**: Extract topbar, breadcrumbs, API connection indicator (`api.checkHealth`), and notifications trigger.
3. **`AppShell.jsx`**: Combine `Sidebar`, `Topbar`, and `<main className="main-content">` children into a coherent layout.

#### Step 1.3: Extract Feature Modules
- Move `EntryFlow`, `Splash`, `Welcome`, `PortalSelection`, `Auth` to `src/features/auth/`.
- Move `Dashboard`, `Donut`, `RecentInspections` to `src/features/dashboard/`.
- Move `Scan`, `HistoryView`, `Detail`, `InspectionTable` to `src/features/inspection/`.
- Move `AnalyticsView` to `src/features/analytics/`.
- Move `ConfigurationView` to `src/features/admin/`.

---

### Phase 2: Role-Based Access Control (RBAC) Architecture

Implement real differentiation between **Field Inspector** (`inspector`) and **Superintendent / Admin** (`admin`).

#### Role Capability Matrix

| Feature / View | Field Inspector (`user` / `inspector`) | Enforcement Admin (`admin`) |
|---|---|---|
| **Default Landing View** | `Scan` or `Dashboard` (Tactical desk) | `Dashboard` (District overview) |
| **New Inspection (Camera/Upload)** | Full Access | Full Access |
| **Inspection Detail & PDF Report** | Full Access | Full Access |
| **Inline Declaration Override** | Full Access (Logs inspector name/ID) | Full Access (Can lock/approve record) |
| **District Audit Trail Log** | Hidden (403 if accessed) | Full Access (Shows inspector overrides) |
| **Rule Engine Threshold Tuning** | Read-Only (Displays current rules) | Editable (Adjusts OCR & Font tolerances) |
| **Bulk Violation Export (CSV/JSON)**| Hidden | Full Access (Export for legal prosecution) |

#### Implementation Steps for AI Agent:
1. **Route Guard Helper**:
   Create `src/components/common/RoleGate.jsx`:
   ```jsx
   export function RoleGate({ allowedRoles, userRole, children, fallback = null }) {
     if (!allowedRoles.includes(userRole)) return fallback;
     return children;
   }
   ```
2. **Admin Feature: `src/features/admin/AuditLogView.jsx`**:
   - Query all inspections that have an `audit_trail` or modified declarations.
   - Table columns: `Timestamp`, `Inspection ID`, `Product`, `Field Changed`, `Old Value`, `Overridden Value`, `Inspector ID / Name`, `Impact on Status`.
3. **Admin Feature: Bulk Export**:
   - In `HistoryView.jsx`, add an `Export Violations` button visible only to `admin`:
   - Exports all `FAIL` and `REVIEW` inspections to a CSV formatted for legal enforcement notices under the Legal Metrology Act, 2009.

---

### Phase 3: Two-Way Interactive SVG/Canvas Bounding-Box Visualizer

Currently, the overlay is a static JPEG rendered by OpenCV on the backend. This phase upgrades it to an **interactive SVG overlay** synchronized with the Rule 6 Declarations Table.

#### Data Contract
The backend returns `ocr_raw.boxes` (array of `[x1, y1, x2, y2]` or polygons) and `fields` mapping.

#### Step 3.1: Create `src/components/visualizer/InteractiveBBoxViewer.jsx`
```jsx
import { useState } from 'react';

export function InteractiveBBoxViewer({ 
  imageUrl, 
  regions = [], 
  hoveredFieldKey, 
  onRegionClick,
  naturalWidth = 1080,
  naturalHeight = 1350
}) {
  const [zoom, setZoom] = useState(1);

  return (
    <div className="bbox-viewer-container" style={{ position: 'relative', overflow: 'hidden' }}>
      <div className="bbox-stage" style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
        <img 
          src={imageUrl} 
          alt="Inspected Package" 
          className="bbox-base-image"
          style={{ width: '100%', height: 'auto', display: 'block' }} 
        />
        <svg 
          viewBox={`0 0 ${naturalWidth} ${naturalHeight}`}
          className="bbox-svg-overlay"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
        >
          {regions.map((region, idx) => {
            const isHighlighted = hoveredFieldKey === region.fieldKey;
            const [x, y, w, h] = region.bbox; // [x, y, width, height]
            return (
              <g key={idx} style={{ pointerEvents: 'all', cursor: 'pointer' }} onClick={() => onRegionClick(region.fieldKey)}>
                <rect
                  x={x}
                  y={y}
                  width={w}
                  height={h}
                  fill={isHighlighted ? "rgba(38, 131, 90, 0.28)" : "rgba(38, 131, 90, 0.08)"}
                  stroke={isHighlighted ? "var(--green)" : "rgba(38, 131, 90, 0.6)"}
                  strokeWidth={isHighlighted ? 4 : 2}
                  strokeDasharray={region.isCompliant ? "none" : "6,4"}
                />
                {isHighlighted && (
                  <text
                    x={x}
                    y={Math.max(20, y - 8)}
                    fill="var(--green)"
                    fontSize="18"
                    fontWeight="700"
                    fontFamily="DM Mono, monospace"
                  >
                    {region.label}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <div className="bbox-zoom-controls">
        <button type="button" onClick={() => setZoom(z => Math.max(1, z - 0.25))}>-</button>
        <span>{Math.round(zoom * 100)}%</span>
        <button type="button" onClick={() => setZoom(z => Math.min(3, z + 0.25))}>+</button>
      </div>
    </div>
  );
}
```

#### Step 3.2: Synchronize with `DeclarationsTable.jsx`
- In `Detail.jsx`, maintain `const [hoveredFieldKey, setHoveredFieldKey] = useState(null)`.
- Pass `onMouseEnter={() => setHoveredFieldKey(key)}` and `onMouseLeave={() => setHoveredFieldKey(null)}` to each row in `DeclarationsTable`.
- When a user hovers over "Maximum retail price", the corresponding rectangle on the packaging lights up in green with an animated pulse.
- When an inspector clicks a box on the photo, auto-scroll and highlight that row in the declarations table.

---

### Phase 4: Field Inspector Ergonomics & Keyboard Shortcuts

Field officers examining physical packaging need maximum operational speed without reaching for the mouse.

#### Step 4.1: Create `src/hooks/useInspectorShortcuts.js`
```javascript
import { useEffect } from 'react';

export function useInspectorShortcuts({
  onCapture,
  onEdit,
  onSave,
  onCancel,
  onDownload,
  isEditing = false,
  activeView = 'dashboard'
}) {
  useEffect(() => {
    function handleKeyDown(event) {
      // Ignore keystrokes when typing in text input fields
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName)) {
        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && isEditing) {
          event.preventDefault();
          onSave?.();
        } else if (event.key === 'Escape' && isEditing) {
          event.preventDefault();
          onCancel?.();
        }
        return;
      }

      switch (event.key.toLowerCase()) {
        case ' ': // Spacebar to snap photo in camera mode
          if (activeView === 'scan') {
            event.preventDefault();
            onCapture?.();
          }
          break;
        case 'e': // Enter edit mode in detail view
          if (activeView === 'detail' && !isEditing) {
            event.preventDefault();
            onEdit?.();
          }
          break;
        case 'p': // Download PDF certificate
          if (activeView === 'detail') {
            event.preventDefault();
            onDownload?.();
          }
          break;
        case 'escape':
          if (isEditing) {
            event.preventDefault();
            onCancel?.();
          }
          break;
        default:
          break;
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onCapture, onEdit, onSave, onCancel, onDownload, isEditing, activeView]);
}
```

#### Step 4.2: Add Keyboard Shortcut Helper Modal
Add a small `?` or `kbd` helper icon in the topbar rendering a cheat sheet for inspectors.

---

### Phase 5: Resilient State & Data Layer

#### Step 5.1: Create `src/hooks/useInspections.js`
Centralize API queries and cache:
- Maintains `inspections` state with fast in-memory map lookup.
- Implements optimistic updates: when `updateInspection(id, fields)` is triggered, immediately update local state, re-render the decision badge, and rollback gracefully if the network request fails.

#### Step 5.2: Local Offline Queue (IndexedDB Fallback)
If the field officer is in a remote godown with poor reception:
- Save captured photos and metadata to IndexedDB (`synaptix_offline_queue`).
- Display an "Offline Queue (X pending)" badge in the topbar.
- Automatically upload and trigger backend OCR pipelines when network connectivity (`navigator.onLine`) returns.

---

## 4. Verification & Testing Protocol for the AI Agent

For every phase executed, the AI agent must run the following automated verification commands and verify green exit codes:

### 1. Frontend Bundle & Syntax Verification
```bash
cd frontend
npm run build
```
- **Expected Outcome**: `vite build` exits with code `0`.
- **Constraint**: Total bundle size must remain $< 100\text{ kB}$ gzipped. Zero unused imports or unresolved component references.

### 2. Full Backend & Rules Integration Verification
```bash
# Run from repository root
python -m pytest cv/tests/ backend/rules/tests/ backend/tests/test_inspector_override.py -v
```
- **Expected Outcome**: All 53 unit & integration tests pass with $100\%$ green status in $< 5\text{ seconds}$.

### 3. Visual & Aesthetic Quality Checks
- Check Light Mode and Dark Mode contrast compliance ($> 4.5:1$ contrast ratio).
- Ensure `.sidebar-rail-toggle` continues to glide cleanly across collapsed state ($68\text{px}$) and expanded state ($246\text{px}$).
- Ensure responsive breakpoints (`980px` tablet, `650px` mobile) work cleanly without horizontal scroll leaks.

---

## 5. Agent Prompt Checklist

When prompting an AI agent to execute tasks from this spec, reference specific sections using this syntax:

```markdown
"Please execute Phase 1 (Component Modularization) and Phase 2 (RBAC RoleGate) exactly as described in docs/FRONTEND_AGENT_EXECUTION_SPEC.md. Keep the existing styling intact, preserve all 53 backend tests, and ensure `npm run build` succeeds."
```
