# Synaptix Design System (DESIGN.md)
## Stripe-Inspired "Financial-Grade Metrology" Theme Specification

> **Version:** 2.0.0  
> **Target Product:** Synaptix — Automated Legal Metrology Inspection System (SIH26034)  
> **Design Language:** Stripe Dashboard / Radar Aesthetic (High-Precision Monochrome, Midnight Navy `#0A2540`, Stripe Royal Iris `#635BFF` / `#0048E5`, and Clinical Elevation)

---

## 1. Design Philosophy

Synaptix is not an ordinary dashboard—it is a **statutory legal metrology enforcement engine**. It inspects consumer packaged goods (FMCG, foods, cosmetics, electronics) for mandatory declarations under the **Legal Metrology (Packaged Commodities) Rules, 2011**.

Inspired by **Stripe's world-renowned dashboard and radar design**, this design system achieves three critical objectives:
1. **Financial-Grade Authority:** Replacing generic gray and green prototypes with Stripe's signature **Midnight Navy (`#0A2540`)**, **Cool Slate Canvas (`#F6F9FC`)**, and **Stripe Royal Iris / Cobalt (`#635BFF` / `#0048E5`)**.
2. **Zero Semantic Collision:** Primary UI actions and system controls belong exclusively to the **Stripe Royal Blue** spectrum. The statutory verdicts (**PASS**, **FAIL**, **REVIEW**) remain strictly isolated in dedicated Emerald, Ruby, and Amber tones.
3. **Frictionless Scannability:** High data-density inspection tables and computer vision bounding box overlays are framed with micro-borders and soft ambient shadows to prevent cognitive fatigue during multi-hour inspection shifts.

---

## 2. Color System & Design Tokens

### A. Core Primitives

```
CANVAS (Light)      : #F6F9FC (Stripe Cool Slate)
SURFACE (Light)     : #FFFFFF (Pure Crisp White)
PRIMARY INK         : #0A2540 (Stripe Deep Midnight Navy)
SECONDARY INK       : #425466 (Stripe Slate Muted)
TERTIARY INK        : #8898AA (Stripe Muted Label)
BORDER & DIVIDER    : #E3E8EE (Stripe Hairline Gray)

STRIPE ROYAL IRIS   : #635BFF (Interactive Primary)
STRIPE DEEP BLUE    : #0048E5 (High-Contrast Button Primary)
IRIS SUBTLE         : #F4F5FE (Active Nav & Badges)

CANVAS (Dark)       : #0A101D (Deep Space Obsidian)
SURFACE (Dark)      : #131E33 (Stripe Midnight Slate Surface)
SURFACE RAISED      : #1A2744 (Elevated Modals / Flyouts)
PRIMARY INK (Dark)  : #F8FAFC (Clean White)
SECONDARY INK (Dark): #94A3B8 (Cool Slate Muted)
```

---

### B. Color Tokens: Light Mode ("Clinical Daylight")

| Token Name | Hex Code | Role & Usage | WCAG Ratio |
|---|---|---|---|
| `--bg-canvas` | `#F6F9FC` | Entire viewport background. Soft, glare-free | N/A |
| `--bg-surface` | `#FFFFFF` | Metric cards, inspection panels, tables | N/A |
| `--bg-surface-hover` | `#F8FAFC` | Table row hover, list item hover | N/A |
| `--ink-primary` | `#0A2540` | Main headings, SKU names, metric numbers | **15.4:1** (AAA) |
| `--ink-secondary` | `#425466` | Form labels, descriptions, subheadings | **7.4:1** (AAA) |
| `--ink-tertiary` | `#8898AA` | Timestamps, table column headers, metadata | **4.6:1** (AA) |
| `--line` | `#E3E8EE` | 1px card borders, table dividers | N/A |
| `--line-subtle` | `#EDF2F7` | Inner cell dividers, secondary separators | N/A |
| **`--primary`** | **`#635BFF`** | Primary buttons, active sidebar pills, tabs | **4.8:1** (AA) |
| `--primary-dark` | `#0048E5` | High-emphasis actions, focused input rings | **8.6:1** (AAA) |
| `--primary-subtle` | `#F4F5FE` | Active sidebar item background, rule badges | N/A |
| `--primary-border` | `#D6D7FE` | Active border highlights | N/A |

---

### C. Color Tokens: Dark Mode ("Stealth Midnight")

