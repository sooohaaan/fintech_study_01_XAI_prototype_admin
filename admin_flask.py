from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, __version__ as flask_version
from functools import wraps
from collector import DataCollector
from recommendation_logic import recommend_products
import pandas as pd
import sys
import os
from sqlalchemy import text
from datetime import datetime, timedelta
import platform
try:
    import psutil
except ImportError:
    psutil = None
import threading
import schedule
import time

# Flask 앱 초기화
# 정적 파일 경로를 절대 경로로 설정하여 실행 위치에 상관없이 찾을 수 있도록 함
basedir = os.path.abspath(os.path.dirname(__file__))
static_dir = os.path.join(basedir, 'static')
template_dir = os.path.join(basedir, 'templates')
components_dir = os.path.join(template_dir, 'components')

# static 폴더가 없으면 자동 생성 (CSS 파일 경로 문제 방지)
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# templates 폴더가 없으면 자동 생성
if not os.path.exists(template_dir):
    os.makedirs(template_dir)

# templates/components 폴더가 없으면 자동 생성
if not os.path.exists(components_dir):
    os.makedirs(components_dir)

# [Self-Repair] CSS 파일이 없으면 자동 생성 (경로 문제 원천 차단)
style_css_path = os.path.join(static_dir, 'style.css')
login_css_path = os.path.join(static_dir, 'login.css')

# Always overwrite style.css to apply latest improvements
with open(style_css_path, 'w', encoding='utf-8') as f:
    f.write("""/* === Material Design 3 (Material You) Theme === */
:root {
    /* ===== Brand Colors (README Design System) ===== */
    --visionary-black: #000000;
    --pure-white: #FFFFFF;
    --insight-gold: #E5AA70;
    --insight-gold-hover: #D4955D;
    --evidence-grey: #717171; /* README: #8E8E8E → Adjusted for WCAG 2.1 AA (4.5:1 on white) */
    --slate-blue-grey: #4A5568;

    /* ===== Core Tokens (all derived from 5 brand colors) ===== */
    /* Primary: Insight Gold */
    --md-sys-color-primary: var(--insight-gold);
    --md-sys-color-on-primary: var(--visionary-black);
    --md-sys-color-primary-container: #FFF8E1;
    --md-sys-color-on-primary-container: #5C3A00;

    /* Secondary: Slate Blue-Grey */
    --md-sys-color-secondary: var(--slate-blue-grey);
    --md-sys-color-on-secondary: var(--pure-white);
    --md-sys-color-secondary-container: #E2E8F0;
    --md-sys-color-on-secondary-container: #2D3748;

    /* Tertiary: Evidence Grey */
    --md-sys-color-tertiary: var(--evidence-grey);
    --md-sys-color-on-tertiary: var(--pure-white);
    --md-sys-color-tertiary-container: #EBEBEB;
    --md-sys-color-on-tertiary-container: #333333;

    /* Error: Semantic Red (UX safety — not brand-replaceable) */
    --md-sys-color-error: #BA1A1A;
    --md-sys-color-on-error: #FFFFFF;

    /* Surfaces & Backgrounds */
    --md-sys-color-background: #F8F9FA;
    --md-sys-color-on-background: var(--visionary-black);
    --md-sys-color-surface: var(--pure-white);
    --md-sys-color-on-surface: var(--visionary-black);
    --md-sys-color-surface-variant: #F0F0F0;
    --md-sys-color-on-surface-variant: var(--slate-blue-grey);

    /* Outline: Evidence Grey + Slate */
    --md-sys-color-outline: var(--evidence-grey);
    --md-sys-color-outline-variant: #CBD5E1;

    /* ===== Compatibility Aliases ===== */
    --primary: var(--md-sys-color-primary);
    --primary-hover: var(--insight-gold-hover);
    --accent: var(--md-sys-color-primary);
    --accent-hover: var(--insight-gold-hover);
    --text-primary-color: var(--md-sys-color-on-primary-container);

    --bg-page: var(--md-sys-color-background);
    --bg-card: var(--md-sys-color-surface);
    --bg-soft: var(--md-sys-color-surface-variant);
    --bg-input: var(--md-sys-color-surface);

    --text-main: var(--md-sys-color-on-surface);
    --text-sub: var(--md-sys-color-on-surface-variant);
    --text-muted: var(--md-sys-color-outline);

    --border: var(--md-sys-color-outline-variant);
    --border-light: #F0F0F0;
    --th-bg: var(--bg-soft);

    /* Functional Colors (semantic — success/danger kept for UX safety) */
    --success-bg: #E8F5E9; --success-fg: #137333;
    --warning-bg: #FFF8E1; --warning-fg: #B8860B;
    --danger-bg: #FFEBEE;  --danger-fg: #C62828;
    --info-bg: #FEF3E2;    --info-fg: #8D5A18;
    --neutral-bg: #F0F0F0; --neutral-fg: #717171;

    /* Shapes & Shadows */
    --radius-card: 16px;
    --radius-btn: 20px;
    --radius-badge: 8px;
    --radius-input: 4px;
    --radius-dialog: 28px; /* M3 Dialog Standard */

    --shadow-sm: 0px 1px 2px rgba(0,0,0,0.3), 0px 1px 3px 1px rgba(0,0,0,0.15);
    --shadow-md: 0px 1px 2px rgba(0,0,0,0.3), 0px 2px 6px 2px rgba(0,0,0,0.15);

    --transition: all 0.2s cubic-bezier(0.2, 0.0, 0, 1.0);
}
html.dark {
    /* Primary: Insight Gold (stays vibrant on dark) */
    --md-sys-color-primary: #E5AA70;
    --md-sys-color-on-primary: #000000;
    --md-sys-color-primary-container: #5C3A00;
    --md-sys-color-on-primary-container: #FFDDB3;

    /* Secondary: Slate Blue-Grey (lightened for dark bg) */
    --md-sys-color-secondary: #A0AEC0;
    --md-sys-color-on-secondary: #1A202C;
    --md-sys-color-secondary-container: #2D3748;
    --md-sys-color-on-secondary-container: #E2E8F0;

    /* Surfaces & Backgrounds */
    --md-sys-color-background: #121212;
    --md-sys-color-on-background: #E0E0E0;
    --md-sys-color-surface: #1E1E1E;
    --md-sys-color-on-surface: #E0E0E0;
    --md-sys-color-surface-variant: #2D3748;
    --md-sys-color-on-surface-variant: #A0AEC0;

    /* Outline: Evidence Grey for dark */
    --md-sys-color-outline: #717171;
    --md-sys-color-outline-variant: #4A5568;

    /* Compatibility Aliases */
    --primary: var(--md-sys-color-primary);
    --primary-hover: #D4955D;
    --accent: var(--md-sys-color-primary);
    --text-primary-color: var(--md-sys-color-primary);

    --bg-page: var(--md-sys-color-background);
    --bg-card: var(--md-sys-color-surface);
    --bg-soft: #2C2C2C;
    --bg-input: #2C2C2C;

    --text-main: #FFFFFF;
    --text-sub: #A0AEC0;
    --text-muted: #717171;

    --border: #333333;
    --border-light: #333333;
    --th-bg: #2C2C2C;

    --shadow-sm: 0px 1px 3px 1px rgba(0,0,0,0.15), 0px 1px 2px 0px rgba(0,0,0,0.3);
    --shadow-md: 0px 2px 6px 2px rgba(0,0,0,0.15), 0px 1px 2px 0px rgba(0,0,0,0.3);
}
/* Narrative Grid: dark mode uses white lines instead of black */
html.dark body {
    background-image: linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
}

/* === Base === */
body { 
    font-family: "Roboto", "Pretendard", "Inter", -apple-system, BlinkMacSystemFont, system-ui, sans-serif; 
    background-color: var(--bg-page); 
    /* The Narrative Grid: Subtle grid pattern for logical structure */
    background-image: linear-gradient(to right, rgba(0, 0, 0, 0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(0, 0, 0, 0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    color: var(--text-main); margin: 0; padding: 0; letter-spacing: 0.01em; -webkit-font-smoothing: antialiased; transition: background-color 0.3s, color 0.3s; line-height: 1.5; }
h1 { color: var(--text-main); font-size: 1.75rem; font-weight: 400; margin: 0 0 1.5rem 0; letter-spacing: 0; }

/* === Layout: Sidebar & Main === */
.app-container { display: flex; min-height: 100vh; }

/* Sidebar */
.sidebar { width: 280px; background: var(--bg-card); border-right: none; display: flex; flex-direction: column; position: fixed; top: 0; bottom: 0; left: 0; z-index: 50; transition: transform 0.3s ease; padding-right: 12px; }
/* The Precision Star: Highlight brand identity in header */
.sidebar-header { padding: 1.5rem 1.5rem 1rem 1.5rem; display: flex; align-items: center; gap: 12px; }
.sidebar-header h2 { font-size: 1.25rem; font-weight: 500; color: var(--text-main); margin: 0; }

.sidebar-nav { flex: 1; overflow-y: auto; padding: 1rem; }
.nav-section { font-size: 0.75rem; font-weight: 500; color: var(--text-sub); margin: 1.5rem 0 0.5rem 1rem; }
.nav-section:first-child { margin-top: 0; }

.nav-item { display: flex; align-items: center; padding: 0 16px; height: 56px; color: var(--text-sub); text-decoration: none; border-radius: 28px; font-weight: 500; margin-bottom: 4px; transition: var(--transition); font-size: 0.9rem; gap: 12px; }
.nav-icon { width: 24px; height: 24px; stroke-width: 2; stroke: currentColor; fill: none; stroke-linecap: round; stroke-linejoin: round; opacity: 0.8; }
.nav-item:hover { background-color: var(--bg-soft); color: var(--text-main); }
.nav-item.active { background-color: var(--md-sys-color-secondary-container); color: var(--md-sys-color-on-secondary-container); font-weight: 600; }
.nav-item.active .nav-icon { opacity: 1; stroke: var(--md-sys-color-on-secondary-container); }

.sidebar-footer { padding: 1rem; border-top: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; gap: 8px; }

/* Main Content */
.main-content { flex: 1; margin-left: 280px; padding: 2rem; max-width: 100%; box-sizing: border-box; transition: margin-left 0.3s ease; }
.top-bar { display: flex; justify-content: flex-end; align-items: center; margin-bottom: 1.5rem; height: 40px; gap: 1rem; }

/* Mobile Responsive Header */
.mobile-header { display: none; padding: 1rem; background: var(--bg-card); border-bottom: 1px solid var(--border); align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 40; }
.mobile-toggle { background: transparent; border: none; font-size: 1.5rem; cursor: pointer; color: var(--text-main); padding: 0.25rem; display: flex; align-items: center; justify-content: center; }
.overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 45; backdrop-filter: blur(2px); }

/* === Components === */
.theme-toggle { padding: 8px; background: transparent; border: 1px solid var(--border); border-radius: 8px; cursor: pointer; font-size: 1.1rem; line-height: 1; transition: var(--transition); color: var(--text-sub); display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; }
.theme-toggle:hover { background: var(--bg-soft); color: var(--text-main); border-color: var(--text-muted); }
.nav-btn { padding: 0 24px; height: 40px; text-decoration: none; border-radius: 20px; font-size: 0.875rem; font-weight: 500; transition: var(--transition); background-color: transparent; color: var(--text-primary-color); border: 1px solid var(--border); display: inline-flex; align-items: center; gap: 8px; }
.nav-btn:hover { background-color: var(--bg-soft); color: var(--text-main); border-color: var(--text-muted); }
.nav-btn.active { background-color: var(--primary); color: var(--md-sys-color-on-primary); border-color: var(--primary); }

/* Notification Badge */
.notification-btn { position: relative; display: flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 50%; color: var(--text-sub); transition: var(--transition); text-decoration: none; }
.notification-btn:hover { background-color: var(--bg-soft); color: var(--text-main); }
.notification-badge { position: absolute; top: 4px; right: 4px; background-color: var(--md-sys-color-error); color: var(--md-sys-color-on-error); font-size: 0.7rem; font-weight: 700; min-width: 16px; height: 16px; border-radius: 8px; display: flex; align-items: center; justify-content: center; padding: 0 4px; box-sizing: border-box; border: 2px solid var(--bg-card); line-height: 1; }

/* === Dashboard & Cards === */
.dashboard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1.5rem; }
.card { background: var(--bg-card); border-radius: var(--radius-card); box-shadow: none; border: 1px solid var(--border); overflow: hidden; display: flex; flex-direction: column; transition: var(--transition); position: relative; }
.card:hover { box-shadow: var(--shadow-md); transform: translateY(-2px); }
.card-header { padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--border-light); display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; background-color: var(--bg-card); }
.card-title-group { display: flex; flex-direction: column; gap: 0.25rem; }
.card-title { font-size: 1rem; font-weight: 500; color: var(--text-main); margin: 0; }
.last-run { font-size: 0.75rem; color: var(--text-muted); font-weight: 500; }
.card-actions { display: flex; align-items: center; gap: 8px; }
.refresh-btn { padding: 6px 12px; background-color: transparent; color: var(--text-primary-color); border: 1px solid var(--text-primary-color); border-radius: 6px; font-size: 0.75rem; font-weight: 600; cursor: pointer; transition: var(--transition); white-space: nowrap; }
.refresh-btn:hover { background-color: var(--primary); color: var(--md-sys-color-on-primary); }
.card-body { padding: 0; flex-grow: 1; display: flex; flex-direction: column; }
.card-p { padding: 1.5rem; }

/* === Alerts & Badges === */
.alert { padding: 1rem; margin-bottom: 1.5rem; border-radius: var(--radius-btn); font-size: 0.9rem; font-weight: 500; display: flex; align-items: center; gap: 10px; }
.success { background-color: var(--success-bg); color: var(--success-fg); border: 1px solid rgba(5, 150, 105, 0.2); }
.error { background-color: var(--danger-bg); color: var(--danger-fg); border: 1px solid rgba(220, 38, 38, 0.2); }
.warning { background-color: var(--warning-bg); color: var(--warning-fg); border: 1px solid rgba(217, 119, 6, 0.2); }

/* === Tables & Logs === */
.log-table-container { overflow-x: auto; max-height: 400px; overflow-y: auto; }
table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.875rem; }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--border-light); }
th { background-color: var(--th-bg); color: var(--text-sub); font-weight: 600; position: sticky; top: 0; z-index: 10; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
td { color: var(--text-main); }
tbody tr { transition: background-color 0.15s; }
tbody tr:hover { background-color: var(--bg-soft); }
th.text-right, td.text-right { text-align: right; }
th.text-center, td.text-center { text-align: center; }
.table-wrapper { overflow-x: auto; background: var(--bg-card); border-radius: var(--radius-card); box-shadow: none; border: 1px solid var(--border); }

/* === Status Indicators === */
.badge { padding: 4px 10px; border-radius: var(--radius-badge); font-size: 0.75rem; font-weight: 600; display: inline-flex; align-items: center; gap: 4px; line-height: 1; }
.badge-success { background: var(--success-bg); color: var(--success-fg); }
.badge-warning { background: var(--warning-bg); color: var(--warning-fg); }
.badge-danger { background: var(--danger-bg); color: var(--danger-fg); }
.badge-info { background: var(--info-bg); color: var(--info-fg); }
.badge-neutral { background: var(--neutral-bg); color: var(--neutral-fg); }
.badge-on { background: var(--success-bg); color: var(--success-fg); padding: 4px 12px; border-radius: var(--radius-btn); font-size: 0.75rem; font-weight: 700; }
.badge-off { background: var(--neutral-bg); color: var(--neutral-fg); padding: 4px 12px; border-radius: var(--radius-btn); font-size: 0.75rem; font-weight: 700; }
.badge-lg { padding: 6px 16px; font-size: 0.85rem; }

/* === Summary & Banners === */
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
.summary-card { background: var(--bg-card); padding: 1.5rem; border-radius: var(--radius-card); box-shadow: none; border: 1px solid var(--border); display: flex; flex-direction: column; align-items: center; justify-content: center; transition: var(--transition); }
.summary-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.summary-value { font-size: 2rem; font-weight: 800; color: var(--text-main); margin: 0.5rem 0; line-height: 1; }
.summary-label { color: var(--text-sub); font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
.help-text { font-size: 0.8rem; color: var(--text-muted); margin: 6px 0 0 0; line-height: 1.4; }
.info-banner { background: var(--info-bg); border: 1px solid rgba(229, 170, 112, 0.3); border-radius: var(--radius-btn); padding: 1rem; color: var(--text-primary-color); font-size: 0.9rem; margin-bottom: 1.5rem; line-height: 1.5; display: flex; gap: 12px; align-items: flex-start; }
.warn-banner { background: var(--warning-bg); border: 1px solid rgba(245, 158, 11, 0.2); border-radius: var(--radius-btn); padding: 1rem; color: var(--warning-fg); font-size: 0.9rem; margin-bottom: 1rem; line-height: 1.5; }

/* === Forms & Buttons === */
input, select, textarea { background: transparent; color: var(--text-main); border: 1px solid var(--md-sys-color-outline); border-radius: 4px; transition: var(--transition); font-family: inherit; height: 56px; padding: 0 16px; }
input:focus, select:focus, textarea:focus { border-color: var(--primary); border-width: 2px; outline: none; padding: 0 15px; }
/* Button Base */
.btn { display: inline-flex; align-items: center; justify-content: center; padding: 0 24px; height: 40px; border-radius: 20px; font-weight: 500; font-size: 0.875rem; letter-spacing: 0.1px; transition: var(--transition); text-decoration: none; border: none; cursor: pointer; white-space: nowrap; }
button { display: inline-flex; align-items: center; justify-content: center; padding: 0 24px; height: 40px; border: none; border-radius: 20px; background-color: var(--primary); color: var(--md-sys-color-on-primary); font-weight: 500; cursor: pointer; transition: var(--transition); font-size: 0.875rem; letter-spacing: 0.1px; }
button:hover, .btn-primary:hover { background-color: var(--primary-hover); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
button:disabled, button[disabled] { opacity: 0.38; cursor: not-allowed; pointer-events: none; }
button:disabled:hover, button[disabled]:hover { transform: none; box-shadow: none; background-color: var(--primary); }
.btn-primary { background-color: var(--primary); color: var(--md-sys-color-on-primary); }
/* Slider (Range) */
.btn-sm { height: 32px; padding: 0 16px; font-size: 0.8rem; }
input[type=range] { -webkit-appearance: none; width: 100%; background: transparent; height: 44px; padding: 0; border: none; margin: 0; }
input[type=range]:focus { outline: none; border: none; padding: 0; }
/* Webkit */
input[type=range]::-webkit-slider-runnable-track { width: 100%; height: 4px; cursor: pointer; background: var(--md-sys-color-surface-variant); border-radius: 2px; }
input[type=range]::-webkit-slider-thumb { height: 20px; width: 20px; border-radius: 50%; background: var(--primary); cursor: pointer; -webkit-appearance: none; margin-top: -8px; box-shadow: var(--shadow-sm); transition: transform 0.1s, box-shadow 0.2s; }
input[type=range]:focus::-webkit-slider-thumb { box-shadow: 0 0 0 8px rgba(229, 170, 112, 0.2); }
input[type=range]::-webkit-slider-thumb:hover { transform: scale(1.2); box-shadow: 0 0 0 6px rgba(229, 170, 112, 0.1); }
/* Firefox */
input[type=range]::-moz-range-track { width: 100%; height: 4px; cursor: pointer; background: var(--md-sys-color-surface-variant); border-radius: 2px; }
input[type=range]::-moz-range-thumb { height: 20px; width: 20px; border: none; border-radius: 50%; background: var(--primary); cursor: pointer; box-shadow: var(--shadow-sm); transition: transform 0.1s, box-shadow 0.2s; }
input[type=range]:focus::-moz-range-thumb { box-shadow: 0 0 0 8px rgba(229, 170, 112, 0.2); }
input[type=range]::-moz-range-thumb:hover { transform: scale(1.2); box-shadow: 0 0 0 6px rgba(229, 170, 112, 0.1); }
.btn-accent { background-color: var(--accent); color: var(--md-sys-color-on-primary); display: inline-flex; align-items: center; justify-content: center; padding: 0 24px; height: 40px; border-radius: 20px; font-weight: 500; font-size: 0.875rem; transition: var(--transition); text-decoration: none; border: none; cursor: pointer; }
.btn-accent:hover { background-color: var(--accent-hover); transform: translateY(-1px); box-shadow: var(--shadow-md); }
.btn-tonal { background-color: var(--md-sys-color-secondary-container); color: var(--md-sys-color-on-secondary-container); }
.btn-tonal:hover { background-color: var(--md-sys-color-secondary); color: var(--md-sys-color-on-secondary); box-shadow: var(--shadow-sm); }
.btn-icon { padding: 8px; background-color: transparent; color: var(--text-sub); border: 1px solid transparent; border-radius: 8px; cursor: pointer; transition: var(--transition); display: inline-flex; align-items: center; justify-content: center; }
.btn-icon:hover { background-color: var(--bg-card); color: var(--text-primary-color); box-shadow: var(--shadow-sm); }
.btn-outline-danger { padding: 6px 14px; background: transparent; color: var(--danger-fg); border: 1px solid var(--danger-fg); border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.85rem; }
.btn-outline-danger:hover { background: var(--danger-bg); }
.btn-outline-success { padding: 6px 14px; background: transparent; color: var(--success-fg); border: 1px solid var(--success-fg); border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.85rem; }
.btn-outline-success:hover { background: var(--success-bg); }
/* Password Toggle Icon */
.password-toggle-icon { transition: color 0.2s ease; }
.password-toggle-icon:hover { color: var(--text-primary-color); }
.form-inline { margin: 0; }
.form-group { margin-bottom: 1.25rem; }
.form-label { display: block; font-weight: 500; margin-bottom: 0.5rem; color: var(--text-main); font-size: 0.875rem; }
.form-input, .form-select, .form-textarea { width: 100%; box-sizing: border-box; }
.form-textarea { resize: vertical; min-height: 100px; }

/* Radio Chips */
.radio-group { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.radio-chip { position: relative; }
.radio-chip input { position: absolute; opacity: 0; width: 0; height: 0; }
.radio-chip span { display: inline-block; padding: 6px 12px; background: var(--bg-input); border: 1px solid var(--border); border-radius: 20px; font-size: 0.8rem; color: var(--text-sub); cursor: pointer; transition: all 0.2s; }
.radio-chip input:checked + span { background: var(--primary); color: white; border-color: var(--primary); font-weight: 600; }
.radio-chip span:hover { border-color: var(--primary); }

/* Toggle Switch */
.toggle-switch { position: relative; display: inline-block; width: 52px; height: 32px; vertical-align: middle; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: var(--md-sys-color-surface-variant); border: 2px solid var(--md-sys-color-outline); border-radius: 100px; transition: all 0.2s cubic-bezier(0.2, 0.0, 0, 1.0); }
.slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 8px; bottom: 8px; background-color: var(--md-sys-color-outline); border-radius: 50%; transition: all 0.2s cubic-bezier(0.2, 0.0, 0, 1.0); }
/* Checked State (M3) */
input:checked + .slider { background-color: var(--md-sys-color-primary); border-color: var(--md-sys-color-primary); }
input:checked + .slider:before { transform: translateX(12px); width: 24px; height: 24px; bottom: 4px; background-color: var(--md-sys-color-on-primary); }
/* Hover State */
.toggle-switch:hover .slider:before { background-color: var(--md-sys-color-on-surface-variant); }
input:checked:hover + .slider:before { background-color: var(--md-sys-color-primary-container); }

/* Progress Bar */
.progress-track { background-color: var(--border-light); border-radius: 8px; height: 20px; overflow: hidden; width: 100%; }
.progress-fill { background-color: var(--primary); height: 100%; border-radius: var(--radius-btn); transition: width 0.3s ease; min-width: 2px; }

/* === System Status Bar === */
.system-status-bar { display: flex; gap: 1.5rem; background: var(--bg-card); padding: 0.75rem 1.5rem; border-radius: var(--radius-card); border: 1px solid var(--border); margin-bottom: 2rem; align-items: center; flex-wrap: wrap; box-shadow: none; }
.status-item { display: flex; align-items: center; gap: 10px; font-size: 0.85rem; text-decoration: none; color: inherit; padding: 4px 8px; border-radius: 6px; transition: var(--transition); }
.status-item:hover { background-color: var(--bg-soft); }
.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.dot-success { background-color: var(--success-fg); box-shadow: 0 0 0 2px var(--success-bg); }
.dot-danger { background-color: var(--danger-fg); box-shadow: 0 0 0 2px var(--danger-bg); }
.dot-warning { background-color: var(--warning-fg); box-shadow: 0 0 0 2px var(--warning-bg); }
.dot-info { background-color: var(--primary); box-shadow: 0 0 0 2px rgba(229, 170, 112, 0.4); }
.status-label { font-weight: 600; color: var(--text-sub); }
.status-value { font-weight: 700; color: var(--text-main); font-family: monospace; }
.spacer { flex: 1; }
.version-text { color: var(--text-muted); font-size: 0.8rem; }

/* === Utilities === */
.w-full { width: 100%; }
.flex { display: flex; }
.flex-col { flex-direction: column; }
.flex-wrap { flex-wrap: wrap; }
.items-center { align-items: center; }
.items-end { align-items: flex-end; }
.justify-between { justify-content: space-between; }
.gap-1 { gap: 0.25rem; }
.gap-2 { gap: 0.5rem; }
.gap-4 { gap: 1rem; }
.mb-1 { margin-bottom: 0.25rem; }
.mb-2 { margin-bottom: 0.5rem; }
.mb-3 { margin-bottom: 0.75rem; }
.mb-4 { margin-bottom: 1rem; }
.mb-6 { margin-bottom: 1.5rem; }
.mt-0 { margin-top: 0; }
.mt-2 { margin-top: 0.5rem; }
.mt-4 { margin-top: 1rem; }
.text-center { text-align: center; }
.text-right { text-align: right; }
.font-bold { font-weight: 700; }
.font-semibold { font-weight: 600; }
.text-sm { font-size: 0.85rem; }
.text-lg { font-size: 1.1rem; }
.text-primary { color: var(--text-primary-color); }
.text-success { color: var(--success-fg); }
.text-warning { color: var(--warning-fg); }
.text-danger { color: var(--danger-fg); }
.text-sub { color: var(--text-sub); }
.text-muted { color: var(--text-muted); }
.bg-soft { background-color: var(--bg-soft); }
.rounded-lg { border-radius: 8px; }
.flex-1 { flex: 1; }
.p-4 { padding: 1rem; }
.p-5 { padding: 1.25rem; }
.p-2 { padding: 0.5rem; }
.mobile-header-content { display: flex; align-items: center; gap: 10px; }
.mobile-title { margin: 0; font-size: 1.1rem; font-weight: 800; color: var(--primary); }
.logout-link { color: var(--danger-fg); padding: 0.75rem; font-size: 0.9rem; margin: 0; font-weight: 600; }
.logout-link:hover { background-color: var(--danger-bg); color: var(--danger-fg); }
.logout-icon { width: 18px; height: 18px; }
.th-w-30 { width: 30%; }
.th-w-15 { width: 15%; }
.th-w-40 { width: 40%; }
.mt-neg-1 { margin-top: -1rem; }
.nowrap { white-space: nowrap; }
.h-fit { height: fit-content; }
.dashed-border { border: 2px dashed var(--border); }
.w-150 { width: 150px; }
.w-120 { width: 120px; }
.min-w-150 { min-width: 150px; }
.min-w-120 { min-width: 120px; }
.min-w-200 { min-width: 200px; }
.flex-2 { flex: 2; }
.max-w-600 { max-width: 600px; }
.bg-border-light { background-color: var(--border-light); }
.border-danger { border-color: var(--md-sys-color-error, #BA1A1A); }
.w-auto { width: auto; }
.border { border: 1px solid var(--border); }
.text-truncate { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 250px; }
.border-b { border-bottom: 1px solid var(--border-light); }
.text-left { text-align: left; }

/* Spacing Utilities */
.space-y-4 > * + * { margin-top: 1rem; }
.space-y-2 > * + * { margin-top: 0.5rem; }

/* Positioning & Visibility */
.relative { position: relative; }
.absolute { position: absolute; }
.right-3 { right: 0.75rem; }
.top-50p { top: 50%; }
.translate-y-50n { transform: translateY(-50%); }
.pr-10 { padding-right: 2.5rem; }
.font-mono { font-family: monospace; }
.font-medium { font-weight: 500; }
.uppercase { text-transform: uppercase; }
.cursor-pointer { cursor: pointer; }
.cursor-not-allowed { cursor: not-allowed; }
.inline-flex { display: inline-flex; }
.items-start { align-items: flex-start; }
.justify-end { justify-content: flex-end; }
.justify-center { justify-content: center; }
.inset-0 { top: 0; right: 0; bottom: 0; left: 0; }
.z-10 { z-index: 10; }
.opacity-50 { opacity: 0.5; }
.text-xs { font-size: 0.75rem; }
.text-main { color: var(--text-main); }
.tracking-wider { letter-spacing: 0.05em; }
.pt-2 { padding-top: 0.5rem; }
.px-4 { padding-left: 1rem; padding-right: 1rem; }
.py-2 { padding-top: 0.5rem; padding-bottom: 0.5rem; }
.p-1 { padding: 0.25rem; }
.rounded-full { border-radius: 9999px; }

/* Custom Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background-color: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background-color: var(--text-muted); }

/* Grid Systems */
.grid-auto-fit { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem; }
.grid-1-2 { display: grid; grid-template-columns: 1fr 2fr; gap: 2rem; }
.grid-2-1 { display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem; }

/* Credit Weights Card */
.credit-weights-body { display: flex; justify-content: space-around; align-items: center; padding: 1rem 0; }
.weight-item { text-align: center; flex: 1; }
.weight-item.middle { border-left: 1px solid var(--border-light); border-right: 1px solid var(--border-light); }
.weight-label { font-size: 0.85rem; color: var(--text-sub); margin-bottom: 8px; font-weight: 600; }
.weight-value { font-size: 1.5rem; font-weight: 800; }

/* Guide Card */
/* The Precision Star: Highlight core message with accent color border */
.guide-card { border: 1px solid var(--border); border-left: 4px solid var(--primary); background: var(--bg-card); margin-bottom: 2rem; box-shadow: none; border-radius: var(--radius-card); }

/* Card Disabled Overlay (M3: state layer for disabled containers) */
.card-disabled-overlay { position: absolute; top: 0; right: 0; bottom: 0; left: 0; z-index: 10; display: flex; align-items: center; justify-content: center; background-color: var(--bg-page); opacity: 0.75; border-radius: var(--radius-card); cursor: not-allowed; pointer-events: auto; }
.card-disabled-label { padding: 8px 20px; border-radius: 8px; border: 1px solid var(--border); background-color: var(--bg-card); color: var(--danger-fg); font-weight: 600; font-size: 0.85rem; opacity: 1; box-shadow: var(--shadow-sm); }
/* Prevent card hover transform from breaking overlay stacking context */
.card:has(.card-disabled-overlay) { pointer-events: none; }
.card:has(.card-disabled-overlay):hover { transform: none; box-shadow: none; }
.card .card-disabled-overlay { pointer-events: auto; }
/* Toggle switch above overlay */
.card .toggle-switch { position: relative; z-index: 20; pointer-events: auto; }

/* === Responsive Design === */
@media (max-width: 768px) {
    .sidebar { transform: translateX(-100%); }
    .sidebar.active { transform: translateX(0); box-shadow: 4px 0 16px rgba(0,0,0,0.1); }
    .main-content { margin-left: 0; padding: 1rem; }
    .mobile-header { display: flex; }
    .top-bar { display: none; }
    .overlay.active { display: block; }
    body.sidebar-open { overflow: hidden; }

    /* Grid & Flex Adjustments */
    .grid-2, .grid-3, .grid-1-2, .grid-2-1 { grid-template-columns: 1fr !important; }
    .system-status-bar { flex-direction: column; align-items: flex-start; gap: 0.75rem; }
    .status-item { width: 100%; justify-content: space-between; }
    .spacer { display: none; }
    
    /* Credit Weights Card */
    .credit-weights-body { flex-direction: column; gap: 1.5rem; }
    .weight-item.middle { border: none; padding: 1rem 0; border-top: 1px solid var(--border-light); border-bottom: 1px solid var(--border-light); width: 100%; }

    /* Summary Grid */
    .summary-grid { grid-template-columns: 1fr; }
}

/* === Modal & Logs === */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 100; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(2px); }
.modal-overlay.hidden { display: none; }
.modal-content { background: var(--bg-card); width: 90%; max-width: 800px; max-height: 80vh; border-radius: var(--radius-dialog); box-shadow: var(--shadow-md); display: flex; flex-direction: column; border: 1px solid var(--border); animation: modalFadeIn 0.2s ease-out; }
@keyframes modalFadeIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
.modal-header { padding: 1rem 1.5rem; border-bottom: 1px solid var(--border-light); display: flex; justify-content: space-between; align-items: center; }
.modal-header h3 { margin: 0; font-size: 1.1rem; color: var(--text-main); }
.close-btn { background: none; border: none; font-size: 1.5rem; cursor: pointer; color: var(--text-sub); padding: 0; line-height: 1; }
.close-btn:hover { color: var(--text-main); }
.modal-body { padding: 1.5rem; overflow-y: auto; background: var(--bg-soft); }
.log-pre { white-space: pre-wrap; word-break: break-all; font-family: monospace; font-size: 0.85rem; color: var(--text-main); margin: 0; }
.log-message-cell { cursor: pointer; transition: color 0.2s; }
.log-message-cell:hover { color: var(--primary); text-decoration: underline; }

/* Sticky Header (Global) */
.sticky-header {
    position: sticky;
    top: 0;
    z-index: 30;
    margin: -2rem -2rem 2rem -2rem; /* Pull to viewport edges */
    padding: 0.75rem 2rem; /* Restore alignment with content */
    border-radius: 0;
    border: none;
    border-bottom: 1px solid var(--border-light);
    background: rgba(255, 255, 255, 0.90);
    backdrop-filter: blur(8px);
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    display: flex;
    align-items: center;
}
html.dark .sticky-header {
    background: rgba(30, 30, 30, 0.95);
    border-bottom: 1px solid #333;
}
""")

