from flask import Flask, render_template, request, redirect, url_for, session, flash, __version__ as flask_version
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
    f.write("""/* === CSS Variables === */
:root {
    /* Brand Colors */
    --visionary-black: #000000;
    --pure-white: #FFFFFF;
    --insight-gold: #E5AA70;
    --insight-gold-hover: #D4955D;
    --evidence-grey: #8E8E8E;
    --slate-blue-grey: #4A5568;

    --primary: var(--insight-gold);
    --primary-hover: var(--insight-gold-hover);
    --accent: var(--insight-gold);
    --accent-hover: var(--insight-gold-hover);
    
    --bg-page: #F8F9FA; --bg-card: var(--pure-white); --bg-soft: #F3F4F6; --bg-input: var(--pure-white);
    --text-main: var(--visionary-black); --text-sub: var(--slate-blue-grey); --text-muted: var(--evidence-grey);
    --border: #E5E7EB; --border-light: #F3F4F6; --th-bg: #F9FAFB;
    
    --success-bg: #ecfdf5; --success-fg: #059669;
    --warning-bg: #FFFBEB; --warning-fg: #D97706;
    --danger-bg: #FEF2F2;  --danger-fg: #DC2626;
    --info-bg: #FDF6E3;    --info-fg: #B7791F; /* Gold-ish info color */
    --neutral-bg: #F3F4F6; --neutral-fg: var(--slate-blue-grey);
    
    --shadow-sm: 0 1px 2px 0 rgba(0,0,0,0.05);
    --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
    --radius-card: 16px;
    --radius-btn: 10px;
    --radius-badge: 9999px;
    --transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
html.dark {
    --primary: #E5AA70;
    --primary-hover: #D4955D;
    --accent: #E5AA70;
    --accent-hover: #D4955D;
    --bg-page: #121212; --bg-card: #1E1E1E; --bg-soft: #2C2C2C; --bg-input: #2C2C2C;
    --text-main: #FFFFFF; --text-sub: #A0A0A0; --text-muted: #6E6E6E;
    --border: #333333; --border-light: #333333; --th-bg: #1E1E1E;
    --neutral-bg: #333333; --neutral-fg: #A0A0A0;
    --shadow-sm: 0 1px 2px 0 rgba(0,0,0,0.3);
    --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.4), 0 2px 4px -1px rgba(0,0,0,0.2);
}

/* === Base === */
body { 
    font-family: "Pretendard", "Inter", -apple-system, BlinkMacSystemFont, system-ui, sans-serif; 
    background-color: var(--bg-page); 
    /* The Narrative Grid: Subtle grid pattern for logical structure */
    background-image: linear-gradient(to right, rgba(0, 0, 0, 0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(0, 0, 0, 0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    color: var(--text-main); margin: 0; padding: 0; letter-spacing: -0.015em; -webkit-font-smoothing: antialiased; transition: background-color 0.3s, color 0.3s; line-height: 1.5; }
h1 { color: var(--text-main); font-size: 1.5rem; font-weight: 700; margin: 0 0 1.5rem 0; letter-spacing: -0.025em; }

/* === Layout: Sidebar & Main === */
.app-container { display: flex; min-height: 100vh; }

/* Sidebar */
.sidebar { width: 260px; background: var(--bg-card); border-right: 1px solid var(--border); display: flex; flex-direction: column; position: fixed; top: 0; bottom: 0; left: 0; z-index: 50; transition: transform 0.3s ease; }
/* The Precision Star: Highlight brand identity in header */
.sidebar-header { padding: 1.5rem; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid var(--border-light); }
.sidebar-header h2 { font-size: 1.25rem; font-weight: 800; color: var(--primary); margin: 0; letter-spacing: -0.02em; }

.sidebar-nav { flex: 1; overflow-y: auto; padding: 1rem; }
.nav-section { font-size: 0.7rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin: 1.5rem 0 0.5rem 0.75rem; letter-spacing: 0.05em; }
.nav-section:first-child { margin-top: 0; }

.nav-item { display: flex; align-items: center; padding: 0.75rem; color: var(--text-sub); text-decoration: none; border-radius: var(--radius-btn); font-weight: 500; margin-bottom: 4px; transition: var(--transition); font-size: 0.9rem; gap: 10px; }
.nav-icon { width: 20px; height: 20px; stroke-width: 2; stroke: currentColor; fill: none; stroke-linecap: round; stroke-linejoin: round; opacity: 0.7; }
.nav-item:hover { background-color: var(--bg-soft); color: var(--text-main); }
.nav-item.active { background-color: var(--bg-soft); color: var(--primary); font-weight: 700; border-left: 3px solid var(--primary); border-radius: 4px; padding-left: calc(0.75rem - 3px); box-shadow: var(--shadow-sm); }
.nav-item.active .nav-icon { opacity: 1; stroke: var(--primary); }

.sidebar-footer { padding: 1rem; border-top: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; gap: 8px; }

/* Main Content */
.main-content { flex: 1; margin-left: 260px; padding: 2rem; max-width: 100%; box-sizing: border-box; transition: margin-left 0.3s ease; }
.top-bar { display: flex; justify-content: flex-end; align-items: center; margin-bottom: 1.5rem; height: 40px; }

/* Mobile Responsive Header */
.mobile-header { display: none; padding: 1rem; background: var(--bg-card); border-bottom: 1px solid var(--border); align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 40; }
.mobile-toggle { background: transparent; border: none; font-size: 1.5rem; cursor: pointer; color: var(--text-main); padding: 0.25rem; display: flex; align-items: center; justify-content: center; }
.overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 45; backdrop-filter: blur(2px); }

/* === Components === */
.theme-toggle { padding: 8px; background: transparent; border: 1px solid var(--border); border-radius: 8px; cursor: pointer; font-size: 1.1rem; line-height: 1; transition: var(--transition); color: var(--text-sub); display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; }
.theme-toggle:hover { background: var(--bg-soft); color: var(--text-main); border-color: var(--text-muted); }
.nav-btn { padding: 8px 16px; text-decoration: none; border-radius: var(--radius-btn); font-size: 0.85rem; font-weight: 600; transition: var(--transition); background-color: var(--bg-card); color: var(--text-sub); border: 1px solid var(--border); display: inline-flex; align-items: center; gap: 6px; }
.nav-btn:hover { background-color: var(--bg-soft); color: var(--text-main); border-color: var(--text-muted); }
.nav-btn.active { background-color: var(--primary); color: white; border-color: var(--primary); }

/* === Dashboard & Cards === */
.dashboard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1.5rem; }
.card { background: var(--bg-card); border-radius: var(--radius-card); box-shadow: var(--shadow-sm); border: 1px solid var(--border); overflow: hidden; display: flex; flex-direction: column; transition: var(--transition); position: relative; }
.card:hover { box-shadow: var(--shadow-md); transform: translateY(-2px); }
.card-header { padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--border-light); display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; background-color: var(--bg-card); }
.card-title-group { display: flex; flex-direction: column; gap: 0.25rem; }
.card-title { font-size: 1rem; font-weight: 700; color: var(--text-main); margin: 0; }
.last-run { font-size: 0.75rem; color: var(--text-muted); font-weight: 500; }
.card-actions { display: flex; align-items: center; gap: 8px; }
.refresh-btn { padding: 6px 12px; background-color: transparent; color: var(--primary); border: 1px solid var(--primary); border-radius: 6px; font-size: 0.75rem; font-weight: 600; cursor: pointer; transition: var(--transition); white-space: nowrap; }
.refresh-btn:hover { background-color: var(--primary); color: white; }
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
.table-wrapper { overflow-x: auto; background: var(--bg-card); border-radius: var(--radius-card); box-shadow: var(--shadow-sm); border: 1px solid var(--border); }

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
.summary-card { background: var(--bg-card); padding: 1.5rem; border-radius: var(--radius-card); box-shadow: var(--shadow-sm); border: 1px solid var(--border); display: flex; flex-direction: column; align-items: center; justify-content: center; transition: var(--transition); }
.summary-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.summary-value { font-size: 2rem; font-weight: 800; color: var(--text-main); margin: 0.5rem 0; line-height: 1; }
.summary-label { color: var(--text-sub); font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
.help-text { font-size: 0.8rem; color: var(--text-muted); margin: 6px 0 0 0; line-height: 1.4; }
.info-banner { background: var(--info-bg); border: 1px solid rgba(229, 170, 112, 0.3); border-radius: var(--radius-btn); padding: 1rem; color: #8D5A18; font-size: 0.9rem; margin-bottom: 1.5rem; line-height: 1.5; display: flex; gap: 12px; align-items: flex-start; }
.warn-banner { background: var(--warning-bg); border: 1px solid rgba(245, 158, 11, 0.2); border-radius: var(--radius-btn); padding: 1rem; color: var(--warning-fg); font-size: 0.9rem; margin-bottom: 1rem; line-height: 1.5; }

/* === Forms & Buttons === */
input, select, textarea { background: var(--bg-input); color: var(--text-main); border: 1px solid var(--border); border-radius: var(--radius-btn); transition: var(--transition); font-family: inherit; }
input:focus, select:focus, textarea:focus { border-color: var(--primary); outline: none; box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.1); }
button { padding: 0.75rem 1.5rem; border: none; border-radius: var(--radius-btn); background-color: var(--primary); color: white; font-weight: 600; cursor: pointer; transition: var(--transition); font-size: 0.95rem; }
button:hover { background-color: var(--primary-hover); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.btn-accent { background-color: var(--text-main); color: var(--bg-card); }
.btn-accent:hover { background-color: var(--accent-hover); }
.btn-outline-danger { padding: 6px 14px; background: transparent; color: var(--danger-fg); border: 1px solid var(--danger-fg); border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.85rem; }
.btn-outline-danger:hover { background: var(--danger-bg); }
.btn-outline-success { padding: 6px 14px; background: transparent; color: var(--success-fg); border: 1px solid var(--success-fg); border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.85rem; }
.btn-outline-success:hover { background: var(--success-bg); }
.form-inline { margin: 0; }
.form-group { margin-bottom: 1.25rem; }
.form-label { display: block; font-weight: 600; margin-bottom: 0.5rem; color: var(--text-main); font-size: 0.9rem; }
.form-input, .form-select, .form-textarea { width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; box-sizing: border-box; background: var(--bg-input); color: var(--text-main); font-size: 0.95rem; }
.form-textarea { resize: vertical; min-height: 100px; }

/* === System Status Bar === */
.system-status-bar { display: flex; gap: 1.5rem; background: var(--bg-card); padding: 0.75rem 1.5rem; border-radius: var(--radius-card); border: 1px solid var(--border); margin-bottom: 2rem; align-items: center; flex-wrap: wrap; box-shadow: var(--shadow-sm); }
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
.gap-2 { gap: 0.5rem; }
.gap-4 { gap: 1rem; }
.mb-2 { margin-bottom: 0.5rem; }
.mb-3 { margin-bottom: 0.75rem; }
.mb-4 { margin-bottom: 1rem; }
.mb-6 { margin-bottom: 1.5rem; }
.mt-0 { margin-top: 0; }
.mt-2 { margin-top: 0.5rem; }
.text-center { text-align: center; }
.text-right { text-align: right; }
.font-bold { font-weight: 700; }
.text-sm { font-size: 0.85rem; }
.text-lg { font-size: 1.1rem; }
.text-primary { color: var(--primary); }
.text-success { color: var(--success-fg); }
.text-danger { color: var(--danger-fg); }
.text-sub { color: var(--text-sub); }
.text-muted { color: var(--text-muted); }
.bg-soft { background-color: var(--bg-soft); }
.rounded-lg { border-radius: 8px; }
.flex-1 { flex: 1; }
.p-4 { padding: 1rem; }
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
.text-green-500 { color: #10b981; }
.text-orange-500 { color: #f59e0b; }
.w-150 { width: 150px; }
.w-120 { width: 120px; }
.min-w-150 { min-width: 150px; }
.min-w-120 { min-width: 120px; }
.min-w-200 { min-width: 200px; }
.flex-2 { flex: 2; }
.max-w-600 { max-width: 600px; }
.bg-border-light { background-color: var(--border-light); }
.border-danger { border-color: var(--danger-bg); }
.w-auto { width: auto; }
.text-truncate { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 250px; }
.border-b { border-bottom: 1px solid var(--border-light); }
.text-left { text-align: left; }

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
.guide-card { border-left: 4px solid var(--primary); background: var(--bg-card); margin-bottom: 2rem; box-shadow: var(--shadow-md); }

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
}""")

