from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from functools import wraps
from collector import DataCollector
from recommendation_logic import recommend_products
import pandas as pd
import sys
import os
from sqlalchemy import text

# Flask 앱 초기화
# base.html이 현재 폴더에 있으므로 template_folder를 현재 경로('.')로 설정
app = Flask(__name__, template_folder='.')
app.secret_key = 'super_secret_key_for_admin_prototype'  # 세션 사용을 위한 비밀키 설정

# --------------------------------------------------------------------------
# [HTML] 사용자 화면과 동일한 디자인을 적용할 수 있는 템플릿
# --------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">

<head>
    <meta charset="UTF-8">
    {% if auto_refresh %}
    <meta http-equiv="refresh" content="30; url={{ url_for('index') }}">
    {% endif %}
    <title>Fintech Admin (Flask)</title>
    <style>
        body { font-family: 'Noto Sans KR', sans-serif; background-color: #f8f9fa; padding: 2rem; }
        .container { max-width: 1200px; margin: 0 auto; }
        
        /* Header Style */
        .header-container {
            background: white;
            padding: 1.5rem 2rem;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            margin-bottom: 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        h1 { color: #1e3a8a; margin: 0; font-size: 1.5rem; font-weight: 700; }

        /* Card Grid Layout */
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 1.5rem;
        }
        
        .card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border: 1px solid #e5e7eb;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        
        .card-header {
            padding: 1.25rem;
            border-bottom: 1px solid #f3f4f6;
            background-color: #fff;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }
        
        .card-title-group {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }
        
        .card-title {
            font-size: 1.1rem;
            font-weight: 700;
            color: #111827;
            margin: 0;
        }
        
        .last-run {
            font-size: 0.8rem;
            color: #6b7280;
        }
        
        .refresh-btn {
            padding: 0.5rem 0.75rem;
            background-color: #eff6ff;
            color: #2563eb;
            border: 1px solid #dbeafe;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
        }
        
        .refresh-btn:hover {
            background-color: #2563eb;
            color: white;
            border-color: #2563eb;
        }
        
        .card-body {
            padding: 0;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
        }

        .alert { padding: 1rem; margin-bottom: 1rem; border-radius: 5px; }
        .success { background-color: #d1fae5; color: #065f46; }
        .error { background-color: #fee2e2; color: #991b1b; }

        /* 테이블 스타일 추가 */
        .log-table-container {
            overflow-x: auto;
            max-height: 350px;
            overflow-y: auto;
        }
        table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
        th, td { padding: 10px 15px; text-align: left; border-bottom: 1px solid #f3f4f6; }
        th { background-color: #f9fafb; color: #4b5563; font-weight: 600; position: sticky; top: 0; z-index: 10; }
        tr:last-child td { border-bottom: none; }
        
        .status-badge { padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
        .status-fail { background-color: #fef2f2; color: #dc2626; }
        .status-success { background-color: #ecfdf5; color: #059669; }
        
        .nav-btn {
            padding: 8px 16px; text-decoration: none; border-radius: 6px; font-size: 0.9rem; font-weight: bold; margin-left: 10px;
        }

        /* Summary Dashboard Style */
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .summary-card {
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            border: 1px solid #e5e7eb;
            text-align: center;
        }
        .summary-value {
            font-size: 2rem;
            font-weight: 700;
            color: #1e3a8a;
            margin: 0.5rem 0;
        }
        .summary-label {
            color: #6b7280;
            font-size: 0.9rem;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header-container">
            <h1>🛠️ Fintech Service Admin</h1>
            <div>
                <a href="/toggle_refresh" class="nav-btn" style="background-color: {{ '#d1fae5' if auto_refresh else '#f3f4f6' }}; color: {{ '#065f46' if auto_refresh else '#6b7280' }};">
                    {{ '🔄 자동 갱신: ON' if auto_refresh else '⏸️ 자동 갱신: OFF' }}
                </a>
                <a href="/data/raw_loan_products" class="nav-btn" style="background-color: #e0e7ff; color: #3730a3;">📊 데이터 조회</a>
                <a href="/simulator" class="nav-btn" style="background-color: #fce7f3; color: #9d174d;">🧪 시뮬레이터</a>
                <a href="/settings" class="nav-btn" style="background-color: #f3f4f6; color: #374151;">⚙️ 설정</a>
                <a href="/logout" class="nav-btn" style="background-color: #fee2e2; color: #991b1b;">🚪 로그아웃</a>
            </div>
        </div>

        {% if message %}
            <div class="alert {{ status }}">{{ message }}</div>
        {% endif %}

        <!-- Summary Dashboard -->
        <div class="summary-grid">
            <div class="summary-card">
                <div class="summary-label">🏦 대출 상품 수</div>
                <div class="summary-value">{{ "{:,}".format(stats.loan_count | default(0)) }}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">📈 경제 지표 수</div>
                <div class="summary-value">{{ "{:,}".format(stats.economy_count | default(0)) }}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">📊 소득 통계 수</div>
                <div class="summary-value">{{ "{:,}".format(stats.income_count | default(0)) }}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">📋 총 수집 로그</div>
                <div class="summary-value">{{ "{:,}".format(stats.log_count | default(0)) }}</div>
            </div>
        </div>

        <!-- Policy Weights Summary -->
        <div style="background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; margin-bottom: 2rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin-top: 0; color: #1e3a8a; font-size: 1.1rem;">⚖️ 현재 신용 평가 가중치 설정</h3>
                <a href="/settings" class="nav-btn" style="background-color: #dbeafe; color: #1e40af; padding: 6px 12px; font-size: 0.8rem;">⚙️ 설정 변경</a>
            </div>
            <div style="display: flex; justify-content: space-around; align-items: center; padding-bottom: 1rem; border-bottom: 1px solid #f3f4f6;">
               <div style="text-align: center;">
                   <div style="font-size: 0.9rem; color: #6b7280; margin-bottom: 5px;">💰 소득 비중</div>
                   <div style="font-size: 1.8rem; font-weight: 700; color: #3b82f6;">{{ stats.WEIGHT_INCOME | default(0.5) }}</div>
                </div>
                <div style="text-align: center; border-left: 1px solid #f3f4f6; border-right: 1px solid #f3f4f6; padding: 0 40px;">
                    <div style="font-size: 0.9rem; color: #6b7280; margin-bottom: 5px;">🏢 고용 안정성</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: #10b981;">{{ stats.WEIGHT_JOB_STABILITY | default(0.3) }}</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 0.9rem; color: #6b7280; margin-bottom: 5px;">🏠 자산 비중</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: #f59e0b;">{{ stats.WEIGHT_ESTATE_ASSET | default(0.2) }}</div>
                </div>
            </div>
        </div>

        <div class="dashboard-grid">
            <!-- Card 1: Loan -->
            <div class="card">

                <div class="card-header">
                    <div class="card-title-group">
                        <h3 class="card-title">🏦 금감원 대출상품</h3>
                        <span class="last-run">최근 실행: {{ loan_last_run }}</span>
                    </div>
                    <form action="/trigger" method="post">
                        <button type="submit" name="job" value="loan" class="refresh-btn">🔄 새로고침</button>
                    </form>
                </div>
                <div class="card-body">
                    {{ loan_log_table|safe }}
                </div>
            </div>

            <!-- Card 2: Economy -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title-group">
                        <h3 class="card-title">📈 경제 지표</h3>
                        <span class="last-run">최근 실행: {{ economy_last_run }}</span>
                    </div>
                    <form action="/trigger" method="post">
                        <button type="submit" name="job" value="economy" class="refresh-btn">🔄 새로고침</button>
                    </form>
                </div>
                <div class="card-body">
                    {{ economy_log_table|safe }}
                </div>
            </div>

            <!-- Card 3: Income -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title-group">
                        <h3 class="card-title">📊 통계청 소득정보</h3>
                        <span class="last-run">최근 실행: {{ income_last_run }}</span>
                    </div>
                    <form action="/trigger" method="post">
                        <button type="submit" name="job" value="income" class="refresh-btn">🔄 새로고침</button>
                    </form>
                </div>
                <div class="card-body">
                    {{ income_log_table|safe }}
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

# --------------------------------------------------------------------------
# [HTML] 로그인 화면 템플릿
# --------------------------------------------------------------------------
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>Login - Fintech Admin</title>
    <style>
        body { font-family: 'Noto Sans KR', sans-serif; background-color: #f8f9fa; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-container { background: white; padding: 2.5rem; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }
        h1 { color: #1e3a8a; text-align: center; margin-bottom: 2rem; font-size: 1.5rem; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; }
        input { width: 100%; padding: 12px; margin-bottom: 1rem; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background-color: #3b82f6; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; transition: background 0.2s; }
        button:hover { background-color: #2563eb; }
        .error { color: #dc2626; text-align: center; margin-top: 1rem; font-size: 0.9rem; }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>🔒 관리자 로그인</h1>
        <form method="post">
            <input type="text" name="username" placeholder="아이디" required>
            <input type="password" name="password" placeholder="비밀번호" required>
            <button type="submit">로그인</button>
        </form>
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="error">{{ messages[0] }}</div>

            {% endif %}
        {% endwith %}
    </div>
</body>
</html>
"""

# --------------------------------------------------------------------------
# [HTML] 데이터 조회 템플릿
# --------------------------------------------------------------------------
DATA_VIEWER_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
    <h1>📊 수집 데이터 조회: {{ table_name }}</h1>
    <div style="margin-bottom: 20px;">
        <a href="/data/raw_loan_products" style="margin-right: 10px; font-weight: bold; color: {{ '#2563eb' if table_name == 'raw_loan_products' else '#6b7280' }}">🏦 대출 상품</a>
        <a href="/data/raw_economic_indicators" style="margin-right: 10px; font-weight: bold; color: {{ '#2563eb' if table_name == 'raw_economic_indicators' else '#6b7280' }}">📈 경제 지표</a>
        <a href="/data/raw_income_stats" style="margin-right: 10px; font-weight: bold; color: {{ '#2563eb' if table_name == 'raw_income_stats' else '#6b7280' }}">📊 소득 통계</a>
        <a href="/data/collection_logs" style="margin-right: 10px; font-weight: bold; color: {{ '#2563eb' if table_name == 'collection_logs' else '#6b7280' }}">📋 수집 로그</a>
    </div>
    
    <!-- Search Form -->
    <form method="get" action="{{ url_for('view_data', table_name=table_name) }}" style="margin-bottom: 20px; background: #f9fafb; padding: 15px; border-radius: 8px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
        <span style="font-weight: bold; color: #4b5563;">🔍 검색:</span>
        <select name="search_col" style="padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; background: white;">
            {% for col in columns %}
                <option value="{{ col }}" {% if search_col == col %}selected{% endif %}>{{ col }}</option>
            {% endfor %}
        </select>
        <input type="text" name="search_val" value="{{ search_val if search_val else '' }}" placeholder="검색어 입력..." style="padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; flex-grow: 1; min-width: 200px;">
        <button type="submit" style="padding: 8px 16px; background-color: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">검색</button>
        {% if search_val %}
            <a href="{{ url_for('view_data', table_name=table_name) }}" style="padding: 8px 16px; background-color: #9ca3af; color: white; text-decoration: none; border-radius: 4px; font-weight: bold;">초기화</a>
        {% endif %}
    </form>

    <div style="overflow-x: auto; background: white; padding: 1rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr>
                    {% for col in columns %}
                        <th style="background-color: #f3f4f6; padding: 10px; text-align: left; border-bottom: 2px solid #e5e7eb; white-space: nowrap;">
                            <a href="{{ url_for('view_data', table_name=table_name, page=1, sort_by=col, order='desc' if sort_by == col and order == 'asc' else 'asc', search_col=search_col, search_val=search_val) }}" 
                               style="text-decoration: none; color: #374151; display: flex; align-items: center; gap: 5px;">
                                {{ col }}
                                {% if sort_by == col %}
                                    <span style="color: #2563eb; font-size: 0.8em;">{{ '▲' if order == 'asc' else '▼' }}</span>
                                {% else %}
                                    <span style="color: #9ca3af; font-size: 0.8em; opacity: 0.5;">⇅</span>
                                {% endif %}
                            </a>
                        </th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for row in rows %}
                <tr>
                    {% for cell in row %}
                        <td style="padding: 10px; border-bottom: 1px solid #f3f4f6;">{{ cell }}</td>
                    {% endfor %}
                </tr>
                {% else %}
                <tr>
                    <td colspan="{{ columns|length }}" style="padding: 20px; text-align: center; color: #6b7280;">데이터가 없습니다.</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- Pagination Controls -->
    <div style="margin-top: 20px; display: flex; justify-content: center; align-items: center; gap: 15px;">
        {% if page > 1 %}
            <a href="{{ url_for('view_data', table_name=table_name, page=page-1, sort_by=sort_by, order=order, search_col=search_col, search_val=search_val) }}" style="padding: 8px 16px; background-color: #f3f4f6; color: #374151; text-decoration: none; border-radius: 6px; font-weight: bold;">◀ 이전</a>
        {% else %}
            <span style="padding: 8px 16px; background-color: #f9fafb; color: #9ca3af; border-radius: 6px; font-weight: bold; cursor: not-allowed;">◀ 이전</span>
        {% endif %}
        
        <span style="font-weight: 600; color: #4b5563;">
            Page <span style="color: #2563eb;">{{ page }}</span> of {{ total_pages }} 
            <span style="color: #9ca3af; font-size: 0.9em; margin-left: 5px;">(Total: {{ "{:,}".format(total_count) }})</span>
        </span>
        
        {% if page < total_pages %}
            <a href="{{ url_for('view_data', table_name=table_name, page=page+1, sort_by=sort_by, order=order, search_col=search_col, search_val=search_val) }}" style="padding: 8px 16px; background-color: #f3f4f6; color: #374151; text-decoration: none; border-radius: 6px; font-weight: bold;">다음 ▶</a>
        {% else %}
            <span style="padding: 8px 16px; background-color: #f9fafb; color: #9ca3af; border-radius: 6px; font-weight: bold; cursor: not-allowed;">다음 ▶</span>
        {% endif %}
    </div>
{% endblock %}
"""

# --------------------------------------------------------------------------
# [HTML] 추천 시뮬레이터 템플릿
# --------------------------------------------------------------------------
SIMULATOR_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
    <h1>🧪 대출 추천 시뮬레이터</h1>
    <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 2rem;">
        <!-- 입력 폼 -->
        <div style="background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); height: fit-content;">
            <h3 style="margin-top: 0;">👤 가상 유저 프로필</h3>
            <form method="post">
                <label style="display: block; margin-bottom: 0.5rem; font-weight: 600;">💰 연소득 (원)</label>
                <input type="number" name="annual_income" value="{{ income }}" style="width: 100%; padding: 10px; margin-bottom: 1rem; border: 1px solid #e5e7eb; border-radius: 6px;">
                
                <label style="display: block; margin-bottom: 0.5rem; font-weight: 600;">💸 희망 대출 금액 (원)</label>
                <input type="number" name="desired_amount" value="{{ amount }}" style="width: 100%; padding: 10px; margin-bottom: 1rem; border: 1px solid #e5e7eb; border-radius: 6px;">
                
                <label style="display: block; margin-bottom: 0.5rem; font-weight: 600;">🏢 고용 형태 (안정성)</label>
                <select name="job_score" style="width: 100%; padding: 10px; margin-bottom: 1rem; border: 1px solid #e5e7eb; border-radius: 6px; background: white;">
                    <option value="1.0" {% if job_score == 1.0 %}selected{% endif %}>대기업/공무원 (매우 안정)</option>
                    <option value="0.8" {% if job_score == 0.8 %}selected{% endif %}>중견/중소기업 (안정)</option>
                    <option value="0.5" {% if job_score == 0.5 %}selected{% endif %}>프리랜서/계약직 (보통)</option>
                    <option value="0.2" {% if job_score == 0.2 %}selected{% endif %}>무직/기타 (불안정)</option>
                </select>

                <label style="display: block; margin-bottom: 0.5rem; font-weight: 600;">🏠 보유 자산 (원)</label>
                <input type="number" name="asset_amount" value="{{ asset_amount }}" style="width: 100%; padding: 10px; margin-bottom: 1rem; border: 1px solid #e5e7eb; border-radius: 6px;">
                
                <button type="submit" style="width: 100%;">🔍 추천 실행</button>
            </form>
        </div>

        <!-- 결과 영역 -->
        <div>
            <h3 style="margin-top: 0;">🎯 추천 결과</h3>
            {% if result_html %}
                <div style="background: white; padding: 1rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow-x: auto;">
                    {{ result_html|safe }}
                </div>
                <p style="color: #6b7280; font-size: 0.9rem; margin-top: 10px;">
                    * 예상 금리는 현재 설정된 가중치 정책과 유저 소득에 따라 계산됩니다.
                </p>
            {% else %}
                <div style="background: #f9fafb; padding: 2rem; border-radius: 12px; text-align: center; color: #9ca3af; border: 2px dashed #e5e7eb;">
                    왼쪽 폼에 정보를 입력하고 추천을 실행해보세요.
                </div>
            {% endif %}
        </div>
    </div>
{% endblock %}
"""


def generate_log_table():
    table_html = """
    <div class="log-table-container">
        <table>
            <thead>
                <tr>
                    <th style="width: 30%;">실행 시간</th>
                    <th style="width: 15%;">상태</th>
                    <th style="width: 15%;">건수</th>
                    <th style="width: 40%;">메시지</th>
                </tr>
            </thead>
            <tbody>
                {% for log in logs %}
                <tr>
                    <td>{{ log.executed_at.strftime('%Y-%m-%d %H:%M:%S') if log.executed_at else '-' }}</td>
                    <td><span class="status-badge {{ 'status-fail' if log.status == 'FAIL' else 'status-success' }}">
                        {{ '❌ ' if log.status == 'FAIL' else '✅ ' }}{{ log.status }}
                    </span></td>
                    <td>{{ log.row_count }}</td>
                    <td title="{{ log.error_message if log.error_message else '' }}">
                        <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 250px; color: #6b7280; font-size: 0.9em;">
                            {{ log.error_message if log.error_message else '-' }}
                        </div>
                    </td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="4" style="text-align: center; padding: 2rem; color: #9ca3af;">수집된 로그가 없습니다.</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    """
    return table_html

def login_required(f):
    """로그인 여부를 확인하는 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_dashboard_stats(engine):
    """전체 데이터 수집 현황 통계 조회"""
    stats = {'loan_count': 0, 'economy_count': 0, 'income_count': 0, 'log_count': 0}
    # 가중치 기본값 설정
    stats['WEIGHT_INCOME'] = 0.5
    stats['WEIGHT_JOB_STABILITY'] = 0.3
    stats['WEIGHT_ESTATE_ASSET'] = 0.2

    try:
        with engine.connect() as conn:
            try: stats['loan_count'] = conn.execute(text("SELECT COUNT(*) FROM raw_loan_products")).scalar()
            except: pass
            try: stats['economy_count'] = conn.execute(text("SELECT COUNT(*) FROM raw_economic_indicators")).scalar()
            except: pass
            try: stats['income_count'] = conn.execute(text("SELECT COUNT(*) FROM raw_income_stats")).scalar()
            except: pass
            try: stats['log_count'] = conn.execute(text("SELECT COUNT(*) FROM collection_logs")).scalar()
            except: pass
            
            # 가중치 설정 조회
            try:
                rows = conn.execute(text("SELECT config_key, config_value FROM service_config")).fetchall()
                for row in rows:
                    stats[row[0]] = float(row[1])
            except: pass
    except Exception:
        pass
    return stats

def get_recent_logs(engine, source=None, limit=50):
    """DB에서 로그를 조회하여 딕셔너리 리스트로 반환"""
    try:
        query = "SELECT * FROM collection_logs"
        if source:
            query += f" WHERE target_source = '{source}'"
        query += " ORDER BY executed_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        df = pd.read_sql(query, engine)
        return df.to_dict(orient='records')
    except Exception:
        return []

@app.route('/data/<table_name>')
@login_required
def view_data(table_name):
    # 보안을 위해 허용된 테이블만 조회 가능
    allowed_tables = ['raw_loan_products', 'raw_economic_indicators', 'raw_income_stats', 'collection_logs', 'service_config']
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
        
        # 1. 컬럼 목록 조회 (검색 및 정렬 유효성 검사)
        meta_df = pd.read_sql(f"SELECT * FROM {table_name} LIMIT 0", collector.engine)
        columns = meta_df.columns.tolist()

        # 2. 검색 조건 구성
        where_clause = ""
        params = {}
        if search_col and search_val and search_col in columns:
            where_clause = f" WHERE {search_col} LIKE %(search_val)s"
            params['search_val'] = f"%{search_val}%"

        # 3. 전체 데이터 개수 조회 (검색 조건 포함)
        count_query = f"SELECT COUNT(*) FROM {table_name}" + where_clause
        count_df = pd.read_sql(count_query, collector.engine, params=params)
        total_count = count_df.iloc[0, 0]
        
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        
        # 페이지 범위 보정
        if page < 1: page = 1
        if page > total_pages: page = total_pages
        
        offset = (page - 1) * per_page
        
        # 4. 데이터 조회 쿼리 구성
        query = f"SELECT * FROM {table_name}" + where_clause
        if sort_by and sort_by in columns:
            safe_order = 'DESC' if order.upper() == 'DESC' else 'ASC'
            query += f" ORDER BY {sort_by} {safe_order}"
        
        query += f" LIMIT {per_page} OFFSET {offset}"
        
        df = pd.read_sql(query, collector.engine, params=params)
        rows = df.values.tolist()
        
        return render_template_string(DATA_VIEWER_TEMPLATE, 
                                      table_name=table_name, columns=columns, rows=rows, 
                                      page=page, total_pages=total_pages, total_count=total_count,
                                      sort_by=sort_by, order=order,
                                      search_col=search_col, search_val=search_val)
    except Exception as e:
        flash(f"데이터 조회 실패: {e}", "error")
        return redirect(url_for('index'))

@app.route('/simulator', methods=['GET', 'POST'])
@login_required
def simulator():
    result_html = None
    income = 50000000  # 기본값
    amount = 10000000  # 기본값
    job_score = 0.8    # 기본값
    asset_amount = 0   # 기본값
    
    if request.method == 'POST':
        try:
            income = int(request.form.get('annual_income', 0))
            amount = int(request.form.get('desired_amount', 0))
            job_score = float(request.form.get('job_score', 0.5))
            asset_amount = int(request.form.get('asset_amount', 0))
            
            collector = DataCollector()
            user_profile = {
                'annual_income': income, 'desired_amount': amount,
                'job_score': job_score, 'asset_amount': asset_amount
            }
            recommendations = recommend_products(collector.engine, user_profile)
            
            if not recommendations.empty:
                # 결과 테이블 스타일링
                result_html = recommendations.to_html(classes='table', index=False, border=0)
                result_html = result_html.replace('class="dataframe table"', 'style="width: 100%; border-collapse: collapse;"')
                result_html = result_html.replace('<th>', '<th style="background-color: #eff6ff; color: #1e3a8a; padding: 10px; text-align: left;">')
                result_html = result_html.replace('<td>', '<td style="padding: 10px; border-bottom: 1px solid #f3f4f6;">')
            else:
                result_html = "<p style='padding: 1rem; color: #dc2626;'>조건에 맞는 추천 상품이 없습니다.</p>"
                
        except Exception as e:
            flash(f"시뮬레이션 오류: {e}", "error")
            
    return render_template_string(SIMULATOR_TEMPLATE, result_html=result_html, 
                                  income=income, amount=amount, job_score=job_score, asset_amount=asset_amount)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        try:
            collector = DataCollector()
            new_income_w = float(request.form['income_weight'])
            new_job_w = float(request.form['job_weight'])
            new_asset_w = float(request.form['asset_weight'])

            total_weight = new_income_w + new_job_w + new_asset_w
            if abs(total_weight - 1.0) > 0.01:
                flash(f"⚠️ 가중치 합계가 1.0이 아닙니다. (현재: {total_weight:.2f}) - 의도한 것이 아니라면 조정해주세요.", 'warning')
            else:
                with collector.engine.connect() as conn:
                    updates = [
                        {'key': 'WEIGHT_INCOME', 'val': new_income_w},
                        {'key': 'WEIGHT_JOB_STABILITY', 'val': new_job_w},
                        {'key': 'WEIGHT_ESTATE_ASSET', 'val': new_asset_w}
                    ]
                    for item in updates:
                        conn.execute(
                            text("UPDATE service_config SET config_value = :val WHERE config_key = :key"),
                            item
                        )
                    conn.commit()
                flash("✅ 정책 설정이 데이터베이스에 반영되었습니다!", 'success')
                return redirect(url_for('settings'))  # Refresh to show updated values
        except Exception as e:
            flash(f"설정 로드/저장 중 오류 발생: {e}", 'error')

    try:
        collector = DataCollector()
        config_df = pd.read_sql("SELECT * FROM service_config", collector.engine)
        configs = dict(zip(config_df['config_key'], config_df['config_value']))
        
        income_weight = float(configs.get('WEIGHT_INCOME', 0.5))
        job_weight = float(configs.get('WEIGHT_JOB_STABILITY', 0.3))
        asset_weight = float(configs.get('WEIGHT_ESTATE_ASSET', 0.2))

        return render_template_string("""
            {% extends "base.html" %}
            {% block content %}
                <h1>⚙️ 신용 평가 가중치 설정</h1>
                <form method="post" action="{{ url_for('settings') }}">
                    소득 비중: <input type="number" step="0.01" name="income_weight" value="{{ income_weight }}"><br>
                    고용 안정성: <input type="number" step="0.01" name="job_weight" value="{{ job_weight }}"><br>
                    부동산 자산: <input type="number" step="0.01" name="asset_weight" value="{{ asset_weight }}"><br>
                    <button type="submit">저장</button>
                </form>
            {% endblock %}
        """, income_weight=income_weight, job_weight=job_weight, asset_weight=asset_weight)
    except Exception as e:
        return f"Error loading settings: {e}"
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # 환경 변수에서 관리자 계정 정보 로드 (기본값: admin / admin1234)
        env_user = os.getenv('ADMIN_USER', 'admin')
        env_password = os.getenv('ADMIN_PASSWORD', 'admin1234')
        
        if username == env_user and password == env_password:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('아이디 또는 비밀번호가 올바르지 않습니다.')
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/toggle_refresh')
def toggle_refresh():
    # 세션에서 현재 상태 가져오기 (기본값 True), 상태 반전 후 저장
    session['auto_refresh'] = not session.get('auto_refresh', True)
    return redirect(url_for('index'))

@app.route('/', methods=['GET'])
@login_required
def index():
    try:

        collector = DataCollector()
        stats = get_dashboard_stats(collector.engine)
        loan_logs = get_recent_logs(collector.engine, source='FSS_LOAN_API', limit=50)
        economy_logs = get_recent_logs(collector.engine, source='ECONOMIC_INDICATORS', limit=50)
        income_logs = get_recent_logs(collector.engine, source='KOSIS_INCOME_API', limit=50)
        
        loan_last_run = loan_logs[0]['executed_at'].strftime('%Y-%m-%d %H:%M') if loan_logs and loan_logs[0]['executed_at'] else "-"
        economy_last_run = economy_logs[0]['executed_at'].strftime('%Y-%m-%d %H:%M') if economy_logs and economy_logs[0]['executed_at'] else "-"
        income_last_run = income_logs[0]['executed_at'].strftime('%Y-%m-%d %H:%M') if income_logs and income_logs[0]['executed_at'] else "-"
        
        loan_log_table = render_template_string(generate_log_table(), logs=loan_logs)
        economy_log_table = render_template_string(generate_log_table(), logs=economy_logs)
        income_log_table = render_template_string(generate_log_table(), logs=income_logs)

        return render_template_string(HTML_TEMPLATE, loan_logs=loan_logs, economy_logs=economy_logs, income_logs=income_logs, loan_log_table=loan_log_table, economy_log_table=economy_log_table,
                                       income_log_table=income_log_table, loan_last_run=loan_last_run, economy_last_run=economy_last_run, income_last_run=income_last_run,
                                       auto_refresh=session.get('auto_refresh', True),
                                       stats=stats)
    except Exception as e:
        # 에러 발생 시에도 빈 테이블을 보여주기 위해 생성
        empty_table = render_template_string(generate_log_table(), logs=[])
        # DB 연결 실패 등 오류 발생 시 빈 로그와 에러 메시지 전달
        return render_template_string(HTML_TEMPLATE,
                                       message=f"⚠️ 시스템 오류: {e}",
                                       status="error",
                                       loan_last_run="-",
                                       economy_last_run="-",
                                       income_last_run="-",
                                       loan_log_table=empty_table,
                                       economy_log_table=empty_table,
                                       income_log_table=empty_table,
                                       auto_refresh=session.get('auto_refresh', True),
                                       stats={})


@app.route('/trigger', methods=['POST'])
@login_required
def trigger_job():
    job_type = request.form.get('job')
    
    try:
        collector = DataCollector() # collector.py의 로직 재사용
        stats = get_dashboard_stats(collector.engine)
        
        if job_type == 'loan':
            collector.collect_fss_loan_products()
            msg = "✅ 대출상품 수집이 완료되었습니다."
        elif job_type == 'economy':
            collector.collect_economic_indicators()
            msg = "✅ 경제 지표 수집이 완료되었습니다."
        elif job_type == 'income':
            collector.collect_kosis_income_stats()
            msg = "✅ 소득 통계 수집이 완료되었습니다."
        else:
            msg = "⚠️ 알 수 없는 작업입니다."
        
        # 작업 완료 후 최신 로그 다시 조회
        loan_logs = get_recent_logs(collector.engine, source='FSS_LOAN_API', limit=50)
        economy_logs = get_recent_logs(collector.engine, source='ECONOMIC_INDICATORS', limit=50)
        income_logs = get_recent_logs(collector.engine, source='KOSIS_INCOME_API', limit=50)
        
        loan_last_run = loan_logs[0]['executed_at'].strftime('%Y-%m-%d %H:%M') if loan_logs and loan_logs[0]['executed_at'] else "-"
        economy_last_run = economy_logs[0]['executed_at'].strftime('%Y-%m-%d %H:%M') if economy_logs and economy_logs[0]['executed_at'] else "-"
        income_last_run = income_logs[0]['executed_at'].strftime('%Y-%m-%d %H:%M') if income_logs and income_logs[0]['executed_at'] else "-"
        
        loan_log_table = render_template_string(generate_log_table(), logs=loan_logs)
        economy_log_table = render_template_string(generate_log_table(), logs=economy_logs)
        income_log_table = render_template_string(generate_log_table(), logs=income_logs)
        return render_template_string(HTML_TEMPLATE, message=msg, status="success", loan_logs=loan_logs, economy_logs=economy_logs, income_logs=income_logs,  loan_log_table=loan_log_table, economy_log_table=economy_log_table,
                                       income_log_table=income_log_table, loan_last_run=loan_last_run, economy_last_run=economy_last_run, income_last_run=income_last_run,
                                       auto_refresh=session.get('auto_refresh', True),
                                       stats=stats)
    except Exception as e:
        # 기본값 설정 (빈 테이블)
        loan_last_run, economy_last_run, income_last_run = "-", "-", "-"
        empty_table = render_template_string(generate_log_table(), logs=[])
        loan_log_table = economy_log_table = income_log_table = empty_table
        
        if 'collector' in locals():
            stats = get_dashboard_stats(collector.engine)
            try:
                # 에러가 났더라도 로그 조회 시도
                loan_logs = get_recent_logs(collector.engine, source='FSS_LOAN_API', limit=50)
                economy_logs = get_recent_logs(collector.engine, source='ECONOMIC_INDICATORS', limit=50)
                income_logs = get_recent_logs(collector.engine, source='KOSIS_INCOME_API', limit=50)
                
                loan_last_run = loan_logs[0]['executed_at'].strftime('%Y-%m-%d %H:%M') if loan_logs and loan_logs[0]['executed_at'] else "-"
                economy_last_run = economy_logs[0]['executed_at'].strftime('%Y-%m-%d %H:%M') if economy_logs and economy_logs[0]['executed_at'] else "-"
                income_last_run = income_logs[0]['executed_at'].strftime('%Y-%m-%d %H:%M') if income_logs and income_logs[0]['executed_at'] else "-"
                loan_log_table = render_template_string(generate_log_table(), logs=loan_logs)
                economy_log_table = render_template_string(generate_log_table(), logs=economy_logs)
                income_log_table = render_template_string(generate_log_table(), logs=income_logs)
            except:
                pass
        
        return render_template_string(HTML_TEMPLATE, message=f"❌ 실행 실패: {e}", status="error", 
                                      loan_last_run=loan_last_run, economy_last_run=economy_last_run, income_last_run=income_last_run,
                                      loan_log_table=loan_log_table, economy_log_table=economy_log_table, income_log_table=income_log_table,
                                      auto_refresh=session.get('auto_refresh', True),
                                      stats=stats if 'stats' in locals() else {})





if __name__ == '__main__':
    # 실행: python admin_flask.py
    app.run(host='0.0.0.0', debug=True, port=5001)