# Always overwrite login.css to apply latest brand colors
with open(login_css_path, 'w', encoding='utf-8') as f:
    f.write(""":root {
    --primary: #E5AA70; --primary-hover: #D4955D;
    --on-primary: #000000;
    --bg-page: #F8F9FA; --bg-card: #FFFFFF; --bg-input: #FFFFFF;
    --text-main: #000000; --text-sub: #4A5568;
    --border: #8E8E8E;
    --danger-fg: #BA1A1A;
    --shadow-md: 0px 1px 2px rgba(0,0,0,0.3), 0px 2px 6px 2px rgba(0,0,0,0.15);
    --radius-card: 28px; --radius-btn: 20px;
}
html.dark {
    --primary: #E5AA70; --primary-hover: #D4955D;
    --on-primary: #000000;
    --bg-page: #121212; --bg-card: #1E1E1E; --bg-input: #2C2C2C;
    --text-main: #FFFFFF; --text-sub: #A0A0A0;
    --border: #4F4F4F;
    --shadow-md: 0px 2px 6px 2px rgba(0,0,0,0.15), 0px 1px 2px 0px rgba(0,0,0,0.3);
}
body { font-family: "Roboto", "Pretendard", sans-serif; background-color: var(--bg-page); color: var(--text-main); display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; letter-spacing: 0.01em; -webkit-font-smoothing: antialiased; transition: background-color 0.3s, color 0.3s; }
.login-container { background: var(--bg-card); padding: 3rem 2.5rem; border-radius: var(--radius-card); box-shadow: var(--shadow-md); width: 100%; max-width: 400px; border: none; transition: background-color 0.3s; }
h1 { color: var(--text-main); text-align: center; margin-bottom: 1.5rem; font-size: 1.75rem; font-weight: 400; margin-top: 0; }
input { width: 100%; height: 56px; padding: 0 16px; margin-bottom: 1.5rem; border: 1px solid var(--border); border-radius: 4px; box-sizing: border-box; background: transparent; color: var(--text-main); transition: all 0.2s; }
input:focus { border-color: var(--primary); border-width: 2px; outline: none; padding: 0 15px; }
button { width: 100%; height: 40px; background-color: var(--primary); color: var(--on-primary); border: none; border-radius: var(--radius-btn); font-weight: 500; cursor: pointer; transition: background-color 0.2s; font-size: 0.875rem; letter-spacing: 0.1px; }
button:hover { background-color: var(--primary-hover); }
.error { color: var(--danger-fg); text-align: center; margin-top: 1rem; font-size: 0.9rem; }
.remember-me { text-align: left; margin-bottom: 1.5rem; font-size: 0.9rem; color: var(--text-sub); display: flex; align-items: center; }
.remember-me input { width: auto; margin: 0 0.5rem 0 0; height: auto; cursor: pointer; }
.remember-me label { cursor: pointer; display: flex; align-items: center; }
/* Utility classes (shared with style.css) */
.text-center { text-align: center; }
.text-sub { color: var(--text-sub); }
.text-sm { font-size: 0.85rem; }
.mb-6 { margin-bottom: 1.5rem; }""")