# Always overwrite login.css to apply latest brand colors
with open(login_css_path, 'w', encoding='utf-8') as f:
    f.write(""":root {
    --primary: #E5AA70; --primary-hover: #D4955D;
    --accent: #E5AA70;
    --accent-hover: #D4955D;
    --bg-page: #F8F9FA; --bg-card: #FFFFFF; --bg-input: #FFFFFF;
    --text-main: #000000; --text-sub: #4A5568;
    --border: #E7E7E7;
    --danger-fg: #dc2626;
    --shadow-md: 0 3px 4px -1px rgba(0,0,0,0.1), 0 1px 3px -1px rgba(0,0,0,0.1);
    --radius-card: 14px; --radius-btn: 12px;
}
html.dark {
    --primary: #E5AA70; --primary-hover: #D4955D;
    --accent: #E5AA70;
    --accent-hover: #D4955D;
    --bg-page: #121212; --bg-card: #1E1E1E; --bg-input: #2C2C2C;
    --text-main: #FFFFFF; --text-sub: #A0A0A0;
    --border: #4F4F4F;
    --shadow-md: 0 3px 4px -1px rgba(0,0,0,0.3), 0 1px 3px -1px rgba(0,0,0,0.2);
}
body { font-family: "Pretendard", "Inter", -apple-system, BlinkMacSystemFont, system-ui, sans-serif; background-color: var(--bg-page); color: var(--text-main); display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; letter-spacing: -0.015em; -webkit-font-smoothing: antialiased; transition: background-color 0.3s, color 0.3s; }
.login-container { background: var(--bg-card); padding: 2.5rem; border-radius: var(--radius-card); box-shadow: var(--shadow-md); width: 100%; max-width: 400px; border: 1px solid var(--border); transition: background-color 0.3s, border-color 0.3s; }
h1 { color: var(--primary); text-align: center; margin-bottom: 2rem; font-size: 1.5rem; border-bottom: 2px solid var(--primary); padding-bottom: 10px; }
input { width: 100%; padding: 12px; margin-bottom: 1rem; border: 1px solid var(--border); border-radius: var(--radius-btn); box-sizing: border-box; background: var(--bg-input); color: var(--text-main); transition: border-color 0.2s; }
input:focus { border-color: var(--primary); outline: none; }
button { width: 100%; padding: 12px; background-color: var(--primary); color: white; border: none; border-radius: var(--radius-btn); font-weight: 600; cursor: pointer; transition: background-color 0.2s; }
button:hover { background-color: var(--primary-hover); }
.error { color: var(--danger-fg); text-align: center; margin-top: 1rem; font-size: 0.9rem; }""")