| Token Name | Hex Code | Role & Usage | WCAG Ratio |
|---|---|---|---|
| `--bg-canvas` | `#0A101D` | Deep obsidian background with midnight undertone | N/A |
| `--bg-surface` | `#131E33` | Elevated inspection panels and metric cards | N/A |
| `--bg-surface-hover` | `#1B2A47` | Interactive card and row hover states | N/A |
| `--ink-primary` | `#F8FAFC` | Headings, inspection IDs, data figures | **16.1:1** (AAA) |
| `--ink-secondary` | `#94A3B8` | Descriptions, metadata, secondary stats | **6.8:1** (AAA) |
| `--ink-tertiary` | `#64748B` | Table headers, monospace timestamps | **4.5:1** (AA) |
| `--line` | `rgba(255, 255, 255, 0.08)` | 1px precision panel border | N/A |
| `--line-subtle` | `rgba(255, 255, 255, 0.04)` | Micro-dividers | N/A |
| **`--primary`** | **`#7A73FF`** | Luminous Stripe Iris for dark backgrounds | **5.4:1** (AA) |
| `--primary-hover` | `#9B95FF` | Active button hover state | N/A |
| `--primary-subtle` | `rgba(99, 91, 255, 0.14)` | Ambient active pills, glowing chip background | N/A |
| `--primary-border` | `rgba(99, 91, 255, 0.32)` | Active tab & badge borders | N/A |

---

### D. Statutory Legal Metrology Verdict Colors (Isolated)

> **Architectural Law:** Never blend brand Blue with statutory verdicts. Rule verdicts are strictly reserved:

```
┌────────────────────────────────────────────────────────────────────────┐
│ PASS (Rule Compliant)                                                  │
│   Light: Text #0E6245 | Bg #CBF4C9 | Border #A3E6B2                    │
│   Dark : Text #4ADE80 | Bg rgba(74, 222, 128, 0.12) | Border #22C55E   │
│   Usage: Mandated declarations present & above minimum font size       │
├────────────────────────────────────────────────────────────────────────┤
│ FAIL (Statutory Violation)                                             │
│   Light: Text #DF1B41 | Bg #FDE8E8 | Border #F8B4B4                    │
│   Dark : Text #F87171 | Bg rgba(223, 27, 65, 0.15) | Border #EF4444    │
│   Usage: Missing MRP, font height < 2mm, absent manufacturer address   │
├────────────────────────────────────────────────────────────────────────┤
│ REVIEW (Manual Verification Required)                                  │
│   Light: Text #8B5704 | Bg #FFF3D6 | Border #FDE199                    │
│   Dark : Text #FBBF24 | Bg rgba(251, 191, 36, 0.12) | Border #F59E0B   │
│   Usage: OCR low confidence (<0.75), skew/glare, borderline font height│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Elevation & Shadow Model (Stripe Multi-Layer Depth)

Stripe’s interface feels premium because it uses **ambient double-layer shadows** combined with **subtle 1px micro-borders**:

```css
/* Stripe Multi-Layer Shadows */
--shadow-sm: 0 1px 3px 0 rgba(50, 50, 93, 0.08), 0 1px 2px 0 rgba(0, 0, 0, 0.04);
--shadow-card: 0 2px 5px -1px rgba(50, 50, 93, 0.12), 0 1px 3px -1px rgba(0, 0, 0, 0.08);
--shadow-raised: 0 13px 27px -5px rgba(50, 50, 93, 0.16), 0 8px 16px -8px rgba(0, 0, 0, 0.12);
--shadow-button: 0 2px 4px rgba(99, 91, 255, 0.2), 0 1px 2px rgba(0, 0, 0, 0.08);
```

In Dark Mode, box-shadows shift to **luminescent edge highlights**:
```css
--shadow-card-dark: 0 0 0 1px rgba(255, 255, 255, 0.07), 0 8px 24px -4px rgba(0, 0, 0, 0.6);
```

---

## 4. Typography System

### Font Stacks
* **Primary UI & Headings:** `'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
* **Monospace Data & Rule Citations:** `'JetBrains Mono', 'DM Mono', SFMono-Regular, monospace`

### Typographic Hierarchy