# [Self-Repair] 주요 HTML 템플릿 파일 자동 생성
templates_to_create = {
    'base.html': """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    {% block head_meta %}{% endblock %}
    <title>TrustFin Admin</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}" type="text/css">
    <script>
        (function() {
            var saved = localStorage.getItem('adminTheme');
            var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            if (saved === 'dark' || (!saved && prefersDark)) {
                document.documentElement.classList.add('dark');
            }
        })();
    </script>
</head>
<body>
    <div class="app-container">
        <div class="overlay" id="sidebar-overlay" onclick="toggleSidebar()"></div>
        
        <!-- Mobile Header -->
        <div class="mobile-header">
            <div class="mobile-header-content">
                <button class="mobile-toggle" onclick="toggleSidebar()">☰</button>
                <h2 class="mobile-title">TrustFin Admin</h2>
            </div>
        </div>

        <!-- Sidebar -->
        <nav class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h2>TrustFin Admin</h2>
            </div>
            <div class="sidebar-nav">
                <div class="nav-section">Dashboard</div>
                <a href="/" class="nav-item {{ 'active' if request.endpoint == 'index' else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>
                    Home
                </a>

                <div class="nav-section">Service Management</div>
                <a href="/members" class="nav-item {{ 'active' if request.endpoint and request.endpoint.startswith('member') else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                    회원 관리
                </a>
                <a href="/user-stats" class="nav-item {{ 'active' if request.endpoint and request.endpoint.startswith('user_stats') else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
                    유저 스탯
                </a>
                <a href="/products" class="nav-item {{ 'active' if request.endpoint == 'products' else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"></line><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
                    상품 관리
                </a>
                <a href="/missions" class="nav-item {{ 'active' if request.endpoint and request.endpoint.startswith('mission') else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path><line x1="4" y1="22" x2="4" y2="15"></line></svg>
                    미션 관리
                </a>
                <a href="/points" class="nav-item {{ 'active' if request.endpoint in ['points', 'point_detail', 'points_adjust'] else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect><line x1="1" y1="10" x2="23" y2="10"></line></svg>
                    포인트 관리
                </a>
                <a href="/point-products" class="nav-item {{ 'active' if request.endpoint and (request.endpoint.startswith('point_product') or request.endpoint == 'point_purchases') else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>
                    포인트 상품
                </a>

                <div class="nav-section">System & Config</div>
                <a href="/system-info" class="nav-item {{ 'active' if request.endpoint == 'system_info' else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                    시스템 정보
                </a>
                <a href="/collection-management" class="nav-item {{ 'active' if request.endpoint == 'collection_management' else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    수집 관리
                </a>
                <a href="/credit-weights" class="nav-item {{ 'active' if request.endpoint == 'credit_weights' else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><line x1="4" y1="21" x2="4" y2="14"></line><line x1="4" y1="10" x2="4" y2="3"></line><line x1="12" y1="21" x2="12" y2="12"></line><line x1="12" y1="8" x2="12" y2="3"></line><line x1="20" y1="21" x2="20" y2="16"></line><line x1="20" y1="12" x2="20" y2="3"></line><line x1="1" y1="14" x2="7" y2="14"></line><line x1="9" y1="8" x2="15" y2="8"></line><line x1="17" y1="16" x2="23" y2="16"></line></svg>
                    신용평가 설정
                </a>
                <a href="/recommend-settings" class="nav-item {{ 'active' if request.endpoint == 'recommend_settings' else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                    추천 설정
                </a>

                <div class="nav-section">Tools</div>
                <a href="/simulator" class="nav-item {{ 'active' if request.endpoint == 'simulator' else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polygon points="10 8 16 12 10 16 10 8"></polygon></svg>
                    시뮬레이터
                </a>
                <a href="/data/raw_loan_products" class="nav-item {{ 'active' if request.endpoint == 'view_data' else '' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s 9-1.34 9-3V5"></path></svg>
                    데이터 조회
                </a>
            </div>
            <div class="sidebar-footer">
                <button onclick="toggleDarkMode()" class="theme-toggle" title="다크모드 전환"><span id="theme-icon">🌙</span></button>
                <a href="/logout" class="nav-item logout-link">
                    <svg class="nav-icon logout-icon" viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
                    로그아웃
                </a>
            </div>
        </nav>

        <!-- Main Content -->
        <main class="main-content">
            {% block top_bar %}
            <div class="system-status-bar sticky-header">
                <a href="/data/raw_loan_products" class="status-item" title="데이터베이스 연결 상태입니다. 클릭하면 데이터 조회 페이지로 이동합니다.">
                    <span class="status-dot {{ 'dot-success' if system_status.db else 'dot-danger' }}"></span>
                    <span class="status-label">DB Connection</span>
                    <span class="status-value">{{ 'Connected' if system_status.db else 'Disconnected' }}</span>
                </a>
                <a href="/collection-management" class="status-item" title="활성화된 데이터 수집기 수 / 전체 수집기 수. 클릭하면 수집 관리 페이지로 이동합니다.">
                    <span class="status-dot {{ 'dot-success' if system_status.collectors_active == system_status.collectors_total else 'dot-warning' if system_status.collectors_active > 0 else 'dot-danger' }}"></span>
                    <span class="status-label">Collectors</span>
                    <span class="status-value">{{ system_status.collectors_active }}/{{ system_status.collectors_total }} Active</span>
                </a>
                <a href="/system-info" class="status-item" title="서버 현재 시간. 클릭하면 시스템 정보 페이지로 이동합니다.">
                    <span class="status-dot dot-info"></span>
                    <span class="status-label">System Time</span>
                    <span class="status-value">{{ system_status.now }}</span>
                </a>
                <a href="/data/collection_logs?search_col=status&search_val=FAIL" class="status-item" title="최근 24시간 내 발생한 수집 실패 로그 건수입니다. 클릭하면 실패 로그를 조회합니다.">
                    <span class="status-dot {{ 'dot-success' if system_status.recent_errors == 0 else 'dot-danger' }}"></span>
                    <span class="status-label">Recent Errors (24h)</span>
                    <span class="status-value">{{ 'None' if system_status.recent_errors == 0 else system_status.recent_errors ~ ' Found' }}</span>
                </a>
                <div class="spacer"></div>
                {% block header_actions %}{% endblock %}
                <a href="/toggle_refresh" class="nav-btn {{ 'active' if auto_refresh else '' }}" title="{{ '자동 새로고침 ON: 30초마다 대시보드가 자동 업데이트됩니다. 클릭하면 OFF로 전환합니다.' if auto_refresh else '자동 새로고침 OFF: 클릭하면 30초 간격 자동 업데이트를 켭니다.' }}">
                    {{ 'Auto Refresh: ON' if auto_refresh else 'Auto Refresh: OFF' }}
                </a>
                <a href="/data/notifications" class="notification-btn" title="알림">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
                    {% if unread_notifications_count > 0 %}
                    <span class="notification-badge">{{ unread_notifications_count if unread_notifications_count <= 99 else '99+' }}</span>
                    {% endif %}
                </a>
            </div>
            {% endblock %}

        {% if message %}
            <div class="alert {{ status }}">{{ message }}</div>
        {% endif %}

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, msg in messages %}
                    <div class="alert {{ 'success' if category == 'success' else 'error' if category == 'error' else 'warning' }}">{{ msg }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
        </main>
    </div> <!-- End app-container -->

    <!-- Log Detail Modal -->
    <div id="logModal" class="modal-overlay hidden">
        <div class="modal-content">
            <div class="modal-header">
                <h3>로그 상세 메시지</h3>
                <button onclick="closeLogModal()" class="close-btn">&times;</button>
            </div>
            <div class="modal-body">
                <pre id="logModalBody" class="log-pre"></pre>
            </div>
        </div>
    </div>

    <script>
        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('active');
            document.getElementById('sidebar-overlay').classList.toggle('active');
            document.body.classList.toggle('sidebar-open');
        }
        function toggleDarkMode() {
            var html = document.documentElement;
            var isDark = html.classList.toggle('dark');
            localStorage.setItem('adminTheme', isDark ? 'dark' : 'light');
            document.getElementById('theme-icon').textContent = isDark ? '☀️' : '🌙';
        }
        (function() {
            if (document.documentElement.classList.contains('dark')) {
                var icon = document.getElementById('theme-icon');
                if (icon) icon.textContent = '☀️';
            }
        })();

        window.addEventListener('resize', function() {
            if (window.innerWidth > 768) {
                document.getElementById('sidebar').classList.remove('active');
                document.getElementById('sidebar-overlay').classList.remove('active');
                document.body.classList.remove('sidebar-open');
            }
        });

        function showLogMessage(msg) {
            if (!msg || msg === 'None' || msg === '-') return;
            document.getElementById('logModalBody').textContent = msg;
            document.getElementById('logModal').classList.remove('hidden');
        }
        function closeLogModal() {
            document.getElementById('logModal').classList.add('hidden');
        }
        window.onclick = function(event) {
            var modal = document.getElementById('logModal');
            if (event.target == modal) closeLogModal();
        }
    </script>
</body>
</html>""",
    'login.html': """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8"><title>Login - TrustFin Admin</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='login.css') }}" type="text/css">
    <script>
        (function() {
            var saved = localStorage.getItem('adminTheme');
            var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            if (saved === 'dark' || (!saved && prefersDark)) {
                document.documentElement.classList.add('dark');
            }
        })();
    </script>
</head>
<body>
    <div class="login-container">
        <h1>관리자 로그인</h1>
        <p class="text-center text-sub text-sm mb-6">관리자 계정으로만 접근 가능합니다. 계정 정보가 없으면 시스템 담당자에게 문의하세요.</p>
        <form method="post">
            <input type="text" name="username" placeholder="관리자 아이디 입력 (예: admin)" aria-label="관리자 아이디" value="{{ saved_username or '' }}" required>
            <input type="password" name="password" placeholder="비밀번호 입력" aria-label="비밀번호" required>
            <div class="remember-me">
                <label><input type="checkbox" name="remember_me" {% if saved_username %}checked{% endif %}> 아이디 저장</label>
            </div>
            <button type="submit">로그인</button>
        </form>
        {% with messages = get_flashed_messages() %}
            {% if messages %}<div class="error">{{ messages[0] }}</div>{% endif %}
        {% endwith %}
    </div>
</body>
</html>""",
    'index.html': """{% extends "base.html" %}

{% block head_meta %}
    {% if auto_refresh %}
    <meta http-equiv="refresh" content="30; url={{ url_for('index') }}">
    {% endif %}
{% endblock %}

{% block content %}
        <!-- Educational Guide Card -->
        <div class="card guide-card">
            <div class="card-p">
                <div class="flex items-center gap-2 mb-2">
                    <span class="badge badge-info">Dashboard Guide</span>
                    <h3 class="font-bold text-sm">통합 관제 대시보드</h3>
                </div>
                <div class="text-sm text-sub space-y-2">
                    <p><strong>목적:</strong> 서비스의 전반적인 건강 상태(Health)와 핵심 지표를 한눈에 파악합니다.</p>
                    <p><strong>기능:</strong>
                        1. <strong>시스템 상태:</strong> DB 연결 및 수집기 활성 상태 모니터링.<br>
                        2. <strong>데이터 요약:</strong> 수집된 금융 데이터의 총량 확인.<br>
                        3. <strong>수집 로그:</strong> 각 데이터 소스별 최근 실행 결과(성공/실패) 및 에러 확인.
                    </p>
                </div>
            </div>
        </div>

        <div class="summary-grid">
            <div class="summary-card" title="금감원 API에서 수집된 대출 상품의 총 건수입니다.">
                <div class="summary-label">대출 상품 수</div>
                <div class="summary-value">{{ "{:,}".format(stats.loan_count | default(0)) }}</div>
            </div>
            <div class="summary-card" title="통계청에서 수집된 경제 지표(금리, 물가 등)의 총 건수입니다.">
                <div class="summary-label">경제 지표 수</div>
                <div class="summary-value">{{ "{:,}".format(stats.economy_count | default(0)) }}</div>
            </div>
            <div class="summary-card" title="통계청 KOSIS에서 수집된 소득 통계의 총 건수입니다.">
                <div class="summary-label">소득 통계 수</div>
                <div class="summary-value">{{ "{:,}".format(stats.income_count | default(0)) }}</div>
            </div>
            <div class="summary-card" title="모든 데이터 소스의 수집 실행 기록(성공/실패 포함)의 총 건수입니다.">
                <div class="summary-label">총 수집 로그</div>
                <div class="summary-value">{{ "{:,}".format(stats.log_count | default(0)) }}</div>
            </div>
        </div>

        <div class="grid-2 mb-6">
            <!-- 신용 평가 가중치 요약 -->
            <div class="card h-fit">
                <div class="card-header">
                    <h3 class="card-title">현재 신용 평가 가중치</h3>
                    <a href="/credit-weights" class="nav-btn" title="신용평가 가중치 상세 설정 페이지로 이동합니다.">설정 변경</a>
                </div>
                <div class="card-p">
                    <p class="help-text mb-3">세 가중치의 합은 1.0이어야 합니다.</p>
                    <div class="credit-weights-body">
                       <div class="weight-item">
                           <div class="weight-label">소득 비중</div>
                           <div class="weight-value text-primary" title="WEIGHT_INCOME">{{ stats.WEIGHT_INCOME | default(0.5) }}</div>
                        </div>
                        <div class="weight-item middle">
                            <div class="weight-label">고용 안정성</div>
                            <div class="weight-value text-success" title="WEIGHT_JOB_STABILITY">{{ stats.WEIGHT_JOB_STABILITY | default(0.3) }}</div>
                        </div>
                        <div class="weight-item">
                            <div class="weight-label">자산 비중</div>
                            <div class="weight-value text-warning" title="WEIGHT_ESTATE_ASSET">{{ stats.WEIGHT_ESTATE_ASSET | default(0.2) }}</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- [New] 로그 상태 차트 -->
            <div class="card h-fit">
                <div class="card-header">
                    <h3 class="card-title">최근 24시간 수집 상태</h3>
                </div>
                <div class="card-p flex items-center justify-center" style="min-height: 180px;">
                    <div style="width: 140px; height: 140px; position: relative;">
                        <canvas id="logStatusChart"></canvas>
                        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; pointer-events: none;">
                            <div style="font-size: 0.7rem; color: var(--text-muted); line-height: 1.2;">Total</div>
                            <div style="font-size: 1.2rem; font-weight: 800; color: var(--text-main); line-height: 1;" id="cnt-total">0</div>
                        </div>
                    </div>
                    <div class="ml-6">
                        <div class="flex items-center gap-2 mb-1 cursor-pointer hover:opacity-75 transition" onclick="window.location.href='{{ url_for('index', status_filter='SUCCESS') }}'" title="Success 로그 필터링">
                            <span class="status-dot dot-success"></span><span class="text-sm text-sub">Success</span><span class="font-bold ml-auto" id="cnt-success">0</span>
                        </div>
                        <div class="flex items-center gap-2 mb-1 cursor-pointer hover:opacity-75 transition" onclick="window.location.href='{{ url_for('index', status_filter='FAIL') }}'" title="Fail 로그 필터링">
                            <span class="status-dot dot-danger"></span><span class="text-sm text-sub">Fail</span><span class="font-bold ml-auto" id="cnt-fail">0</span>
                        </div>
                        <div class="flex items-center gap-2 cursor-pointer hover:opacity-75 transition" onclick="window.location.href='{{ url_for('index', status_filter='SKIPPED') }}'" title="Skipped 로그 필터링">
                            <span class="status-dot" style="background:#E5E7EB;"></span><span class="text-sm text-sub">Skipped</span><span class="font-bold ml-auto" id="cnt-skipped">0</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                const stats = {{ stats.log_stats_24h | tojson | default('{}') }};
                let success = (stats['SUCCESS'] || 0) + (stats['SUCCESS (MOCK)'] || 0);
                let fail = stats['FAIL'] || 0;
                let skipped = stats['SKIPPED'] || 0;
                
                document.getElementById('cnt-success').textContent = success;
                document.getElementById('cnt-fail').textContent = fail;
                document.getElementById('cnt-skipped').textContent = skipped;
                
                const total = success + fail + skipped;
                document.getElementById('cnt-total').textContent = total;

                const ctx = document.getElementById('logStatusChart').getContext('2d');
                
                new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Success', 'Fail', 'Skipped'],
                        datasets: [{
                            data: total === 0 ? [1] : [success, fail, skipped],
                            backgroundColor: total === 0 ? ['#F3F4F6'] : ['#10B981', '#F43F5E', '#E5E7EB'],
                            borderWidth: 0,
                            hoverOffset: total === 0 ? 0 : 4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '70%',
                        plugins: { legend: { display: false }, tooltip: { enabled: total > 0 } },
                        onClick: (e, elements) => {
                            if (elements.length > 0) {
                                const index = elements[0].index;
                                const labels = ['SUCCESS', 'FAIL', 'SKIPPED'];
                                if (labels[index]) {
                                    window.location.href = '/?status_filter=' + labels[index];
                                }
                            }
                        },
                        onHover: (event, chartElement) => {
                            event.native.target.style.cursor = chartElement[0] ? 'pointer' : 'default';
                        }
                    }
                });
            });
        </script>

        <div class="dashboard-grid">
            <!-- Card 1: Loan -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title-group">
                        <h3 class="card-title">금감원 대출상품</h3>
                        <span class="last-run">최근 실행: {{ loan_last_run | time_ago }}</span>
                    </div>
                    <div class="card-actions">
                        <span class="{{ 'badge-on' if stats.COLLECTOR_FSS_LOAN_ENABLED|default('1') == '1' else 'badge-off' }}" title="{{ '수집 활성화: 자동 수집이 실행됩니다.' if stats.COLLECTOR_FSS_LOAN_ENABLED|default('1') == '1' else '수집 비활성화: 수집 관리 메뉴에서 변경하세요.' }}">
                            {{ 'ON' if stats.COLLECTOR_FSS_LOAN_ENABLED|default('1') == '1' else 'OFF' }}
                        </span>
                        <form action="/trigger" method="post" style="margin:0;">
                            <button type="submit" name="job" value="loan" class="refresh-btn" title="금감원 대출상품 데이터를 지금 즉시 새로고침(수집)합니다.">새로고침</button>
                        </form>
                    </div>
                </div>
                <div class="card-body">
                    {% with logs=loan_logs %}{% include 'components/log_table.html' %}{% endwith %}
                </div>
            </div>

            <!-- Card 2: Economy -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title-group">
                        <h3 class="card-title">경제 지표</h3>
                        <span class="last-run">최근 실행: {{ economy_last_run | time_ago }}</span>
                    </div>
                    <div class="card-actions">
                        <span class="{{ 'badge-on' if stats.COLLECTOR_ECONOMIC_ENABLED|default('1') == '1' else 'badge-off' }}" title="{{ '수집 활성화: 자동 수집이 실행됩니다.' if stats.COLLECTOR_ECONOMIC_ENABLED|default('1') == '1' else '수집 비활성화: 수집 관리 메뉴에서 변경하세요.' }}">
                            {{ 'ON' if stats.COLLECTOR_ECONOMIC_ENABLED|default('1') == '1' else 'OFF' }}
                        </span>
                        <form action="/trigger" method="post" style="margin:0;">
                            <button type="submit" name="job" value="economy" class="refresh-btn" title="경제 지표 데이터를 지금 즉시 새로고침(수집)합니다.">새로고침</button>
                        </form>
                    </div>
                </div>
                <div class="card-body">
                    {% with logs=economy_logs %}{% include 'components/log_table.html' %}{% endwith %}
                </div>
            </div>

            <!-- Card 3: Income -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title-group">
                        <h3 class="card-title">통계청 소득정보</h3>
                        <span class="last-run">최근 실행: {{ income_last_run | time_ago }}</span>
                    </div>
                    <div class="card-actions">
                        <span class="{{ 'badge-on' if stats.COLLECTOR_KOSIS_INCOME_ENABLED|default('1') == '1' else 'badge-off' }}" title="{{ '수집 활성화: 자동 수집이 실행됩니다.' if stats.COLLECTOR_KOSIS_INCOME_ENABLED|default('1') == '1' else '수집 비활성화: 수집 관리 메뉴에서 변경하세요.' }}">
                            {{ 'ON' if stats.COLLECTOR_KOSIS_INCOME_ENABLED|default('1') == '1' else 'OFF' }}
                        </span>
                        <form action="/trigger" method="post" style="margin:0;">
                            <button type="submit" name="job" value="income" class="refresh-btn" title="통계청 소득정보를 지금 즉시 새로고침(수집)합니다.">새로고침</button>
                        </form>
                    </div>
                </div>
                <div class="card-body">
                    {% with logs=income_logs %}{% include 'components/log_table.html' %}{% endwith %}
                </div>
            </div>
        </div>
{% endblock %}""",
    'components/log_table.html': """<div class="log-table-container">
    <table class="w-full">
        <thead><tr>
            <th scope="col" class="th-w-30 text-left nowrap">
                <a href="{{ url_for('index', sort_by='executed_at', order='asc' if sort_by == 'executed_at' and order == 'desc' else 'desc', status_filter=status_filter) }}" style="text-decoration: none; color: inherit; display: inline-flex; align-items: center; gap: 4px;">
                    실행 시간
                    {% if sort_by == 'executed_at' %}
                        <span class="text-primary">{{ '▲' if order == 'asc' else '▼' }}</span>
                    {% endif %}
                </a>
            </th>
            <th scope="col" class="th-w-10 text-center nowrap">레벨</th>
            <th scope="col" class="th-w-15 text-center nowrap">
                <a href="{{ url_for('index', sort_by=sort_by, order=order, status_filter='FAIL' if not status_filter else 'SUCCESS' if status_filter == 'FAIL' else '') }}" style="text-decoration: none; color: inherit; display: inline-flex; align-items: center; gap: 4px; justify-content: center;" title="클릭하여 상태 필터 변경 (전체 -> 실패 -> 성공)">
                    상태
                    {% if status_filter %}
                        <span class="badge {{ 'badge-danger' if status_filter == 'FAIL' else 'badge-success' }}" style="font-size: 0.6em; padding: 1px 4px;">{{ status_filter }}</span>
                    {% else %}
                        <span style="font-size: 0.7em; color: var(--text-muted);">ALL</span>
                    {% endif %}
                </a>
            </th>
            <th scope="col" class="th-w-15 text-right nowrap">
                <a href="{{ url_for('index', sort_by='row_count', order='asc' if sort_by == 'row_count' and order == 'desc' else 'desc', status_filter=status_filter) }}" style="text-decoration: none; color: inherit; display: inline-flex; align-items: center; gap: 4px; width: 100%; justify-content: flex-end;">
                    건수
                    {% if sort_by == 'row_count' %}
                        <span class="text-primary">{{ '▲' if order == 'asc' else '▼' }}</span>
                    {% endif %}
                </a>
            </th>
            <th scope="col" class="th-w-30 text-left nowrap">메시지</th>
        </tr></thead>
        <tbody>
            {% for log in logs %}
            <tr>
                <td class="text-sub text-left">{{ log.executed_at.strftime('%Y-%m-%d %H:%M:%S') if log.executed_at else '-' }}</td>
                <td class="text-center">
                    <span class="badge {{ 'badge-danger' if log.level == 'ERROR' else 'badge-warning' if log.level == 'WARNING' else 'badge-info' }}">{{ log.level or 'INFO' }}</span>
                </td>
                <td class="text-center">
                    <span class="badge {{ 'badge-danger' if log.status == 'FAIL' else 'badge-success' if log.status == 'SUCCESS' else 'badge-neutral' }}">{{ log.status }}</span>
                </td>
                <td class="text-right font-bold text-primary nowrap">{{ "{:,}".format(log.row_count) }}</td>
                <td class="text-left" title="{{ log.error_message if log.error_message else '' }}">
                    <div class="text-sub text-sm text-truncate log-message-cell" 
                         onclick="showLogMessage(this.getAttribute('data-msg'))" 
                         data-msg="{{ log.error_message or '' }}">
                        {{ log.error_message if log.error_message else '-' }}
                    </div>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="5" class="text-center text-muted p-4">수집된 로그가 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>""",
    'collection_management.html': """{% extends "base.html" %}
{% block content %}
<h1>금융 데이터 수집 관리</h1>

<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">Collection Guide</span>
            <h3 class="font-bold text-sm">금융 데이터 수집 관리</h3>
        </div>
        <div class="text-sm text-sub space-y-2">
            <p><strong>목적:</strong> 외부 기관(금감원, 통계청 등)의 데이터를 가져오는 파이프라인을 제어합니다.</p>
            <p><strong>사용 방법:</strong>
                1. <strong>토글 스위치:</strong> 각 수집기의 자동 실행 여부(ON/OFF)를 제어합니다.<br>
                2. <strong>설정 폼:</strong> API 인증키, 수집 주기(매일/매월), 수집 기간을 설정하고 저장합니다.<br>
                3. <strong>새로고침:</strong> '데이터 새로고침' 버튼으로 즉시 수집을 실행합니다.
            </p>
        </div>
    </div>
</div>

<div class="info-banner">데이터 수집 소스별로 자동 수집 활성화 여부를 설정하고, 필요 시 데이터를 즉시 새로고침(수집)할 수 있습니다. OFF 상태에서는 자동 스케줄 수집이 실행되지 않으며, 새로고침 버튼도 비활성화됩니다.</div>

<div class="dashboard-grid">
    {% for src in sources %}
    <div class="card card-p">
        <div class="flex justify-between items-start mb-6 relative" style="z-index: 20;">
            <div>
                <h3 class="card-title text-lg mb-1">{{ src.label }}</h3>
                <p class="text-xs text-muted">{{ src.api_desc }}</p>
            </div>
            <form action="/toggle_collector" method="post" style="margin:0;">
                <input type="hidden" name="source" value="{{ src.key }}">
                <label class="toggle-switch" title="{{ '클릭하여 비활성화' if src.enabled else '클릭하여 활성화' }}">
                    <input type="checkbox" onchange="this.form.submit()" {{ 'checked' if src.enabled else '' }}>
                    <span class="slider"></span>
                </label>
            </form>
        </div>
        
        <!-- Status Grid -->
        <div class="grid-3 gap-4 mb-6 p-4 bg-soft rounded-lg border">
            <div class="flex flex-col gap-1">
                <span class="text-xs text-muted font-medium uppercase tracking-wider">상태</span>
                <div class="flex items-center gap-2">
                    <span class="badge {{ 'badge-success' if src.last_status == 'SUCCESS' else 'badge-danger' if src.last_status == 'FAIL' else 'badge-neutral' }}">{{ src.last_status or '-' }}</span>
                    <form action="/trigger" method="post" class="inline-flex">
                        <button type="submit" name="job" value="{{ src.trigger_val }}" title="데이터 새로고침" class="btn-icon rounded-full {{ 'opacity-50 cursor-not-allowed' if not src.enabled else '' }}" {{ 'disabled' if not src.enabled else '' }} style="width: 32px; height: 32px; padding: 0; min-width: 32px;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3"/></svg>
                        </button>
                    </form>
                </div>
            </div>
            <div class="flex flex-col gap-1">
                <span class="text-xs text-muted font-medium uppercase tracking-wider">최근 실행</span>
                <span class="text-sm font-bold text-main font-mono">{{ src.last_run }}</span>
            </div>
            <div class="flex flex-col gap-1">
                <span class="text-xs text-muted font-medium uppercase tracking-wider">누적 데이터</span>
                <span class="text-sm font-bold text-primary font-mono">{{ src.total_count }}</span>
            </div>
        </div>

        <!-- Configuration -->
        <form action="/collection-management/config" method="post" class="space-y-4">
            <div>
                <label class="form-label text-xs uppercase text-muted mb-2">API Key (인증키)</label>
                <div class="relative">
                    <input type="password" id="input_{{ src.key }}" name="{{ src.api_field }}" value="{{ src.api_value }}" placeholder="인증키를 입력하세요" class="form-input text-sm w-full font-mono bg-soft pr-10">
                    <span onclick="togglePassword('input_{{ src.key }}', this)" class="password-toggle-icon absolute right-3 top-50p translate-y-50n cursor-pointer text-muted" title="키 보기/숨기기">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                    </span>
                </div>
                <p class="help-text mt-1">해당 기관에서 발급받은 API Key가 있어야 데이터 수집이 가능합니다.</p>
            </div>
            
            <div class="grid-2 gap-4">
                <div>
                    <label class="form-label text-xs uppercase text-muted mb-2">수집 주기</label>
                    <div class="radio-group">
                        {% set f_val = src.freq_value %}
                        {% set freq_options = [('daily', '매일'), ('weekly', '매주'), ('monthly', '매월')] %}
                        
                        {% for val, label in freq_options %}
                        <label class="radio-chip">
                            <input type="radio" name="{{ src.freq_field }}" value="{{ val }}" 
                                   {% if f_val == val %}checked{% endif %}>
                            <span>{{ label }}</span>
                        </label>
                        {% endfor %}
                    </div>
                    <p class="help-text mt-1">데이터 갱신 빈도를 설정합니다.</p>
                </div>
                <div>
                    <label class="form-label text-xs uppercase text-muted mb-2">수집 기간</label>
                    <div class="radio-group">
                        {% set p_val = src.period_value | int %}
                        {% set options = [(0, '전체'), (1, '1개월'), (3, '3개월'), (6, '6개월'), (12, '1년')] %}
                        {% set is_custom = p_val not in [0, 1, 3, 6, 12] %}
                        
                        {% for val, label in options %}
                        <label class="radio-chip">
                            <input type="radio" name="{{ src.period_field }}_opt" value="{{ val }}" 
                                   onchange="togglePeriodInput(this, '{{ src.period_field }}')"
                                   {% if p_val == val %}checked{% endif %}>
                            <span>{{ label }}</span>
                        </label>
                        {% endfor %}
                        
                        <label class="radio-chip">
                            <input type="radio" name="{{ src.period_field }}_opt" value="custom" 
                                   onchange="togglePeriodInput(this, '{{ src.period_field }}')"
                                   {% if is_custom %}checked{% endif %}>
                            <span>기타</span>
                        </label>
                    </div>
                    <input type="number" id="{{ src.period_field }}" name="{{ src.period_field }}" value="{{ src.period_value }}" min="0" max="60" class="form-input text-sm w-full mt-2" style="{{ 'display:none;' if not is_custom else '' }}" placeholder="개월 수 입력">
                    <p class="help-text mt-1">과거 데이터를 얼마나 가져올지 설정합니다. (0=전체)</p>
                </div>
            </div>

            <div class="flex justify-end pt-2">
                <button type="submit" class="btn-primary">
                    설정 저장
                </button>
            </div>
        </form>

        {% if not src.enabled %}
        <div class="card-disabled-overlay">
            <div class="card-disabled-label">
                수집 비활성화됨
            </div>
        </div>
        {% endif %}
    </div>
    {% endfor %}
</div>

<script>
function togglePeriodInput(radio, targetId) {
    var input = document.getElementById(targetId);
    if (radio.value === 'custom') {
        input.style.display = 'block';
        input.focus();
    } else {
        input.style.display = 'none';
        input.value = radio.value;
    }
}
function togglePassword(inputId, iconSpan) {
    var input = document.getElementById(inputId);
    if (input.type === "password") {
        input.type = "text";
        iconSpan.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>';
    } else {
        input.type = "password";
        iconSpan.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
    }
}
</script>
{% endblock %}""",
    'credit_weights.html': """{% extends "base.html" %}
{% block content %}
<h1>신용평가 가중치 관리</h1>

<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">Policy Guide</span>
            <h3 class="font-bold text-sm">신용 평가 가중치 설정</h3>
        </div>
        <div class="text-sm text-sub space-y-2">
            <p><strong>목적:</strong> AI가 사용자의 신용 점수를 산출할 때 사용하는 핵심 변수의 중요도를 조정합니다.</p>
            <p><strong>로직:</strong> <code>최종 점수 = (소득점수 × 소득비중) + (고용점수 × 고용비중) + (자산점수 × 자산비중)</code></p>
            <p><strong>사용 방법:</strong>
                슬라이더를 움직여 각 항목의 비중을 조절하세요. <strong>세 항목의 합계는 반드시 1.0</strong>이어야 합니다.
            </p>
        </div>
    </div>
</div>

<p class="text-sub mb-6">신용 평가 로직의 구성 요소를 수치화하여 조절합니다. 변경 사항은 대출 추천 결과에 즉시 반영됩니다.</p>

<form method="post">
    <!-- 섹션 1: 핵심 가중치 -->
    <div class="card card-p mb-6">
        <h3 class="card-title text-primary mt-0">핵심 가중치 (합계 = 1.0)</h3>
        <div class="grid-3 mb-4">
            <div>
                <label class="form-label text-primary">소득 비중 (WEIGHT_INCOME)</label>
                <input type="range" min="0" max="1" step="0.01" name="income_weight" value="{{ income_weight }}" id="rng_income" oninput="syncWeight()" class="w-full">
                <input type="number" step="0.01" min="0" max="1" id="num_income" value="{{ income_weight }}" onchange="syncFromNum('income')" class="form-input mt-2">
                <p class="help-text">0.0~1.0 범위. 값이 클수록 연 소득이 신용 점수에 더 큰 영향을 미칩니다.</p>
            </div>
            <div>
                <label class="form-label text-success">고용 안정성 (WEIGHT_JOB_STABILITY)</label>
                <input type="range" min="0" max="1" step="0.01" name="job_weight" value="{{ job_weight }}" id="rng_job" oninput="syncWeight()" class="w-full">
                <input type="number" step="0.01" min="0" max="1" id="num_job" value="{{ job_weight }}" onchange="syncFromNum('job')" class="form-input mt-2">
                <p class="help-text">0.0~1.0 범위. 고용 형태(대기업·공무원→1.0, 무직→0.2)와 곱해집니다.</p>
            </div>
            <div>
                <label class="form-label text-warning">자산 비중 (WEIGHT_ESTATE_ASSET)</label>
                <input type="range" min="0" max="1" step="0.01" name="asset_weight" value="{{ asset_weight }}" id="rng_asset" oninput="syncWeight()" class="w-full">
                <input type="number" step="0.01" min="0" max="1" id="num_asset" value="{{ asset_weight }}" onchange="syncFromNum('asset')" class="form-input mt-2">
                <p class="help-text">0.0~1.0 범위. 보유 자산 금액을 정규화한 점수에 곱해집니다.</p>
            </div>
        </div>
        <!-- 합계 표시 + 비율 바 -->
        <div class="mb-2 text-lg font-bold" title="세 가중치의 합은 반드시 1.0이어야 합니다.">합계: <span id="weightSum" class="{{ 'text-success' if (income_weight + job_weight + asset_weight) | round(2) == 1.0 else 'text-danger' }}">{{ (income_weight + job_weight + asset_weight) | round(2) }}</span></div>
        <div style="display: flex; height: 24px; border-radius: 8px; overflow: hidden; border: 1px solid var(--border);">
            <div id="bar_income" style="background: var(--primary); transition: width 0.2s; width: {{ income_weight * 100 }}%;"></div>
            <div id="bar_job" style="background: var(--success-fg); transition: width 0.2s; width: {{ job_weight * 100 }}%;"></div>
            <div id="bar_asset" style="background: var(--warning-fg); transition: width 0.2s; width: {{ asset_weight * 100 }}%;"></div>
        </div>
    </div>

    <!-- 섹션 2: 정규화 기준 -->
    <div class="card card-p mb-6">
        <h3 class="card-title text-primary mt-0">정규화 기준 (Normalization Ceiling)</h3>
        <p class="help-text mb-4">입력한 금액을 100%로 보고 비율로 0.0~1.0 점수를 매깁니다. 예: 소득 기준이 1억원이면 소득 5천만원인 유저는 점수 0.5를 받습니다.</p>
        <div class="grid-2">
            <div>
                <label class="form-label">소득 만점 기준 (원)</label>
                <input type="number" name="norm_income_ceiling" value="{{ norm_income_ceiling | int }}" step="10000000" placeholder="예: 100000000 (1억원)" class="form-input">
                <div class="text-sm text-sub mt-2">현재: {{ "{:,.0f}".format(norm_income_ceiling) }}원</div>
                <p class="help-text">이 금액 이상의 연 소득은 소득 점수 1.0(만점)을 받습니다. 기본값: 1억원.</p>
            </div>
            <div>
                <label class="form-label">자산 만점 기준 (원)</label>
                <input type="number" name="norm_asset_ceiling" value="{{ norm_asset_ceiling | int }}" step="10000000" placeholder="예: 500000000 (5억원)" class="form-input">
                <div class="text-sm text-sub mt-2">현재 설정: {{ "{:,.0f}".format(norm_asset_ceiling) }}원</div>
                <p class="help-text">이 금액 이상의 보유 자산은 자산 점수 1.0(만점)을 받습니다. 기본값: 5억원.</p>
            </div>
        </div>
    </div>

    <!-- 섹션 3: XAI 설명 임계값 -->
    <div class="card card-p mb-6">
        <h3 class="card-title text-primary mt-0">XAI 설명 임계값 (Explanation Thresholds)</h3>
        <p class="help-text mb-4">XAI 설명 텍스트에 표시될 최소 기여도 임계값입니다. 예: 소득 임계값이 0.15이면 소득 기여도가 15% 이상인 경우에만 설명이 표시됩니다. 값이 낮을수록 더 많은 항목이 표시됩니다.</p>
        <div class="grid-3">
            <div>
                <label class="form-label">소득 기여도 임계값</label>
                <input type="number" step="0.01" name="xai_threshold_income" value="{{ xai_threshold_income }}" class="form-input">
                <p class="help-text">권장 범위: 0.05~0.30. 기본값 0.15.</p>
            </div>
            <div>
                <label class="form-label">고용 기여도 임계값</label>
                <input type="number" step="0.01" name="xai_threshold_job" value="{{ xai_threshold_job }}" class="form-input">
                <p class="help-text">권장 범위: 0.05~0.25. 기본값 0.10.</p>
            </div>
            <div>
                <label class="form-label">자산 기여도 임계값</label>
                <input type="number" step="0.01" name="xai_threshold_asset" value="{{ xai_threshold_asset }}" class="form-input">
                <p class="help-text">권장 범위: 0.02~0.20. 기본값 0.05.</p>
            </div>
        </div>
    </div>

    <div class="flex justify-end">
        <button type="submit" title="변경 사항을 즉시 DB에 저장합니다." class="btn-accent">설정 저장</button>
    </div>
</form>

<script>
function syncWeight() {
    var i = parseFloat(document.getElementById('rng_income').value);
    var j = parseFloat(document.getElementById('rng_job').value);
    var a = parseFloat(document.getElementById('rng_asset').value);
    document.getElementById('num_income').value = i.toFixed(2);
    document.getElementById('num_job').value = j.toFixed(2);
    document.getElementById('num_asset').value = a.toFixed(2);
    var sum = (i + j + a).toFixed(2);
    var el = document.getElementById('weightSum');
    el.textContent = sum;
    el.style.color = Math.abs(parseFloat(sum) - 1.0) < 0.015 ? 'var(--success-fg)' : 'var(--danger-fg)';
    document.getElementById('bar_income').style.width = (i * 100) + '%';
    document.getElementById('bar_job').style.width = (j * 100) + '%';
    document.getElementById('bar_asset').style.width = (a * 100) + '%';
}
function syncFromNum(which) {
    var val = parseFloat(document.getElementById('num_' + which).value);
    document.getElementById('rng_' + which).value = val;
    syncWeight();
}
</script>
{% endblock %}""",
    'recommend_settings.html': """{% extends "base.html" %}
{% block content %}
<h1>대출 추천 알고리즘 설정</h1>

<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">Algorithm Guide</span>
            <h3 class="font-bold text-sm">대출 추천 알고리즘 설정</h3>
        </div>
        <div class="text-sm text-sub space-y-2">
            <p><strong>목적:</strong> 사용자에게 대출 상품을 추천할 때의 우선순위와 필터링 규칙을 정의합니다.</p>
            <p><strong>사용 방법:</strong>
                1. <strong>최대 추천 수:</strong> 사용자 화면에 보여줄 상품 개수를 제한합니다.<br>
                2. <strong>정렬 우선순위:</strong> '금리 낮은 순' 또는 '한도 높은 순' 중 기본 정렬 방식을 선택합니다.<br>
                3. <strong>금리 민감도:</strong> 신용 점수에 따라 금리가 변동되는 폭을 조절합니다. (1.0 = 기본)
            </p>
        </div>
    </div>
</div>

<div class="info-banner">이 설정은 사용자에게 노출되는 대출 추천 목록의 정렬 방식, 표시 개수, 조건 미달 시 처리 방법을 제어합니다. 변경 사항은 저장 즉시 추천 API에 적용됩니다.</div>

<form method="post">
    <div class="card card-p mb-6">
        <h3 class="card-title text-primary mt-0">추천 파라미터</h3>
        <div class="grid-2">
            <div>
                <label class="form-label">최대 추천 수</label>
                <input type="number" name="max_count" value="{{ max_count }}" min="1" max="20" class="form-input">
                <p class="help-text">사용자에게 보여줄 최대 추천 상품 수입니다. 권장: 3~7개.</p>
            </div>
            <div>
                <label class="form-label">정렬 우선순위</label>
                <select name="sort_priority" class="form-select">
                    <option value="rate" {% if sort_priority == 'rate' %}selected{% endif %}>예상 금리 낮은 순 (rate)</option>
                    <option value="limit" {% if sort_priority == 'limit' %}selected{% endif %}>대출 한도 높은 순 (limit)</option>
                </select>
                <p class="help-text">"금리 낮은 순"은 이자 부담 최소화, "한도 높은 순"은 대출 가능 금액 최대화 방향입니다.</p>
            </div>
            <div>
                <label class="form-label">Fallback 모드</label>
                <select name="fallback_mode" class="form-select">
                    <option value="show_all" {% if fallback_mode == 'show_all' %}selected{% endif %}>전체 상품 표시 (show_all)</option>
                    <option value="show_none" {% if fallback_mode == 'show_none' %}selected{% endif %}>빈 결과 반환 (show_none)</option>
                </select>
                <p class="help-text">희망 대출 금액을 지원하는 상품이 없을 때의 처리 방식입니다.</p>
            </div>
            <div>
                <label class="form-label">금리 스프레드 민감도</label>
                <input type="number" step="0.1" name="rate_sensitivity" value="{{ rate_sensitivity }}" min="0.1" max="3.0" class="form-input">
                <p class="help-text">1.0이 기본값입니다. 높을수록 신용 점수 차이에 따른 금리 차이가 커집니다.</p>
            </div>
        </div>
    </div>
    <div class="flex justify-end">
        <button type="submit" title="변경 사항을 저장합니다." class="btn-primary">설정 저장</button>
    </div>
</form>
{% endblock %}""",
    'products.html': """{% extends "base.html" %}
{% block content %}
<h1>대출 상품 관리</h1>

<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">운영 관리</span>
            <h3 class="font-bold text-sm">상품 노출 제어</h3>
        </div>
        <p class="text-sm text-sub">
            수집된 금융 상품 중 일시적으로 판매가 중단되거나 정책상 노출을 제한해야 하는 경우가 발생합니다. 관리자가 직접 상품의 노출 여부를 제어함으로써, 사용자에게 <strong>유효하고 정확한 정보</strong>만 제공되도록 관리합니다.
        </p>
    </div>
</div>

<div class="info-banner">수집된 대출 상품의 사용자 노출 여부를 관리합니다. 비노출 처리된 상품은 추천 결과에서 제외됩니다.</div>

<div class="summary-grid mb-6">
    <div class="summary-card" title="수집된 대출 상품의 전체 건수입니다.">
        <div class="summary-label">전체 상품</div>
        <div class="summary-value">{{ total_count }}</div>
    </div>
    <div class="summary-card" title="현재 사용자에게 노출 중인 상품 수입니다.">
        <div class="summary-label">노출 중</div>
        <div class="summary-value text-success">{{ visible_count }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">비노출</div>
        <div class="summary-value text-danger">{{ hidden_count }}</div>
    </div>
</div>

<div class="flex justify-between items-center mb-6 flex-wrap gap-2">
    <form method="get" class="flex gap-2 items-center flex-wrap">
        <input type="text" name="search" value="{{ search }}" placeholder="은행 또는 상품명 검색..." class="form-input w-auto min-w-200">
        <button type="submit" class="btn-accent">검색</button>
        {% if search %}<a href="/products" class="nav-btn">초기화</a>{% endif %}
    </form>
</div>

<div class="table-wrapper">
    <table class="w-full">
    </div>
</div>

<div class="table-wrapper">
    <table class="w-full">
        <thead><tr>
            <th>은행</th>
            <th>상품명</th>
            <th class="text-right">최저 금리</th>
            <th class="text-right">최고 금리</th>
            <th class="text-right">대출 한도</th>
            <th class="text-center">상태</th>
            <th class="text-center">관리</th>
        </tr></thead>
        <tbody>
            {% for p in products %}
            <tr>
                <td>{{ p.bank_name }}</td>
                <td class="font-bold">{{ p.product_name }}</td>
                <td class="text-right">{{ p.loan_rate_min }}%</td>
                <td class="text-right">{{ p.loan_rate_max }}%</td>
                <td class="text-right">{{ "{:,.0f}".format(p.loan_limit) }}원</td>
                <td class="text-center">
                    {% if p.is_visible == 1 %}
                        <span class="badge badge-success">노출</span>
                    {% else %}
                        <span class="badge badge-danger">비노출</span>
                    {% endif %}
                </td>
                <td class="text-center">
                    <form action="/products/toggle_visibility" method="post" class="form-inline">
                        <input type="hidden" name="bank_name" value="{{ p.bank_name }}">
                        <input type="hidden" name="product_name" value="{{ p.product_name }}">
                        <button type="submit" class="{{ 'btn-outline-danger' if p.is_visible == 1 else 'btn-outline-success' }}">
                            {{ '비노출 처리' if p.is_visible == 1 else '노출 처리' }}
                        </button>
                    </form>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="7" class="text-center text-sub p-4">등록된 상품이 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<div class="flex justify-between items-center mt-4">
    {% if page > 1 %}<a href="{{ url_for('products', page=page-1, search=search) }}" class="nav-btn">이전</a>
    {% else %}<span class="nav-btn" style="opacity: 0.5; cursor: default;">이전</span>{% endif %}
    <span class="text-sub font-bold">Page <span class="text-primary">{{ page }}</span> / {{ total_pages }}</span>
    {% if page < total_pages %}<a href="{{ url_for('products', page=page+1, search=search) }}" class="nav-btn">다음</a>
    {% else %}<span class="nav-btn" style="opacity: 0.5; cursor: default;">다음</span>{% endif %}
</div>
{% endblock %}""",
    'missions.html': """{% extends "base.html" %}
{% block content %}
<div class="flex justify-between items-center mb-2">
    <h1>미션 관리</h1>
    <a href="/missions/deletion-logs" class="nav-btn">
        🗑️ 삭제 로그 조회
        {% if deleted_count > 0 %}
        <span class="badge badge-danger" style="font-size: 0.75em; padding: 2px 6px;">{{ deleted_count }}</span>
        {% endif %}
    </a>
</div>

<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">행동 경제학 적용</span>
            <h3 class="font-bold text-sm">금융 행동 변화 유도 (Nudge)</h3>
        </div>
        <p class="text-sm text-sub">
            TrustFin은 단순히 대출을 추천하는 것을 넘어, 사용자가 <strong>더 나은 금융 조건</strong>을 갖추도록 돕습니다. AI가 분석한 사용자의 취약점(예: 낮은 신용점수, 부족한 자산)을 보완할 수 있는 구체적인 행동을 <strong>'미션'</strong> 형태로 제안합니다. <br>이 페이지에서는 생성된 미션들의 현황을 모니터링하여, 사용자들이 실제로 금융 행동을 변화시키고 있는지 파악합니다.
        </p>
    </div>
</div>

<div class="info-banner">AI가 유저의 대출 목적과 재무 상황을 바탕으로 자동 생성한 미션 목록입니다.</div>

<div class="summary-grid mb-6">
    <div class="summary-card">
        <div class="summary-label">전체 미션</div>
        <div class="summary-value">{{ total }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">대기(pending)</div>
        <div class="summary-value text-sub">{{ pending }}</div>
        <a href="{{ url_for('missions', status_filter='pending') }}" class="btn-tonal btn-sm mt-2" style="text-decoration: none; font-size: 0.75rem; padding: 4px 12px; height: auto;">모아보기</a>
    </div>
    <div class="summary-card">
        <div class="summary-label">진행(in_progress)</div>
        <div class="summary-value text-primary">{{ in_progress }}</div>
        <a href="{{ url_for('missions', status_filter='in_progress') }}" class="btn-tonal btn-sm mt-2" style="text-decoration: none; font-size: 0.75rem; padding: 4px 12px; height: auto;">모아보기</a>
    </div>
    <div class="summary-card">
        <div class="summary-label">완료(completed)</div>
        <div class="summary-value text-success">{{ completed }}</div>
        <a href="{{ url_for('missions', status_filter='completed') }}" class="btn-tonal btn-sm mt-2" style="text-decoration: none; font-size: 0.75rem; padding: 4px 12px; height: auto;">모아보기</a>
    </div>
    <div class="summary-card">
        <div class="summary-label">만료(expired)</div>
        <div class="summary-value text-danger">{{ expired }}</div>
        <a href="{{ url_for('missions', status_filter='expired') }}" class="btn-tonal btn-sm mt-2" style="text-decoration: none; font-size: 0.75rem; padding: 4px 12px; height: auto;">모아보기</a>
    </div>
    <div class="summary-card">
        <div class="summary-label">포기(given_up)</div>
        <div class="summary-value text-sub">{{ given_up }}</div>
        <a href="{{ url_for('missions', status_filter='given_up') }}" class="btn-tonal btn-sm mt-2" style="text-decoration: none; font-size: 0.75rem; padding: 4px 12px; height: auto;">모아보기</a>
    </div>
    <div class="summary-card" title="{{ type_completion_tooltip }}">
        <div class="summary-label">완료율</div>
        <div class="summary-value text-primary">{{ "%.1f" | format(completion_rate) }}%</div>
    </div>
</div>

<div class="card card-p mb-6">
    <h3 class="card-title text-primary text-sm mt-0">유형별 분포</h3>
    {% for type_name, count in type_counts.items() %}
    {% set rate = type_rates.get(type_name, 0) %}
    <div class="flex items-center mb-2 gap-2">
        <span style="width: 90px; font-size: 0.85rem; font-weight: 600; {{ 'color: var(--danger-fg);' if rate < 50 else '' }}" title="완료율: {{ '%.1f'|format(rate) }}%">{{ type_name }}</span>
        <div class="progress-track" style="flex: 1;">
            <div class="progress-fill" style="width: {{ (count / total * 100) if total > 0 else 0 }}%; {{ 'background-color: var(--danger-fg);' if rate < 50 else '' }}"></div>
        </div>
        <span style="width: 30px; text-align: right; font-size: 0.85rem;">{{ count }}</span>
    </div>
    {% endfor %}
</div>

<div class="card card-p mb-6">
    <h3 class="card-title text-primary text-sm mt-0 mb-4">유형별 상태 상세</h3>
    <div style="overflow-x: auto;">
        <table class="w-full" style="font-size: 0.85rem;">
            <thead>
                <tr>
                    <th style="background: transparent; padding-left: 4px;">유형</th>
                    <th class="text-center" style="background: transparent;">대기</th>
                    <th class="text-center" style="background: transparent;">진행</th>
                    <th class="text-center" style="background: transparent;">완료</th>
                    <th class="text-center" style="background: transparent;">만료</th>
                    <th class="text-center" style="background: transparent;">포기</th>
                    <th class="text-right" style="background: transparent;">완료율</th>
                    <th class="text-right" style="background: transparent; padding-right: 4px;">합계</th>
                </tr>
            </thead>
            <tbody>
                {% for type_name in type_counts.keys() %}
                {% set s_counts = type_status_counts.get(type_name, {}) %}
                {% set rate = type_rates.get(type_name, 0) %}
                <tr>
                    <td class="font-bold" style="padding-left: 4px;">{{ type_name }}</td>
                    <td class="text-center text-sub">{{ s_counts.get('pending', 0) }}</td>
                    <td class="text-center text-primary">{{ s_counts.get('in_progress', 0) }}</td>
                    <td class="text-center text-success">{{ s_counts.get('completed', 0) }}</td>
                    <td class="text-center text-danger">{{ s_counts.get('expired', 0) }}</td>
                    <td class="text-center text-muted">{{ s_counts.get('given_up', 0) }}</td>
                    <td class="text-right font-bold {{ 'text-danger' if rate < 50 else 'text-primary' }}">{{ "%.1f"|format(rate) }}%</td>
                    <td class="text-right font-bold" style="padding-right: 4px;">{{ type_counts.get(type_name, 0) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<form method="get" class="mb-4 bg-soft rounded-lg flex gap-2 items-center flex-wrap p-4">
    <span class="font-semibold text-sub">필터:</span>
    <select name="status_filter" class="form-select w-auto">
        <option value="">전체 상태</option>
        <option value="pending" {% if status_filter == 'pending' %}selected{% endif %}>대기 (pending)</option>
        <option value="in_progress" {% if status_filter == 'in_progress' %}selected{% endif %}>진행 (in_progress)</option>
        <option value="completed" {% if status_filter == 'completed' %}selected{% endif %}>완료 (completed)</option>
        <option value="expired" {% if status_filter == 'expired' %}selected{% endif %}>만료 (expired)</option>
        <option value="given_up" {% if status_filter == 'given_up' %}selected{% endif %}>포기 (given_up)</option>
    </select>
    <select name="type_filter" class="form-select w-auto">
        <option value="">전체 유형</option>
        <option value="savings" {% if type_filter == 'savings' %}selected{% endif %}>savings (저축)</option>
        <option value="spending" {% if type_filter == 'spending' %}selected{% endif %}>spending (지출 절감)</option>
        <option value="credit" {% if type_filter == 'credit' %}selected{% endif %}>credit (신용 관리)</option>
        <option value="investment" {% if type_filter == 'investment' %}selected{% endif %}>investment (투자)</option>
        <option value="lifestyle" {% if type_filter == 'lifestyle' %}selected{% endif %}>lifestyle (생활 습관)</option>
    </select>
    <select name="difficulty_filter" class="form-select w-auto">
        <option value="">전체 난이도</option>
        <option value="easy" {% if difficulty_filter == 'easy' %}selected{% endif %}>easy (쉬움)</option>
        <option value="medium" {% if difficulty_filter == 'medium' %}selected{% endif %}>medium (보통)</option>
        <option value="hard" {% if difficulty_filter == 'hard' %}selected{% endif %}>hard (어려움)</option>
    </select>
    <button type="submit" class="btn-primary">적용</button>
    {% if status_filter or type_filter or difficulty_filter %}
        <a href="/missions" class="nav-btn">초기화</a>
    {% endif %}
</form>

<form method="post" id="bulkForm">
    <input type="hidden" name="change_reason" id="hidden_change_reason">
    <input type="hidden" name="delete_reason" id="hidden_delete_reason">
    <div class="flex justify-between items-center mb-2">
        <div class="flex gap-2 items-center">
            <select name="new_status" id="new_status_select" class="form-select py-1 h-8 text-sm w-auto">
                <option value="">상태 변경...</option>
                <option value="pending">pending</option>
                <option value="in_progress">in_progress</option>
                <option value="completed">completed</option>
                <option value="expired">expired</option>
                <option value="given_up">given_up</option>
            </select>
            <button type="button" onclick="openBulkUpdateModal()" class="btn-tonal btn-sm">일괄 변경</button>
        </div>
        <button type="button" onclick="openBulkDeleteModal()" class="btn-outline-danger btn-sm">선택 삭제</button>
    </div>
    <div class="table-wrapper">
        <table class="w-full">
            <thead><tr>
                <th class="text-center" style="width: 40px;"><input type="checkbox" onclick="toggleAll(this)"></th>
            <th>ID</th>
            <th>유저</th>
            <th>미션 제목</th>
            <th>유형</th>
            <th>대출 목적</th>
            <th>상태</th>
            <th>
                <a href="{{ url_for('missions', sort_by='difficulty', order='desc' if sort_by == 'difficulty' and order == 'asc' else 'asc', status_filter=status_filter, type_filter=type_filter, difficulty_filter=difficulty_filter) }}" style="text-decoration: none; color: inherit;">
                    난이도 {% if sort_by == 'difficulty' %}<span class="text-primary">{{ '▲' if order == 'asc' else '▼' }}</span>{% endif %}
                </a>
            </th>
            <th>
                <a href="{{ url_for('missions', sort_by='reward_points', order='asc' if sort_by == 'reward_points' and order == 'desc' else 'desc', status_filter=status_filter, type_filter=type_filter, difficulty_filter=difficulty_filter) }}" style="text-decoration: none; color: inherit;">
                    포인트 {% if sort_by == 'reward_points' %}<span class="text-primary">{{ '▲' if order == 'asc' else '▼' }}</span>{% endif %}
                </a>
            </th>
            <th>마감일</th>
        </tr></thead>
        <tbody>
            {% for m in missions %}
            <tr>
                <td class="text-center"><input type="checkbox" name="mission_ids" value="{{ m.mission_id }}"></td>
                <td>{{ m.mission_id }}</td>
                <td>{{ m.user_id }}</td>
                <td class="font-bold">
                    <a href="/missions/{{ m.mission_id }}" class="text-primary" style="text-decoration: none;">{{ m.mission_title }}</a>
                </td>
                <td><span class="badge badge-info">{{ m.mission_type }}</span></td>
                <td>{{ m.loan_purpose or '-' }}</td>
                <td>
                    {% if m.status == 'completed' %}
                        <span class="badge badge-success">completed</span>
                    {% elif m.status == 'in_progress' %}
                        <span class="badge badge-info">in_progress</span>
                    {% elif m.status == 'expired' %}
                        <span class="badge badge-danger">expired</span>
                    {% elif m.status == 'given_up' %}
                        <span class="badge badge-neutral">given_up</span>
                    {% else %}
                        <span class="badge badge-warning">pending</span>
                    {% endif %}
                </td>
                <td>{{ m.difficulty }}</td>
                <td>{{ m.reward_points }}</td>
                <td>{{ m.due_date or '-' }}</td>
            </tr>
            {% else %}
            <tr><td colspan="10" class="text-center text-sub p-4">미션이 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
</form>

<div class="flex justify-between items-center mt-4">
    {% if page > 1 %}<a href="{{ url_for('missions', page=page-1, status_filter=status_filter, type_filter=type_filter, difficulty_filter=difficulty_filter, sort_by=sort_by, order=order) }}" class="nav-btn">이전</a>
    {% else %}<span class="nav-btn" style="opacity: 0.5; cursor: default;">이전</span>{% endif %}
    <span class="text-sub font-bold">Page <span class="text-primary">{{ page }}</span> / {{ total_pages }}</span>
    {% if page < total_pages %}<a href="{{ url_for('missions', page=page+1, status_filter=status_filter, type_filter=type_filter, difficulty_filter=difficulty_filter, sort_by=sort_by, order=order) }}" class="nav-btn">다음</a>
    {% else %}<span class="nav-btn" style="opacity: 0.5; cursor: default;">다음</span>{% endif %}
</div>

<!-- Bulk Update Modal -->
<div id="bulkUpdateModal" class="modal-overlay hidden" onclick="if(event.target === this) closeBulkUpdateModal()">
    <div class="modal-content" style="max-width: 500px;">
        <div class="modal-header">
            <h3>일괄 상태 변경</h3>
            <button onclick="closeBulkUpdateModal()" class="close-btn">&times;</button>
        </div>
        <div class="modal-body">
            <p class="mb-4">선택한 미션의 상태를 <span id="modalStatusDisplay" class="font-bold text-primary"></span>(으)로 변경합니다.</p>
            <div class="form-group">
                <label class="form-label">변경 사유 (History 기록)</label>
                <textarea id="modalReasonInput" class="form-textarea" rows="3" placeholder="예: 정책 변경으로 인한 일괄 처리"></textarea>
            </div>
            <div class="flex justify-end gap-2">
                <button onclick="closeBulkUpdateModal()" class="btn-tonal">취소</button>
                <button onclick="submitBulkUpdate()" class="btn-primary">변경 확정</button>
            </div>
        </div>
    </div>
</div>

<!-- Bulk Delete Modal -->
<div id="bulkDeleteModal" class="modal-overlay hidden" onclick="if(event.target === this) closeBulkDeleteModal()">
    <div class="modal-content" style="max-width: 500px;">
        <div class="modal-header">
            <h3 class="text-danger">일괄 삭제</h3>
            <button onclick="closeBulkDeleteModal()" class="close-btn">&times;</button>
        </div>
        <div class="modal-body">
            <div class="warn-banner mb-4">선택한 미션을 정말 삭제하시겠습니까? 삭제된 데이터는 복구할 수 없습니다.</div>
            <div class="form-group">
                <label class="form-label">삭제 사유 (필수)</label>
                <textarea id="modalDeleteReasonInput" class="form-textarea" rows="3" placeholder="예: 기간 만료 데이터 정리"></textarea>
            </div>
            <div class="flex justify-end gap-2">
                <button onclick="closeBulkDeleteModal()" class="btn-tonal">취소</button>
                <button onclick="submitBulkDelete()" class="btn-outline-danger">삭제 확정</button>
            </div>
        </div>
    </div>
</div>

<script>
function toggleAll(source) {
    var checkboxes = document.getElementsByName('mission_ids');
    for(var i=0, n=checkboxes.length;i<n;i++) {
        checkboxes[i].checked = source.checked;
    }
}

function openBulkUpdateModal() {
    var statusSelect = document.getElementById('new_status_select');
    var selectedStatus = statusSelect.value;
    if (!selectedStatus) { alert('변경할 상태를 선택해주세요.'); return; }
    var checkboxes = document.querySelectorAll('input[name="mission_ids"]:checked');
    if (checkboxes.length === 0) { alert('변경할 미션을 선택해주세요.'); return; }
    document.getElementById('modalStatusDisplay').textContent = selectedStatus;
    document.getElementById('bulkUpdateModal').classList.remove('hidden');
    document.getElementById('modalReasonInput').focus();
}
function closeBulkUpdateModal() { document.getElementById('bulkUpdateModal').classList.add('hidden'); }
function submitBulkUpdate() {
    var reason = document.getElementById('modalReasonInput').value;
    if (!reason.trim()) { alert('변경 사유를 입력해주세요.'); return; }
    document.getElementById('hidden_change_reason').value = reason;
    var form = document.getElementById('bulkForm');
    form.action = "/missions/bulk_update_status";
    form.submit();
}

function openBulkDeleteModal() {
    var checkboxes = document.querySelectorAll('input[name="mission_ids"]:checked');
    if (checkboxes.length === 0) { alert('삭제할 미션을 선택해주세요.'); return; }
    document.getElementById('bulkDeleteModal').classList.remove('hidden');
    document.getElementById('modalDeleteReasonInput').focus();
}
function closeBulkDeleteModal() { document.getElementById('bulkDeleteModal').classList.add('hidden'); }
function submitBulkDelete() {
    var reason = document.getElementById('modalDeleteReasonInput').value;
    if (!reason.trim()) { alert('삭제 사유를 입력해주세요.'); return; }
    document.getElementById('hidden_delete_reason').value = reason;
    var form = document.getElementById('bulkForm');
    form.action = "/missions/bulk_delete";
    form.submit();
}
</script>
{% endblock %}""",
    'mission_deletion_logs.html': """{% extends "base.html" %}
{% block content %}
<h1>삭제된 미션 로그</h1>
<a href="/missions" class="nav-btn mb-4">미션 목록으로 돌아가기</a>

<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">Audit Log</span>
            <h3 class="font-bold text-sm">삭제 이력 감사</h3>
        </div>
        <p class="text-sm text-sub">
            삭제된 미션의 상세 정보와 삭제 사유를 조회합니다. 이는 데이터 복구 요청 대응이나 운영 감사를 위한 백업 데이터입니다.
        </p>
    </div>
</div>

<div class="table-wrapper">
    <table class="w-full">
        <thead><tr>
            <th>Log ID</th>
            <th>Mission ID</th>
            <th>User ID</th>
            <th>미션 제목</th>
            <th>유형</th>
            <th>삭제 전 상태</th>
            <th>포인트</th>
            <th>삭제 사유</th>
            <th>삭제자</th>
            <th>삭제 일시</th>
        </tr></thead>
        <tbody>
            {% for log in logs %}
            <tr>
                <td>{{ log.log_id }}</td>
                <td>{{ log.mission_id }}</td>
                <td>{{ log.user_id }}</td>
                <td class="font-bold">{{ log.mission_title }}</td>
                <td><span class="badge badge-neutral">{{ log.mission_type }}</span></td>
                <td>{{ log.status }}</td>
                <td>{{ log.reward_points }}</td>
                <td class="text-danger">{{ log.delete_reason }}</td>
                <td>{{ log.admin_id }}</td>
                <td>{{ log.deleted_at }}</td>
            </tr>
            {% else %}
            <tr><td colspan="10" class="text-center text-sub p-4">삭제 로그가 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}""",
    'mission_detail.html': """{% extends "base.html" %}
{% block content %}
<h1>미션 상세</h1>
<a href="/missions" class="nav-btn mb-4">목록으로 돌아가기</a>
<div class="info-banner">미션 상세 정보입니다. 이 페이지는 읽기 전용이며, 미션 상태는 시스템에 의해 자동으로 관리됩니다.</div>

<div class="card card-p">
    <div class="flex justify-between items-start mb-4">
        <h3 class="card-title text-primary mt-0">미션 정보</h3>
        {% if mission.status in ['pending', 'in_progress'] %}
        <form action="/missions/{{ mission.mission_id }}/complete" method="post" onsubmit="return confirm('미션을 강제 완료 처리하고 포인트를 지급하시겠습니까?');">
            <button type="submit" class="btn-primary btn-sm">미션 완료 처리 (포인트 지급)</button>
        </form>
        {% endif %}
    </div>
    <table class="w-full">
        <tr><td class="font-bold text-sub w-150">Mission ID</td><td>{{ mission.mission_id }}</td></tr>
        <tr><td class="font-bold text-sub">유저 ID</td><td>{{ mission.user_id }}</td></tr>
        <tr>
            <td class="font-bold text-sub">미션 제목</td>
            <td>
                <form action="/missions/{{ mission.mission_id }}/update_title" method="post" class="flex gap-2 items-center">
                    <input type="text" name="mission_title" value="{{ mission.mission_title }}" class="form-input py-1 h-8 text-sm w-full" required>
                    <button type="submit" class="btn-tonal btn-sm">변경</button>
                </form>
            </td>
        </tr>
        <tr>
            <td class="font-bold text-sub">미션 설명</td>
            <td>
                <form action="/missions/{{ mission.mission_id }}/update_description" method="post" class="flex gap-2 items-start">
                    <textarea name="mission_description" class="form-textarea py-1 text-sm w-full" rows="2">{{ mission.mission_description or '' }}</textarea>
                    <button type="submit" class="btn-tonal btn-sm mt-1">변경</button>
                </form>
            </td>
        </tr>
        <tr>
            <td class="font-bold text-sub">유형</td>
            <td>
                <form action="/missions/{{ mission.mission_id }}/update_type" method="post" class="flex gap-2 items-center">
                    <select name="mission_type" class="form-select py-1 h-8 text-sm w-auto">
                        <option value="savings" {% if mission.mission_type == 'savings' %}selected{% endif %}>savings (저축)</option>
                        <option value="spending" {% if mission.mission_type == 'spending' %}selected{% endif %}>spending (지출)</option>
                        <option value="credit" {% if mission.mission_type == 'credit' %}selected{% endif %}>credit (신용)</option>
                        <option value="investment" {% if mission.mission_type == 'investment' %}selected{% endif %}>investment (투자)</option>
                        <option value="lifestyle" {% if mission.mission_type == 'lifestyle' %}selected{% endif %}>lifestyle (생활)</option>
                    </select>
                    <button type="submit" class="btn-tonal btn-sm">변경</button>
                </form>
            </td>
        </tr>
        <tr>
            <td class="font-bold text-sub">자동 달성 조건</td>
            <td>
                <form action="/missions/{{ mission.mission_id }}/update_tracking" method="post" class="flex gap-2 items-center flex-wrap">
                    <select name="tracking_key" class="form-select py-1 h-8 text-sm w-auto">
                        <option value="">(없음)</option>
                        <option value="credit_score" {% if mission.tracking_key == 'credit_score' %}selected{% endif %}>credit_score (신용점수)</option>
                        <option value="dsr" {% if mission.tracking_key == 'dsr' %}selected{% endif %}>dsr (DSR)</option>
                        <option value="cardUsageRate" {% if mission.tracking_key == 'cardUsageRate' %}selected{% endif %}>cardUsageRate (카드사용률)</option>
                        <option value="delinquency" {% if mission.tracking_key == 'delinquency' %}selected{% endif %}>delinquency (연체)</option>
                        <option value="salaryTransfer" {% if mission.tracking_key == 'salaryTransfer' %}selected{% endif %}>salaryTransfer (급여이체)</option>
                        <option value="highInterestLoan" {% if mission.tracking_key == 'highInterestLoan' %}selected{% endif %}>highInterestLoan (고금리대출)</option>
                        <option value="minusLimit" {% if mission.tracking_key == 'minusLimit' %}selected{% endif %}>minusLimit (마이너스통장)</option>
                        <option value="openBanking" {% if mission.tracking_key == 'openBanking' %}selected{% endif %}>openBanking (오픈뱅킹)</option>
                        <option value="checkedCredit" {% if mission.tracking_key == 'checkedCredit' %}selected{% endif %}>checkedCredit (신용조회)</option>
                        <option value="checkedMembership" {% if mission.tracking_key == 'checkedMembership' %}selected{% endif %}>checkedMembership (멤버십확인)</option>
                    </select>
                    <select name="tracking_operator" class="form-select py-1 h-8 text-sm w-auto">
                        <option value="">(연산자)</option>
                        <option value="eq" {% if mission.tracking_operator == 'eq' %}selected{% endif %}>= (일치)</option>
                        <option value="gte" {% if mission.tracking_operator == 'gte' %}selected{% endif %}>&gt;= (이상)</option>
                        <option value="lte" {% if mission.tracking_operator == 'lte' %}selected{% endif %}>&lt;= (이하)</option>
                        <option value="gt" {% if mission.tracking_operator == 'gt' %}selected{% endif %}>&gt; (초과)</option>
                        <option value="lt" {% if mission.tracking_operator == 'lt' %}selected{% endif %}>&lt; (미만)</option>
                    </select>
                    <input type="number" step="0.1" name="tracking_value" value="{{ mission.tracking_value }}" class="form-input py-1 h-8 text-sm w-auto" style="width: 80px;" placeholder="값">
                    <button type="submit" class="btn-tonal btn-sm">변경</button>
                </form>
            </td>
        </tr>
        <tr>
            <td class="font-bold text-sub">대출 목적</td>
            <td>
                <form action="/missions/{{ mission.mission_id }}/update_purpose" method="post" class="flex gap-2 items-center">
                    <input type="text" name="loan_purpose" value="{{ mission.loan_purpose or '' }}" class="form-input py-1 h-8 text-sm w-auto" placeholder="예: 생활안정자금">
                    <button type="submit" class="btn-tonal btn-sm">변경</button>
                </form>
            </td>
        </tr>
        <tr>
            <td class="font-bold text-sub">상태</td>
            <td>
                <form action="/missions/{{ mission.mission_id }}/update_status" method="post" class="flex gap-2 items-center">
                    <select name="status" class="form-select py-1 h-8 text-sm w-auto">
                        <option value="pending" {% if mission.status == 'pending' %}selected{% endif %}>pending (대기)</option>
                        <option value="in_progress" {% if mission.status == 'in_progress' %}selected{% endif %}>in_progress (진행)</option>
                        <option value="completed" {% if mission.status == 'completed' %}selected{% endif %}>completed (완료)</option>
                        <option value="expired" {% if mission.status == 'expired' %}selected{% endif %}>expired (만료)</option>
                        <option value="given_up" {% if mission.status == 'given_up' %}selected{% endif %}>given_up (포기)</option>
                    </select>
                    <button type="submit" class="btn-tonal btn-sm">변경</button>
                </form>
            </td>
        </tr>
        <tr>
            <td class="font-bold text-sub">난이도</td>
            <td>
                <form action="/missions/{{ mission.mission_id }}/update_difficulty" method="post" class="flex gap-2 items-center">
                    <select name="difficulty" class="form-select py-1 h-8 text-sm w-auto">
                        <option value="easy" {% if mission.difficulty == 'easy' %}selected{% endif %}>easy</option>
                        <option value="medium" {% if mission.difficulty == 'medium' %}selected{% endif %}>medium</option>
                        <option value="hard" {% if mission.difficulty == 'hard' %}selected{% endif %}>hard</option>
                    </select>
                    <button type="submit" class="btn-tonal btn-sm">변경</button>
                </form>
            </td>
        </tr>
        <tr>
            <td class="font-bold text-sub">보상 포인트</td>
            <td>
                <form action="/missions/{{ mission.mission_id }}/update_reward" method="post" class="flex gap-2 items-center">
                    <input type="number" name="reward_points" value="{{ mission.reward_points }}" class="form-input py-1 h-8 text-sm w-auto" style="width: 100px;">
                    <button type="submit" class="btn-tonal btn-sm">변경</button>
                </form>
            </td>
        </tr>
        <tr>
            <td class="font-bold text-sub">마감일</td>
            <td>
                <form action="/missions/{{ mission.mission_id }}/update_duedate" method="post" class="flex gap-2 items-center">
                    <input type="date" name="due_date" value="{{ mission.due_date }}" class="form-input py-1 h-8 text-sm w-auto">
                    <button type="submit" class="btn-tonal btn-sm">변경</button>
                </form>
            </td>
        </tr>
        <tr><td class="font-bold text-sub">완료일</td><td>{{ mission.completed_at or '-' }}</td></tr>
        <tr><td class="font-bold text-sub">생성일</td><td>{{ mission.created_at }}</td></tr>
    </table>
</div>

<div class="card card-p mt-6">
    <div class="flex justify-between items-center mb-4">
        <h3 class="card-title text-primary mt-0">동일 미션 수행 유저 ({{ related_users|length }}명)</h3>
        <a href="/missions/{{ mission.mission_id }}/download_related" class="btn-tonal btn-sm" title="목록을 CSV로 다운로드">CSV 다운로드</a>
    </div>
    <div class="table-wrapper">
        <table class="w-full">
            <thead><tr>
                <th>User ID</th>
                <th class="text-center">상태</th>
                <th>시작일</th>
                <th>완료일</th>
                <th class="text-center">상세</th>
            </tr></thead>
            <tbody>
                {% for u in related_users %}
                <tr class="{{ 'bg-soft' if u.mission_id == mission.mission_id else '' }}">
                    <td class="font-bold">{{ u.user_id }}</td>
                    <td class="text-center">
                        {% if u.status == 'completed' %}
                            <span class="badge badge-success">completed</span>
                        {% elif u.status == 'in_progress' %}
                            <span class="badge badge-info">in_progress</span>
                        {% elif u.status == 'expired' %}
                            <span class="badge badge-danger">expired</span>
                        {% elif u.status == 'given_up' %}
                            <span class="badge badge-neutral">given_up</span>
                        {% else %}
                            <span class="badge badge-warning">pending</span>
                        {% endif %}
                    </td>
                    <td>{{ u.created_at }}</td>
                    <td>{{ u.completed_at or '-' }}</td>
                    <td class="text-center">
                        {% if u.mission_id != mission.mission_id %}
                        <a href="/missions/{{ u.mission_id }}" class="btn-tonal btn-sm">이동</a>
                        {% else %}
                        <span class="text-xs text-muted">현재 보고중</span>
                        {% endif %}
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="5" class="text-center text-sub p-4">수행 중인 다른 유저가 없습니다.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<div class="card card-p mt-6">
    <h3 class="card-title text-primary mt-0 mb-4">변경 이력 (History)</h3>
    <div class="table-wrapper">
        <table class="w-full">
            <thead><tr>
                <th>일시</th>
                <th>관리자</th>
                <th>유형</th>
                <th>내용</th>
            </tr></thead>
            <tbody>
                {% for h in history %}
                <tr>
                    <td class="text-sub">{{ h.created_at }}</td>
                    <td>{{ h.admin_id }}</td>
                    <td><span class="badge badge-neutral">{{ h.change_type }}</span></td>
                    <td>{{ h.description }}</td>
                </tr>
                {% else %}
                <tr><td colspan="4" class="text-center text-sub p-4">변경 이력이 없습니다.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<div class="card card-p mt-6 border-danger">
    <h3 class="card-title text-danger text-sm mt-0 mb-3">미션 삭제</h3>
    <div class="warn-banner">삭제된 미션은 복구할 수 없습니다.</div>
    <form action="/missions/{{ mission.mission_id }}/delete" method="post" onsubmit="return confirm('정말 이 미션을 삭제하시겠습니까?');">
        <button type="submit" class="w-full btn-outline-danger">미션 삭제</button>
    </form>
</div>
{% endblock %}""",
    'points.html': """{% extends "base.html" %}
{% block content %}
<h1>포인트 생애주기 관리</h1>

<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">Tokenomics</span>
            <h3 class="font-bold text-sm">포인트 순환 구조 (Lifecycle)</h3>
        </div>
        <div class="text-sm text-sub space-y-2">
            <p>TrustFin 포인트 시스템은 <strong>발행(Minting) → 지급(Allocation) → 유통(Circulation) → 소각(Burn)</strong>의 생애주기를 가집니다.</p>
            <ul style="list-style-type: disc; padding-left: 20px; margin: 0;">
                <li><strong>지급 (Earning):</strong> 미션 달성 시 시스템 풀에서 사용자에게 포인트가 지급됩니다. (동기 부여)</li>
                <li><strong>사용 (Spending):</strong> 포인트 상품 구매 시 포인트가 회수되어 소각됩니다. (가치 실현)</li>
                <li><strong>소멸/회수 (Expiration/Clawback):</strong> 유효기간 만료 또는 어뷰징 적발 시 포인트를 회수하여 총 유통량을 조절합니다.</li>
            </ul>
        </div>
    </div>
</div>

<div class="info-banner">전체 포인트의 공급량과 유통량을 모니터링하고, 개별 유저의 포인트 흐름을 제어합니다.</div>

<form method="get" class="mb-6 bg-soft rounded-lg flex gap-2 items-center flex-wrap p-4">
    <span class="font-semibold text-sub">기간 설정:</span>
    <input type="date" name="start_date" value="{{ start_date or '' }}" class="form-input w-auto">
    <span class="text-sub">~</span>
    <input type="date" name="end_date" value="{{ end_date or '' }}" class="form-input w-auto">
    <input type="text" name="search_user" value="{{ search_user }}" placeholder="유저 ID 검색" class="form-input w-auto">
    <button type="submit" class="btn-primary">조회</button>
    <a href="/points" class="nav-btn">전체 기간</a>
</form>

<div class="summary-grid mb-6">
    <div class="summary-card">
        <div class="summary-label">총 발행량 (Minted)</div>
        <div class="summary-value text-success">{{ "{:,}".format(total_minted) }}</div>
        <p class="help-text">지급된 포인트 총액</p>
    </div>
    <div class="summary-card">
        <div class="summary-label">현재 유통량 (Circulating)</div>
        <div class="summary-value text-primary">{{ "{:,}".format(total_balance) }}</div>
        <p class="help-text">현재 유저 보유 잔액 (Snapshot)</p>
    </div>
    <div class="summary-card">
        <div class="summary-label">총 사용 (Spent)</div>
        <div class="summary-value text-danger">{{ "{:,}".format(total_spent_purchase) }}</div>
        <p class="help-text">상품 구매로 소각된 포인트</p>
    </div>
    <div class="summary-card">
        <div class="summary-label">기타 감소 (Clawback/Expired)</div>
        <div class="summary-value text-sub">{{ "{:,}".format(total_clawback + total_expired) }}</div>
        <p class="help-text" title="회수: {{ '{:,}'.format(total_clawback) }} / 소멸: {{ '{:,}'.format(total_expired) }}">
            회수: {{ "{:,}".format(total_clawback) }} / 소멸: {{ "{:,}".format(total_expired) }}</p>
    </div>
    <div class="summary-card">
        <div class="summary-label">참여 유저 수</div>
        <div class="summary-value">{{ user_count }}</div>
        <p class="help-text">포인트 시스템 활성 유저</p>
    </div>
</div>

<div class="card card-p mb-6">
    <h3 class="card-title text-primary mt-0">포인트 유동성 제어 (Manual Control)</h3>
    <div class="warn-banner">특정 유저에게 포인트를 추가 지급(Mint)하거나, 보유 포인트를 회수(Burn)합니다.</div>
    <form method="post" action="/points/adjust" class="grid-3 gap-4 items-end">
        <div>
            <label class="form-label text-sm">대상 유저 ID</label>
            <input type="text" name="user_id" placeholder="예: user_001" required class="form-input">
        </div>
        <div>
            <label class="form-label text-sm">조정 금액</label>
            <input type="number" name="amount" placeholder="양수: 지급 / 음수: 회수" required class="form-input">
        </div>
        <div>
            <label class="form-label text-sm">조정 사유 (Audit Log)</label>
            <input type="text" name="reason" placeholder="예: 시스템 오류 보상, 어뷰징 회수" required class="form-input">
        </div>
        <div class="col-span-3 flex justify-end mt-2" style="grid-column: span 3;">
            <button type="submit" class="btn-primary">실행</button>
        </div>
    </form>
</div>

<div class="table-wrapper">
    <div class="flex justify-between items-center mb-4">
        <h3 class="card-title text-sm mt-0">유저별 보유 현황</h3>
    </div>
    <table class="w-full">
        <thead><tr>
            <th>유저 ID</th>
            <th class="text-right">보유 잔액 (Balance)</th>
            <th class="text-right">누적 획득 (Earned)</th>
            <th class="text-right">누적 사용 (Spent)</th>
            <th>최근 변동일</th>
            <th class="text-center">상세 내역</th>
        </tr></thead>
        <tbody>
            {% for u in users %}
            <tr>
                <td class="font-bold">{{ u.user_id }}</td>
                <td class="text-right font-bold text-primary">{{ "{:,}".format(u.balance) }}</td>
                <td class="text-right text-success">+{{ "{:,}".format(u.total_earned) }}</td>
                <td class="text-right text-danger">-{{ "{:,}".format(u.total_spent) }}</td>
                <td>{{ u.updated_at if u.updated_at else '-' }}</td>
                <td class="text-center">
                    <a href="/points/{{ u.user_id }}" class="btn-tonal btn-sm">Transaction</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="6" class="text-center text-sub p-4">포인트 데이터가 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<div class="flex justify-between items-center mt-4">
    {% if page > 1 %}<a href="{{ url_for('points', page=page-1, start_date=start_date, end_date=end_date, search_user=search_user) }}" class="nav-btn">이전</a>
    {% else %}<span class="nav-btn" style="opacity: 0.5; cursor: default;">이전</span>{% endif %}
    <span class="text-sub font-bold">Page <span class="text-primary">{{ page }}</span> / {{ total_pages }}</span>
    {% if page < total_pages %}<a href="{{ url_for('points', page=page+1, start_date=start_date, end_date=end_date, search_user=search_user) }}" class="nav-btn">다음</a>
    {% else %}<span class="nav-btn" style="opacity: 0.5; cursor: default;">다음</span>{% endif %}
</div>
{% endblock %}""",
    'point_detail.html': """{% extends "base.html" %}
{% block content %}
<h1>포인트 상세 - {{ user_id }}</h1>
<a href="/points" class="nav-btn mb-4">목록으로 돌아가기</a>
<div class="info-banner">해당 유저의 포인트 잔액과 전체 거래 내역을 확인할 수 있습니다.</div>

<div class="summary-grid mb-6">
    <div class="summary-card">
        <div class="summary-label">현재 잔액</div>
        <div class="summary-value">{{ "{:,}".format(user.balance) }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">총 지급</div>
        <div class="summary-value text-success">{{ "{:,}".format(user.total_earned) }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">총 사용</div>
        <div class="summary-value text-danger">{{ "{:,}".format(user.total_spent) }}</div>
    </div>
</div>

<div class="table-wrapper">
    <h3 class="card-title text-primary text-sm mb-3">거래 내역</h3>
    <table class="w-full">
        <thead><tr>
            <th>ID</th>
            <th class="text-right">금액</th>
            <th>유형</th>
            <th>사유</th>
            <th>관리자</th>
            <th>참조 ID</th>
            <th>일시</th>
        </tr></thead>
        <tbody>
            {% for t in transactions %}
            <tr>
                <td>{{ t.transaction_id }}</td>
                <td class="text-right font-bold {{ 'text-success' if t.amount > 0 else 'text-danger' }}">{{ '{:+,}'.format(t.amount) }}</td>
                <td>
                    {% if t.transaction_type == 'mission_reward' %}
                        <span class="badge badge-success">mission_reward</span>
                    {% elif t.transaction_type == 'purchase' %}
                        <span class="badge badge-danger">purchase</span>
                    {% elif t.transaction_type == 'manual' %}
                        <span class="badge badge-info">manual</span>
                    {% elif t.transaction_type == 'expired' %}
                        <span class="badge badge-neutral">expired</span>
                    {% else %}
                        <span class="badge badge-neutral">{{ t.transaction_type }}</span>
                    {% endif %}
                </td>
                <td>{{ t.reason or '-' }}</td>
                <td>{{ t.admin_id or '-' }}</td>
                <td>{{ t.reference_id or '-' }}</td>
                <td>{{ t.created_at }}</td>
            </tr>
            {% else %}
            <tr><td colspan="7" class="text-center text-sub p-4">거래 내역이 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}""",
    'point_products.html': """{% extends "base.html" %}
{% block content %}
<h1>포인트 상품 관리</h1>

<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">순환 구조</span>
            <h3 class="font-bold text-sm">포인트의 실질적 가치</h3>
        </div>
        <p class="text-sm text-sub">
            획득한 포인트가 단순한 숫자에 그치지 않고, 실제 생활에 유용한 혜택(쿠폰, 금리 할인권 등)으로 교환될 수 있어야 합니다. 이러한 <strong>선순환 구조</strong>는 사용자가 TrustFin 생태계에 머무르게 하는 핵심 요인이 됩니다.
        </p>
    </div>
</div>

<div class="info-banner">포인트로 교환 가능한 상품을 등록하고 관리합니다.</div>

<div class="summary-grid mb-6">
    <div class="summary-card">
        <div class="summary-label">전체 상품</div>
        <div class="summary-value">{{ total_count }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">활성 상품</div>
        <div class="summary-value text-success">{{ active_count }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">비활성 상품</div>
        <div class="summary-value text-danger">{{ inactive_count }}</div>
    </div>
</div>

<div class="flex gap-2 mb-6">
    <a href="/point-products/add" class="btn-accent">상품 추가</a>
    <a href="/point-products/purchases" class="nav-btn">구매 내역 조회</a>
</div>

<div class="table-wrapper">
    <table class="w-full">
        <thead><tr>
            <th>ID</th>
            <th>상품명</th>
            <th>유형</th>
            <th class="text-right">포인트 가격</th>
            <th class="text-right">재고</th>
            <th class="text-center">상태</th>
            <th class="text-center">관리</th>
        </tr></thead>
        <tbody>
            {% for p in products %}
            <tr>
                <td>{{ p.product_id }}</td>
                <td class="font-bold">{{ p.product_name }}</td>
                <td><span class="badge badge-info">{{ p.product_type }}</span></td>
                <td class="text-right font-bold">{{ "{:,}".format(p.point_cost) }}P</td>
                <td class="text-right {{ 'text-danger font-bold' if p.stock_quantity <= 5 else '' }}">{{ p.stock_quantity }}{{ ' (부족)' if p.stock_quantity <= 5 else '' }}</td>
                <td class="text-center">
                    {% if p.is_active == 1 %}
                        <span class="badge-on">활성</span>
                    {% else %}
                        <span class="badge-off">비활성</span>
                    {% endif %}
                </td>
                <td class="text-center">
                    <div class="flex gap-2 justify-center">
                        <a href="/point-products/{{ p.product_id }}/edit" class="btn-tonal btn-sm">수정</a>
                        <form action="/point-products/{{ p.product_id }}/toggle" method="post" class="form-inline">
                            <button type="submit" class="{{ 'btn-outline-danger' if p.is_active == 1 else 'btn-outline-success' }}">
                                {{ '비활성' if p.is_active == 1 else '활성' }}
                            </button>
                        </form>
                    </div>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="7" class="text-center text-sub p-4">등록된 상품이 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<div class="flex justify-between items-center mt-4">
    {% if page > 1 %}<a href="{{ url_for('point_products', page=page-1) }}" class="nav-btn">이전</a>
    {% else %}<span class="nav-btn" style="opacity: 0.5; cursor: default;">이전</span>{% endif %}
    <span class="text-sub font-bold">Page <span class="text-primary">{{ page }}</span> / {{ total_pages }}</span>
    {% if page < total_pages %}<a href="{{ url_for('point_products', page=page+1) }}" class="nav-btn">다음</a>
    {% else %}<span class="nav-btn" style="opacity: 0.5; cursor: default;">다음</span>{% endif %}
</div>
{% endblock %}""",
    'point_product_form.html': """{% extends "base.html" %}
{% block content %}
<h1>{{ '상품 수정' if product else '상품 추가' }}</h1>
<a href="/point-products" class="nav-btn mb-4">목록으로 돌아가기</a>
<div class="info-banner">{{ '기존 상품 정보를 수정합니다.' if product else '새로운 포인트 상품을 등록합니다.' }}</div>

<div class="card card-p max-w-600">
    <form method="post">
        <div class="form-group">
            <label class="form-label">상품명</label>
            <input type="text" name="product_name" value="{{ product.product_name if product else '' }}" required placeholder="예: 스타벅스 아메리카노 쿠폰" class="form-input">
        </div>
        <div class="form-group">
            <label class="form-label">상품 유형</label>
            <select name="product_type" class="form-select">
                <option value="coupon" {% if product and product.product_type == 'coupon' %}selected{% endif %}>coupon (쿠폰)</option>
                <option value="gift_card" {% if product and product.product_type == 'gift_card' %}selected{% endif %}>gift_card (상품권)</option>
                <option value="discount" {% if product and product.product_type == 'discount' %}selected{% endif %}>discount (할인)</option>
                <option value="merchandise" {% if product and product.product_type == 'merchandise' %}selected{% endif %}>merchandise (상품)</option>
                <option value="experience" {% if product and product.product_type == 'experience' %}selected{% endif %}>experience (이용권)</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">설명</label>
            <textarea name="description" rows="3" placeholder="상품 설명" class="form-textarea">{{ product.description if product else '' }}</textarea>
        </div>
        <div class="grid-2 mb-6">
            <div>
                <label class="form-label">포인트 가격</label>
                <input type="number" name="point_cost" value="{{ product.point_cost if product else '' }}" min="1" required placeholder="예: 1000" class="form-input">
            </div>
            <div>
                <label class="form-label">재고 수량</label>
                <input type="number" name="stock_quantity" value="{{ product.stock_quantity if product else '' }}" min="0" required placeholder="예: 100" class="form-input">
            </div>
        </div>
        <div class="flex justify-end">
            <button type="submit" class="btn-accent">저장</button>
        </div>
    </form>
</div>
{% endblock %}""",
    'point_purchases.html': """{% extends "base.html" %}
{% block content %}
<h1>포인트 구매 내역</h1>
<a href="/point-products" class="nav-btn mb-4">상품 목록으로 돌아가기</a>
<div class="info-banner">유저들의 포인트 상품 구매 내역을 조회합니다.</div>

<div class="summary-grid mb-6">
    <div class="summary-card">
        <div class="summary-label">총 구매 건수</div>
        <div class="summary-value">{{ total_purchases }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">총 사용 포인트</div>
        <div class="summary-value text-danger">{{ "{:,}".format(total_points_used) }}P</div>
    </div>
</div>

<div class="table-wrapper">
    <table class="w-full">
        <thead><tr>
            <th>구매 ID</th>
            <th>유저 ID</th>
            <th>상품명</th>
            <th class="text-right">사용 포인트</th>
            <th class="text-center">상태</th>
            <th>구매일</th>
        </tr></thead>
        <tbody>
            {% for p in purchases %}
            <tr>
                <td>{{ p.purchase_id }}</td>
                <td class="font-bold">{{ p.user_id }}</td>
                <td>{{ p.product_name or '(삭제된 상품)' }}</td>
                <td class="text-right font-bold">{{ "{:,}".format(p.point_cost) }}P</td>
                <td class="text-center">
                    {% if p.status == 'completed' %}
                        <span class="badge badge-success">completed</span>
                    {% elif p.status == 'cancelled' %}
                        <span class="badge badge-neutral">cancelled</span>
                    {% else %}
                        <span class="badge badge-warning">{{ p.status }}</span>
                    {% endif %}
                </td>
                <td>{{ p.purchased_at }}</td>
            </tr>
            {% else %}
            <tr><td colspan="6" class="text-center text-sub p-4">구매 내역이 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}""",
    'members.html': """{% extends "base.html" %}
{% block content %}
<h1>회원 관리</h1>

<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">사용자 관리</span>
            <h3 class="font-bold text-sm">통합적인 사용자 뷰</h3>
        </div>
        <p class="text-sm text-sub">
            사용자의 기본 정보뿐만 아니라, 활동 내역(포인트, 미션, 대출 신청 등)을 통합적으로 관리합니다. 이는 개별 사용자에 대한 깊이 있는 이해를 돕고, 향후 <strong>개인화된 서비스</strong>를 제공하기 위한 기초 데이터가 됩니다.
        </p>
    </div>
</div>

<div class="info-banner">등록된 회원을 조회, 검색, 추가, 수정, 상태 변경할 수 있습니다.</div>

<div class="summary-grid mb-6">
    <div class="summary-card">
        <div class="summary-label">전체 회원</div>
        <div class="summary-value">{{ total_count }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">활성 회원</div>
        <div class="summary-value text-success">{{ active_count }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">정지 회원</div>
        <div class="summary-value text-danger">{{ suspended_count }}</div>
    </div>
</div>

<div class="flex justify-between items-center mb-6 flex-wrap gap-2">
    <form method="get" action="/members" class="flex gap-2 items-center flex-wrap">
        <input type="text" name="search_name" value="{{ search_name }}" placeholder="회원 이름으로 검색..." class="form-input w-auto min-w-150">
        <select name="search_status" class="form-select w-auto">
            <option value="">전체 상태</option>
            <option value="active" {% if search_status == 'active' %}selected{% endif %}>활성</option>
            <option value="suspended" {% if search_status == 'suspended' %}selected{% endif %}>정지</option>
            <option value="withdrawn" {% if search_status == 'withdrawn' %}selected{% endif %}>탈퇴</option>
        </select>
        <button type="submit" class="btn-accent">검색</button>
        {% if search_name or search_status %}
        <a href="/members" class="nav-btn">초기화</a>
        {% endif %}
    </form>
    <a href="/members/add" class="btn-accent">회원 추가</a>
</div>

<div class="table-wrapper">
    <table class="w-full">
        <thead><tr>
            <th>회원 ID</th>
            <th>이름</th>
            <th>이메일</th>
            <th>전화번호</th>
            <th class="text-center">상태</th>
            <th>가입일</th>
            <th class="text-center">관리</th>
        </tr></thead>
        <tbody>
            {% for u in members %}
            <tr>
                <td style="font-family: monospace;">{{ u.user_id }}</td>
                <td class="font-bold">{{ u.user_name }}</td>
                <td>{{ u.email or '-' }}</td>
                <td>{{ u.phone or '-' }}</td>
                <td class="text-center">
                    {% if u.status == 'active' %}
                        <span class="badge badge-success">활성</span>
                    {% elif u.status == 'suspended' %}
                        <span class="badge badge-danger">정지</span>
                    {% else %}
                        <span class="badge badge-neutral">탈퇴</span>
                    {% endif %}
                </td>
                <td>{{ u.join_date or '-' }}</td>
                <td class="text-center">
                    <a href="/members/{{ u.user_id }}" class="btn-tonal btn-sm">상세</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="7" class="text-center text-sub p-4">등록된 회원이 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}""",
    'member_detail.html': """{% extends "base.html" %}
{% block content %}
<h1>회원 상세 정보</h1>
<a href="/members" class="nav-btn mb-4">목록으로 돌아가기</a>
<div class="info-banner">회원의 기본 정보, 포인트 현황, 미션 현황, 포인트 구매 내역을 통합 조회합니다.</div>

<div class="grid-2-1 mb-6">
    <div class="card card-p">
        <div class="flex justify-between items-center mb-4">
            <h3 class="card-title text-primary mt-0">기본 정보</h3>
            <a href="/members/{{ user.user_id }}/edit" class="btn-tonal btn-sm">수정</a>
        </div>
        <table class="w-full">
            <tr><td class="font-bold text-sub w-120">회원 ID</td><td style="font-family: monospace;">{{ user.user_id }}</td></tr>
            <tr class="bg-soft"><td class="font-bold text-sub">이름</td><td>{{ user.user_name }}</td></tr>
            <tr><td class="font-bold text-sub">이메일</td><td>{{ user.email or '-' }}</td></tr>
            <tr class="bg-soft"><td class="font-bold text-sub">전화번호</td><td>{{ user.phone or '-' }}</td></tr>
            <tr><td class="font-bold text-sub">가입일</td><td>{{ user.join_date or '-' }}</td></tr>
            <tr class="bg-soft"><td class="font-bold text-sub">메모</td><td>{{ user.memo or '-' }}</td></tr>
        </table>
    </div>

    <div class="flex flex-col gap-4">
        <div class="card card-p">
            <h3 class="card-title text-primary text-sm mt-0 mb-4">현재 상태</h3>
            <div style="text-align: center; margin-bottom: 1rem;">
                {% if user.status == 'active' %}
                    <span class="badge badge-success badge-lg">활성</span>
                {% elif user.status == 'suspended' %}
                    <span class="badge badge-danger badge-lg">정지</span>
                {% else %}
                    <span class="badge badge-neutral badge-lg">탈퇴</span>
                {% endif %}
            </div>
            <form action="/members/{{ user.user_id }}/status" method="post" class="flex gap-2">
                <select name="new_status" class="form-select flex-1">
                    <option value="active" {% if user.status == 'active' %}selected{% endif %}>활성</option>
                    <option value="suspended" {% if user.status == 'suspended' %}selected{% endif %}>정지</option>
                    <option value="withdrawn" {% if user.status == 'withdrawn' %}selected{% endif %}>탈퇴</option>
                </select>
                <button type="submit" class="btn-tonal">변경</button>
            </form>
        </div>
        <div class="card card-p border-danger">
            <h3 class="card-title text-danger text-sm mt-0 mb-3">회원 삭제</h3>
            <div class="warn-banner">삭제된 회원은 복구할 수 없습니다.</div>
            <form action="/members/{{ user.user_id }}/delete" method="post" onsubmit="return confirm('정말 삭제하시겠습니까?');">
                <button type="submit" class="w-full btn-outline-danger">회원 삭제</button>
            </form>
        </div>
    </div>
</div>

<div class="summary-grid mb-6">
    <div class="summary-card">
        <div class="summary-label">포인트 잔액</div>
        <div class="summary-value">{{ "{:,}".format(points.balance) }}P</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">총 지급</div>
        <div class="summary-value text-success">{{ "{:,}".format(points.total_earned) }}P</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">총 사용</div>
        <div class="summary-value text-danger">{{ "{:,}".format(points.total_spent) }}P</div>
    </div>
</div>

<div class="card card-p mb-6">
    <h3 class="card-title text-primary mt-0 mb-4">미션 현황 ({{ missions|length }}건)</h3>
    {% if missions %}
    <div style="overflow-x: auto;">
        <table class="w-full">
            <thead><tr>
                <th>미션명</th>
                <th>유형</th>
                <th class="text-center">상태</th>
                <th class="text-right">보상 포인트</th>
                <th>마감일</th>
            </tr></thead>
            <tbody>
                {% for m in missions %}
                <tr>
                    <td class="font-bold">{{ m.mission_title }}</td>
                    <td><span class="badge badge-info">{{ m.mission_type }}</span></td>
                    <td class="text-center">
                        {% if m.status == 'completed' %}
                            <span class="badge badge-success">완료</span>
                        {% elif m.status == 'in_progress' %}
                            <span class="badge badge-info">진행중</span>
                        {% elif m.status == 'expired' %}
                            <span class="badge badge-danger">만료</span>
                        {% else %}
                            <span class="badge badge-warning">대기</span>
                        {% endif %}
                    </td>
                    <td class="text-right font-bold">{{ "{:,}".format(m.reward_points) }}P</td>
                    <td>{{ m.due_date or '-' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <p class="text-center text-muted p-4">미션 내역이 없습니다.</p>
    {% endif %}
</div>

<div class="card card-p">
    <h3 class="card-title text-primary mt-0 mb-4">포인트 구매 내역 ({{ purchases|length }}건)</h3>
    {% if purchases %}
    <div style="overflow-x: auto;">
        <table class="w-full">
            <thead><tr>
                <th>상품명</th>
                <th class="text-right">사용 포인트</th>
                <th class="text-center">상태</th>
                <th>구매일</th>
            </tr></thead>
            <tbody>
                {% for p in purchases %}
                <tr>
                    <td class="font-bold">{{ p.product_name or '(삭제된 상품)' }}</td>
                    <td class="text-right font-bold">{{ "{:,}".format(p.point_cost) }}P</td>
                    <td class="text-center">
                        {% if p.status == 'completed' %}
                            <span class="badge badge-success">completed</span>
                        {% elif p.status == 'cancelled' %}
                            <span class="badge badge-neutral">cancelled</span>
                        {% else %}
                            <span class="badge badge-warning">{{ p.status }}</span>
                        {% endif %}
                    </td>
                    <td>{{ p.purchased_at }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <p class="text-center text-muted p-4">구매 내역이 없습니다.</p>
    {% endif %}
</div>
{% endblock %}""",
    'member_form.html': """{% extends "base.html" %}
{% block content %}
<h1>{{ '회원 정보 수정' if user else '신규 회원 등록' }}</h1>
<a href="/members" class="nav-btn mb-4">목록으로 돌아가기</a>
<div class="info-banner">{{ '기존 회원 정보를 수정합니다.' if user else '신규 회원을 등록합니다.' }}</div>

<div class="card card-p max-w-600">
    <form method="post">
        <div class="form-group">
            <label class="form-label">회원 ID</label>
            {% if user %}
                <input type="text" value="{{ user.user_id }}" disabled class="form-input bg-border-light text-sub">
                <p class="help-text">회원 ID는 등록 후 변경할 수 없습니다.</p>
            {% else %}
                <input type="text" name="user_id" required placeholder="예: user_007" class="form-input">
            {% endif %}
        </div>
        <div class="form-group">
            <label class="form-label">이름</label>
            <input type="text" name="user_name" value="{{ user.user_name if user else '' }}" required placeholder="예: 홍길동" class="form-input">
        </div>
        <div class="grid-2 mb-4">
            <div>
                <label class="form-label">이메일</label>
                <input type="email" name="email" value="{{ user.email if user else '' }}" placeholder="예: user@example.com" class="form-input">
            </div>
            <div>
                <label class="form-label">전화번호</label>
                <input type="text" name="phone" value="{{ user.phone if user else '' }}" placeholder="010-0000-0000" class="form-input">
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">가입일</label>
            <input type="date" name="join_date" value="{{ user.join_date if user else '' }}" class="form-input">
        </div>
        <div class="form-group">
            <label class="form-label">메모</label>
            <textarea name="memo" rows="3" placeholder="관리자 메모" class="form-textarea">{{ user.memo if user and user.memo else '' }}</textarea>
        </div>
        <div class="flex justify-end">
            <button type="submit" class="btn-accent">저장</button>
        </div>
    </form>
</div>
{% endblock %}""",
    'system_info.html': """{% extends "base.html" %}
{% block content %}
<h1>시스템 정보</h1>

<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">시스템 투명성</span>
            <h3 class="font-bold text-sm">환경 및 인프라 모니터링</h3>
        </div>
        <p class="text-sm text-sub">
            안정적인 서비스 운영을 위해 서버 리소스와 데이터베이스 연결 상태를 투명하게 공개합니다. 이는 시스템의 <strong>가용성(Availability)</strong>을 보장하고, 문제 발생 시 신속하게 대응하기 위한 기초 자료로 활용됩니다.
        </p>
    </div>
</div>

<div class="info-banner">서버 환경 및 애플리케이션 상태 정보를 확인합니다.</div>

<div class="dashboard-grid">
    <div class="card">
        <div class="card-header"><h3 class="card-title">서버 환경</h3></div>
        <div class="card-body card-p">
            <table class="w-full">
                <tr><th class="w-150">OS</th><td>{{ sys_info.os }}</td></tr>
                <tr><th>Python Version</th><td>{{ sys_info.python_version }}</td></tr>
                <tr><th>Flask Version</th><td>{{ sys_info.flask_version }}</td></tr>
                <tr><th>Working Directory</th><td>{{ sys_info.cwd }}</td></tr>
                <tr><th>Memory Usage</th><td>{{ sys_info.memory_mb }} MB</td></tr>
            </table>
        </div>
    </div>
    <div class="card">
        <div class="card-header"><h3 class="card-title">데이터베이스 정보</h3></div>
        <div class="card-body card-p">
            <table class="w-full">
                <tr><th class="w-150">DB Type</th><td>MySQL (via SQLAlchemy)</td></tr>
                <tr><th>DB Version</th><td>{{ db_info.version }}</td></tr>
                <tr><th>Connection Status</th><td><span class="badge badge-success">Connected</span></td></tr>
            </table>
        </div>
    </div>
</div>
{% endblock %}""",
    'data_viewer.html': """{% extends "base.html" %}
{% block content %}
    <h1>수집 데이터 조회: {{ table_name }}</h1>

    <div class="card guide-card">
        <div class="card-p">
            <div class="flex items-center gap-2 mb-2">
                <span class="badge badge-info">데이터 접근성</span>
                <h3 class="font-bold text-sm">원시 데이터(Raw Data) 조회</h3>
            </div>
            <p class="text-sm text-sub">
                AI 모델 학습과 서비스 운영에 사용되는 실제 데이터를 있는 그대로 조회할 수 있습니다. 데이터가 어떻게 저장되고 관리되는지 직접 확인함으로써, 데이터 파이프라인의 <strong>신뢰성</strong>을 검증할 수 있습니다.
            </p>
        </div>
    </div>

    <div class="info-banner">수집된 원시 데이터를 테이블별로 조회합니다.</div>
    <div class="mb-4 flex flex-wrap gap-2">
        <a href="/data/raw_loan_products" class="nav-btn {{ 'active' if table_name == 'raw_loan_products' else '' }}">대출 상품</a>
        <a href="/data/raw_economic_indicators" class="nav-btn {{ 'active' if table_name == 'raw_economic_indicators' else '' }}">경제 지표</a>
        <a href="/data/raw_income_stats" class="nav-btn {{ 'active' if table_name == 'raw_income_stats' else '' }}">소득 통계</a>
        <a href="/data/collection_logs" class="nav-btn {{ 'active' if table_name == 'collection_logs' else '' }}">수집 로그</a>
        <a href="/data/missions" class="nav-btn {{ 'active' if table_name == 'missions' else '' }}">미션</a>
        <a href="/data/user_points" class="nav-btn {{ 'active' if table_name == 'user_points' else '' }}">유저 포인트</a>
        <a href="/data/point_transactions" class="nav-btn {{ 'active' if table_name == 'point_transactions' else '' }}">포인트 거래</a>
        <a href="/data/point_products" class="nav-btn {{ 'active' if table_name == 'point_products' else '' }}">포인트 상품</a>
        <a href="/data/point_purchases" class="nav-btn {{ 'active' if table_name == 'point_purchases' else '' }}">포인트 구매</a>
        <a href="/data/users" class="nav-btn {{ 'active' if table_name == 'users' else '' }}">회원</a>
        <a href="/data/notifications" class="nav-btn {{ 'active' if table_name == 'notifications' else '' }}">알림</a>
    </div>
    <form method="get" action="{{ url_for('view_data', table_name=table_name) }}" class="mb-4 bg-soft rounded-lg flex gap-2 items-center flex-wrap p-4">
        <span class="font-semibold text-sub">검색:</span>
        <select name="search_col" class="form-select w-auto">
            {% for col in columns %}<option value="{{ col }}" {% if search_col == col %}selected{% endif %}>{{ col }}</option>{% endfor %}
        </select>
        <input type="text" name="search_val" value="{{ search_val if search_val else '' }}" placeholder="검색어 입력" class="form-input flex-1 min-w-200">
        <button type="submit" class="btn-accent">검색</button>
        {% if search_val %}<a href="{{ url_for('view_data', table_name=table_name) }}" class="nav-btn">초기화</a>{% endif %}
    </form>
    <div class="table-wrapper">
        <table class="w-full">
            <thead><tr>
                {% for col in columns %}
                <th class="nowrap">
                    <a href="{{ url_for('view_data', table_name=table_name, page=1, sort_by=col, order='desc' if sort_by == col and order == 'asc' else 'asc', search_col=search_col, search_val=search_val) }}" style="text-decoration: none; color: inherit;">
                        {{ col }} {% if sort_by == col %}<span class="text-primary">{{ '▲' if order == 'asc' else '▼' }}</span>{% endif %}
                    </a>
                </th>
                {% endfor %}
            </tr></thead>
            <tbody>
                {% for row in rows %}
                <tr>
                    {% for col in columns %}
                    <td>
                        {% if col in ['status', 'type', 'transaction_type', 'product_type'] %}
                            <span class="badge badge-neutral">{{ row[col] }}</span>
                        {% else %}
                            {{ row[col] }}
                        {% endif %}
                    </td>
                    {% endfor %}
                </tr>
                {% else %}<tr><td colspan="{{ columns|length }}" class="text-center text-sub p-4">데이터가 없습니다.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    <div class="flex justify-between items-center mt-4">
        {% if page > 1 %}<a href="{{ url_for('view_data', table_name=table_name, page=page-1, sort_by=sort_by, order=order, search_col=search_col, search_val=search_val) }}" class="nav-btn">이전</a>
        {% else %}<span class="nav-btn" style="opacity: 0.5; cursor: default;">이전</span>{% endif %}
        <span class="text-sub font-bold">Page <span class="text-primary">{{ page }}</span> / {{ total_pages }} ({{ "{:,}".format(total_count) }}건)</span>
        {% if page < total_pages %}<a href="{{ url_for('view_data', table_name=table_name, page=page+1, sort_by=sort_by, order=order, search_col=search_col, search_val=search_val) }}" class="nav-btn">다음</a>
        {% else %}<span class="nav-btn" style="opacity: 0.5; cursor: default;">다음</span>{% endif %}
    </div>
{% endblock %}""",
    'simulator.html': """{% extends "base.html" %}
{% block content %}
    <h1>대출 추천 시뮬레이터</h1>

    <div class="card guide-card">
        <div class="card-p">
            <div class="flex items-center gap-2 mb-2">
                <span class="badge badge-info">Simulation Guide</span>
                <h3 class="font-bold text-sm">대출 추천 시뮬레이터</h3>
            </div>
            <div class="text-sm text-sub space-y-2">
                <p><strong>목적:</strong> 현재 설정된 신용 평가 가중치와 추천 알고리즘이 실제 사용자에게 어떤 결과를 보여줄지 미리 검증합니다.</p>
                <p><strong>사용 방법:</strong>
                    왼쪽 폼에 가상의 사용자 프로필(소득, 희망 금액, 직업 등)을 입력하고 '추천 실행' 버튼을 누르세요.<br>
                    오른쪽 결과 화면에서 추천된 상품 목록과 예상 금리, 그리고 <strong>AI의 추천 사유(XAI)</strong>를 확인할 수 있습니다.
                </p>
                <p><strong>참고:</strong> 이 시뮬레이션은 실제 데이터베이스에 저장되지 않는 테스트용입니다.</p>
            </div>
        </div>
    </div>

    <div class="info-banner">가상의 유저 프로필을 입력하여 현재 신용평가 가중치 설정이 추천 결과에 어떤 영향을 미치는지 미리 확인할 수 있습니다.</div>
    <div class="grid-1-2">
        <div class="card card-p h-fit">
            <h3 class="card-title mt-0 mb-4">가상 유저 프로필</h3>
            <form method="post">
                <label class="form-label">연소득 (원)</label>
                <input type="number" name="annual_income" value="{{ income }}" placeholder="예: 50000000" class="form-input mb-1">
                <p class="help-text mb-3">원 단위로 입력합니다.</p>
                <label class="form-label">희망 대출 금액 (원)</label>
                <input type="number" name="desired_amount" value="{{ amount }}" placeholder="예: 100000000" class="form-input mb-1">
                <p class="help-text mb-3">이 금액 이상을 지원하는 상품만 추천됩니다.</p>
                <label class="form-label">고용 형태 (안정성)</label>
                <select name="job_score" class="form-select mb-1">
                    <option value="1.0" {% if job_score == 1.0 %}selected{% endif %}>대기업/공무원 (매우 안정)</option>
                    <option value="0.8" {% if job_score == 0.8 %}selected{% endif %}>중견/중소기업 (안정)</option>
                    <option value="0.5" {% if job_score == 0.5 %}selected{% endif %}>프리랜서/계약직 (보통)</option>
                    <option value="0.2" {% if job_score == 0.2 %}selected{% endif %}>무직/기타 (불안정)</option>
                </select>
                <p class="help-text mb-3">고용 안정성 점수로 변환됩니다.</p>
                <label class="form-label">보유 자산 (원)</label>
                <input type="number" name="asset_amount" value="{{ asset_amount }}" placeholder="예: 200000000" class="form-input mb-1">
                <p class="help-text mb-3">부동산, 금융 자산 등 총액을 원 단위로 입력합니다.</p>
                <button type="submit" class="btn-accent w-full">추천 실행 (AI)</button>
            </form>
        </div>
        <div class="card card-p h-fit">
            <h3 class="card-title mt-0 mb-4">추천 결과</h3>
            {% if result_html %}
                <div class="table-wrapper">{{ result_html|safe }}</div>
                <p class="text-sub text-sm mt-2">* 예상 금리는 현재 설정된 가중치 정책과 유저 프로필에 따라 계산됩니다.</p>
            {% else %}
                <div class="bg-soft rounded-lg text-center text-muted p-4 dashed-border">왼쪽 폼에 정보를 입력하고 추천을 실행해보세요.</div>
            {% endif %}
        </div>
    </div>
{% endblock %}""",
    'user_stats.html': """{% extends "base.html" %}
{% block content %}
<h1>유저 스탯 관리</h1>
<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">Data Management</span>
            <h3 class="font-bold text-sm">유저 금융 데이터 관리</h3>
        </div>
        <p class="text-sm text-sub">
            미션 자동 달성 여부를 판단하는 기준이 되는 유저의 금융 데이터(신용점수, DSR, 자산 연동 여부 등)를 조회하고 수정합니다.
        </p>
    </div>
</div>

<form method="get" class="mb-6 bg-soft rounded-lg flex gap-2 items-center flex-wrap p-4">
    <span class="font-semibold text-sub">기간 설정:</span>
    <input type="date" name="start_date" value="{{ start_date or '' }}" class="form-input w-auto">
    <span class="text-sub">~</span>
    <input type="date" name="end_date" value="{{ end_date or '' }}" class="form-input w-auto">
    <button type="submit" class="btn-primary">조회</button>
    <a href="/missions/deletion-logs" class="nav-btn">전체 기간</a>
</form>

<div class="table-wrapper">
    <table class="w-full">
        <thead><tr>
            <th>User ID</th>
            <th class="text-right">신용점수</th>
            <th class="text-right">DSR</th>
            <th class="text-right">카드사용률</th>
            <th class="text-center">연체</th>
            <th class="text-center">급여이체</th>
            <th class="text-center">관리</th>
        </tr></thead>
        <tbody>
            {% for s in stats %}
            <tr>
                <td class="font-bold">{{ s.user_id }}</td>
                <td class="text-right">{{ s.credit_score }}</td>
                <td class="text-right">{{ s.dsr }}%</td>
                <td class="text-right">{{ s.card_usage_rate }}%</td>
                <td class="text-center">{{ s.delinquency }}건</td>
                <td class="text-center">
                    {% if s.salary_transfer == 1 %}<span class="badge badge-success">Y</span>{% else %}<span class="badge badge-neutral">N</span>{% endif %}
                </td>
                <td class="text-center">
                    <a href="/user-stats/{{ s.user_id }}/edit" class="btn-tonal btn-sm">수정</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="7" class="text-center text-sub p-4">데이터가 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}""",
    'user_stats_form.html': """{% extends "base.html" %}
{% block content %}
<h1>유저 스탯 수정</h1>
<a href="/user-stats" class="nav-btn mb-4">목록으로 돌아가기</a>

<div class="card card-p max-w-600">
    <form method="post">
        <div class="form-group">
            <label class="form-label">User ID</label>
            <input type="text" value="{{ stat.user_id }}" disabled class="form-input bg-border-light">
        </div>
        <div class="grid-2 mb-4">
            <div>
                <label class="form-label">신용점수 (Credit Score)</label>
                <input type="number" name="credit_score" value="{{ stat.credit_score }}" class="form-input">
            </div>
            <div>
                <label class="form-label">DSR (%)</label>
                <input type="number" step="0.1" name="dsr" value="{{ stat.dsr }}" class="form-input">
            </div>
        </div>
        <div class="grid-2 mb-4">
            <div>
                <label class="form-label">카드 사용률 (%)</label>
                <input type="number" step="0.1" name="card_usage_rate" value="{{ stat.card_usage_rate }}" class="form-input">
            </div>
            <div>
                <label class="form-label">연체 건수</label>
                <input type="number" name="delinquency" value="{{ stat.delinquency }}" class="form-input">
            </div>
        </div>
        <div class="grid-2 mb-4">
            <div>
                <label class="form-label">고금리 대출 잔액</label>
                <input type="number" name="high_interest_loan" value="{{ stat.high_interest_loan }}" class="form-input">
            </div>
            <div>
                <label class="form-label">마이너스 통장 한도</label>
                <input type="number" name="minus_limit" value="{{ stat.minus_limit }}" class="form-input">
            </div>
        </div>
        <div class="grid-2 mb-4">
            <div>
                <label class="form-label">급여 이체 여부</label>
                <select name="salary_transfer" class="form-select">
                    <option value="0" {% if stat.salary_transfer == 0 %}selected{% endif %}>미설정 (0)</option>
                    <option value="1" {% if stat.salary_transfer == 1 %}selected{% endif %}>설정 (1)</option>
                </select>
            </div>
            <div>
                <label class="form-label">오픈뱅킹 연결</label>
                <select name="open_banking" class="form-select">
                    <option value="0" {% if stat.open_banking == 0 %}selected{% endif %}>미연결 (0)</option>
                    <option value="1" {% if stat.open_banking == 1 %}selected{% endif %}>연결 (1)</option>
                </select>
            </div>
        </div>
        <div class="grid-2 mb-6">
            <div>
                <label class="form-label">신용점수 조회 이력</label>
                <select name="checked_credit" class="form-select">
                    <option value="0" {% if stat.checked_credit == 0 %}selected{% endif %}>없음 (0)</option>
                    <option value="1" {% if stat.checked_credit == 1 %}selected{% endif %}>있음 (1)</option>
                </select>
            </div>
            <div>
                <label class="form-label">멤버십 확인 이력</label>
                <select name="checked_membership" class="form-select">
                    <option value="0" {% if stat.checked_membership == 0 %}selected{% endif %}>없음 (0)</option>
                    <option value="1" {% if stat.checked_membership == 1 %}selected{% endif %}>있음 (1)</option>
                </select>
            </div>
        </div>
        <div class="flex justify-end">
            <button type="submit" class="btn-primary">저장</button>
        </div>
    </form>
</div>
{% endblock %}"""
}