# [Self-Repair] 주요 HTML 템플릿 파일 자동 생성
templates_to_create = {
    'base.html': """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    {% block head_meta %}{% endblock %}
    <title>TrustFin Admin</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}?v=16" type="text/css">
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
            <div class="top-bar">
                {% block header_actions %}{% endblock %}
            </div>

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
    </script>
</body>
</html>""",
    'login.html': """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8"><title>Login - TrustFin Admin</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='login.css') }}?v=16" type="text/css">
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
        <p class="text-center text-sub text-sm mb-6 mt-neg-1">관리자 계정으로만 접근 가능합니다. 계정 정보가 없으면 시스템 담당자에게 문의하세요.</p>
        <form method="post">
            <input type="text" name="username" placeholder="관리자 아이디 입력 (예: admin)" required>
            <input type="password" name="password" placeholder="비밀번호 입력" required>
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

{% block header_actions %}
    <a href="/toggle_refresh" class="nav-btn {{ 'active' if auto_refresh else '' }}" title="{{ '자동 새로고침 ON: 30초마다 대시보드가 자동 업데이트됩니다. 클릭하면 OFF로 전환합니다.' if auto_refresh else '자동 새로고침 OFF: 클릭하면 30초 간격 자동 업데이트를 켭니다.' }}">
        {{ 'Auto Refresh: ON' if auto_refresh else 'Auto Refresh: OFF' }}
    </a>
{% endblock %}

{% block content %}
        <!-- Educational Guide Card -->
        <div class="card guide-card">
            <div class="card-p">
                <div class="flex items-center gap-2 mb-2">
                    <span class="badge badge-info">교육용 가이드</span>
                    <h3 class="font-bold text-sm">대시보드의 역할</h3>
                </div>
                <p class="text-sm text-sub">
                    이 대시보드는 <strong>TrustFin</strong> 서비스의 두뇌 역할을 하는 관리자 페이지의 메인 화면입니다. 금융 데이터 수집 현황, 시스템 상태, 그리고 핵심적인 신용 평가 가중치를 한눈에 파악할 수 있도록 설계되었습니다. <br>특히 <strong>'현재 신용 평가 가중치'</strong> 섹션은 AI가 어떤 기준으로 사용자를 평가하고 있는지 투명하게 보여주며, 이는 XAI(설명 가능한 AI)의 핵심 원칙인 <strong>투명성</strong>을 관리자 관점에서 구현한 것입니다.
                </p>
            </div>
        </div>

        <!-- System Status Bar -->
        <div class="system-status-bar">
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
            <div class="status-item">
                <span class="status-label">Version</span>
                <span class="status-value version-text">v0.1.0 (Proto)</span>
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

        <!-- 신용 평가 가중치 요약 -->
        <div class="card mb-6">
            <div class="card-header">
                <h3 class="card-title">현재 신용 평가 가중치</h3>
                <a href="/credit-weights" class="nav-btn" title="신용평가 가중치 상세 설정 페이지로 이동합니다.">설정 변경</a>
            </div>
            <div class="card-p">
                <p class="help-text mb-3">세 가중치의 합은 1.0이어야 합니다. 자세한 조정은 <strong>신용평가 설정</strong> 메뉴에서 할 수 있습니다.</p>
                <div class="credit-weights-body">
               <div class="weight-item">
                   <div class="weight-label">소득 비중</div>
                   <div class="weight-value text-primary" title="WEIGHT_INCOME: 유저의 연 소득이 신용 점수에 미치는 가중치">{{ stats.WEIGHT_INCOME | default(0.5) }}</div>
                </div>
                <div class="weight-item middle">
                    <div class="weight-label">고용 안정성</div>
                    <div class="weight-value" style="color: #10b981;" title="WEIGHT_JOB_STABILITY: 고용 형태에 따른 안정성이 신용 점수에 미치는 가중치">{{ stats.WEIGHT_JOB_STABILITY | default(0.3) }}</div>
                </div>
                <div class="weight-item">
                    <div class="weight-label">자산 비중</div>
                    <div class="weight-value" style="color: #f59e0b;" title="WEIGHT_ESTATE_ASSET: 보유 자산이 신용 점수에 미치는 가중치">{{ stats.WEIGHT_ESTATE_ASSET | default(0.2) }}</div>
                </div>
            </div>
            </div>
        </div>

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
                            <button type="submit" name="job" value="loan" class="refresh-btn" title="금감원 대출상품 데이터를 지금 즉시 수동 수집합니다.">새로고침</button>
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
                            <button type="submit" name="job" value="economy" class="refresh-btn" title="경제 지표 데이터를 지금 즉시 수동 수집합니다.">새로고침</button>
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
                            <button type="submit" name="job" value="income" class="refresh-btn" title="통계청 소득정보를 지금 즉시 수동 수집합니다.">새로고침</button>
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
            <th class="th-w-30 text-left nowrap">실행 시간</th>
            <th class="th-w-15 text-center nowrap">상태</th>
            <th class="th-w-15 text-right nowrap">건수</th>
            <th class="th-w-40 text-left nowrap">메시지</th>
        </tr></thead>
        <tbody>
            {% for log in logs %}
            <tr>
                <td class="text-sub text-left">{{ log.executed_at.strftime('%Y-%m-%d %H:%M:%S') if log.executed_at else '-' }}</td>
                <td class="text-center">
                    <span class="badge {{ 'badge-danger' if log.status == 'FAIL' else 'badge-success' if log.status == 'SUCCESS' else 'badge-neutral' }}">{{ log.status }}</span>
                </td>
                <td class="text-right font-bold text-primary nowrap">{{ "{:,}".format(log.row_count) }}</td>
                <td class="text-left" title="{{ log.error_message if log.error_message else '' }}">
                    <div class="text-sub text-sm text-truncate">{{ log.error_message if log.error_message else '-' }}</div>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="4" class="text-center text-muted p-4">수집된 로그가 없습니다.</td></tr>
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
            <span class="badge badge-info">설계 의도</span>
            <h3 class="font-bold text-sm">데이터 수집의 투명성</h3>
        </div>
        <p class="text-sm text-sub">
            신뢰할 수 있는 AI는 신뢰할 수 있는 데이터에서 시작됩니다. 이 페이지에서는 <strong>금융감독원(대출상품), 통계청(소득/경제지표)</strong> 등 공신력 있는 외부 기관의 데이터를 수집하는 파이프라인을 관리합니다. <br>각 데이터 소스별로 수집 상태를 모니터링하고 제어함으로써, AI 모델이 학습하고 추론하는 데이터의 <strong>최신성과 무결성</strong>을 보장합니다.
        </p>
    </div>
</div>

<div class="info-banner">데이터 수집 소스별로 자동 수집 활성화 여부를 설정하고, 필요 시 수동으로 즉시 수집할 수 있습니다. OFF 상태에서는 자동 스케줄 수집이 실행되지 않으며, 수동 수집 버튼도 비활성화됩니다.</div>

<div class="dashboard-grid">
    {% for src in sources %}
    <div class="card card-p">
        <div class="flex justify-between items-center mb-4">
            <h3 class="card-title">{{ src.label }}</h3>
            <span class="{{ 'badge-on' if src.enabled else 'badge-off' }}" title="{{ '수집 활성화 상태' if src.enabled else '수집 비활성화 상태' }}">
                {{ 'ON' if src.enabled else 'OFF' }}
            </span>
        </div>
        <div class="text-sm text-sub mb-4">
            <div>최근 실행: {{ src.last_run }}</div>
            <div>최근 상태: <span class="font-bold {{ 'text-success' if src.last_status == 'SUCCESS' else 'text-danger' if src.last_status == 'FAIL' else 'text-sub' }}">{{ src.last_status or '-' }}</span></div>
            <div>수집 건수: {{ src.last_count }}</div>
        </div>
        <div class="flex gap-2">
            <form action="/toggle_collector" method="post" class="flex-1">
                <input type="hidden" name="source" value="{{ src.key }}">
                <button type="submit" title="{{ '수집을 비활성화합니다.' if src.enabled else '수집을 활성화합니다.' }}" class="{{ 'btn-outline-danger' if src.enabled else 'btn-outline-success' }} w-full p-2">
                    {{ '비활성화' if src.enabled else '활성화' }}
                </button>
            </form>
            <form action="/trigger" method="post" class="flex-1">
                <button type="submit" name="job" value="{{ src.trigger_val }}" title="지금 즉시 이 소스의 데이터를 수집합니다." class="refresh-btn w-full p-2"
                    {{ 'disabled' if not src.enabled else '' }}>수동 수집</button>
            </form>
        </div>
        {% if not src.enabled %}
        <p class="help-text text-danger mt-2">수집이 비활성화되어 있습니다. 수동 수집을 실행하려면 먼저 활성화하세요.</p>
        {% endif %}
    </div>
    {% endfor %}
</div>
{% endblock %}""",
    'credit_weights.html': """{% extends "base.html" %}
{% block content %}
<h1>신용평가 가중치 관리</h1>

<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">XAI 핵심 기능</span>
            <h3 class="font-bold text-sm">설명 가능한 신용 평가 모델링</h3>
        </div>
        <p class="text-sm text-sub">
            기존 금융권의 신용 평가는 '블랙박스'처럼 내부 로직을 알기 어려웠습니다. TrustFin은 관리자가 <strong>소득, 고용 안정성, 자산</strong> 등 핵심 변수의 가중치를 직접 조정하고, 그 결과가 어떻게 반영되는지 시뮬레이션할 수 있게 합니다. <br>이 설정값은 사용자에게 제공되는 <strong>'AI 분석 리포트'</strong>의 근거가 되며, 사용자가 자신의 평가 결과를 납득하고 개선할 수 있도록 돕는 <strong>설명 가능성(Explainability)</strong>의 기반이 됩니다.
        </p>
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
                <label class="form-label text-green-500">고용 안정성 (WEIGHT_JOB_STABILITY)</label>
                <input type="range" min="0" max="1" step="0.01" name="job_weight" value="{{ job_weight }}" id="rng_job" oninput="syncWeight()" class="w-full">
                <input type="number" step="0.01" min="0" max="1" id="num_job" value="{{ job_weight }}" onchange="syncFromNum('job')" class="form-input mt-2">
                <p class="help-text">0.0~1.0 범위. 고용 형태(대기업·공무원→1.0, 무직→0.2)와 곱해집니다.</p>
            </div>
            <div>
                <label class="form-label text-orange-500">자산 비중 (WEIGHT_ESTATE_ASSET)</label>
                <input type="range" min="0" max="1" step="0.01" name="asset_weight" value="{{ asset_weight }}" id="rng_asset" oninput="syncWeight()" class="w-full">
                <input type="number" step="0.01" min="0" max="1" id="num_asset" value="{{ asset_weight }}" onchange="syncFromNum('asset')" class="form-input mt-2">
                <p class="help-text">0.0~1.0 범위. 보유 자산 금액을 정규화한 점수에 곱해집니다.</p>
            </div>
        </div>
        <!-- 합계 표시 + 비율 바 -->
        <div class="mb-2 text-lg font-bold" title="세 가중치의 합은 반드시 1.0이어야 합니다.">합계: <span id="weightSum" class="{{ 'text-success' if (income_weight + job_weight + asset_weight) | round(2) == 1.0 else 'text-danger' }}">{{ (income_weight + job_weight + asset_weight) | round(2) }}</span></div>
        <div style="display: flex; height: 24px; border-radius: 8px; overflow: hidden; border: 1px solid var(--border);">
            <div id="bar_income" style="background: var(--primary); transition: width 0.2s; width: {{ income_weight * 100 }}%;"></div>
            <div id="bar_job" style="background: #10b981; transition: width 0.2s; width: {{ job_weight * 100 }}%;"></div>
            <div id="bar_asset" style="background: #f59e0b; transition: width 0.2s; width: {{ asset_weight * 100 }}%;"></div>
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
                <span class="text-sm text-sub">현재: {{ "{:,.0f}".format(norm_income_ceiling) }}원</span>
                <p class="help-text">이 금액 이상의 연 소득은 소득 점수 1.0(만점)을 받습니다. 기본값: 1억원.</p>
            </div>
            <div>
                <label class="form-label">자산 만점 기준 (원)</label>
                <input type="number" name="norm_asset_ceiling" value="{{ norm_asset_ceiling | int }}" step="10000000" placeholder="예: 500000000 (5억원)" class="form-input">
                <span class="text-sm text-sub">현재: {{ "{:,.0f}".format(norm_asset_ceiling) }}원</span>
                <p class="help-text">이 금액 이상의 보유 자산은 자산 점수 1.0(만점)을 받습니다. 기본값: 5억원.</p>
            </div>
        </div>
    </div>

    <!-- 섹션 3: XAI 설명 임계값 -->
    <div class="card card-p mb-6">
        <h3 class="card-title mt-0" style="color: var(--accent);">XAI 설명 임계값 (Explanation Thresholds)</h3>
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

    <button type="submit" title="변경 사항을 즉시 DB에 저장합니다." class="btn-accent" style="padding: 12px 32px; font-size: 1rem;">설정 저장</button>
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
            <span class="badge badge-info">서비스 전략</span>
            <h3 class="font-bold text-sm">추천 알고리즘의 유연성</h3>
        </div>
        <p class="text-sm text-sub">
            단순히 금리가 낮은 상품만 추천하는 것이 정답은 아닙니다. 사용자의 상황(한도가 중요한지, 금리가 중요한지)에 따라 추천 전략을 유연하게 변경할 수 있어야 합니다. <br>이 페이지에서는 <strong>정렬 우선순위</strong>와 <strong>금리 민감도</strong> 등을 조정하여, AI가 어떤 기준으로 상품을 추천할지 서비스의 방향성을 결정합니다.
        </p>
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
    <button type="submit" title="변경 사항을 저장합니다." class="btn-accent" style="padding: 12px 32px; font-size: 1rem;">설정 저장</button>
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
{% endblock %}""",
    'missions.html': """{% extends "base.html" %}
{% block content %}
<h1>미션 관리</h1>

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
    </div>
    <div class="summary-card">
        <div class="summary-label">진행(in_progress)</div>
        <div class="summary-value text-primary">{{ in_progress }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">완료(completed)</div>
        <div class="summary-value text-success">{{ completed }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">완료율</div>
        <div class="summary-value text-primary">{{ "%.1f" | format(completion_rate) }}%</div>
    </div>
</div>

<div class="card card-p mb-6">
    <h3 class="card-title text-primary text-sm mt-0">유형별 분포</h3>
    {% for type_name, count in type_counts.items() %}
    <div class="flex items-center mb-2 gap-2">
        <span style="width: 90px; font-size: 0.85rem; font-weight: 600;">{{ type_name }}</span>
        <div style="flex: 1; background: var(--border-light); border-radius: 8px; height: 20px;">
            <div style="background: var(--primary); height: 100%; border-radius: var(--radius-btn); width: {{ (count / total * 100) if total > 0 else 0 }}%; min-width: 2px;"></div>
        </div>
        <span style="width: 30px; text-align: right; font-size: 0.85rem;">{{ count }}</span>
    </div>
    {% endfor %}
</div>

<form method="get" class="mb-4 bg-soft rounded-lg flex gap-2 items-center flex-wrap p-4">
    <span class="font-semibold text-sub">필터:</span>
    <select name="status_filter" class="form-select w-auto">
        <option value="">전체 상태</option>
        <option value="pending" {% if status_filter == 'pending' %}selected{% endif %}>대기 (pending)</option>
        <option value="in_progress" {% if status_filter == 'in_progress' %}selected{% endif %}>진행 (in_progress)</option>
        <option value="completed" {% if status_filter == 'completed' %}selected{% endif %}>완료 (completed)</option>
        <option value="expired" {% if status_filter == 'expired' %}selected{% endif %}>만료 (expired)</option>
    </select>
    <select name="type_filter" class="form-select w-auto">
        <option value="">전체 유형</option>
        <option value="savings" {% if type_filter == 'savings' %}selected{% endif %}>savings (저축)</option>
        <option value="spending" {% if type_filter == 'spending' %}selected{% endif %}>spending (지출 절감)</option>
        <option value="credit" {% if type_filter == 'credit' %}selected{% endif %}>credit (신용 관리)</option>
        <option value="investment" {% if type_filter == 'investment' %}selected{% endif %}>investment (투자)</option>
        <option value="lifestyle" {% if type_filter == 'lifestyle' %}selected{% endif %}>lifestyle (생활 습관)</option>
    </select>
    <button type="submit" class="btn-accent" style="padding: 8px 16px;">적용</button>
    {% if status_filter or type_filter %}
        <a href="/missions" class="nav-btn">초기화</a>
    {% endif %}
</form>

<div class="table-wrapper">
    <table class="w-full">
        <thead><tr>
            <th>ID</th>
            <th>유저</th>
            <th>미션 제목</th>
            <th>유형</th>
            <th>대출 목적</th>
            <th>상태</th>
            <th>난이도</th>
            <th>포인트</th>
            <th>마감일</th>
        </tr></thead>
        <tbody>
            {% for m in missions %}
            <tr>
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
                    {% else %}
                        <span class="badge badge-warning">pending</span>
                    {% endif %}
                </td>
                <td>{{ m.difficulty }}</td>
                <td>{{ m.reward_points }}</td>
                <td>{{ m.due_date or '-' }}</td>
            </tr>
            {% else %}
            <tr><td colspan="9" class="text-center text-sub p-4">미션이 없습니다.</td></tr>
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
    <table class="w-full">
        <tr><td class="font-bold text-sub w-150">Mission ID</td><td>{{ mission.mission_id }}</td></tr>
        <tr><td class="font-bold text-sub">유저 ID</td><td>{{ mission.user_id }}</td></tr>
        <tr><td class="font-bold text-sub">미션 제목</td><td class="font-bold">{{ mission.mission_title }}</td></tr>
        <tr><td class="font-bold text-sub">미션 설명</td><td>{{ mission.mission_description or '-' }}</td></tr>
        <tr><td class="font-bold text-sub">유형</td><td>{{ mission.mission_type }}</td></tr>
        <tr><td class="font-bold text-sub">대출 목적</td><td>{{ mission.loan_purpose or '-' }}</td></tr>
        <tr><td class="font-bold text-sub">상태</td><td>{{ mission.status }}</td></tr>
        <tr><td class="font-bold text-sub">난이도</td><td>{{ mission.difficulty }}</td></tr>
        <tr><td class="font-bold text-sub">보상 포인트</td><td>{{ mission.reward_points }}</td></tr>
        <tr><td class="font-bold text-sub">마감일</td><td>{{ mission.due_date or '-' }}</td></tr>
        <tr><td class="font-bold text-sub">완료일</td><td>{{ mission.completed_at or '-' }}</td></tr>
        <tr><td class="font-bold text-sub">생성일</td><td>{{ mission.created_at }}</td></tr>
    </table>
</div>
{% endblock %}""",
    'points.html': """{% extends "base.html" %}
{% block content %}
<h1>포인트 관리</h1>

<div class="card guide-card">
    <div class="card-p">
        <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-info">게이미피케이션</span>
            <h3 class="font-bold text-sm">보상 시스템과 동기 부여</h3>
        </div>
        <p class="text-sm text-sub">
            금융 활동은 지루하고 어렵게 느껴질 수 있습니다. 이를 극복하기 위해 <strong>포인트 보상 시스템</strong>을 도입했습니다. 미션 달성에 대한 즉각적인 보상(포인트)을 제공함으로써, 사용자가 지속적으로 금융 상태를 관리하고 개선하도록 <strong>동기를 부여</strong>합니다.
        </p>
    </div>
</div>

<div class="info-banner">유저별 포인트 잔액, 지급/사용 현황을 모니터링합니다.</div>

<div class="summary-grid mb-6">
    <div class="summary-card">
        <div class="summary-label">총 유저 수</div>
        <div class="summary-value">{{ user_count }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">총 유통 포인트</div>
        <div class="summary-value">{{ "{:,}".format(total_balance) }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">총 지급 포인트</div>
        <div class="summary-value text-success">{{ "{:,}".format(total_earned) }}</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">총 사용 포인트</div>
        <div class="summary-value text-danger">{{ "{:,}".format(total_spent) }}</div>
    </div>
</div>

<div class="card card-p mb-6">
    <h3 class="card-title text-primary mt-0">수동 포인트 조정</h3>
    <div class="warn-banner">수동 포인트 조정은 즉시 반영되며 취소할 수 없습니다.</div>
    <form method="post" action="/points/adjust" class="flex gap-2 items-end flex-wrap">
        <div class="flex-1 min-w-150">
            <label class="form-label text-sm">유저 ID</label>
            <input type="text" name="user_id" placeholder="예: user_001" required class="form-input">
        </div>
        <div class="flex-1 min-w-120">
            <label class="form-label text-sm">금액 (양수=지급, 음수=차감)</label>
            <input type="number" name="amount" placeholder="예: 100 또는 -50" required class="form-input">
        </div>
        <div class="flex-2 min-w-200">
            <label class="form-label text-sm">사유</label>
            <input type="text" name="reason" placeholder="예: 이벤트 보상, 오류 정정" required class="form-input">
        </div>
        <button type="submit" class="btn-accent" style="padding: 10px 20px; white-space: nowrap;">포인트 조정</button>
    </form>
</div>

<div class="table-wrapper">
    <table class="w-full">
        <thead><tr>
            <th>유저 ID</th>
            <th class="text-right">잔액</th>
            <th class="text-right">총 지급</th>
            <th class="text-right">총 사용</th>
            <th>최근 업데이트</th>
            <th class="text-center">상세</th>
        </tr></thead>
        <tbody>
            {% for u in users %}
            <tr>
                <td class="font-bold">{{ u.user_id }}</td>
                <td class="text-right font-bold text-primary">{{ "{:,}".format(u.balance) }}</td>
                <td class="text-right text-success">{{ "{:,}".format(u.total_earned) }}</td>
                <td class="text-right text-danger">{{ "{:,}".format(u.total_spent) }}</td>
                <td>{{ u.updated_at if u.updated_at else '-' }}</td>
                <td class="text-center">
                    <a href="/points/{{ u.user_id }}" class="text-primary font-bold" style="text-decoration: none;">거래 내역</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="6" class="text-center text-sub p-4">포인트 데이터가 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
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
    <a href="/point-products/add" class="btn-accent" style="padding: 10px 20px; text-decoration: none;">상품 추가</a>
    <a href="/point-products/purchases" class="nav-btn" style="padding: 10px 20px; font-size: 1rem;">구매 내역 조회</a>
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
                        <a href="/point-products/{{ p.product_id }}/edit" class="nav-btn" style="padding: 4px 12px; font-size: 0.8rem;">수정</a>
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
        <button type="submit" class="btn-accent" style="padding: 12px 32px; font-size: 1rem;">저장</button>
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
        <button type="submit" class="btn-accent" style="padding: 8px 16px;">검색</button>
        {% if search_name or search_status %}
        <a href="/members" class="nav-btn">초기화</a>
        {% endif %}
    </form>
    <a href="/members/add" class="btn-accent" style="padding: 10px 20px; text-decoration: none;">회원 추가</a>
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
                    <a href="/members/{{ u.user_id }}" class="nav-btn" style="padding: 4px 12px; font-size: 0.8rem;">상세</a>
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
            <a href="/members/{{ user.user_id }}/edit" class="nav-btn" style="padding: 6px 16px; font-size: 0.85rem;">수정</a>
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
                <button type="submit" class="btn-accent" style="padding: 8px 16px; background-color: var(--warning-fg);">변경</button>
            </form>
        </div>
        <div class="card card-p border-danger">
            <h3 class="card-title text-danger text-sm mt-0 mb-3">회원 삭제</h3>
            <div class="warn-banner">삭제된 회원은 복구할 수 없습니다.</div>
            <form action="/members/{{ user.user_id }}/delete" method="post" onsubmit="return confirm('정말 삭제하시겠습니까?');">
                <button type="submit" class="w-full btn-outline-danger" style="padding: 10px;">회원 삭제</button>
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
        <button type="submit" class="btn-accent" style="padding: 12px 32px; font-size: 1rem;">저장</button>
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
        <div class="card-body" style="padding: 1.5rem;">
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
        <div class="card-body" style="padding: 1.5rem;">
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
    </div>
    <form method="get" action="{{ url_for('view_data', table_name=table_name) }}" class="mb-4 bg-soft rounded-lg flex gap-2 items-center flex-wrap p-4">
        <span class="font-semibold text-sub">검색:</span>
        <select name="search_col" class="form-select w-auto">
            {% for col in columns %}<option value="{{ col }}" {% if search_col == col %}selected{% endif %}>{{ col }}</option>{% endfor %}
        </select>
        <input type="text" name="search_val" value="{{ search_val if search_val else '' }}" placeholder="검색어 입력" class="form-input flex-1 min-w-200">
        <button type="submit" class="btn-accent" style="padding: 8px 16px;">검색</button>
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
                {% for row in rows %}<tr>{% for cell in row %}<td>{{ cell }}</td>{% endfor %}</tr>
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
                <span class="badge badge-info">XAI 검증 도구</span>
                <h3 class="font-bold text-sm">알고리즘 시뮬레이션</h3>
            </div>
            <p class="text-sm text-sub">
                설정한 신용 평가 가중치와 추천 알고리즘이 실제 사용자에게 어떤 결과를 보여줄지 미리 확인하는 도구입니다. 다양한 가상 프로필(사회초년생, 고소득자 등)을 입력하여 AI의 판단 결과를 검증함으로써, 알고리즘의 <strong>공정성과 정확성</strong>을 테스트할 수 있습니다.
            </p>
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
        <div>
            <h3 class="card-title mt-0 mb-4">추천 결과</h3>
            {% if result_html %}
                <div class="table-wrapper">{{ result_html|safe }}</div>
                <p class="text-sub text-sm mt-2">* 예상 금리는 현재 설정된 가중치 정책과 유저 프로필에 따라 계산됩니다.</p>
            {% else %}
                <div class="bg-soft rounded-lg text-center text-muted p-4 dashed-border">왼쪽 폼에 정보를 입력하고 추천을 실행해보세요.</div>
            {% endif %}
        </div>
    </div>
{% endblock %}"""
}