| Level | Size | Weight | Line Height | Tracking | Token Usage |
|---|---|---|---|---|---|
| **Display 1** | `28px` | `700` | `1.15` | `-0.8px` | Page Titles (`Inspection Hub`) |
| **Section H2** | `18px` | `600` | `1.25` | `-0.4px` | Panel Titles (`Recent Inspections`) |
| **Card H3** | `14px` | `600` | `1.30` | `-0.2px` | Card Subtitles, Section Headers |
| **Body Primary** | `13px` | `500` | `1.50` | `normal` | Product names, Rule explanations |
| **Body Secondary** | `12px` | `400` | `1.45` | `normal` | Timestamps, inspector notes |
| **Mono Small** | `11px` | `500` | `1.30` | `0.04em` | Batch IDs, Rule 6(1)(a) badges |
| **Eyebrow** | `10px` | `700` | `1.20` | `0.10em` | Uppercase category labels |

> **Crucial Rule:** All numeric measurements (`Net Wt: 500g`, `₹ 120.00`, `98.4%`) must use CSS `font-variant-numeric: tabular-nums;` to prevent layout shift during live updates.

---

## 5. Key Component Specifications

### 1. The Stripe-Style Metric KPI Card
* **Background:** `--bg-surface` (`#FFFFFF` in light, `#131E33` in dark)
* **Border:** `1px solid var(--line)`
* **Corner Radius:** `8px`
* **Padding:** `20px 22px`
* **Shadow:** `var(--shadow-card)`
* **Hover:** Subtle `-1px` transform with enhanced shadow
* **Value Format:**
  * Label: `11px` bold uppercase `--ink-secondary`
  * Number: `28px` bold `--ink-primary` with `letter-spacing: -0.8px`
  * Trend / Context Pill: Subtle background with green/red indicator text

### 2. The Inspection Data Table
* **Structure:** Zero vertical column dividers; only clean horizontal borders (`1px solid var(--line)`).
* **Header:** Sticky top, `background: var(--bg-surface)`, text in `--ink-tertiary`, `font-size: 10px`, uppercase with `letter-spacing: 0.08em`.
* **Row Height:** `52px` vertical comfort padding.
* **Row Hover:** Smooth transition to `--bg-surface-hover` (`120ms ease`).
* **Status Badges:** Rounded pill (`border-radius: 20px`), `padding: 4px 10px`, `font-size: 11px`, `font-weight: 600`.

### 3. Visual Inspection Panel (Computer Vision Overlays)
* **Canvas Frame:** Clean neutral charcoal frame (`#0A101D`) to maximize contrast against FMCG packaging photos.
* **Bounding Boxes:**
  * *Compliant Detection (e.g., MRP present):* `1.5px solid #635BFF` (Stripe Iris) or `#22C55E` with subtle glow.
  * *Violation Detection (e.g., Font < 2mm):* `2px solid #DF1B41` (Stripe Ruby Red) with alert tooltip.
* **Badge Callouts:** Semi-translucent glass tags (`backdrop-filter: blur(8px)`) showing confidence scores (`99.2%`).

### 4. Primary & Secondary Buttons
* **Primary Button:**
  * Background: `linear-gradient(180deg, #635BFF 0%, #4B42FE 100%)`
  * Text: `#FFFFFF`, `font-weight: 600`, `font-size: 12px`
  * Border: `1px solid rgba(0, 0, 0, 0.12)`
  * Shadow: `0 1px 2px rgba(0,0,0,0.12), inset 0 1px 0 rgba(255,255,255,0.2)`
* **Secondary Button:**
  * Background: `#FFFFFF`
  * Text: `--ink-primary` (`#0A2540`)
  * Border: `1px solid var(--line)`
  * Shadow: `var(--shadow-sm)`

---

## 6. Complete CSS Token Drop-in File (`styles.css`)