for filename, content in templates_to_create.items():
    path = os.path.join(template_dir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

app = Flask(__name__, static_folder=static_dir, static_url_path='/static', template_folder=template_dir)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_only_fallback_key')

# [Self-Repair] 정적 파일 캐싱 방지 (Cache Busting)
# url_for('static', filename='...') 호출 시 파일의 수정 시간(mtime)을 v 파라미터로 자동 추가
@app.url_defaults
def hashed_url_for_static_file(endpoint, values):
    if 'static' == endpoint or endpoint.endswith('.static'):
        filename = values.get('filename')
        if filename:
            static_folder = app.static_folder
            try:
                file_path = os.path.join(static_folder, filename)
                if os.path.exists(file_path):
                    values['v'] = int(os.stat(file_path).st_mtime)
            except Exception:
                pass

# ==========================================================================
# [헬퍼] 공통 유틸리티 함수
# ==========================================================================

def time_ago(value):
    """datetime 객체를 받아 상대적인 시간 문자열로 반환하는 필터"""
    if not value or value == "-":
        return "-"
    if not isinstance(value, datetime):
        return str(value)
    
    now = datetime.now()
    diff = now - value
    
    if diff < timedelta(seconds=60):
        return "방금 전"
    elif diff < timedelta(seconds=3600):
        return f"{int(diff.seconds / 60)}분 전"
    elif diff < timedelta(days=1):
        return f"{int(diff.seconds / 3600)}시간 전"
    elif diff < timedelta(days=7):
        return f"{diff.days}일 전"
    else:
        return value.strftime('%Y-%m-%d')

app.jinja_env.filters['time_ago'] = time_ago

def get_all_configs(engine):
    """service_config 테이블 전체를 dict로 로드"""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT config_key, config_value FROM service_config")).fetchall()
            return {row[0]: row[1] for row in rows}
    except Exception:
        return {}

def log_mission_change(conn, mission_id, change_type, description, admin_id='admin'):
    """미션 변경 이력 기록"""
    try:
        conn.execute(text("""
            INSERT INTO mission_history (mission_id, admin_id, change_type, description)
            VALUES (:mid, :aid, :ctype, :desc)
        """), {'mid': mission_id, 'aid': admin_id, 'ctype': change_type, 'desc': description})
    except Exception as e:
        print(f"History logging failed: {e}")

def init_schema(engine):
    """앱 시작 시 필요한 스키마 및 기본 설정값 보장"""
    config_defaults = [
        ('WEIGHT_INCOME', '0.5'),
        ('WEIGHT_JOB_STABILITY', '0.3'),
        ('WEIGHT_ESTATE_ASSET', '0.2'),
        ('COLLECTOR_FSS_LOAN_ENABLED', '1'),
        ('COLLECTOR_KOSIS_INCOME_ENABLED', '1'),
        ('COLLECTOR_ECONOMIC_ENABLED', '1'),
        ('NORM_INCOME_CEILING', '100000000'),
        ('NORM_ASSET_CEILING', '500000000'),
        ('XAI_THRESHOLD_INCOME', '0.15'),
        ('XAI_THRESHOLD_JOB', '0.1'),
        ('XAI_THRESHOLD_ASSET', '0.05'),
        ('RECOMMEND_MAX_COUNT', '5'),
        ('RECOMMEND_SORT_PRIORITY', 'rate'),
        ('RECOMMEND_FALLBACK_MODE', 'show_all'),
        ('RECOMMEND_RATE_SPREAD_SENSITIVITY', '1.0'),
        ('API_KEY_FSS', ''),  # 금융감독원 API Key
        ('API_KEY_KOSIS', ''), # 통계청 API Key
        ('API_KEY_ECOS', ''),  # 한국은행 API Key
        ('COLLECTION_PERIOD_FSS_LOAN', '0'), # 금감원 수집 기간
        ('COLLECTION_PERIOD_ECONOMIC', '0'), # 경제지표 수집 기간
        ('COLLECTION_PERIOD_KOSIS_INCOME', '0'), # 통계청 수집 기간
        ('COLLECTION_FREQUENCY_FSS_LOAN', 'daily'), # 금감원 수집 주기
        ('COLLECTION_FREQUENCY_ECONOMIC', 'daily'), # 경제지표 수집 주기
        ('COLLECTION_FREQUENCY_KOSIS_INCOME', 'monthly'), # 통계청 수집 주기
    ]
    try:
        with engine.connect() as conn:
            # [Self-Repair] service_config 테이블 생성 (없을 경우)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS service_config (
                    config_key VARCHAR(100) PRIMARY KEY,
                    config_value TEXT
                )
            """))

            # service_config 기본값 시드
            for key, default in config_defaults:
                existing = conn.execute(
                    text("SELECT 1 FROM service_config WHERE config_key = :k"), {'k': key}
                ).fetchone()
                if not existing:
                    conn.execute(
                        text("INSERT INTO service_config (config_key, config_value) VALUES (:k, :v)"),
                        {'k': key, 'v': default}
                    )

            # Feature 4: is_visible 컬럼 추가
            try:
                conn.execute(text("SELECT is_visible FROM raw_loan_products LIMIT 0"))
            except Exception:
                try:
                    conn.execute(text("ALTER TABLE raw_loan_products ADD COLUMN is_visible TINYINT(1) NOT NULL DEFAULT 1"))
                except Exception:
                    pass

            # Feature 5: missions 테이블 생성
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS missions (
                    mission_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(100) NOT NULL,
                    mission_title VARCHAR(255) NOT NULL,
                    mission_description TEXT,
                    mission_type VARCHAR(50) NOT NULL DEFAULT 'savings',
                    loan_purpose VARCHAR(100),
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    difficulty VARCHAR(20) NOT NULL DEFAULT 'medium',
                    reward_points INT DEFAULT 0,
                    due_date DATE,
                    completed_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """))

            # Feature 10: mission_history 테이블 생성
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS mission_history (
                    history_id INT AUTO_INCREMENT PRIMARY KEY,
                    mission_id INT NOT NULL,
                    admin_id VARCHAR(100) DEFAULT 'system',
                    change_type VARCHAR(50) NOT NULL,
                    description TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_mission_id (mission_id)
                )
            """))

            # [New] Add tracking columns to missions
            try:
                conn.execute(text("SELECT tracking_key FROM missions LIMIT 0"))
            except Exception:
                try:
                    conn.execute(text("ALTER TABLE missions ADD COLUMN tracking_key VARCHAR(50)"))
                    conn.execute(text("ALTER TABLE missions ADD COLUMN tracking_operator VARCHAR(10)"))
                    conn.execute(text("ALTER TABLE missions ADD COLUMN tracking_value FLOAT"))
                except Exception:
                    pass

            # missions mock 데이터 (테이블이 비어 있을 때만)
            count = conn.execute(text("SELECT COUNT(*) FROM missions")).scalar()
            if count == 0:
                mock_missions = [
                    ("user_001", "비상금 100만원 모으기", "3개월 내 비상금 100만원을 저축하세요", "savings", "생활안정자금", "in_progress", "easy", 50),
                    ("user_001", "커피 지출 30% 줄이기", "이번 달 커피 지출을 지난달 대비 30% 줄여보세요", "spending", "생활안정자금", "pending", "medium", 80),
                    ("user_002", "신용점수 50점 올리기", "6개월 내 신용점수를 50점 이상 올려보세요", "credit", "신용대출", "in_progress", "hard", 200),
                    ("user_002", "적금 자동이체 설정", "월 50만원 적금 자동이체를 설정하세요", "savings", "전세자금", "completed", "easy", 30),
                    ("user_003", "투자 포트폴리오 분산", "3개 이상의 자산군에 분산 투자하세요", "investment", "재테크", "pending", "hard", 150),
                    ("user_003", "주 3회 가계부 작성", "한 달간 주 3회 이상 가계부를 작성하세요", "lifestyle", "생활안정자금", "in_progress", "easy", 40),
                    ("user_004", "대출 상환 10% 추가 납입", "이번 달 대출 원금의 10%를 추가 상환하세요", "credit", "주택담보대출", "completed", "medium", 100),
                    ("user_005", "월 지출 예산 설정하기", "카테고리별 월 지출 예산을 설정하고 지켜보세요", "spending", "생활안정자금", "expired", "easy", 30),
                    ("user_006", "구독 서비스 정리", "사용하지 않는 구독 서비스를 해지하세요", "spending", "지출관리", "given_up", "easy", 20),
                ]
                for m in mock_missions:
                    conn.execute(text("""
                        INSERT INTO missions (user_id, mission_title, mission_description, mission_type, loan_purpose, status, difficulty, reward_points, due_date)
                        VALUES (:uid, :title, :desc, :mtype, :purpose, :status, :diff, :pts, DATE_ADD(CURDATE(), INTERVAL 30 DAY))
                    """), {'uid': m[0], 'title': m[1], 'desc': m[2], 'mtype': m[3], 'purpose': m[4], 'status': m[5], 'diff': m[6], 'pts': m[7]})

            # [New] Create user_stats table for mission tracking
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id VARCHAR(100) PRIMARY KEY,
                    credit_score INT DEFAULT 0,
                    dsr FLOAT DEFAULT 0,
                    card_usage_rate FLOAT DEFAULT 0,
                    delinquency INT DEFAULT 0,
                    salary_transfer TINYINT(1) DEFAULT 0,
                    high_interest_loan INT DEFAULT 0,
                    minus_limit INT DEFAULT 0,
                    open_banking TINYINT(1) DEFAULT 0,
                    checked_credit TINYINT(1) DEFAULT 0,
                    checked_membership TINYINT(1) DEFAULT 0,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """))

            # [New] Mock data for user_stats and update missions tracking info
            if conn.execute(text("SELECT COUNT(*) FROM user_stats")).scalar() == 0:
                mock_stats = [
                    ('user_001', 750, 35.5, 25.0, 0, 1, 0, 0, 1, 1, 1),
                    ('user_002', 620, 55.0, 80.0, 1, 0, 1, 5000000, 0, 0, 0),
                    ('user_003', 850, 20.0, 10.0, 0, 1, 0, 0, 1, 1, 1),
                    ('user_004', 500, 70.0, 90.0, 2, 0, 2, 10000000, 0, 0, 0),
                    ('user_005', 680, 42.0, 40.0, 0, 1, 0, 0, 1, 0, 0),
                    ('user_006', 900, 15.0, 5.0, 0, 1, 0, 0, 1, 1, 1),
                ]
                for s in mock_stats:
                    conn.execute(text("INSERT INTO user_stats (user_id, credit_score, dsr, card_usage_rate, delinquency, salary_transfer, high_interest_loan, minus_limit, open_banking, checked_credit, checked_membership) VALUES (:uid, :cs, :dsr, :cur, :del, :st, :hil, :ml, :ob, :cc, :cm)"), {'uid': s[0], 'cs': s[1], 'dsr': s[2], 'cur': s[3], 'del': s[4], 'st': s[5], 'hil': s[6], 'ml': s[7], 'ob': s[8], 'cc': s[9], 'cm': s[10]})
                
                conn.execute(text("UPDATE missions SET tracking_key='delinquency', tracking_operator='eq', tracking_value=0 WHERE mission_title LIKE '%연체%'"))
                conn.execute(text("UPDATE missions SET tracking_key='cardUsageRate', tracking_operator='lte', tracking_value=30 WHERE mission_title LIKE '%신용카드%'"))
                conn.execute(text("UPDATE missions SET tracking_key='salaryTransfer', tracking_operator='eq', tracking_value=1 WHERE mission_title LIKE '%자동이체%' OR mission_title LIKE '%급여%'"))

            # Feature 6: user_points 테이블 생성
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_points (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(100) NOT NULL UNIQUE,
                    balance INT NOT NULL DEFAULT 0,
                    total_earned INT NOT NULL DEFAULT 0,
                    total_spent INT NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """))

            # Feature 6: point_transactions 테이블 생성
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS point_transactions (
                    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(100) NOT NULL,
                    amount INT NOT NULL,
                    transaction_type VARCHAR(30) NOT NULL DEFAULT 'manual',
                    reason VARCHAR(255),
                    admin_id VARCHAR(100),
                    reference_id VARCHAR(100),
                    expires_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # [Self-Repair] point_transactions 테이블에 expires_at 컬럼 추가 (없을 경우)
            try:
                conn.execute(text("SELECT expires_at FROM point_transactions LIMIT 0"))
            except Exception:
                try:
                    conn.execute(text("ALTER TABLE point_transactions ADD COLUMN expires_at DATETIME"))
                except Exception:
                    pass

            # Feature 7: point_products 테이블 생성
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS point_products (
                    product_id INT AUTO_INCREMENT PRIMARY KEY,
                    product_name VARCHAR(255) NOT NULL,
                    product_type VARCHAR(50) NOT NULL DEFAULT 'coupon',
                    description TEXT,
                    point_cost INT NOT NULL DEFAULT 0,
                    stock_quantity INT NOT NULL DEFAULT 0,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """))

            # Feature 7: point_purchases 테이블 생성
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS point_purchases (
                    purchase_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(100) NOT NULL,
                    product_id INT NOT NULL,
                    point_cost INT NOT NULL,
                    status VARCHAR(30) NOT NULL DEFAULT 'completed',
                    purchased_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # user_points mock 데이터
            up_count = conn.execute(text("SELECT COUNT(*) FROM user_points")).scalar()
            if up_count == 0:
                mock_user_points = [
                    ("user_001", 1250, 2500, 1250),
                    ("user_002", 3800, 5000, 1200),
                    ("user_003", 500, 800, 300),
                    ("user_004", 0, 1000, 1000),
                    ("user_005", 2100, 2100, 0),
                    ("user_006", 750, 1500, 750),
                ]
                for up in mock_user_points:
                    conn.execute(text("""
                        INSERT INTO user_points (user_id, balance, total_earned, total_spent)
                        VALUES (:uid, :bal, :earned, :spent)
                    """), {'uid': up[0], 'bal': up[1], 'earned': up[2], 'spent': up[3]})

            # point_transactions mock 데이터
            pt_count = conn.execute(text("SELECT COUNT(*) FROM point_transactions")).scalar()
            if pt_count == 0:
                mock_transactions = [
                    ("user_001", 500, "mission_reward", "비상금 100만원 모으기 미션 완료 보상", "system", "mission_1"),
                    ("user_001", 200, "manual", "이벤트 참여 보너스", "admin", None),
                    ("user_001", -300, "purchase", "스타벅스 아메리카노 쿠폰 구매", "system", "purchase_1"),
                    ("user_002", 1000, "mission_reward", "신용점수 50점 올리기 미션 완료", "system", "mission_3"),
                    ("user_002", -500, "purchase", "CU 편의점 5000원 상품권 구매", "system", "purchase_2"),
                    ("user_003", 300, "manual", "신규 가입 웰컴 포인트", "admin", None),
                    ("user_004", -200, "adjustment", "포인트 오류 차감 정정", "admin", None),
                    ("user_005", 2100, "mission_reward", "적금 자동이체 설정 미션 완료", "system", "mission_4"),
                ]
                for t in mock_transactions:
                    # [Self-Repair] 미션 보상인 경우 유효기간 1년 설정
                    expires_at = None
                    if t[2] == 'mission_reward':
                        expires_at = datetime.now() + timedelta(days=365)

                    conn.execute(text("""
                        INSERT INTO point_transactions (user_id, amount, transaction_type, reason, admin_id, reference_id, expires_at)
                        VALUES (:uid, :amt, :ttype, :reason, :admin, :ref, :exp)
                    """), {'uid': t[0], 'amt': t[1], 'ttype': t[2], 'reason': t[3], 'admin': t[4], 'ref': t[5], 'exp': expires_at})

            # point_products mock 데이터
            pp_count = conn.execute(text("SELECT COUNT(*) FROM point_products")).scalar()
            if pp_count == 0:
                mock_products = [
                    ("스타벅스 아메리카노", "coupon", "스타벅스 아메리카노 1잔 교환권", 300, 100, 1),
                    ("CU 편의점 5000원 상품권", "gift_card", "CU 편의점에서 사용 가능한 5000원 상품권", 500, 50, 1),
                    ("대출 금리 0.1%p 할인", "discount", "대출 신청 시 금리 0.1%p 할인 쿠폰", 1000, 20, 1),
                    ("배달의민족 10000원 쿠폰", "coupon", "배달의민족 10000원 할인 쿠폰", 800, 30, 1),
                    ("넷플릭스 1개월 이용권", "experience", "넷플릭스 스탠다드 1개월 이용권", 2000, 10, 0),
                ]
                for p in mock_products:
                    conn.execute(text("""
                        INSERT INTO point_products (product_name, product_type, description, point_cost, stock_quantity, is_active)
                        VALUES (:name, :ptype, :desc, :cost, :stock, :active)
                    """), {'name': p[0], 'ptype': p[1], 'desc': p[2], 'cost': p[3], 'stock': p[4], 'active': p[5]})

            # point_purchases mock 데이터
            ppur_count = conn.execute(text("SELECT COUNT(*) FROM point_purchases")).scalar()
            if ppur_count == 0:
                mock_purchases = [
                    ("user_001", 1, 300, "completed"),
                    ("user_002", 2, 500, "completed"),
                    ("user_001", 4, 800, "completed"),
                    ("user_003", 1, 300, "cancelled"),
                    ("user_002", 3, 1000, "completed"),
                ]
                for pur in mock_purchases:
                    conn.execute(text("""
                        INSERT INTO point_purchases (user_id, product_id, point_cost, status)
                        VALUES (:uid, :pid, :cost, :status)
                    """), {'uid': pur[0], 'pid': pur[1], 'cost': pur[2], 'status': pur[3]})

            # Feature 8: users 테이블 생성
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(100) PRIMARY KEY,
                    user_name VARCHAR(100) NOT NULL,
                    email VARCHAR(200),
                    phone VARCHAR(20),
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    join_date DATE,
                    memo TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """))

            # users mock 데이터 (기존 user_001~006과 매칭)
            users_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            if users_count == 0:
                mock_users = [
                    ("user_001", "김민수", "minsu@example.com", "010-1234-5678", "active", "2024-01-15"),
                    ("user_002", "이지영", "jiyoung@example.com", "010-2345-6789", "active", "2024-02-20"),
                    ("user_003", "박준호", "junho@example.com", "010-3456-7890", "active", "2024-03-10"),
                    ("user_004", "최수연", "suyeon@example.com", "010-4567-8901", "suspended", "2024-04-05"),
                    ("user_005", "정태윤", "taeyun@example.com", "010-5678-9012", "active", "2024-05-22"),
                    ("user_006", "한서윤", "seoyun@example.com", "010-6789-0123", "active", "2024-06-30"),
                ]
                for u in mock_users:
                    conn.execute(text("""
                        INSERT INTO users (user_id, user_name, email, phone, status, join_date)
                        VALUES (:uid, :name, :email, :phone, :status, :join_date)
                    """), {'uid': u[0], 'name': u[1], 'email': u[2], 'phone': u[3], 'status': u[4], 'join_date': u[5]})

            # Feature 9: notifications 테이블 생성
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(100) NOT NULL,
                    message TEXT NOT NULL,
                    type VARCHAR(20) NOT NULL DEFAULT 'info',
                    is_read TINYINT(1) NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # [Self-Repair] notifications 테이블에 type 컬럼 추가 (없을 경우)
            try:
                conn.execute(text("SELECT type FROM notifications LIMIT 0"))
            except Exception:
                try:
                    conn.execute(text("ALTER TABLE notifications ADD COLUMN type VARCHAR(20) NOT NULL DEFAULT 'info'"))
                except Exception:
                    pass

            conn.commit()
    except Exception as e:
        print(f"Schema init warning: {e}")

# [Improvement] Singleton DataCollector to reuse DB connection pool
_collector_instance = None

def get_collector():
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = DataCollector()
    return _collector_instance

# [Improvement] Background Scheduler
def run_schedule_loop():
    while True:
        schedule.run_pending()
        time.sleep(1)

def start_scheduler():
    # 스케줄러 스레드 시작 (Daemon 스레드로 실행하여 메인 프로세스 종료 시 함께 종료)
    # 실제 Job 등록은 collector.py 내부나 별도 설정 함수에서 수행된다고 가정
    if not any(t.name == "SchedulerThread" for t in threading.enumerate()):
        # [Self-Repair] 스케줄러 작업 등록
        collector = get_collector()
        # 매일 자정에 만료된 포인트 처리
        schedule.every().day.at("00:00").do(collector.process_expired_points)
        # [New] 매분 미션 달성 여부 확인 (테스트용)
        schedule.every().minute.do(collector.check_mission_progress)
        # [New] 매일 자정에 미션 만료 처리
        schedule.every().day.at("00:00").do(collector.check_mission_expiration)
        
        scheduler_thread = threading.Thread(target=run_schedule_loop, daemon=True, name="SchedulerThread")
        scheduler_thread.start()
        print("Background scheduler started.")

# 앱 시작 시 스키마 초기화 (DB 연결 가능 시)
try:
    _init_collector = get_collector()
    init_schema(_init_collector.engine)
except Exception as e:
    print(f"Init schema skipped: {e}")

# ==========================================================================
# [함수] 로그 테이블 생성기, 인증, 통계
# ==========================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_dashboard_stats(engine):
    stats = {'loan_count': 0, 'economy_count': 0, 'income_count': 0, 'log_count': 0,
             'WEIGHT_INCOME': 0.5, 'WEIGHT_JOB_STABILITY': 0.3, 'WEIGHT_ESTATE_ASSET': 0.2,
             'COLLECTOR_FSS_LOAN_ENABLED': '1', 'COLLECTOR_KOSIS_INCOME_ENABLED': '1', 'COLLECTOR_ECONOMIC_ENABLED': '1',
             'log_stats_24h': {}}
    try:
        with engine.connect() as conn:
            try: stats['loan_count'] = conn.execute(text("SELECT COUNT(*) FROM raw_loan_products")).scalar()
            except Exception: pass
            try: stats['economy_count'] = conn.execute(text("SELECT COUNT(*) FROM raw_economic_indicators")).scalar()
            except Exception: pass
            try: stats['income_count'] = conn.execute(text("SELECT COUNT(*) FROM raw_income_stats")).scalar()
            except Exception: pass
            try: stats['log_count'] = conn.execute(text("SELECT COUNT(*) FROM collection_logs")).scalar()
            except Exception: pass
            
            # [New] 24h Log Stats for Chart
            try:
                cutoff = datetime.now() - timedelta(hours=24)
                rows = conn.execute(text("""
                    SELECT status, COUNT(*) FROM collection_logs 
                    WHERE executed_at >= :cutoff GROUP BY status
                """), {'cutoff': cutoff}).fetchall()
                stats['log_stats_24h'] = {row[0]: row[1] for row in rows}
            except Exception: pass

            try:
                rows = conn.execute(text("SELECT config_key, config_value FROM service_config")).fetchall()
                for row in rows:
                    if row[0].startswith('WEIGHT_'):
                        stats[row[0]] = float(row[1])
                    else:
                        stats[row[0]] = row[1]
            except Exception: pass
    except Exception:
        pass
    return stats

@app.context_processor
def inject_global_vars():
    if 'logged_in' not in session:
        return {}
    
    vars = {}
    
    # Notifications
    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM notifications WHERE is_read = 0")).scalar()
        vars['unread_notifications_count'] = count
    except Exception:
        vars['unread_notifications_count'] = 0

    # System Status
    try:
        collector = get_collector()
        stats = get_dashboard_stats(collector.engine)
        
        # Recent errors
        recent_errors = 0
        try:
            with collector.engine.connect() as conn:
                cutoff = datetime.now() - timedelta(hours=24)
                recent_errors = conn.execute(
                    text("SELECT COUNT(*) FROM collection_logs WHERE status = 'FAIL' AND executed_at >= :cutoff"),
                    {'cutoff': cutoff}
                ).scalar()
        except Exception:
            pass

        collectors_active = 0
        if stats.get('COLLECTOR_FSS_LOAN_ENABLED') == '1': collectors_active += 1
        if stats.get('COLLECTOR_ECONOMIC_ENABLED') == '1': collectors_active += 1
        if stats.get('COLLECTOR_KOSIS_INCOME_ENABLED') == '1': collectors_active += 1

        vars['system_status'] = {
            'db': True,
            'collectors_active': collectors_active,
            'collectors_total': 3,
            'now': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'recent_errors': recent_errors
        }
    except Exception:
        vars['system_status'] = {
            'db': False, 'collectors_active': 0, 'collectors_total': 3, 
            'now': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'recent_errors': 0
        }
        
    vars['auto_refresh'] = session.get('auto_refresh', True)
    
    return vars

def get_recent_logs(engine, source=None, limit=50, sort_by='executed_at', order='desc', status_filter=None):
    try:
        params = {}
        query = "SELECT * FROM collection_logs"
        conditions = []
        if source:
            conditions.append("target_source = %(source)s")
            params['source'] = source
        if status_filter:
            conditions.append("status LIKE %(status)s")
            params['status'] = f"{status_filter}%"
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        # Sorting
        allowed_cols = ['executed_at', 'level', 'status', 'row_count']
        if sort_by not in allowed_cols: sort_by = 'executed_at'
        safe_order = 'ASC' if order.lower() == 'asc' else 'DESC'
        
        query += f" ORDER BY {sort_by} {safe_order}"
        
        if limit:
            query += " LIMIT %(limit)s"
            params['limit'] = limit
        df = pd.read_sql(query, engine, params=params)
        return df.to_dict(orient='records')
    except Exception:
        return []

def _render_dashboard(message=None, status=None):
    """대시보드 렌더링 공통 로직 (index, trigger 공용)"""
    try:
        # [New] Sorting parameters
        sort_by = request.args.get('sort_by', 'executed_at')
        order = request.args.get('order', 'desc')
        status_filter = request.args.get('status_filter')

        collector = get_collector()
        stats = get_dashboard_stats(collector.engine)
        loan_logs = get_recent_logs(collector.engine, source='FSS_LOAN_API', limit=50, sort_by=sort_by, order=order, status_filter=status_filter)
        economy_logs = get_recent_logs(collector.engine, source='ECONOMIC_INDICATORS', limit=50, sort_by=sort_by, order=order, status_filter=status_filter)
        income_logs = get_recent_logs(collector.engine, source='KOSIS_INCOME_API', limit=50, sort_by=sort_by, order=order, status_filter=status_filter)

        loan_last_run = loan_logs[0]['executed_at'] if loan_logs and loan_logs[0].get('executed_at') else None
        economy_last_run = economy_logs[0]['executed_at'] if economy_logs and economy_logs[0].get('executed_at') else None
        income_last_run = income_logs[0]['executed_at'] if income_logs and income_logs[0].get('executed_at') else None

        # 최근 24시간 에러 로그 확인
        recent_errors = 0
        try:
            with collector.engine.connect() as conn:
                cutoff = datetime.now() - timedelta(hours=24)
                recent_errors = conn.execute(
                    text("SELECT COUNT(*) FROM collection_logs WHERE status = 'FAIL' AND executed_at >= :cutoff"),
                    {'cutoff': cutoff}
                ).scalar()
        except Exception:
            pass

        # 시스템 상태 구성
        collectors_active = 0
        if stats.get('COLLECTOR_FSS_LOAN_ENABLED') == '1': collectors_active += 1
        if stats.get('COLLECTOR_ECONOMIC_ENABLED') == '1': collectors_active += 1
        if stats.get('COLLECTOR_KOSIS_INCOME_ENABLED') == '1': collectors_active += 1

        system_status = {
            'db': True,
            'collectors_active': collectors_active,
            'collectors_total': 3,
            'now': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'recent_errors': recent_errors
        }

        return render_template('index.html',
            message=message, status=status,
            loan_logs=loan_logs, economy_logs=economy_logs, income_logs=income_logs,
            loan_last_run=loan_last_run, economy_last_run=economy_last_run, income_last_run=income_last_run,
            auto_refresh=session.get('auto_refresh', True), stats=stats,
            system_status=system_status,
            sort_by=sort_by, order=order, status_filter=status_filter)
    except Exception as e:
        system_status_error = {'db': False, 'collectors_active': 0, 'collectors_total': 3, 'now': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'recent_errors': 0}
        return render_template('index.html',
            message=message or f"시스템 오류: {e}", status=status or "error",
            loan_last_run="-", economy_last_run="-", income_last_run="-",
            loan_logs=[], economy_logs=[], income_logs=[],
            auto_refresh=session.get('auto_refresh', True), stats={},
            system_status=system_status_error,
            sort_by='executed_at', order='desc', status_filter=None)

# ==========================================================================
# [라우트] 인증
# ==========================================================================

# [Self-Repair] 로그인 시도 제한 (Brute Force 방지)
login_attempts = {}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

@app.route('/login', methods=['GET', 'POST'])
def login():
    ip = request.remote_addr
    now = datetime.now()

    # 잠김 확인
    if ip in login_attempts:
        attempts, last_time = login_attempts[ip]
        if attempts >= MAX_LOGIN_ATTEMPTS:
            if now - last_time < LOCKOUT_DURATION:
                remaining_min = int((LOCKOUT_DURATION - (now - last_time)).total_seconds() / 60) + 1
                flash(f"로그인 시도 횟수 초과. {remaining_min}분 후에 다시 시도해주세요.")
                return render_template('login.html', saved_username=request.cookies.get('saved_username'))
            else:
                # 잠김 시간 경과 후 초기화
                login_attempts[ip] = (0, now)

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember_me = request.form.get('remember_me')

        if username == os.getenv('ADMIN_USER', 'admin') and password == os.getenv('ADMIN_PASSWORD', 'admin1234'):
            # 로그인 성공 시 시도 횟수 초기화
            if ip in login_attempts:
                del login_attempts[ip]

            session['logged_in'] = True
            response = redirect(url_for('index'))
            
            if remember_me:
                # 쿠키 보안 설정: httponly=True, samesite='Lax', secure=request.is_secure
                response.set_cookie('saved_username', username, max_age=30*24*60*60, httponly=True, samesite='Lax', secure=request.is_secure)
            else:
                response.delete_cookie('saved_username')
            
            return response
        else:
            # 로그인 실패 시 시도 횟수 증가
            attempts, _ = login_attempts.get(ip, (0, now))
            login_attempts[ip] = (attempts + 1, now)
            
            remaining = MAX_LOGIN_ATTEMPTS - (attempts + 1)
            if remaining > 0:
                flash(f'아이디 또는 비밀번호가 올바르지 않습니다. (남은 기회: {remaining}회)')
            else:
                flash(f'로그인 시도 횟수를 초과했습니다. 15분간 로그인이 제한됩니다.')
    
    saved_username = request.cookies.get('saved_username')
    return render_template('login.html', saved_username=saved_username)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/toggle_refresh')
@login_required
def toggle_refresh():
    session['auto_refresh'] = not session.get('auto_refresh', True)
    return redirect(url_for('index'))

# ==========================================================================
# [라우트] 메인 대시보드
# ==========================================================================

@app.route('/', methods=['GET'])
@login_required
def index():
    return _render_dashboard()

# ==========================================================================
# [라우트] F1: 수집 관리
# ==========================================================================

@app.route('/collection-management')
@login_required
def collection_management():
    try:
        collector = get_collector()
        configs = get_all_configs(collector.engine)

        source_defs = [
            {'key': 'FSS_LOAN', 'config_key': 'COLLECTOR_FSS_LOAN_ENABLED', 'label': '금감원 대출상품 (FSS Loan API)', 'trigger_val': 'loan', 'log_source': 'FSS_LOAN_API', 'api_field': 'fss_key', 'api_key': 'API_KEY_FSS', 'api_desc': '금융상품통합비교공시 API 인증키', 'period_field': 'period_fss_loan', 'period_key': 'COLLECTION_PERIOD_FSS_LOAN', 'freq_field': 'freq_fss_loan', 'freq_key': 'COLLECTION_FREQUENCY_FSS_LOAN'},
            {'key': 'ECONOMIC', 'config_key': 'COLLECTOR_ECONOMIC_ENABLED', 'label': '경제 지표 (Economic Indicators)', 'trigger_val': 'economy', 'log_source': 'ECONOMIC_INDICATORS', 'api_field': 'ecos_key', 'api_key': 'API_KEY_ECOS', 'api_desc': 'ECOS 통계 API 인증키', 'period_field': 'period_economic', 'period_key': 'COLLECTION_PERIOD_ECONOMIC', 'freq_field': 'freq_economic', 'freq_key': 'COLLECTION_FREQUENCY_ECONOMIC'},
            {'key': 'KOSIS_INCOME', 'config_key': 'COLLECTOR_KOSIS_INCOME_ENABLED', 'label': '통계청 소득정보 (KOSIS Income)', 'trigger_val': 'income', 'log_source': 'KOSIS_INCOME_API', 'api_field': 'kosis_key', 'api_key': 'API_KEY_KOSIS', 'api_desc': 'KOSIS 공유서비스 API 인증키', 'period_field': 'period_kosis_income', 'period_key': 'COLLECTION_PERIOD_KOSIS_INCOME', 'freq_field': 'freq_kosis_income', 'freq_key': 'COLLECTION_FREQUENCY_KOSIS_INCOME'},
        ]

        sources = []
        for sd in source_defs:
            logs = get_recent_logs(collector.engine, source=sd['log_source'], limit=1)
            last_log = logs[0] if logs else {}
            
            # 집계 데이터 조회 (최초 실행, 누적 건수)
            try:
                with collector.engine.connect() as conn:
                    agg = conn.execute(text("""
                        SELECT MIN(executed_at), SUM(row_count) 
                        FROM collection_logs 
                        WHERE target_source = :s
                    """), {'s': sd['log_source']}).fetchone()
                    first_run = agg[0].strftime('%Y-%m-%d %H:%M') if agg[0] else '-'
                    total_count = int(agg[1]) if agg[1] else 0
            except Exception:
                first_run = '-'
                total_count = 0

            sources.append({
                'key': sd['key'],
                'label': sd['label'],
                'trigger_val': sd['trigger_val'],
                'enabled': configs.get(sd['config_key'], '1') == '1',
                'last_run': last_log.get('executed_at', '-') if not last_log.get('executed_at') else last_log['executed_at'].strftime('%Y-%m-%d %H:%M'),
                'last_status': last_log.get('status', '-'),
                'api_field': sd['api_field'],
                'api_value': configs.get(sd['api_key'], ''),
                'api_desc': sd['api_desc'],
                'period_field': sd['period_field'],
                'period_value': configs.get(sd['period_key'], '0'),
                'freq_field': sd['freq_field'],
                'freq_value': configs.get(sd['freq_key'], 'daily'),
                'first_run': first_run,
                'total_count': "{:,}".format(total_count)
            })

        return render_template('collection_management.html', sources=sources)
    except Exception as e:
        flash(f"수집 관리 페이지 로드 실패: {e}", "error")
        return redirect(url_for('index'))

@app.route('/toggle_collector', methods=['POST'])
@login_required
def toggle_collector():
    source = request.form.get('source')
    source_map = {
        'FSS_LOAN': 'COLLECTOR_FSS_LOAN_ENABLED',
        'KOSIS_INCOME': 'COLLECTOR_KOSIS_INCOME_ENABLED',
        'ECONOMIC': 'COLLECTOR_ECONOMIC_ENABLED',
    }
    config_key = source_map.get(source)
    if not config_key:
        flash('잘못된 수집 소스입니다.', 'error')
        return redirect(url_for('collection_management'))

    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            current = conn.execute(text("SELECT config_value FROM service_config WHERE config_key = :k"), {'k': config_key}).scalar()
            new_val = '0' if current == '1' else '1'
            conn.execute(text("UPDATE service_config SET config_value = :v WHERE config_key = :k"), {'v': new_val, 'k': config_key})
            conn.commit()
        flash(f'{source} 수집기가 {"ON" if new_val == "1" else "OFF"}로 변경되었습니다.', 'success')
    except Exception as e:
        flash(f'설정 변경 실패: {e}', 'error')
    return redirect(url_for('collection_management'))

@app.route('/collection-management/config', methods=['POST'])
@login_required
def update_collection_config():
    try:
        # 폼에서 전송된 값만 업데이트 (개별 카드 저장 지원)
        key_map = {
            'fss_key': 'API_KEY_FSS',
            'kosis_key': 'API_KEY_KOSIS',
            'ecos_key': 'API_KEY_ECOS',
            'period_fss_loan': 'COLLECTION_PERIOD_FSS_LOAN',
            'period_economic': 'COLLECTION_PERIOD_ECONOMIC',
            'period_kosis_income': 'COLLECTION_PERIOD_KOSIS_INCOME',
            'freq_fss_loan': 'COLLECTION_FREQUENCY_FSS_LOAN',
            'freq_economic': 'COLLECTION_FREQUENCY_ECONOMIC',
            'freq_kosis_income': 'COLLECTION_FREQUENCY_KOSIS_INCOME'
        }
        
        collector = get_collector()
        with collector.engine.connect() as conn:
            for form_key, db_key in key_map.items():
                if form_key in request.form:
                    val = request.form[form_key]
                    conn.execute(text("UPDATE service_config SET config_value = :v WHERE config_key = :k"), {'v': val, 'k': db_key})
            conn.commit()
        flash("수집 설정이 저장되었습니다.", "success")
    except Exception as e:
        flash(f"설정 저장 실패: {e}", "error")
    return redirect(url_for('collection_management'))

@app.route('/trigger', methods=['POST'])
@login_required
def trigger_job():
    job_type = request.form.get('job')
    try:
        collector = get_collector()
        configs = get_all_configs(collector.engine)

        enable_map = {'loan': 'COLLECTOR_FSS_LOAN_ENABLED', 'economy': 'COLLECTOR_ECONOMIC_ENABLED', 'income': 'COLLECTOR_KOSIS_INCOME_ENABLED'}
        config_key = enable_map.get(job_type)
        if config_key and configs.get(config_key, '1') != '1':
            return _render_dashboard(message=f"해당 수집 소스가 비활성화 상태입니다. 수집 관리에서 활성화해주세요.", status="warning")

        if job_type == 'loan':
            collector.collect_fss_loan_products()
            msg = "대출상품 수집이 완료되었습니다."
        elif job_type == 'economy':
            collector.collect_economic_indicators()
            msg = "경제 지표 수집이 완료되었습니다."
        elif job_type == 'income':
            collector.collect_kosis_income_stats()
            msg = "소득 통계 수집이 완료되었습니다."
        else:
            msg = "알 수 없는 작업입니다."

        return _render_dashboard(message=msg, status="success")
    except Exception as e:
        return _render_dashboard(message=f"실행 실패: {e}", status="error")

# ==========================================================================
# [라우트] F2: 신용평가 가중치 관리
# ==========================================================================

@app.route('/credit-weights', methods=['GET', 'POST'])
@login_required
def credit_weights():
    try:
        collector = get_collector()
        configs = get_all_configs(collector.engine)

        if request.method == 'POST':
            updates = {
                'WEIGHT_INCOME': request.form['income_weight'],
                'WEIGHT_JOB_STABILITY': request.form['job_weight'],
                'WEIGHT_ESTATE_ASSET': request.form['asset_weight'],
                'NORM_INCOME_CEILING': request.form['norm_income_ceiling'],
                'NORM_ASSET_CEILING': request.form['norm_asset_ceiling'],
                'XAI_THRESHOLD_INCOME': request.form['xai_threshold_income'],
                'XAI_THRESHOLD_JOB': request.form['xai_threshold_job'],
                'XAI_THRESHOLD_ASSET': request.form['xai_threshold_asset'],
            }
            weight_sum = float(updates['WEIGHT_INCOME']) + float(updates['WEIGHT_JOB_STABILITY']) + float(updates['WEIGHT_ESTATE_ASSET'])
            if abs(weight_sum - 1.0) > 0.01:
                flash(f"가중치 합계가 1.0이 아닙니다. (현재: {weight_sum:.2f})", 'warning')
            else:
                with collector.engine.connect() as conn:
                    for key, val in updates.items():
                        conn.execute(text("UPDATE service_config SET config_value = :v WHERE config_key = :k"), {'v': str(val), 'k': key})
                    conn.commit()
                flash("신용평가 설정이 저장되었습니다.", 'success')
                return redirect(url_for('credit_weights'))

        template_vars = {
            'income_weight': float(configs.get('WEIGHT_INCOME', '0.5')),
            'job_weight': float(configs.get('WEIGHT_JOB_STABILITY', '0.3')),
            'asset_weight': float(configs.get('WEIGHT_ESTATE_ASSET', '0.2')),
            'norm_income_ceiling': float(configs.get('NORM_INCOME_CEILING', '100000000')),
            'norm_asset_ceiling': float(configs.get('NORM_ASSET_CEILING', '500000000')),
            'xai_threshold_income': float(configs.get('XAI_THRESHOLD_INCOME', '0.15')),
            'xai_threshold_job': float(configs.get('XAI_THRESHOLD_JOB', '0.1')),
            'xai_threshold_asset': float(configs.get('XAI_THRESHOLD_ASSET', '0.05')),
        }
        return render_template('credit_weights.html', **template_vars)
    except Exception as e:
        flash(f"신용평가 설정 로드 실패: {e}", 'error')
        return redirect(url_for('index'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    return redirect(url_for('credit_weights'))

# ==========================================================================
# [라우트] F3: 대출 추천 가중치 관리
# ==========================================================================

@app.route('/recommend-settings', methods=['GET', 'POST'])
@login_required
def recommend_settings():
    try:
        collector = get_collector()
        configs = get_all_configs(collector.engine)

        if request.method == 'POST':
            updates = {
                'RECOMMEND_MAX_COUNT': request.form['max_count'],
                'RECOMMEND_SORT_PRIORITY': request.form['sort_priority'],
                'RECOMMEND_FALLBACK_MODE': request.form['fallback_mode'],
                'RECOMMEND_RATE_SPREAD_SENSITIVITY': request.form['rate_sensitivity'],
            }
            with collector.engine.connect() as conn:
                for key, val in updates.items():
                    conn.execute(text("UPDATE service_config SET config_value = :v WHERE config_key = :k"), {'v': str(val), 'k': key})
                conn.commit()
            flash("추천 설정이 저장되었습니다.", 'success')
            return redirect(url_for('recommend_settings'))

        return render_template('recommend_settings.html',
            max_count=int(configs.get('RECOMMEND_MAX_COUNT', '5')),
            sort_priority=configs.get('RECOMMEND_SORT_PRIORITY', 'rate'),
            fallback_mode=configs.get('RECOMMEND_FALLBACK_MODE', 'show_all'),
            rate_sensitivity=float(configs.get('RECOMMEND_RATE_SPREAD_SENSITIVITY', '1.0')))
    except Exception as e:
        flash(f"추천 설정 로드 실패: {e}", 'error')
        return redirect(url_for('index'))

# ==========================================================================
# [라우트] F4: 대출 상품 관리
# ==========================================================================

@app.route('/products')
@login_required
def products():
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')
        per_page = 20
        offset = (page - 1) * per_page

        collector = get_collector()
        
        # Base Query
        query = "SELECT * FROM raw_loan_products"
        count_query = "SELECT COUNT(*) FROM raw_loan_products"
        params = {}
        
        if search:
            condition = " WHERE bank_name LIKE :s OR product_name LIKE :s"
            query += condition
            count_query += condition
            params['s'] = f"%{search}%"
            
        # Pagination
        with collector.engine.connect() as conn:
            total_count = conn.execute(text(count_query), params).scalar()
            # Stats (Global)
            visible_count = conn.execute(text("SELECT COUNT(*) FROM raw_loan_products WHERE is_visible = 1")).scalar()
            hidden_count = conn.execute(text("SELECT COUNT(*) FROM raw_loan_products WHERE is_visible = 0")).scalar()

        total_pages = max(1, (total_count + per_page - 1) // per_page)
        
        query += f" LIMIT {per_page} OFFSET {offset}"
        
        df = pd.read_sql(query, collector.engine, params=params)
        products_list = df.to_dict(orient='records')

        return render_template('products.html',
            products=products_list, total_count=total_count,
            visible_count=visible_count, hidden_count=hidden_count,
            page=page, total_pages=total_pages, search=search)
    except Exception as e:
        flash(f"상품 목록 로드 실패: {e}", 'error')
        return redirect(url_for('index'))

@app.route('/products/toggle_visibility', methods=['POST'])
@login_required
def toggle_product_visibility():
    bank = request.form.get('bank_name')
    product = request.form.get('product_name')
    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            current = conn.execute(
                text("SELECT is_visible FROM raw_loan_products WHERE bank_name = :b AND product_name = :p"),
                {'b': bank, 'p': product}
            ).scalar()
            new_val = 0 if current == 1 else 1
            conn.execute(
                text("UPDATE raw_loan_products SET is_visible = :v WHERE bank_name = :b AND product_name = :p"),
                {'v': new_val, 'b': bank, 'p': product}
            )
            conn.commit()
        flash(f"'{product}' 상품이 {'노출' if new_val == 1 else '비노출'} 처리되었습니다.", 'success')
    except Exception as e:
        flash(f"상태 변경 실패: {e}", 'error')
    return redirect(url_for('products'))

# ==========================================================================
# [라우트] F5: 미션 관리
# ==========================================================================

@app.route('/missions')
@login_required
def missions():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        collector = get_collector()
        status_filter = request.args.get('status_filter', '')
        type_filter = request.args.get('type_filter', '')
        difficulty_filter = request.args.get('difficulty_filter', '')
        sort_by = request.args.get('sort_by', 'created_at')
        order = request.args.get('order', 'desc')

        where_clauses = []
        params = {}
        if status_filter:
            where_clauses.append("status = %(sf)s")
            params['sf'] = status_filter
        if type_filter:
            where_clauses.append("mission_type = %(tf)s")
            params['tf'] = type_filter
        if difficulty_filter:
            where_clauses.append("difficulty = %(df)s")
            params['df'] = difficulty_filter

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Count query for pagination
        count_query = f"SELECT COUNT(*) FROM missions{where_sql}"
        count_df = pd.read_sql(count_query, collector.engine, params=params)
        total_count = count_df.iloc[0, 0]
        total_pages = max(1, (total_count + per_page - 1) // per_page)

        allowed_sort = ['created_at', 'reward_points', 'difficulty']
        if sort_by not in allowed_sort:
            sort_by = 'created_at'
        safe_order = 'ASC' if order == 'asc' else 'DESC'
        
        if sort_by == 'difficulty':
            query = f"SELECT * FROM missions{where_sql} ORDER BY FIELD(difficulty, 'easy', 'medium', 'hard') {safe_order} LIMIT {per_page} OFFSET {offset}"
        else:
            query = f"SELECT * FROM missions{where_sql} ORDER BY {sort_by} {safe_order} LIMIT {per_page} OFFSET {offset}"
        df = pd.read_sql(query, collector.engine, params=params)
        missions_list = df.to_dict(orient='records')

        # 통계 (필터 무관 전체 기준)
        try:
            stats_df = pd.read_sql("SELECT status, COUNT(*) as cnt FROM missions GROUP BY status", collector.engine)
            stats_dict = dict(zip(stats_df['status'], stats_df['cnt']))
        except Exception:
            stats_dict = {}
        total = sum(stats_dict.values())
        completed = stats_dict.get('completed', 0)

        try:
            type_df = pd.read_sql("SELECT mission_type, COUNT(*) as cnt FROM missions GROUP BY mission_type", collector.engine)
            type_counts = dict(zip(type_df['mission_type'], type_df['cnt']))
        except Exception:
            type_counts = {}

        # [New] 유형별 완료율 툴팁 생성 및 정렬 (완료율 낮은 순)
        type_completion_tooltip = ""
        type_rates = {}
        try:
            comp_df = pd.read_sql("SELECT mission_type, COUNT(*) as cnt FROM missions WHERE status = 'completed' GROUP BY mission_type", collector.engine)
            comp_counts = dict(zip(comp_df['mission_type'], comp_df['cnt']))
            
            for mtype, total_cnt in type_counts.items():
                comp_cnt = comp_counts.get(mtype, 0)
                rate = (comp_cnt / total_cnt * 100) if total_cnt > 0 else 0
                type_rates[mtype] = rate
            
            # 완료율 낮은 순으로 정렬
            sorted_types = sorted(type_counts.keys(), key=lambda x: type_rates.get(x, 0))
            type_counts = {k: type_counts[k] for k in sorted_types}

            lines = []
            for mtype in sorted_types:
                rate = type_rates.get(mtype, 0)
                lines.append(f"{mtype}: {rate:.1f}%")
            type_completion_tooltip = "\n".join(lines)
        except Exception:
            pass

        # [New] 유형별 상태 카운트 집계
        type_status_counts = {}
        try:
            ts_df = pd.read_sql("SELECT mission_type, status, COUNT(*) as cnt FROM missions GROUP BY mission_type, status", collector.engine)
            for _, row in ts_df.iterrows():
                mtype = row['mission_type']
                status = row['status']
                cnt = row['cnt']
                if mtype not in type_status_counts:
                    type_status_counts[mtype] = {}
                type_status_counts[mtype][status] = cnt
        except Exception:
            pass

        # [New] 삭제된 미션 카운트 조회
        deleted_count = 0
        try:
            with collector.engine.connect() as conn:
                deleted_count = conn.execute(text("SELECT COUNT(*) FROM mission_deletion_logs")).scalar()
        except Exception:
            pass

        return render_template('missions.html',
            missions=missions_list, total=total,
            pending=stats_dict.get('pending', 0),
            in_progress=stats_dict.get('in_progress', 0),
            completed=completed,
            expired=stats_dict.get('expired', 0),
            given_up=stats_dict.get('given_up', 0),
            completion_rate=(completed / total * 100) if total > 0 else 0,
            type_counts=type_counts,
            type_status_counts=type_status_counts,
            type_rates=type_rates,
            type_completion_tooltip=type_completion_tooltip,
            deleted_count=deleted_count,
            status_filter=status_filter, type_filter=type_filter, difficulty_filter=difficulty_filter,
            sort_by=sort_by, order=order,
            page=page, total_pages=total_pages)
    except Exception as e:
        flash(f"미션 목록 로드 실패: {e}", 'error')
        return redirect(url_for('index'))

@app.route('/missions/<int:mission_id>')
@login_required
def mission_detail(mission_id):
    try:
        collector = get_collector()
        df = pd.read_sql("SELECT * FROM missions WHERE mission_id = %(id)s", collector.engine, params={'id': mission_id})
        if df.empty:
            flash('미션을 찾을 수 없습니다.', 'error')
            return redirect(url_for('missions'))
        mission = df.iloc[0].to_dict()

        # [New] 동일 미션 수행 유저 조회 (제목 기준)
        related_df = pd.read_sql("""
            SELECT mission_id, user_id, status, created_at, completed_at 
            FROM missions 
            WHERE mission_title = %(title)s 
            ORDER BY created_at DESC
        """, collector.engine, params={'title': mission['mission_title']})
        related_users = related_df.to_dict(orient='records')

        # [New] 변경 이력 조회
        history_df = pd.read_sql("SELECT * FROM mission_history WHERE mission_id = %(id)s ORDER BY created_at DESC", collector.engine, params={'id': mission_id})
        history = history_df.to_dict(orient='records')

        return render_template('mission_detail.html', mission=mission, related_users=related_users, history=history)
    except Exception as e:
        flash(f"미션 상세 로드 실패: {e}", 'error')
        return redirect(url_for('missions'))

@app.route('/missions/<int:mission_id>/download_related')
@login_required
def mission_download_related(mission_id):
    try:
        collector = get_collector()
        # 미션 제목 조회
        with collector.engine.connect() as conn:
            title = conn.execute(text("SELECT mission_title FROM missions WHERE mission_id = :id"), {'id': mission_id}).scalar()
        
        df = pd.read_sql("""
            SELECT mission_id, user_id, status, created_at, completed_at 
            FROM missions 
            WHERE mission_title = %(title)s 
            ORDER BY created_at DESC
        """, collector.engine, params={'title': title})
        
        csv_data = df.to_csv(index=False, encoding='utf-8-sig')
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=mission_{mission_id}_users.csv"}
        )
    except Exception as e:
        flash(f"다운로드 실패: {e}", 'error')
        return redirect(url_for('mission_detail', mission_id=mission_id))

@app.route('/missions/<int:mission_id>/complete', methods=['POST'])
@login_required
def mission_complete(mission_id):
    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            # 미션 정보 조회
            mission = conn.execute(
                text("SELECT user_id, reward_points, status, mission_title FROM missions WHERE mission_id = :id"),
                {'id': mission_id}
            ).fetchone()
            
            if not mission:
                flash('미션을 찾을 수 없습니다.', 'error')
                return redirect(url_for('missions'))
            
            user_id, reward, status, title = mission
            
            if status == 'completed':
                flash('이미 완료된 미션입니다.', 'warning')
                return redirect(url_for('mission_detail', mission_id=mission_id))
            
            # 1. 미션 상태 업데이트
            conn.execute(
                text("UPDATE missions SET status = 'completed', completed_at = NOW() WHERE mission_id = :id"),
                {'id': mission_id}
            )
            log_mission_change(conn, mission_id, 'complete', "미션 강제 완료 처리")
            
            # 2. 포인트 지급 (유효기간 1년 설정)
            if reward > 0:
                expires_at = datetime.now() + timedelta(days=365)
                
                # 트랜잭션 기록 (expires_at 포함)
                conn.execute(text("""
                    INSERT INTO point_transactions (user_id, amount, transaction_type, reason, admin_id, reference_id, expires_at)
                    VALUES (:uid, :amt, 'mission_reward', :reason, 'system', :ref, :exp)
                """), {
                    'uid': user_id, 
                    'amt': reward, 
                    'reason': f"{title} 미션 완료 보상", 
                    'ref': f"mission_{mission_id}",
                    'exp': expires_at
                })
                
                # 유저 잔액 업데이트
                conn.execute(text("""
                    UPDATE user_points 
                    SET balance = balance + :amt, total_earned = total_earned + :amt 
                    WHERE user_id = :uid
                """), {'amt': reward, 'uid': user_id})
                
                # user_points가 없을 경우 생성 (방어 코드)
                if conn.execute(text("SELECT ROW_COUNT()")).rowcount == 0:
                     conn.execute(text("""
                        INSERT INTO user_points (user_id, balance, total_earned, total_spent)
                        VALUES (:uid, :amt, :amt, 0)
                    """), {'uid': user_id, 'amt': reward})
                
                # [Self-Repair] 알림 생성
                conn.execute(text("""
                    INSERT INTO notifications (user_id, message, type)
                    VALUES (:uid, :msg, 'success')
                """), {'uid': user_id, 'msg': f"축하합니다! '{title}' 미션을 완료하고 {reward}P를 받았습니다."})

            conn.commit()
            
        flash(f"미션이 완료 처리되고 {reward}포인트가 지급되었습니다. (유효기간 1년)", 'success')
    except Exception as e:
        flash(f"미션 완료 처리 실패: {e}", 'error')
        
    return redirect(url_for('mission_detail', mission_id=mission_id))

@app.route('/missions/<int:mission_id>/update_title', methods=['POST'])
@login_required
def mission_update_title(mission_id):
    try:
        new_title = request.form.get('mission_title')
        if not new_title:
            flash('미션 제목을 입력해주세요.', 'error')
            return redirect(url_for('mission_detail', mission_id=mission_id))

        collector = get_collector()
        with collector.engine.connect() as conn:
            conn.execute(text("UPDATE missions SET mission_title = :title WHERE mission_id = :id"), {'title': new_title, 'id': mission_id})
            log_mission_change(conn, mission_id, 'update_title', f"제목 변경: {new_title}")
            conn.commit()
        flash(f"미션 제목이 변경되었습니다.", 'success')
    except Exception as e:
        flash(f"제목 변경 실패: {e}", 'error')
    return redirect(url_for('mission_detail', mission_id=mission_id))

@app.route('/missions/<int:mission_id>/update_description', methods=['POST'])
@login_required
def mission_update_description(mission_id):
    try:
        new_desc = request.form.get('mission_description')
        collector = get_collector()
        with collector.engine.connect() as conn:
            conn.execute(text("UPDATE missions SET mission_description = :desc WHERE mission_id = :id"), {'desc': new_desc, 'id': mission_id})
            log_mission_change(conn, mission_id, 'update_desc', "설명 변경")
            conn.commit()
        flash(f"미션 설명이 변경되었습니다.", 'success')
    except Exception as e:
        flash(f"설명 변경 실패: {e}", 'error')
    return redirect(url_for('mission_detail', mission_id=mission_id))

@app.route('/missions/<int:mission_id>/update_type', methods=['POST'])
@login_required
def mission_update_type(mission_id):
    try:
        new_type = request.form.get('mission_type')
        valid_types = ['savings', 'spending', 'credit', 'investment', 'lifestyle']
        if new_type not in valid_types:
            flash('유효하지 않은 미션 유형입니다.', 'error')
            return redirect(url_for('mission_detail', mission_id=mission_id))

        collector = get_collector()
        with collector.engine.connect() as conn:
            conn.execute(text("UPDATE missions SET mission_type = :mtype WHERE mission_id = :id"), {'mtype': new_type, 'id': mission_id})
            log_mission_change(conn, mission_id, 'update_type', f"유형 변경: {new_type}")
            conn.commit()
        flash(f"미션 유형이 '{new_type}'(으)로 변경되었습니다.", 'success')
    except Exception as e:
        flash(f"유형 변경 실패: {e}", 'error')
    return redirect(url_for('mission_detail', mission_id=mission_id))

@app.route('/missions/<int:mission_id>/update_tracking', methods=['POST'])
@login_required
def mission_update_tracking(mission_id):
    try:
        key = request.form.get('tracking_key')
        op = request.form.get('tracking_operator')
        val = request.form.get('tracking_value')
        
        # 빈 문자열 처리 (조건 삭제)
        if not key or not op or val == '':
            key = None
            op = None
            val = None
        
        collector = get_collector()
        with collector.engine.connect() as conn:
            conn.execute(text("UPDATE missions SET tracking_key = :key, tracking_operator = :op, tracking_value = :val WHERE mission_id = :id"), {'key': key, 'op': op, 'val': val, 'id': mission_id})
            log_mission_change(conn, mission_id, 'update_tracking', f"자동 달성 조건 변경: {key} {op} {val}")
            conn.commit()
        
        if key:
            flash(f"자동 달성 조건이 변경되었습니다. ({key} {op} {val})", 'success')
        else:
            flash("자동 달성 조건이 삭제되었습니다.", 'success')
    except Exception as e:
        flash(f"조건 변경 실패: {e}", 'error')
    return redirect(url_for('mission_detail', mission_id=mission_id))

@app.route('/missions/<int:mission_id>/update_purpose', methods=['POST'])
@login_required
def mission_update_purpose(mission_id):
    try:
        new_purpose = request.form.get('loan_purpose')
        collector = get_collector()
        with collector.engine.connect() as conn:
            conn.execute(text("UPDATE missions SET loan_purpose = :purpose WHERE mission_id = :id"), {'purpose': new_purpose, 'id': mission_id})
            log_mission_change(conn, mission_id, 'update_purpose', f"대출 목적 변경: {new_purpose}")
            conn.commit()
        flash(f"대출 목적이 변경되었습니다.", 'success')
    except Exception as e:
        flash(f"대출 목적 변경 실패: {e}", 'error')
    return redirect(url_for('mission_detail', mission_id=mission_id))

@app.route('/missions/<int:mission_id>/update_status', methods=['POST'])
@login_required
def mission_update_status(mission_id):
    try:
        new_status = request.form.get('status')
        valid_statuses = ['pending', 'in_progress', 'completed', 'expired', 'given_up']
        if new_status not in valid_statuses:
            flash('유효하지 않은 상태입니다.', 'error')
            return redirect(url_for('mission_detail', mission_id=mission_id))

        collector = get_collector()
        with collector.engine.connect() as conn:
            if new_status == 'completed':
                conn.execute(text("UPDATE missions SET status = :status, completed_at = IFNULL(completed_at, NOW()) WHERE mission_id = :id"), {'status': new_status, 'id': mission_id})
            else:
                conn.execute(text("UPDATE missions SET status = :status, completed_at = NULL WHERE mission_id = :id"), {'status': new_status, 'id': mission_id})
            log_mission_change(conn, mission_id, 'update_status', f"상태 변경: {new_status}")
            conn.commit()
        flash(f"미션 상태가 '{new_status}'(으)로 변경되었습니다.", 'success')
    except Exception as e:
        flash(f"상태 변경 실패: {e}", 'error')
    return redirect(url_for('mission_detail', mission_id=mission_id))

@app.route('/missions/<int:mission_id>/update_difficulty', methods=['POST'])
@login_required
def mission_update_difficulty(mission_id):
    try:
        new_difficulty = request.form.get('difficulty')
        if new_difficulty not in ['easy', 'medium', 'hard']:
            flash('유효하지 않은 난이도입니다.', 'error')
            return redirect(url_for('mission_detail', mission_id=mission_id))

        collector = get_collector()
        with collector.engine.connect() as conn:
            conn.execute(text("UPDATE missions SET difficulty = :diff WHERE mission_id = :id"), {'diff': new_difficulty, 'id': mission_id})
            log_mission_change(conn, mission_id, 'update_difficulty', f"난이도 변경: {new_difficulty}")
            conn.commit()
        flash(f"미션 난이도가 '{new_difficulty}'(으)로 변경되었습니다.", 'success')
    except Exception as e:
        flash(f"난이도 변경 실패: {e}", 'error')
    return redirect(url_for('mission_detail', mission_id=mission_id))

@app.route('/missions/<int:mission_id>/update_reward', methods=['POST'])
@login_required
def mission_update_reward(mission_id):
    try:
        new_reward = int(request.form.get('reward_points', 0))
        if new_reward < 0:
            flash('보상 포인트는 0 이상이어야 합니다.', 'error')
            return redirect(url_for('mission_detail', mission_id=mission_id))

        collector = get_collector()
        with collector.engine.connect() as conn:
            conn.execute(text("UPDATE missions SET reward_points = :pts WHERE mission_id = :id"), {'pts': new_reward, 'id': mission_id})
            log_mission_change(conn, mission_id, 'update_reward', f"보상 포인트 변경: {new_reward}")
            conn.commit()
        flash(f"미션 보상 포인트가 {new_reward}P로 변경되었습니다.", 'success')
    except ValueError:
        flash('유효하지 않은 포인트 값입니다.', 'error')
    except Exception as e:
        flash(f"보상 포인트 변경 실패: {e}", 'error')
    return redirect(url_for('mission_detail', mission_id=mission_id))

@app.route('/missions/<int:mission_id>/update_duedate', methods=['POST'])
@login_required
def mission_update_duedate(mission_id):
    try:
        new_date = request.form.get('due_date')
        collector = get_collector()
        with collector.engine.connect() as conn:
            if not new_date:
                conn.execute(text("UPDATE missions SET due_date = NULL WHERE mission_id = :id"), {'id': mission_id})
                flash("미션 마감일이 삭제되었습니다.", 'success')
                log_mission_change(conn, mission_id, 'update_duedate', "마감일 삭제")
            else:
                conn.execute(text("UPDATE missions SET due_date = :date WHERE mission_id = :id"), {'date': new_date, 'id': mission_id})
                log_mission_change(conn, mission_id, 'update_duedate', f"마감일 변경: {new_date}")
                flash(f"미션 마감일이 {new_date}로 변경되었습니다.", 'success')
            conn.commit()
    except Exception as e:
        flash(f"마감일 변경 실패: {e}", 'error')
    return redirect(url_for('mission_detail', mission_id=mission_id))

@app.route('/missions/<int:mission_id>/delete', methods=['POST'])
@login_required
def mission_delete(mission_id):
    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            conn.execute(text("DELETE FROM missions WHERE mission_id = :id"), {'id': mission_id})
            conn.commit()
        flash("미션이 삭제되었습니다.", 'success')
    except Exception as e:
        flash(f"미션 삭제 실패: {e}", 'error')
    return redirect(url_for('missions'))

@app.route('/missions/bulk_update_status', methods=['POST'])
@login_required
def missions_bulk_update_status():
    try:
        mission_ids = request.form.getlist('mission_ids')
        new_status = request.form.get('new_status')
        change_reason = request.form.get('change_reason')
        
        if not mission_ids:
            flash('변경할 미션을 선택해주세요.', 'warning')
            return redirect(url_for('missions'))
            
        if not new_status:
            flash('변경할 상태를 선택해주세요.', 'warning')
            return redirect(url_for('missions'))

        if not change_reason:
            change_reason = "일괄 상태 변경 (사유 미입력)"

        collector = get_collector()
        with collector.engine.connect() as conn:
            for mid in mission_ids:
                if new_status == 'completed':
                    conn.execute(text("UPDATE missions SET status = :status, completed_at = IFNULL(completed_at, NOW()) WHERE mission_id = :id"), {'status': new_status, 'id': mid})
                else:
                    conn.execute(text("UPDATE missions SET status = :status, completed_at = NULL WHERE mission_id = :id"), {'status': new_status, 'id': mid})
                
                log_mission_change(conn, mid, 'bulk_update_status', f"일괄 상태 변경({new_status}): {change_reason}")
            conn.commit()
        
        flash(f"{len(mission_ids)}개의 미션 상태가 '{new_status}'(으)로 변경되었습니다.", 'success')
    except Exception as e:
        flash(f"일괄 변경 실패: {e}", 'error')
    return redirect(url_for('missions'))

@app.route('/missions/bulk_delete', methods=['POST'])
@login_required
def missions_bulk_delete():
    try:
        mission_ids = request.form.getlist('mission_ids')
        delete_reason = request.form.get('delete_reason')

        if not mission_ids:
            flash('삭제할 미션을 선택해주세요.', 'warning')
            return redirect(url_for('missions'))

        if not delete_reason:
            delete_reason = "일괄 삭제 (사유 미입력)"

        collector = get_collector()
        with collector.engine.connect() as conn:
            # [New] 삭제 로그 테이블 생성 (없을 경우)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS mission_deletion_logs (
                    log_id INT AUTO_INCREMENT PRIMARY KEY,
                    mission_id INT,
                    user_id VARCHAR(100),
                    mission_title VARCHAR(255),
                    mission_type VARCHAR(50),
                    status VARCHAR(20),
                    reward_points INT,
                    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    delete_reason TEXT,
                    admin_id VARCHAR(100)
                )
            """))

            for mid in mission_ids:
                # 삭제 전 정보 백업
                m = conn.execute(text("SELECT * FROM missions WHERE mission_id = :id"), {'id': mid}).fetchone()
                if m:
                    conn.execute(text("""
                        INSERT INTO mission_deletion_logs (mission_id, user_id, mission_title, mission_type, status, reward_points, delete_reason, admin_id)
                        VALUES (:mid, :uid, :title, :mtype, :status, :reward, :reason, 'admin')
                    """), {
                        'mid': m.mission_id, 'uid': m.user_id, 'title': m.mission_title, 
                        'mtype': m.mission_type, 'status': m.status, 'reward': m.reward_points,
                        'reason': delete_reason
                    })
                    log_mission_change(conn, mid, 'bulk_delete', f"삭제됨 (사유: {delete_reason})")

                conn.execute(text("DELETE FROM missions WHERE mission_id = :id"), {'id': mid})
            conn.commit()
        
        flash(f"{len(mission_ids)}개의 미션이 삭제되었습니다.", 'success')
    except Exception as e:
        flash(f"일괄 삭제 실패: {e}", 'error')
    return redirect(url_for('missions'))