for filename, content in templates_to_create.items():
    path = os.path.join(template_dir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

app = Flask(__name__, static_folder=static_dir, static_url_path='/static', template_folder=template_dir)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_only_fallback_key')

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
    ]
    try:
        with engine.connect() as conn:
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
                ]
                for m in mock_missions:
                    conn.execute(text("""
                        INSERT INTO missions (user_id, mission_title, mission_description, mission_type, loan_purpose, status, difficulty, reward_points, due_date)
                        VALUES (:uid, :title, :desc, :mtype, :purpose, :status, :diff, :pts, DATE_ADD(CURDATE(), INTERVAL 30 DAY))
                    """), {'uid': m[0], 'title': m[1], 'desc': m[2], 'mtype': m[3], 'purpose': m[4], 'status': m[5], 'diff': m[6], 'pts': m[7]})

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
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

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
                    conn.execute(text("""
                        INSERT INTO point_transactions (user_id, amount, transaction_type, reason, admin_id, reference_id)
                        VALUES (:uid, :amt, :ttype, :reason, :admin, :ref)
                    """), {'uid': t[0], 'amt': t[1], 'ttype': t[2], 'reason': t[3], 'admin': t[4], 'ref': t[5]})

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

            conn.commit()
    except Exception as e:
        print(f"Schema init warning: {e}")

