"""Design tokens, typography, and CSS styling for the RippleMap dashboard."""

# Core Palette Tokens
COLOR_BG_DARK = "#0B1120"
COLOR_SURFACE = "#162032"
COLOR_SURFACE_ELEVATED = "#1E293B"
COLOR_BORDER = "#334155"
COLOR_TEXT_PRIMARY = "#F8FAFC"
COLOR_TEXT_MUTED = "#94A3B8"

# Accents
COLOR_CYAN = "#06B6D4"
COLOR_TEAL = "#14B8A6"
COLOR_AMBER = "#F59E0B"
COLOR_CRIMSON = "#EF4444"
COLOR_EMERALD = "#10B981"
COLOR_PURPLE = "#8B5CF6"


CUSTOM_CSS = f"""
<style>
/* Global resets & typography */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}}

code, pre, .mono {{
    font-family: 'JetBrains Mono', monospace;
}}

/* Main container spacing */
.main .block-container {{
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 1400px;
}}

/* Header Banner */
.rm-header {{
    background: linear-gradient(135deg, rgba(6, 182, 212, 0.12) 0%, rgba(15, 23, 42, 0.6) 100%);
    border: 1px solid rgba(6, 182, 212, 0.25);
    border-radius: 12px;
    padding: 1.25rem 1.75rem;
    margin-bottom: 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

.rm-header-title {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}}

.rm-header-subtitle {{
    color: {COLOR_TEXT_MUTED};
    font-size: 0.875rem;
    margin-top: 0.25rem;
}}

/* Metric Cards */
.rm-metric-card {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 1rem 1.25rem;
    transition: transform 0.15s ease, border-color 0.15s ease;
    height: 100%;
}}

.rm-metric-card:hover {{
    border-color: {COLOR_CYAN};
}}

.rm-metric-label {{
    color: {COLOR_TEXT_MUTED};
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.25rem;
}}

.rm-metric-value {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 1.6rem;
    font-weight: 700;
    line-height: 1.2;
}}

.rm-metric-sub {{
    color: {COLOR_CYAN};
    font-size: 0.8rem;
    font-weight: 500;
    margin-top: 0.35rem;
}}

/* Badges and Chips */
.rm-badge {{
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.55rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    line-height: 1;
}}

.rm-badge-cyan {{
    background-color: rgba(6, 182, 212, 0.15);
    color: #38BDF8;
    border: 1px solid rgba(6, 182, 212, 0.3);
}}

.rm-badge-amber {{
    background-color: rgba(245, 158, 11, 0.15);
    color: #FBBF24;
    border: 1px solid rgba(245, 158, 11, 0.3);
}}

.rm-badge-crimson {{
    background-color: rgba(239, 68, 68, 0.15);
    color: #F87171;
    border: 1px solid rgba(239, 68, 68, 0.3);
}}

.rm-badge-emerald {{
    background-color: rgba(16, 185, 129, 0.15);
    color: #34D399;
    border: 1px solid rgba(16, 185, 129, 0.3);
}}

.rm-badge-purple {{
    background-color: rgba(139, 92, 246, 0.15);
    color: #A78BFA;
    border: 1px solid rgba(139, 92, 246, 0.3);
}}

/* Simulation Notice Banner */
.rm-sim-banner {{
    background: rgba(245, 158, 11, 0.08);
    border-left: 4px solid {COLOR_AMBER};
    padding: 0.65rem 1rem;
    border-radius: 4px;
    color: #FCD34D;
    font-size: 0.8rem;
    margin-bottom: 1rem;
}}

/* Surface Card Containers */
.rm-card {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 1rem;
}}

/* Section Titles */
.rm-section-title {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 1.15rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}}

/* Table adjustments */
div[data-testid="stDataFrame"] {{
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid {COLOR_BORDER};
}}
</style>
"""


def render_badge(text: str, variant: str = "cyan") -> str:
    """Generates an HTML badge string with appropriate variant styling."""
    return f'<span class="rm-badge rm-badge-{variant}">{text}</span>'