@app.route('/missions/deletion-logs')
@login_required
def mission_deletion_logs():
    try:
        collector = get_collector()
        
        # Date Filter
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        query = "SELECT * FROM mission_deletion_logs"
        params = {}
        where_clauses = []
        
        if start_date_str:
            where_clauses.append("deleted_at >= :start")
            params['start'] = f"{start_date_str} 00:00:00"
        if end_date_str:
            where_clauses.append("deleted_at <= :end")
            params['end'] = f"{end_date_str} 23:59:59"
            
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        query += " ORDER BY deleted_at DESC"

        try:
            df = pd.read_sql(query, collector.engine, params=params)
            logs = df.to_dict(orient='records')
        except Exception:
            # 테이블이 없거나 조회 실패 시 빈 리스트
            logs = []
        return render_template('mission_deletion_logs.html', logs=logs, start_date=start_date_str, end_date=end_date_str)
    except Exception as e:
        flash(f"로그 조회 실패: {e}", 'error')
        return redirect(url_for('missions'))

# ==========================================================================
# [라우트] F6: 포인트 관리
# ==========================================================================

@app.route('/points')
@login_required
def points():
    try:
        collector = get_collector()
        
        # Date Filter
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        search_user = request.args.get('search_user', '')
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        # Base query for transactions
        query = "SELECT transaction_type, amount FROM point_transactions"
        params = {}
        where_clauses = []
        
        if start_date_str:
            where_clauses.append("created_at >= :start")
            params['start'] = f"{start_date_str} 00:00:00"
        if end_date_str:
            where_clauses.append("created_at <= :end")
            params['end'] = f"{end_date_str} 23:59:59"
            
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Calculate stats from transactions
        total_minted = 0
        total_spent_purchase = 0
        total_clawback = 0
        total_expired = 0

        with collector.engine.connect() as conn:
            tx_rows = conn.execute(text(query), params).fetchall()
            for t_type, amt in tx_rows:
                if amt > 0:
                    total_minted += amt
                else:
                    abs_amt = abs(amt)
                    if t_type == 'purchase':
                        total_spent_purchase += abs_amt
                    elif t_type == 'expired':
                        total_expired += abs_amt
                    else:
                        # manual(negative), adjustment, etc. -> Clawback
                        total_clawback += abs_amt

        # User list Pagination & Search
        user_query = "SELECT * FROM user_points"
        user_count_query = "SELECT COUNT(*) FROM user_points"
        user_params = {}
        
        if search_user:
            condition = " WHERE user_id LIKE :u"
            user_query += condition
            user_count_query += condition
            user_params['u'] = f"%{search_user}%"
            
        with collector.engine.connect() as conn:
            user_count = conn.execute(text(user_count_query), user_params).scalar()
            # Global Balance
            total_balance = conn.execute(text("SELECT SUM(balance) FROM user_points")).scalar() or 0

        total_pages = max(1, (user_count + per_page - 1) // per_page)
        
        user_query += f" ORDER BY updated_at DESC LIMIT {per_page} OFFSET {offset}"
        
        df = pd.read_sql(user_query, collector.engine, params=user_params)
        users_list = df.to_dict(orient='records')

        return render_template('points.html',
            users=users_list, user_count=user_count,
            total_balance=total_balance, 
            total_minted=total_minted, 
            total_spent_purchase=total_spent_purchase,
            total_clawback=total_clawback,
            total_expired=total_expired,
            start_date=start_date_str, end_date=end_date_str, search_user=search_user,
            page=page, total_pages=total_pages)
    except Exception as e:
        flash(f"포인트 관리 로드 실패: {e}", 'error')
        return redirect(url_for('index'))

@app.route('/points/<user_id>')
@login_required
def point_detail(user_id):
    try:
        collector = get_collector()
        user_df = pd.read_sql("SELECT * FROM user_points WHERE user_id = %(uid)s",
                               collector.engine, params={'uid': user_id})
        if user_df.empty:
            flash('해당 유저의 포인트 정보를 찾을 수 없습니다.', 'error')
            return redirect(url_for('points'))
        user = user_df.iloc[0].to_dict()

        tx_df = pd.read_sql("SELECT * FROM point_transactions WHERE user_id = %(uid)s ORDER BY created_at DESC",
                             collector.engine, params={'uid': user_id})
        transactions = tx_df.to_dict(orient='records')

        return render_template('point_detail.html',
            user_id=user_id, user=user, transactions=transactions)
    except Exception as e:
        flash(f"포인트 상세 로드 실패: {e}", 'error')
        return redirect(url_for('points'))

@app.route('/points/adjust', methods=['POST'])
@login_required
def points_adjust():
    user_id = request.form.get('user_id', '').strip()
    amount = request.form.get('amount', '0').strip()
    reason = request.form.get('reason', '').strip()

    try:
        amount = int(amount)
    except ValueError:
        flash('금액은 정수로 입력해주세요.', 'warning')
        return redirect(url_for('points'))

    if not user_id or amount == 0 or not reason:
        flash('유저 ID, 금액(0 제외), 사유를 모두 입력하세요.', 'warning')
        return redirect(url_for('points'))

    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            existing = conn.execute(
                text("SELECT balance FROM user_points WHERE user_id = :uid"), {'uid': user_id}
            ).fetchone()

            if existing:
                new_balance = existing[0] + amount
                if new_balance < 0:
                    flash(f'잔액 부족: 현재 {existing[0]}P, 차감 요청 {abs(amount)}P', 'warning')
                    return redirect(url_for('points'))
                if amount > 0:
                    conn.execute(text(
                        "UPDATE user_points SET balance = balance + :amt, total_earned = total_earned + :amt WHERE user_id = :uid"
                    ), {'amt': amount, 'uid': user_id})
                else:
                    conn.execute(text(
                        "UPDATE user_points SET balance = balance + :amt, total_spent = total_spent + :abs_amt WHERE user_id = :uid"
                    ), {'amt': amount, 'abs_amt': abs(amount), 'uid': user_id})
            else:
                if amount < 0:
                    flash('존재하지 않는 유저에게 포인트를 차감할 수 없습니다.', 'warning')
                    return redirect(url_for('points'))
                conn.execute(text(
                    "INSERT INTO user_points (user_id, balance, total_earned, total_spent) VALUES (:uid, :amt, :amt, 0)"
                ), {'uid': user_id, 'amt': amount})

            conn.execute(text("""
                INSERT INTO point_transactions (user_id, amount, transaction_type, reason, admin_id)
                VALUES (:uid, :amt, 'manual', :reason, :admin)
            """), {'uid': user_id, 'amt': amount, 'reason': reason, 'admin': 'admin'})
            conn.commit()

        action = "지급" if amount > 0 else "차감"
        flash(f"{user_id}에게 {abs(amount):,} 포인트가 {action}되었습니다.", 'success')
    except Exception as e:
        flash(f"포인트 조정 실패: {e}", 'error')
    return redirect(url_for('points'))

# ==========================================================================
# [라우트] F7: 포인트 상품 관리
# ==========================================================================

@app.route('/point-products')
@login_required
def point_products():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page

        collector = get_collector()
        
        with collector.engine.connect() as conn:
            total_count = conn.execute(text("SELECT COUNT(*) FROM point_products")).scalar()
            # Global Stats
            active_count = conn.execute(text("SELECT COUNT(*) FROM point_products WHERE is_active = 1")).scalar()

        total_pages = max(1, (total_count + per_page - 1) // per_page)
        
        df = pd.read_sql(f"SELECT * FROM point_products ORDER BY created_at DESC LIMIT {per_page} OFFSET {offset}", collector.engine)
        products_list = df.to_dict(orient='records')

        inactive_count = total_count - active_count

        return render_template('point_products.html',
            products=products_list, total_count=total_count,
            active_count=active_count, inactive_count=inactive_count,
            page=page, total_pages=total_pages)
    except Exception as e:
        flash(f"포인트 상품 목록 로드 실패: {e}", 'error')
        return redirect(url_for('index'))

@app.route('/point-products/add', methods=['GET', 'POST'])
@login_required
def point_product_add():
    if request.method == 'POST':
        try:
            collector = get_collector()
            with collector.engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO point_products (product_name, product_type, description, point_cost, stock_quantity, is_active)
                    VALUES (:name, :ptype, :desc, :cost, :stock, 1)
                """), {
                    'name': request.form['product_name'],
                    'ptype': request.form['product_type'],
                    'desc': request.form.get('description', ''),
                    'cost': int(request.form['point_cost']),
                    'stock': int(request.form['stock_quantity']),
                })
                conn.commit()
            flash("상품이 추가되었습니다.", 'success')
            return redirect(url_for('point_products'))
        except Exception as e:
            flash(f"상품 추가 실패: {e}", 'error')

    return render_template('point_product_form.html', product=None)

@app.route('/point-products/purchases')
@login_required
def point_purchases():
    try:
        collector = get_collector()
        df = pd.read_sql("""
            SELECT pp.purchase_id, pp.user_id, p.product_name, pp.point_cost, pp.status, pp.purchased_at
            FROM point_purchases pp
            LEFT JOIN point_products p ON pp.product_id = p.product_id
            ORDER BY pp.purchased_at DESC
        """, collector.engine)
        purchases_list = df.to_dict(orient='records')

        total_points_used = int(df.loc[df['status'] == 'completed', 'point_cost'].sum()) if not df.empty else 0

        return render_template('point_purchases.html',
            purchases=purchases_list, total_purchases=len(purchases_list),
            total_points_used=total_points_used)
    except Exception as e:
        flash(f"구매 내역 로드 실패: {e}", 'error')
        return redirect(url_for('point_products'))

@app.route('/point-products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def point_product_edit(product_id):
    try:
        collector = get_collector()
        if request.method == 'POST':
            with collector.engine.connect() as conn:
                conn.execute(text("""
                    UPDATE point_products
                    SET product_name = :name, product_type = :ptype, description = :desc,
                        point_cost = :cost, stock_quantity = :stock
                    WHERE product_id = :pid
                """), {
                    'name': request.form['product_name'],
                    'ptype': request.form['product_type'],
                    'desc': request.form.get('description', ''),
                    'cost': int(request.form['point_cost']),
                    'stock': int(request.form['stock_quantity']),
                    'pid': product_id,
                })
                conn.commit()
            flash("상품이 수정되었습니다.", 'success')
            return redirect(url_for('point_products'))

        df = pd.read_sql("SELECT * FROM point_products WHERE product_id = %(id)s",
                          collector.engine, params={'id': product_id})
        if df.empty:
            flash('상품을 찾을 수 없습니다.', 'error')
            return redirect(url_for('point_products'))
        product = df.iloc[0].to_dict()
        return render_template('point_product_form.html', product=product)
    except Exception as e:
        flash(f"상품 수정 실패: {e}", 'error')
        return redirect(url_for('point_products'))

@app.route('/point-products/<int:product_id>/toggle', methods=['POST'])
@login_required
def point_product_toggle(product_id):
    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            current = conn.execute(
                text("SELECT is_active FROM point_products WHERE product_id = :pid"),
                {'pid': product_id}
            ).scalar()
            new_val = 0 if current == 1 else 1
            conn.execute(
                text("UPDATE point_products SET is_active = :v WHERE product_id = :pid"),
                {'v': new_val, 'pid': product_id}
            )
            conn.commit()
        flash(f"상품이 {'활성' if new_val == 1 else '비활성'} 처리되었습니다.", 'success')
    except Exception as e:
        flash(f"상태 변경 실패: {e}", 'error')
    return redirect(url_for('point_products'))

# ==========================================================================
# [라우트] F8: 회원 관리
# ==========================================================================

@app.route('/members')
@login_required
def members():
    try:
        collector = get_collector()
        search_name = request.args.get('search_name', '')
        search_status = request.args.get('search_status', '')

        query = "SELECT * FROM users WHERE 1=1"
        params = {}
        if search_name:
            query += " AND user_name LIKE :name"
            params['name'] = f"%{search_name}%"
        if search_status:
            query += " AND status = :status"
            params['status'] = search_status
        query += " ORDER BY created_at DESC"

        with collector.engine.connect() as conn:
            rows = conn.execute(text(query), params).fetchall()
            columns = conn.execute(text(query), params).keys()
            members_list = [dict(zip(columns, row)) for row in rows]

            # 통계 (전체 기준)
            total = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            active = conn.execute(text("SELECT COUNT(*) FROM users WHERE status = 'active'")).scalar()
            suspended = conn.execute(text("SELECT COUNT(*) FROM users WHERE status = 'suspended'")).scalar()

        return render_template('members.html',
            members=members_list, total_count=total,
            active_count=active, suspended_count=suspended,
            search_name=search_name, search_status=search_status)
    except Exception as e:
        flash(f"회원 목록 로드 실패: {e}", 'error')
        return redirect(url_for('index'))

@app.route('/members/add', methods=['GET', 'POST'])
@login_required
def member_add():
    if request.method == 'POST':
        try:
            collector = get_collector()
            with collector.engine.connect() as conn:
                # 중복 체크
                existing = conn.execute(
                    text("SELECT 1 FROM users WHERE user_id = :uid"),
                    {'uid': request.form['user_id']}
                ).fetchone()
                if existing:
                    flash("이미 존재하는 회원 ID입니다.", 'error')
                    return render_template('member_form.html', user=None)

                conn.execute(text("""
                    INSERT INTO users (user_id, user_name, email, phone, join_date, memo)
                    VALUES (:uid, :name, :email, :phone, :join_date, :memo)
                """), {
                    'uid': request.form['user_id'],
                    'name': request.form['user_name'],
                    'email': request.form.get('email', ''),
                    'phone': request.form.get('phone', ''),
                    'join_date': request.form.get('join_date') or None,
                    'memo': request.form.get('memo', ''),
                })
                conn.commit()
            flash("회원이 등록되었습니다.", 'success')
            return redirect(url_for('members'))
        except Exception as e:
            flash(f"회원 등록 실패: {e}", 'error')

    return render_template('member_form.html', user=None)

@app.route('/members/<user_id>')
@login_required
def member_detail(user_id):
    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            # 기본 정보
            row = conn.execute(
                text("SELECT * FROM users WHERE user_id = :uid"), {'uid': user_id}
            ).fetchone()
            if not row:
                flash("회원을 찾을 수 없습니다.", 'error')
                return redirect(url_for('members'))
            columns = conn.execute(text("SELECT * FROM users LIMIT 0")).keys()
            user = dict(zip(columns, row))

            # 포인트 정보
            pt_row = conn.execute(
                text("SELECT balance, total_earned, total_spent FROM user_points WHERE user_id = :uid"),
                {'uid': user_id}
            ).fetchone()
            points = {'balance': pt_row[0], 'total_earned': pt_row[1], 'total_spent': pt_row[2]} if pt_row else {'balance': 0, 'total_earned': 0, 'total_spent': 0}

        # 미션 목록
        missions_df = pd.read_sql(
            "SELECT mission_title, mission_type, status, reward_points, due_date FROM missions WHERE user_id = %(uid)s ORDER BY created_at DESC",
            collector.engine, params={'uid': user_id}
        )
        missions_list = missions_df.to_dict(orient='records')

        # 구매 내역
        purchases_df = pd.read_sql("""
            SELECT pp.point_cost, pp.status, pp.purchased_at, p.product_name
            FROM point_purchases pp
            LEFT JOIN point_products p ON pp.product_id = p.product_id
            WHERE pp.user_id = %(uid)s
            ORDER BY pp.purchased_at DESC
        """, collector.engine, params={'uid': user_id})
        purchases_list = purchases_df.to_dict(orient='records')

        return render_template('member_detail.html',
            user=user, points=points, missions=missions_list, purchases=purchases_list)
    except Exception as e:
        flash(f"회원 상세 로드 실패: {e}", 'error')
        return redirect(url_for('members'))

@app.route('/members/<user_id>/edit', methods=['GET', 'POST'])
@login_required
def member_edit(user_id):
    try:
        collector = get_collector()
        if request.method == 'POST':
            with collector.engine.connect() as conn:
                conn.execute(text("""
                    UPDATE users SET user_name = :name, email = :email, phone = :phone,
                        join_date = :join_date, memo = :memo
                    WHERE user_id = :uid
                """), {
                    'name': request.form['user_name'],
                    'email': request.form.get('email', ''),
                    'phone': request.form.get('phone', ''),
                    'join_date': request.form.get('join_date') or None,
                    'memo': request.form.get('memo', ''),
                    'uid': user_id,
                })
                conn.commit()
            flash("회원 정보가 수정되었습니다.", 'success')
            return redirect(f'/members/{user_id}')

        with collector.engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM users WHERE user_id = :uid"), {'uid': user_id}
            ).fetchone()
            if not row:
                flash("회원을 찾을 수 없습니다.", 'error')
                return redirect(url_for('members'))
            columns = conn.execute(text("SELECT * FROM users LIMIT 0")).keys()
            user = dict(zip(columns, row))

        return render_template('member_form.html', user=user)
    except Exception as e:
        flash(f"회원 수정 실패: {e}", 'error')
        return redirect(url_for('members'))

@app.route('/members/<user_id>/status', methods=['POST'])
@login_required
def member_status(user_id):
    try:
        new_status = request.form.get('new_status')
        if new_status not in ('active', 'suspended', 'withdrawn'):
            flash("유효하지 않은 상태값입니다.", 'error')
            return redirect(f'/members/{user_id}')

        collector = get_collector()
        with collector.engine.connect() as conn:
            conn.execute(
                text("UPDATE users SET status = :status WHERE user_id = :uid"),
                {'status': new_status, 'uid': user_id}
            )
            conn.commit()

        status_labels = {'active': '활성', 'suspended': '정지', 'withdrawn': '탈퇴'}
        flash(f"회원 상태가 '{status_labels[new_status]}'(으)로 변경되었습니다.", 'success')
    except Exception as e:
        flash(f"상태 변경 실패: {e}", 'error')
    return redirect(f'/members/{user_id}')

@app.route('/members/<user_id>/delete', methods=['POST'])
@login_required
def member_delete(user_id):
    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            conn.execute(text("DELETE FROM users WHERE user_id = :uid"), {'uid': user_id})
            conn.commit()
        flash("회원이 삭제되었습니다.", 'success')
    except Exception as e:
        flash(f"회원 삭제 실패: {e}", 'error')
    return redirect(url_for('members'))

# ==========================================================================
# [라우트] F9: 시스템 정보
# ==========================================================================

@app.route('/system-info')
@login_required
def system_info():
    memory_mb = "N/A"
    if psutil:
        try:
            process = psutil.Process(os.getpid())
            memory_mb = round(process.memory_info().rss / 1024 / 1024, 2)
        except Exception:
            pass

    sys_info = {
        'os': f"{platform.system()} {platform.release()}",
        'python_version': sys.version.split()[0],
        'flask_version': flask_version,
        'cwd': os.getcwd(),
        'memory_mb': memory_mb
    }
    db_info = {'version': 'Unknown'}
    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            db_info['version'] = conn.execute(text("SELECT VERSION()")).scalar()
    except Exception:
        pass
    return render_template('system_info.html', sys_info=sys_info, db_info=db_info)

# ==========================================================================
# [라우트] 데이터 조회, 시뮬레이터 (기존 기능 유지)
# ==========================================================================

@app.route('/data/<table_name>')
@login_required
def view_data(table_name):
    allowed_tables = ['raw_loan_products', 'raw_economic_indicators', 'raw_income_stats', 'collection_logs', 'service_config', 'missions', 'user_points', 'point_transactions', 'point_products', 'point_purchases', 'users', 'notifications']
    if table_name not in allowed_tables:
        flash(f"허용되지 않은 테이블입니다: {table_name}", "error")
        return redirect(url_for('index'))

    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort_by')
    order = request.args.get('order', 'asc')
    search_col = request.args.get('search_col')
    search_val = request.args.get('search_val')
    per_page = 20

    try:
        collector = get_collector()
        meta_df = pd.read_sql(f"SELECT * FROM {table_name} LIMIT 0", collector.engine)
        columns = meta_df.columns.tolist()

        where_clause = ""
        params = {}
        if search_col and search_val and search_col in columns:
            where_clause = f" WHERE {search_col} LIKE %(search_val)s"
            params['search_val'] = f"%{search_val}%"

        count_df = pd.read_sql(f"SELECT COUNT(*) FROM {table_name}" + where_clause, collector.engine, params=params)
        total_count = count_df.iloc[0, 0]
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        if page < 1: page = 1
        if page > total_pages: page = total_pages
        offset = (page - 1) * per_page

        query = f"SELECT * FROM {table_name}" + where_clause
        if sort_by and sort_by in columns:
            safe_order = 'DESC' if order.upper() == 'DESC' else 'ASC'
            query += f" ORDER BY {sort_by} {safe_order}"
        query += f" LIMIT {per_page} OFFSET {offset}"

        df = pd.read_sql(query, collector.engine, params=params)
        rows = df.to_dict(orient='records')

        return render_template('data_viewer.html',
            table_name=table_name, columns=columns, rows=rows,
            page=page, total_pages=total_pages, total_count=total_count,
            sort_by=sort_by, order=order, search_col=search_col, search_val=search_val)
    except Exception as e:
        flash(f"데이터 조회 실패: {e}", "error")
        return redirect(url_for('index'))

@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            conn.execute(
                text("UPDATE notifications SET is_read = 1 WHERE notification_id = :id"),
                {'id': notification_id}
            )
            conn.commit()
        flash("알림이 읽음 처리되었습니다.", "success")
    except Exception as e:
        flash(f"알림 처리 실패: {e}", "error")
    return redirect(request.referrer or url_for('view_data', table_name='notifications'))

@app.route('/simulator', methods=['GET', 'POST'])
@login_required
def simulator():
    result_html = None
    income = 50000000
    amount = 10000000
    job_score = 0.8
    asset_amount = 0

    if request.method == 'POST':
        try:
            income = int(request.form.get('annual_income', 0))
            amount = int(request.form.get('desired_amount', 0))
            job_score = float(request.form.get('job_score', 0.5))
            asset_amount = int(request.form.get('asset_amount', 0))

            collector = get_collector()
            user_profile = {'annual_income': income, 'desired_amount': amount, 'job_score': job_score, 'asset_amount': asset_amount}
            recommendations = recommend_products(collector.engine, user_profile)

            if not recommendations.empty:
                # Manual HTML construction for better styling control using static/style.css classes
                html_parts = ['<table class="w-full"><thead><tr>']
                
                # Column mapping for display names
                col_map = {
                    'bank_name': '은행',
                    'product_name': '상품명',
                    'estimated_rate': '예상 금리',
                    'explanation': '추천 사유',
                    'loan_limit': '한도',
                    'loan_rate_min': '최저 금리',
                    'loan_rate_max': '최고 금리'
                }
                
                # Alignment classes
                align_map = {
                    'bank_name': 'text-center nowrap',
                    'estimated_rate': 'text-right nowrap',
                    'loan_limit': 'text-right nowrap',
                    'loan_rate_min': 'text-right nowrap',
                    'loan_rate_max': 'text-right nowrap'
                }

                # Header
                for col in recommendations.columns:
                    label = col_map.get(col, col)
                    align = align_map.get(col, 'text-left')
                    html_parts.append(f'<th class="{align} nowrap">{label}</th>')
                html_parts.append('</tr></thead><tbody>')

                # Body
                for _, row in recommendations.iterrows():
                    html_parts.append('<tr>')
                    for col in recommendations.columns:
                        val = row[col]
                        align = align_map.get(col, 'text-left')
                        
                        # Value formatting
                        if col == 'bank_name':
                            cell_content = f'<span class="badge badge-info">{val}</span>'
                        elif col == 'product_name':
                            cell_content = f'<span class="font-bold">{val}</span>'
                        elif col == 'estimated_rate':
                            cell_content = f'<span class="text-primary font-bold text-lg">{val}%</span>'
                        elif col == 'explanation':
                            cell_content = f'<div class="text-sm text-sub text-truncate" title="{val}">{val}</div>'
                        elif col in ['loan_rate_min', 'loan_rate_max']:
                            cell_content = f'<span class="text-sub">{val}%</span>'
                        elif col == 'loan_limit':
                            cell_content = f'<span class="font-bold">{int(val):,}원</span>'
                        else:
                            cell_content = str(val)
                            
                        html_parts.append(f'<td class="{align}">{cell_content}</td>')
                    html_parts.append('</tr>')
                
                html_parts.append('</tbody></table>')
                result_html = "".join(html_parts)
            else:
                result_html = '<p class="text-center text-danger p-4">조건에 맞는 추천 상품이 없습니다.</p>'
        except Exception as e:
            flash(f"시뮬레이션 오류: {e}", "error")

    return render_template('simulator.html', result_html=result_html,
        income=income, amount=amount, job_score=job_score, asset_amount=asset_amount)

# ==========================================================================
# [라우트] F10: 유저 스탯 관리
# ==========================================================================

@app.route('/user-stats')
@login_required
def user_stats():
    try:
        collector = get_collector()
        df = pd.read_sql("SELECT * FROM user_stats ORDER BY user_id", collector.engine)
        stats_list = df.to_dict(orient='records')
        return render_template('user_stats.html', stats=stats_list)
    except Exception as e:
        flash(f"유저 스탯 목록 로드 실패: {e}", 'error')
        return redirect(url_for('index'))

@app.route('/user-stats/<user_id>/edit', methods=['GET', 'POST'])
@login_required
def user_stats_edit(user_id):
    try:
        collector = get_collector()
        if request.method == 'POST':
            # [New] 입력값 유효성 검사
            try:
                cs = int(request.form.get('credit_score') or 0)
                if not (0 <= cs <= 1000):
                    raise ValueError("신용점수는 0 ~ 1000 사이여야 합니다.")
                
                dsr = float(request.form.get('dsr') or 0)
                if dsr < 0:
                    raise ValueError("DSR은 0% 이상이어야 합니다.")
                
                cur = float(request.form.get('card_usage_rate') or 0)
                if cur < 0:
                    raise ValueError("카드 사용률은 0% 이상이어야 합니다.")
                
                delinq = int(request.form.get('delinquency') or 0)
                if delinq < 0:
                    raise ValueError("연체 건수는 0 이상이어야 합니다.")
                
                # 금액 관련 필드는 음수 불가
                if int(request.form.get('high_interest_loan') or 0) < 0:
                    raise ValueError("고금리 대출 잔액은 0 이상이어야 합니다.")
                if int(request.form.get('minus_limit') or 0) < 0:
                    raise ValueError("마이너스 통장 한도는 0 이상이어야 합니다.")
            except ValueError as e:
                flash(f"입력값 오류: {e}", 'error')
                return redirect(url_for('user_stats_edit', user_id=user_id))

            with collector.engine.connect() as conn:
                exists = conn.execute(text("SELECT 1 FROM user_stats WHERE user_id = :uid"), {'uid': user_id}).scalar()
                
                cols = ['credit_score', 'dsr', 'card_usage_rate', 'delinquency', 'salary_transfer', 
                        'high_interest_loan', 'minus_limit', 'open_banking', 'checked_credit', 'checked_membership']
                
                params = {'uid': user_id}
                updates = []
                for col in cols:
                    val = request.form.get(col)
                    if val == '': # 빈 값은 0으로 처리
                        val = 0
                    params[col] = val
                    updates.append(f"{col} = :{col}")
                
                if exists:
                    sql = f"UPDATE user_stats SET {', '.join(updates)} WHERE user_id = :uid"
                    conn.execute(text(sql), params)
                else:
                    cols_str = ", ".join(cols)
                    vals_str = ", ".join([f":{col}" for col in cols])
                    sql = f"INSERT INTO user_stats (user_id, {cols_str}) VALUES (:uid, {vals_str})"
                    conn.execute(text(sql), params)
                
                conn.commit()
            flash("유저 스탯이 수정되었습니다.", 'success')
            return redirect(url_for('user_stats'))

        df = pd.read_sql("SELECT * FROM user_stats WHERE user_id = %(uid)s", collector.engine, params={'uid': user_id})
        stat = df.iloc[0].to_dict() if not df.empty else {'user_id': user_id, 'credit_score': 0, 'dsr': 0, 'card_usage_rate': 0, 'delinquency': 0, 'salary_transfer': 0, 'high_interest_loan': 0, 'minus_limit': 0, 'open_banking': 0, 'checked_credit': 0, 'checked_membership': 0}
        return render_template('user_stats_form.html', stat=stat)
    except Exception as e:
        flash(f"유저 스탯 수정 실패: {e}", 'error')
        return redirect(url_for('user_stats'))

# ==========================================================================
# 실행
# ==========================================================================

if __name__ == '__main__':
    # Flask의 리로더가 활성화된 경우 메인 프로세스에서만 스케줄러 실행
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        start_scheduler()
    app.run(host='0.0.0.0', debug=True, port=5001)