# 앱 시작 시 스키마 초기화 (DB 연결 가능 시)
try:
    _init_collector = DataCollector()
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
             'COLLECTOR_FSS_LOAN_ENABLED': '1', 'COLLECTOR_KOSIS_INCOME_ENABLED': '1', 'COLLECTOR_ECONOMIC_ENABLED': '1'}
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

def get_recent_logs(engine, source=None, limit=50):
    try:
        params = {}
        query = "SELECT * FROM collection_logs"
        if source:
            query += " WHERE target_source = %(source)s"
            params['source'] = source
        query += " ORDER BY executed_at DESC"
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
        collector = DataCollector()
        stats = get_dashboard_stats(collector.engine)
        loan_logs = get_recent_logs(collector.engine, source='FSS_LOAN_API', limit=50)
        economy_logs = get_recent_logs(collector.engine, source='ECONOMIC_INDICATORS', limit=50)
        income_logs = get_recent_logs(collector.engine, source='KOSIS_INCOME_API', limit=50)

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
            system_status=system_status)
    except Exception as e:
        system_status_error = {'db': False, 'collectors_active': 0, 'collectors_total': 3, 'now': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'recent_errors': 0}
        return render_template('index.html',
            message=message or f"시스템 오류: {e}", status=status or "error",
            loan_last_run="-", economy_last_run="-", income_last_run="-",
            loan_logs=[], economy_logs=[], income_logs=[],
            auto_refresh=session.get('auto_refresh', True), stats={},
            system_status=system_status_error)