```css
/* ==========================================================================
   Synaptix — Stripe Inspired Design System Tokens
   ========================================================================== */

:root {
  /* Surface & Canvas */
  --bg-canvas: #F6F9FC;
  --bg-surface: #FFFFFF;
  --bg-surface-raised: #FFFFFF;
  --bg-surface-hover: #F8FAFC;

  /* Typography */
  --ink-primary: #0A2540;
  --ink-secondary: #425466;
  --ink-tertiary: #8898AA;

  /* Lines & Borders */
  --line: #E3E8EE;
  --line-subtle: #EDF2F7;

  /* Stripe Royal Iris (Primary Brand Accent) */
  --primary: #635BFF;
  --primary-hover: #534AE6;
  --primary-dark: #0048E5;
  --primary-subtle: #F4F5FE;
  --primary-border: #D6D7FE;
  --primary-glow: rgba(99, 91, 255, 0.18);

  /* Legal Metrology Status Tokens (Isolated) */
  --pass: #0E6245;
  --pass-subtle: #CBF4C9;
  --pass-border: #A3E6B2;

  --fail: #DF1B41;
  --fail-subtle: #FDE8E8;
  --fail-border: #F8B4B4;

  --review: #8B5704;
  --review-subtle: #FFF3D6;
  --review-border: #FDE199;

  /* Stripe Double-Layer Shadows */
  --shadow-sm: 0 1px 3px 0 rgba(50, 50, 93, 0.08), 0 1px 2px 0 rgba(0, 0, 0, 0.04);
  --shadow-card: 0 2px 5px -1px rgba(50, 50, 93, 0.12), 0 1px 3px -1px rgba(0, 0, 0, 0.08);
  --shadow-raised: 0 13px 27px -5px rgba(50, 50, 93, 0.16), 0 8px 16px -8px rgba(0, 0, 0, 0.12);
  --shadow-button: 0 2px 4px rgba(99, 91, 255, 0.2), 0 1px 2px rgba(0, 0, 0, 0.08);

  /* Radii */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-pill: 9999px;
}

:root[data-theme='dark'] {
  /* Surface & Canvas (Stealth Midnight) */
  --bg-canvas: #0A101D;
  --bg-surface: #131E33;
  --bg-surface-raised: #1A2744;
  --bg-surface-hover: #1B2A47;

  /* Typography */
  --ink-primary: #F8FAFC;
  --ink-secondary: #94A3B8;
  --ink-tertiary: #64748B;

  /* Lines & Borders */
  --line: rgba(255, 255, 255, 0.08);
  --line-subtle: rgba(255, 255, 255, 0.04);

  /* Luminous Electric Iris */
  --primary: #7A73FF;
  --primary-hover: #9B95FF;
  --primary-dark: #635BFF;
  --primary-subtle: rgba(99, 91, 255, 0.14);
  --primary-border: rgba(99, 91, 255, 0.32);
  --primary-glow: rgba(99, 91, 255, 0.28);

  /* Legal Metrology Status Tokens (Isolated Dark Mode) */
  --pass: #4ADE80;
  --pass-subtle: rgba(74, 222, 128, 0.12);
  --pass-border: rgba(74, 222, 128, 0.25);

  --fail: #F87171;
  --fail-subtle: rgba(223, 27, 65, 0.16);
  --fail-border: rgba(223, 27, 65, 0.30);

  --review: #FBBF24;
  --review-subtle: rgba(251, 191, 36, 0.12);
  --review-border: rgba(251, 191, 36, 0.25);

  /* Dark Elevation Shadows */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.5);
  --shadow-card: 0 0 0 1px rgba(255, 255, 255, 0.07), 0 8px 24px -4px rgba(0, 0, 0, 0.6);
  --shadow-raised: 0 0 0 1px rgba(255, 255, 255, 0.1), 0 16px 36px -6px rgba(0, 0, 0, 0.75);
  --shadow-button: 0 2px 6px rgba(122, 115, 255, 0.3);
}
```

---

## 7. Implementation Checklist for Frontend Engineers

1. **Token Migration:** Ensure all hardcoded hex values in `frontend/src/styles.css` are mapped to `var(--primary)`, `var(--ink-primary)`, and `var(--bg-canvas)`.
2. **Typography Font Features:** Add `font-variant-numeric: tabular-nums` to `.metric-copy strong`, `td`, and `.stat-value` elements.
3. **Status Isolation Verification:** Verify that rule verdicts (`PASS`, `FAIL`, `REVIEW`) only inherit `--pass`, `--fail`, and `--review` and never the `--primary` Iris blue.
4. **Elevation QA:** Ensure cards in dark mode use subtle borders (`1px solid var(--line)`) rather than heavy dropshadows to preserve clarity.
5. **Theme Changing Transitions:** Maintain the dual-layer transition engine (`cubic-bezier(0.4, 0, 0.2, 1)` over `0.30s` on structural containers and `html.theme-transitioning` for global interpolation during toggle), ensuring `prefers-reduced-motion` accessibility is strictly respected.
