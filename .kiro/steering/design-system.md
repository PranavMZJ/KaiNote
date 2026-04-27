---
inclusion: auto
---

# Meeting Minutes App — Design System

This project's frontend follows a premium, Lusion-inspired dark-theme aesthetic. All React/Next.js components must adhere to these design guidelines.

## Design Philosophy

Inspired by [Lusion.co](https://lusion.co/) — a 3D interactive web studio known for bold, immersive, content-forward experiences. The meeting-minutes app adapts this aesthetic for a productivity SaaS context: professional yet visually striking, minimal chrome, generous spacing, and smooth interactions.

## Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `#0A0A0B` | Main background (near-black) |
| `--bg-secondary` | `#111113` | Card/panel backgrounds |
| `--bg-elevated` | `#1A1A1F` | Elevated surfaces, modals |
| `--bg-glass` | `rgba(255, 255, 255, 0.04)` | Glassmorphism panels |
| `--border-subtle` | `rgba(255, 255, 255, 0.08)` | Subtle borders on cards |
| `--border-focus` | `rgba(255, 255, 255, 0.15)` | Focused/hovered borders |
| `--text-primary` | `#F5F5F7` | Primary text (off-white) |
| `--text-secondary` | `#8E8E93` | Secondary/muted text |
| `--text-tertiary` | `#636366` | Tertiary/disabled text |
| `--accent-primary` | `#6C5CE7` | Primary accent (soft purple) |
| `--accent-hover` | `#7C6DF7` | Accent hover state |
| `--accent-glow` | `rgba(108, 92, 231, 0.15)` | Accent glow/shadow |
| `--success` | `#34C759` | Success states |
| `--warning` | `#FF9F0A` | Warning states, needs-review items |
| `--error` | `#FF453A` | Error states, failed status |
| `--recording` | `#FF453A` | Recording indicator (pulsing red) |

## Typography

| Token | Value | Usage |
|-------|-------|-------|
| `--font-display` | `'Inter', system-ui, sans-serif` | Headings, hero text |
| `--font-body` | `'Inter', system-ui, sans-serif` | Body text, UI elements |
| `--font-mono` | `'JetBrains Mono', monospace` | Code, timestamps, JSON |
| `--text-hero` | `clamp(2.5rem, 5vw, 4rem)` | Hero/page titles |
| `--text-h1` | `2rem` / `font-weight: 700` | Section headings |
| `--text-h2` | `1.5rem` / `font-weight: 600` | Sub-section headings |
| `--text-h3` | `1.125rem` / `font-weight: 600` | Card titles |
| `--text-body` | `1rem` / `font-weight: 400` | Body text |
| `--text-small` | `0.875rem` / `font-weight: 400` | Captions, metadata |
| `--text-xs` | `0.75rem` / `font-weight: 500` | Badges, labels |
| `--letter-spacing-tight` | `-0.02em` | Headings |
| `--letter-spacing-wide` | `0.05em` | Uppercase labels |

## Spacing

Use an 8px base grid:

| Token | Value |
|-------|-------|
| `--space-1` | `0.25rem` (4px) |
| `--space-2` | `0.5rem` (8px) |
| `--space-3` | `0.75rem` (12px) |
| `--space-4` | `1rem` (16px) |
| `--space-6` | `1.5rem` (24px) |
| `--space-8` | `2rem` (32px) |
| `--space-12` | `3rem` (48px) |
| `--space-16` | `4rem` (64px) |
| `--space-24` | `6rem` (96px) |

Generous padding on sections (`--space-16` to `--space-24`). Cards use `--space-6` to `--space-8` internal padding.

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | `6px` | Small elements, badges |
| `--radius-md` | `12px` | Buttons, inputs |
| `--radius-lg` | `16px` | Cards, panels |
| `--radius-xl` | `24px` | Modals, large containers |

## Shadows and Effects

```css
/* Glassmorphism panel */
.glass-panel {
  background: var(--bg-glass);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
}

/* Accent glow (buttons, active states) */
.accent-glow {
  box-shadow: 0 0 20px var(--accent-glow), 0 0 60px rgba(108, 92, 231, 0.05);
}

/* Elevated card */
.elevated-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
}

/* Recording pulse */
@keyframes recording-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}
```

## Motion and Transitions

All transitions use smooth easing. No abrupt state changes.

| Token | Value | Usage |
|-------|-------|-------|
| `--ease-out` | `cubic-bezier(0.16, 1, 0.3, 1)` | Default for most transitions |
| `--ease-in-out` | `cubic-bezier(0.65, 0, 0.35, 1)` | Modals, overlays |
| `--duration-fast` | `150ms` | Hover states, small toggles |
| `--duration-normal` | `300ms` | Panel transitions, fades |
| `--duration-slow` | `500ms` | Page transitions, large reveals |

Guidelines:
- Elements fade in with slight upward translate (`translateY(8px)` → `translateY(0)`)
- Buttons scale subtly on hover (`scale(1.02)`)
- Use `will-change: transform, opacity` for animated elements
- Transcript segments slide in from the bottom
- Status changes crossfade smoothly

## Component Patterns

### Buttons

```
Primary: bg accent-primary, text white, radius-md, padding space-3 space-6
         Hover: bg accent-hover, accent-glow shadow, scale(1.02)
         Active: scale(0.98)

Secondary: bg transparent, border border-subtle, text text-primary, radius-md
           Hover: border border-focus, bg bg-glass

Danger: bg transparent, border error at 30% opacity, text error
        Hover: bg error at 10% opacity
```

### Cards (Meeting List Items, Report Sections)

```
bg bg-secondary, border border-subtle, radius-lg, padding space-6
Hover: border border-focus, translateY(-2px), shadow increase
Transition: duration-normal ease-out
```

### Live Transcript Panel

```
bg bg-primary, border-left 2px accent-primary
Segments: fade-in from bottom, space-3 gap
Partial segments: text-tertiary, italic
Final segments: text-primary
Speaker labels: text-xs, uppercase, letter-spacing-wide, accent-primary
Auto-scroll with smooth behavior
```

### Recording Indicator

```
Red dot with recording-pulse animation
Elapsed timer in font-mono
bg bg-elevated with glass effect
Position: fixed or sticky top
```

### Report Renderer

```
Sections separated by border-subtle dividers with space-12 gap
Section headings: text-h2, text-primary, letter-spacing-tight
Decision cards: elevated-card with left border accent-primary
Action items: elevated-card, warning border if needs_human_review
Confidence badge: small pill, color-coded (green ≥0.7, warning <0.7)
Evidence snippets: bg bg-elevated, font-mono, text-small, radius-sm
```

### Status Indicators

```
Pending: text-secondary, subtle pulse
Processing: accent-primary, animated spinner
Completed: success color, checkmark icon
Failed: error color, warning icon with retry button
```

## Accessibility

- Maintain WCAG 2.1 AA contrast ratios (4.5:1 for normal text, 3:1 for large text)
- All interactive elements must have visible focus indicators (accent-primary ring)
- Respect `prefers-reduced-motion` — disable animations when set
- Ensure keyboard navigation works for all interactive elements
- Use semantic HTML and ARIA labels throughout

## Responsive Breakpoints

| Breakpoint | Value | Layout |
|-----------|-------|--------|
| Mobile | `< 640px` | Single column, stacked panels |
| Tablet | `640px – 1024px` | Two-column where appropriate |
| Desktop | `> 1024px` | Full layout with sidebar |

## Do's and Don'ts

**Do:**
- Use generous whitespace — let content breathe
- Keep UI chrome minimal — no heavy borders, no busy backgrounds
- Use the accent color sparingly for emphasis
- Animate state transitions smoothly
- Use glassmorphism for overlays and floating panels

**Don't:**
- Use bright/white backgrounds
- Add decorative borders or heavy box shadows
- Use more than 2 accent colors on a single screen
- Skip transitions between states
- Overcrowd sections — prefer vertical scrolling over cramming