# ==========================================================================
# [라우트] 인증
# ==========================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == os.getenv('ADMIN_USER', 'admin') and password == os.getenv('ADMIN_PASSWORD', 'admin1234'):
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('아이디 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')

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
        collector = DataCollector()
        configs = get_all_configs(collector.engine)

        source_defs = [
            {'key': 'FSS_LOAN', 'config_key': 'COLLECTOR_FSS_LOAN_ENABLED', 'label': '금감원 대출상품 (FSS Loan API)', 'trigger_val': 'loan', 'log_source': 'FSS_LOAN_API'},
            {'key': 'ECONOMIC', 'config_key': 'COLLECTOR_ECONOMIC_ENABLED', 'label': '경제 지표 (Economic Indicators)', 'trigger_val': 'economy', 'log_source': 'ECONOMIC_INDICATORS'},
            {'key': 'KOSIS_INCOME', 'config_key': 'COLLECTOR_KOSIS_INCOME_ENABLED', 'label': '통계청 소득정보 (KOSIS Income)', 'trigger_val': 'income', 'log_source': 'KOSIS_INCOME_API'},
        ]

        sources = []
        for sd in source_defs:
            logs = get_recent_logs(collector.engine, source=sd['log_source'], limit=1)
            last_log = logs[0] if logs else {}
            sources.append({
                'key': sd['key'],
                'label': sd['label'],
                'trigger_val': sd['trigger_val'],
                'enabled': configs.get(sd['config_key'], '1') == '1',
                'last_run': last_log.get('executed_at', '-') if not last_log.get('executed_at') else last_log['executed_at'].strftime('%Y-%m-%d %H:%M'),
                'last_status': last_log.get('status', '-'),
                'last_count': last_log.get('row_count', 0),
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
        collector = DataCollector()
        with collector.engine.connect() as conn:
            current = conn.execute(text("SELECT config_value FROM service_config WHERE config_key = :k"), {'k': config_key}).scalar()
            new_val = '0' if current == '1' else '1'
            conn.execute(text("UPDATE service_config SET config_value = :v WHERE config_key = :k"), {'v': new_val, 'k': config_key})
            conn.commit()
        flash(f'{source} 수집기가 {"ON" if new_val == "1" else "OFF"}로 변경되었습니다.', 'success')
    except Exception as e:
        flash(f'설정 변경 실패: {e}', 'error')
    return redirect(url_for('collection_management'))

@app.route('/trigger', methods=['POST'])
@login_required
def trigger_job():
    job_type = request.form.get('job')
    try:
        collector = DataCollector()
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
        collector = DataCollector()
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
        collector = DataCollector()
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
        collector = DataCollector()
        df = pd.read_sql("SELECT * FROM raw_loan_products", collector.engine)
        products_list = df.to_dict(orient='records')
        for p in products_list:
            if 'is_visible' not in p:
                p['is_visible'] = 1

        visible_count = sum(1 for p in products_list if p.get('is_visible', 1) == 1)
        hidden_count = len(products_list) - visible_count

        return render_template('products.html',
            products=products_list, total_count=len(products_list),
            visible_count=visible_count, hidden_count=hidden_count)
    except Exception as e:
        flash(f"상품 목록 로드 실패: {e}", 'error')
        return redirect(url_for('index'))

@app.route('/products/toggle_visibility', methods=['POST'])
@login_required
def toggle_product_visibility():
    bank = request.form.get('bank_name')
    product = request.form.get('product_name')
    try:
        collector = DataCollector()
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
        collector = DataCollector()
        status_filter = request.args.get('status_filter', '')
        type_filter = request.args.get('type_filter', '')

        where_clauses = []
        params = {}
        if status_filter:
            where_clauses.append("status = %(sf)s")
            params['sf'] = status_filter
        if type_filter:
            where_clauses.append("mission_type = %(tf)s")
            params['tf'] = type_filter

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        query = f"SELECT * FROM missions{where_sql} ORDER BY created_at DESC"
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

        return render_template('missions.html',
            missions=missions_list, total=total,
            pending=stats_dict.get('pending', 0),
            in_progress=stats_dict.get('in_progress', 0),
            completed=completed,
            completion_rate=(completed / total * 100) if total > 0 else 0,
            type_counts=type_counts,
            status_filter=status_filter, type_filter=type_filter)
    except Exception as e:
        flash(f"미션 목록 로드 실패: {e}", 'error')
        return redirect(url_for('index'))

@app.route('/missions/<int:mission_id>')
@login_required
def mission_detail(mission_id):
    try:
        collector = DataCollector()
        df = pd.read_sql("SELECT * FROM missions WHERE mission_id = %(id)s", collector.engine, params={'id': mission_id})
        if df.empty:
            flash('미션을 찾을 수 없습니다.', 'error')
            return redirect(url_for('missions'))
        mission = df.iloc[0].to_dict()
        return render_template('mission_detail.html', mission=mission)
    except Exception as e:
        flash(f"미션 상세 로드 실패: {e}", 'error')
        return redirect(url_for('missions'))

# ==========================================================================
# [라우트] F6: 포인트 관리
# ==========================================================================

@app.route('/points')
@login_required
def points():
    try:
        collector = DataCollector()
        df = pd.read_sql("SELECT * FROM user_points ORDER BY updated_at DESC", collector.engine)
        users_list = df.to_dict(orient='records')

        total_balance = int(df['balance'].sum()) if not df.empty else 0
        total_earned = int(df['total_earned'].sum()) if not df.empty else 0
        total_spent = int(df['total_spent'].sum()) if not df.empty else 0

        return render_template('points.html',
            users=users_list, user_count=len(users_list),
            total_balance=total_balance, total_earned=total_earned, total_spent=total_spent)
    except Exception as e:
        flash(f"포인트 관리 로드 실패: {e}", 'error')
        return redirect(url_for('index'))

@app.route('/points/<user_id>')
@login_required
def point_detail(user_id):
    try:
        collector = DataCollector()
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
        collector = DataCollector()
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
        collector = DataCollector()
        df = pd.read_sql("SELECT * FROM point_products ORDER BY created_at DESC", collector.engine)
        products_list = df.to_dict(orient='records')

        active_count = sum(1 for p in products_list if p.get('is_active', 1) == 1)
        inactive_count = len(products_list) - active_count

        return render_template('point_products.html',
            products=products_list, total_count=len(products_list),
            active_count=active_count, inactive_count=inactive_count)
    except Exception as e:
        flash(f"포인트 상품 목록 로드 실패: {e}", 'error')
        return redirect(url_for('index'))

@app.route('/point-products/add', methods=['GET', 'POST'])
@login_required
def point_product_add():
    if request.method == 'POST':
        try:
            collector = DataCollector()
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
        collector = DataCollector()
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
        collector = DataCollector()
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
        collector = DataCollector()
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
        collector = DataCollector()
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
            collector = DataCollector()
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
        collector = DataCollector()
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
        collector = DataCollector()
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

        collector = DataCollector()
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
        collector = DataCollector()
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
        collector = DataCollector()
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
    allowed_tables = ['raw_loan_products', 'raw_economic_indicators', 'raw_income_stats', 'collection_logs', 'service_config', 'missions', 'user_points', 'point_transactions', 'point_products', 'point_purchases', 'users']
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
        collector = DataCollector()
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
        rows = df.values.tolist()

        return render_template('data_viewer.html',
            table_name=table_name, columns=columns, rows=rows,
            page=page, total_pages=total_pages, total_count=total_count,
            sort_by=sort_by, order=order, search_col=search_col, search_val=search_val)
    except Exception as e:
        flash(f"데이터 조회 실패: {e}", "error")
        return redirect(url_for('index'))

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

            collector = DataCollector()
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
# 실행
# ==========================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)
