from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from functools import wraps
from collector import DataCollector
from recommendation_logic import recommend_products
import pandas as pd
import sys
import os
from sqlalchemy import text

# Flask 앱 초기화
app = Flask(__name__, template_folder='.')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_only_fallback_key')

# ==========================================================================
# [헬퍼] 공통 유틸리티 함수
# ==========================================================================

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
# [HTML] 메인 대시보드 템플릿
# ==========================================================================
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
        .header-container { background: white; padding: 1.5rem 2rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 2rem; }
        .header-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
        h1 { color: #1e3a8a; margin: 0; font-size: 1.5rem; font-weight: 700; }
        .nav-bar { display: flex; flex-wrap: wrap; gap: 6px; }
        .nav-btn { padding: 7px 14px; text-decoration: none; border-radius: 6px; font-size: 0.82rem; font-weight: bold; transition: all 0.2s; }
        .nav-btn:hover { transform: translateY(-1px); box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .dashboard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1.5rem; }
        .card { background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; overflow: hidden; display: flex; flex-direction: column; }
        .card-header { padding: 1.25rem; border-bottom: 1px solid #f3f4f6; background-color: #fff; display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
        .card-title-group { display: flex; flex-direction: column; gap: 0.25rem; }
        .card-title { font-size: 1.1rem; font-weight: 700; color: #111827; margin: 0; }
        .last-run { font-size: 0.8rem; color: #6b7280; }
        .card-actions { display: flex; align-items: center; gap: 8px; }
        .refresh-btn { padding: 0.5rem 0.75rem; background-color: #eff6ff; color: #2563eb; border: 1px solid #dbeafe; border-radius: 6px; font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: all 0.2s; white-space: nowrap; }
        .refresh-btn:hover { background-color: #2563eb; color: white; border-color: #2563eb; }
        .card-body { padding: 0; flex-grow: 1; display: flex; flex-direction: column; }
        .alert { padding: 1rem; margin-bottom: 1rem; border-radius: 5px; }
        .success { background-color: #d1fae5; color: #065f46; }
        .error { background-color: #fee2e2; color: #991b1b; }
        .warning { background-color: #fef3c7; color: #92400e; }
        .log-table-container { overflow-x: auto; max-height: 350px; overflow-y: auto; }
        table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
        th, td { padding: 10px 15px; text-align: left; border-bottom: 1px solid #f3f4f6; }
        th { background-color: #f9fafb; color: #4b5563; font-weight: 600; position: sticky; top: 0; z-index: 10; }
        .status-badge { padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
        .status-fail { background-color: #fef2f2; color: #dc2626; }
        .status-success { background-color: #ecfdf5; color: #059669; }
        .badge-on { background: #d1fae5; color: #065f46; padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
        .badge-off { background: #fee2e2; color: #991b1b; padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
        .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
        .summary-card { background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; text-align: center; }
        .summary-value { font-size: 2rem; font-weight: 700; color: #1e3a8a; margin: 0.5rem 0; }
        .summary-label { color: #6b7280; font-size: 0.9rem; font-weight: 600; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header-container">
            <div class="header-top">
                <h1>Fintech Service Admin</h1>
                <a href="/toggle_refresh" class="nav-btn" style="background-color: {{ '#d1fae5' if auto_refresh else '#f3f4f6' }}; color: {{ '#065f46' if auto_refresh else '#6b7280' }};">
                    {{ 'Auto Refresh: ON' if auto_refresh else 'Auto Refresh: OFF' }}
                </a>
            </div>
            <div class="nav-bar">
                <a href="/" class="nav-btn" style="background-color: #dbeafe; color: #1e40af;">Home</a>
                <a href="/collection-management" class="nav-btn" style="background-color: #fef3c7; color: #92400e;">수집 관리</a>
                <a href="/credit-weights" class="nav-btn" style="background-color: #e0e7ff; color: #3730a3;">신용평가 설정</a>
                <a href="/recommend-settings" class="nav-btn" style="background-color: #fce7f3; color: #9d174d;">추천 설정</a>
                <a href="/products" class="nav-btn" style="background-color: #d1fae5; color: #065f46;">상품 관리</a>
                <a href="/missions" class="nav-btn" style="background-color: #ede9fe; color: #5b21b6;">미션 관리</a>
                <a href="/simulator" class="nav-btn" style="background-color: #fce7f3; color: #9d174d;">시뮬레이터</a>
                <a href="/data/raw_loan_products" class="nav-btn" style="background-color: #e0e7ff; color: #3730a3;">데이터 조회</a>
                <a href="/logout" class="nav-btn" style="background-color: #fee2e2; color: #991b1b;">로그아웃</a>
            </div>
        </div>

        {% if message %}
            <div class="alert {{ status }}">{{ message }}</div>
        {% endif %}

        <div class="summary-grid">
            <div class="summary-card">
                <div class="summary-label">대출 상품 수</div>
                <div class="summary-value">{{ "{:,}".format(stats.loan_count | default(0)) }}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">경제 지표 수</div>
                <div class="summary-value">{{ "{:,}".format(stats.economy_count | default(0)) }}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">소득 통계 수</div>
                <div class="summary-value">{{ "{:,}".format(stats.income_count | default(0)) }}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">총 수집 로그</div>
                <div class="summary-value">{{ "{:,}".format(stats.log_count | default(0)) }}</div>
            </div>
        </div>

        <!-- 신용 평가 가중치 요약 -->
        <div style="background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; margin-bottom: 2rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin-top: 0; color: #1e3a8a; font-size: 1.1rem;">현재 신용 평가 가중치</h3>
                <a href="/credit-weights" class="nav-btn" style="background-color: #dbeafe; color: #1e40af; padding: 6px 12px; font-size: 0.8rem;">설정 변경</a>
            </div>
            <div style="display: flex; justify-content: space-around; align-items: center;">
               <div style="text-align: center;">
                   <div style="font-size: 0.9rem; color: #6b7280; margin-bottom: 5px;">소득 비중</div>
                   <div style="font-size: 1.8rem; font-weight: 700; color: #3b82f6;">{{ stats.WEIGHT_INCOME | default(0.5) }}</div>
                </div>
                <div style="text-align: center; border-left: 1px solid #f3f4f6; border-right: 1px solid #f3f4f6; padding: 0 40px;">
                    <div style="font-size: 0.9rem; color: #6b7280; margin-bottom: 5px;">고용 안정성</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: #10b981;">{{ stats.WEIGHT_JOB_STABILITY | default(0.3) }}</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 0.9rem; color: #6b7280; margin-bottom: 5px;">자산 비중</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: #f59e0b;">{{ stats.WEIGHT_ESTATE_ASSET | default(0.2) }}</div>
                </div>
            </div>
        </div>

        <div class="dashboard-grid">
            <!-- Card 1: Loan -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title-group">
                        <h3 class="card-title">금감원 대출상품</h3>
                        <span class="last-run">최근 실행: {{ loan_last_run }}</span>
                    </div>
                    <div class="card-actions">
                        <span class="{{ 'badge-on' if stats.COLLECTOR_FSS_LOAN_ENABLED|default('1') == '1' else 'badge-off' }}">
                            {{ 'ON' if stats.COLLECTOR_FSS_LOAN_ENABLED|default('1') == '1' else 'OFF' }}
                        </span>
                        <form action="/trigger" method="post" style="margin:0;">
                            <button type="submit" name="job" value="loan" class="refresh-btn">새로고침</button>
                        </form>
                    </div>
                </div>
                <div class="card-body">{{ loan_log_table|safe }}</div>
            </div>

            <!-- Card 2: Economy -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title-group">
                        <h3 class="card-title">경제 지표</h3>
                        <span class="last-run">최근 실행: {{ economy_last_run }}</span>
                    </div>
                    <div class="card-actions">
                        <span class="{{ 'badge-on' if stats.COLLECTOR_ECONOMIC_ENABLED|default('1') == '1' else 'badge-off' }}">
                            {{ 'ON' if stats.COLLECTOR_ECONOMIC_ENABLED|default('1') == '1' else 'OFF' }}
                        </span>
                        <form action="/trigger" method="post" style="margin:0;">
                            <button type="submit" name="job" value="economy" class="refresh-btn">새로고침</button>
                        </form>
                    </div>
                </div>
                <div class="card-body">{{ economy_log_table|safe }}</div>
            </div>

            <!-- Card 3: Income -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title-group">
                        <h3 class="card-title">통계청 소득정보</h3>
                        <span class="last-run">최근 실행: {{ income_last_run }}</span>
                    </div>
                    <div class="card-actions">
                        <span class="{{ 'badge-on' if stats.COLLECTOR_KOSIS_INCOME_ENABLED|default('1') == '1' else 'badge-off' }}">
                            {{ 'ON' if stats.COLLECTOR_KOSIS_INCOME_ENABLED|default('1') == '1' else 'OFF' }}
                        </span>
                        <form action="/trigger" method="post" style="margin:0;">
                            <button type="submit" name="job" value="income" class="refresh-btn">새로고침</button>
                        </form>
                    </div>
                </div>
                <div class="card-body">{{ income_log_table|safe }}</div>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ==========================================================================
# [HTML] 로그인 화면
# ==========================================================================
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8"><title>Login - Fintech Admin</title>
    <style>
        body { font-family: 'Noto Sans KR', sans-serif; background-color: #f8f9fa; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-container { background: white; padding: 2.5rem; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }
        h1 { color: #1e3a8a; text-align: center; margin-bottom: 2rem; font-size: 1.5rem; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; }
        input { width: 100%; padding: 12px; margin-bottom: 1rem; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background-color: #3b82f6; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }
        button:hover { background-color: #2563eb; }
        .error { color: #dc2626; text-align: center; margin-top: 1rem; font-size: 0.9rem; }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>관리자 로그인</h1>
        <form method="post">
            <input type="text" name="username" placeholder="아이디" required>
            <input type="password" name="password" placeholder="비밀번호" required>
            <button type="submit">로그인</button>
        </form>
        {% with messages = get_flashed_messages() %}
            {% if messages %}<div class="error">{{ messages[0] }}</div>{% endif %}
        {% endwith %}
    </div>
</body>
</html>
"""

# ==========================================================================
# [HTML] 데이터 조회 템플릿
# ==========================================================================
DATA_VIEWER_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
    <h1>수집 데이터 조회: {{ table_name }}</h1>
    <div style="margin-bottom: 20px;">
        <a href="/data/raw_loan_products" style="margin-right: 10px; font-weight: bold; color: {{ '#2563eb' if table_name == 'raw_loan_products' else '#6b7280' }}">대출 상품</a>
        <a href="/data/raw_economic_indicators" style="margin-right: 10px; font-weight: bold; color: {{ '#2563eb' if table_name == 'raw_economic_indicators' else '#6b7280' }}">경제 지표</a>
        <a href="/data/raw_income_stats" style="margin-right: 10px; font-weight: bold; color: {{ '#2563eb' if table_name == 'raw_income_stats' else '#6b7280' }}">소득 통계</a>
        <a href="/data/collection_logs" style="margin-right: 10px; font-weight: bold; color: {{ '#2563eb' if table_name == 'collection_logs' else '#6b7280' }}">수집 로그</a>
        <a href="/data/missions" style="margin-right: 10px; font-weight: bold; color: {{ '#2563eb' if table_name == 'missions' else '#6b7280' }}">미션</a>
    </div>
    <form method="get" action="{{ url_for('view_data', table_name=table_name) }}" style="margin-bottom: 20px; background: #f9fafb; padding: 15px; border-radius: 8px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
        <span style="font-weight: bold; color: #4b5563;">검색:</span>
        <select name="search_col" style="padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; background: white;">
            {% for col in columns %}<option value="{{ col }}" {% if search_col == col %}selected{% endif %}>{{ col }}</option>{% endfor %}
        </select>
        <input type="text" name="search_val" value="{{ search_val if search_val else '' }}" placeholder="검색어 입력..." style="padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; flex-grow: 1; min-width: 200px;">
        <button type="submit" style="padding: 8px 16px; background-color: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">검색</button>
        {% if search_val %}<a href="{{ url_for('view_data', table_name=table_name) }}" style="padding: 8px 16px; background-color: #9ca3af; color: white; text-decoration: none; border-radius: 4px; font-weight: bold;">초기화</a>{% endif %}
    </form>
    <div style="overflow-x: auto; background: white; padding: 1rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <table style="width: 100%; border-collapse: collapse;">
            <thead><tr>
                {% for col in columns %}
                <th style="background-color: #f3f4f6; padding: 10px; text-align: left; border-bottom: 2px solid #e5e7eb; white-space: nowrap;">
                    <a href="{{ url_for('view_data', table_name=table_name, page=1, sort_by=col, order='desc' if sort_by == col and order == 'asc' else 'asc', search_col=search_col, search_val=search_val) }}" style="text-decoration: none; color: #374151;">
                        {{ col }} {% if sort_by == col %}<span style="color: #2563eb;">{{ '▲' if order == 'asc' else '▼' }}</span>{% endif %}
                    </a>
                </th>
                {% endfor %}
            </tr></thead>
            <tbody>
                {% for row in rows %}<tr>{% for cell in row %}<td style="padding: 10px; border-bottom: 1px solid #f3f4f6;">{{ cell }}</td>{% endfor %}</tr>
                {% else %}<tr><td colspan="{{ columns|length }}" style="padding: 20px; text-align: center; color: #6b7280;">데이터가 없습니다.</td></tr>{% endfor %}
            </tbody>
        </table>
    </div>
    <div style="margin-top: 20px; display: flex; justify-content: center; align-items: center; gap: 15px;">
        {% if page > 1 %}<a href="{{ url_for('view_data', table_name=table_name, page=page-1, sort_by=sort_by, order=order, search_col=search_col, search_val=search_val) }}" style="padding: 8px 16px; background-color: #f3f4f6; color: #374151; text-decoration: none; border-radius: 6px; font-weight: bold;">이전</a>
        {% else %}<span style="padding: 8px 16px; background-color: #f9fafb; color: #9ca3af; border-radius: 6px;">이전</span>{% endif %}
        <span style="font-weight: 600; color: #4b5563;">Page <span style="color: #2563eb;">{{ page }}</span> / {{ total_pages }} ({{ "{:,}".format(total_count) }}건)</span>
        {% if page < total_pages %}<a href="{{ url_for('view_data', table_name=table_name, page=page+1, sort_by=sort_by, order=order, search_col=search_col, search_val=search_val) }}" style="padding: 8px 16px; background-color: #f3f4f6; color: #374151; text-decoration: none; border-radius: 6px; font-weight: bold;">다음</a>
        {% else %}<span style="padding: 8px 16px; background-color: #f9fafb; color: #9ca3af; border-radius: 6px;">다음</span>{% endif %}
    </div>
{% endblock %}
"""

# ==========================================================================
# [HTML] 추천 시뮬레이터
# ==========================================================================
SIMULATOR_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
    <h1>대출 추천 시뮬레이터</h1>
    <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 2rem;">
        <div style="background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); height: fit-content;">
            <h3 style="margin-top: 0;">가상 유저 프로필</h3>
            <form method="post">
                <label style="display: block; margin-bottom: 0.5rem; font-weight: 600;">연소득 (원)</label>
                <input type="number" name="annual_income" value="{{ income }}" style="width: 100%; padding: 10px; margin-bottom: 1rem; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
                <label style="display: block; margin-bottom: 0.5rem; font-weight: 600;">희망 대출 금액 (원)</label>
                <input type="number" name="desired_amount" value="{{ amount }}" style="width: 100%; padding: 10px; margin-bottom: 1rem; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
                <label style="display: block; margin-bottom: 0.5rem; font-weight: 600;">고용 형태 (안정성)</label>
                <select name="job_score" style="width: 100%; padding: 10px; margin-bottom: 1rem; border: 1px solid #e5e7eb; border-radius: 6px; background: white;">
                    <option value="1.0" {% if job_score == 1.0 %}selected{% endif %}>대기업/공무원 (매우 안정)</option>
                    <option value="0.8" {% if job_score == 0.8 %}selected{% endif %}>중견/중소기업 (안정)</option>
                    <option value="0.5" {% if job_score == 0.5 %}selected{% endif %}>프리랜서/계약직 (보통)</option>
                    <option value="0.2" {% if job_score == 0.2 %}selected{% endif %}>무직/기타 (불안정)</option>
                </select>
                <label style="display: block; margin-bottom: 0.5rem; font-weight: 600;">보유 자산 (원)</label>
                <input type="number" name="asset_amount" value="{{ asset_amount }}" style="width: 100%; padding: 10px; margin-bottom: 1rem; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
                <button type="submit" style="width: 100%;">추천 실행</button>
            </form>
        </div>
        <div>
            <h3 style="margin-top: 0;">추천 결과</h3>
            {% if result_html %}
                <div style="background: white; padding: 1rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow-x: auto;">{{ result_html|safe }}</div>
                <p style="color: #6b7280; font-size: 0.9rem; margin-top: 10px;">* 예상 금리는 현재 설정된 가중치 정책과 유저 프로필에 따라 계산됩니다.</p>
            {% else %}
                <div style="background: #f9fafb; padding: 2rem; border-radius: 12px; text-align: center; color: #9ca3af; border: 2px dashed #e5e7eb;">왼쪽 폼에 정보를 입력하고 추천을 실행해보세요.</div>
            {% endif %}
        </div>
    </div>
{% endblock %}
"""

# ==========================================================================
# [HTML] F1: 수집 관리 페이지
# ==========================================================================
COLLECTION_MGMT_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
<h1>금융 데이터 수집 관리</h1>
<p style="color: #6b7280; margin-bottom: 1.5rem;">데이터 소스별 수집 활성화 여부를 관리하고 수동 수집을 실행합니다.</p>

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem;">
    {% for src in sources %}
    <div style="background: white; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; padding: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <h3 style="margin: 0; font-size: 1.1rem; color: #111827;">{{ src.label }}</h3>
            <span class="{{ 'badge-on' if src.enabled else 'badge-off' }}" style="padding: 4px 12px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;
                background: {{ '#d1fae5' if src.enabled else '#fee2e2' }}; color: {{ '#065f46' if src.enabled else '#991b1b' }};">
                {{ 'ON' if src.enabled else 'OFF' }}
            </span>
        </div>
        <div style="font-size: 0.85rem; color: #6b7280; margin-bottom: 1rem;">
            <div>최근 실행: {{ src.last_run }}</div>
            <div>최근 상태: <span style="font-weight: 600; color: {{ '#059669' if src.last_status == 'SUCCESS' else '#dc2626' if src.last_status == 'FAIL' else '#6b7280' }};">{{ src.last_status or '-' }}</span></div>
            <div>수집 건수: {{ src.last_count }}</div>
        </div>
        <div style="display: flex; gap: 8px;">
            <form action="/toggle_collector" method="post" style="flex: 1;">
                <input type="hidden" name="source" value="{{ src.key }}">
                <button type="submit" style="width: 100%; padding: 8px; border: 1px solid {{ '#dc2626' if src.enabled else '#059669' }}; background: {{ '#fef2f2' if src.enabled else '#ecfdf5' }}; color: {{ '#dc2626' if src.enabled else '#059669' }}; border-radius: 6px; cursor: pointer; font-weight: 600;">
                    {{ '비활성화' if src.enabled else '활성화' }}
                </button>
            </form>
            <form action="/trigger" method="post" style="flex: 1;">
                <button type="submit" name="job" value="{{ src.trigger_val }}" style="width: 100%; padding: 8px; background: #eff6ff; color: #2563eb; border: 1px solid #dbeafe; border-radius: 6px; cursor: pointer; font-weight: 600;"
                    {{ 'disabled' if not src.enabled else '' }}>수동 수집</button>
            </form>
        </div>
    </div>
    {% endfor %}
</div>
{% endblock %}
"""

# ==========================================================================
# [HTML] F2: 신용평가 가중치 관리
# ==========================================================================
CREDIT_WEIGHTS_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
<h1>신용평가 가중치 관리</h1>
<p style="color: #6b7280; margin-bottom: 1.5rem;">신용 평가 로직의 구성 요소를 수치화하여 조절합니다. 변경 사항은 대출 추천 결과에 즉시 반영됩니다.</p>

<form method="post">
    <!-- 섹션 1: 핵심 가중치 -->
    <div style="background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; margin-bottom: 1.5rem;">
        <h3 style="margin-top: 0; color: #1e3a8a;">핵심 가중치 (합계 = 1.0)</h3>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem; margin-bottom: 1rem;">
            <div>
                <label style="display: block; font-weight: 600; margin-bottom: 8px; color: #3b82f6;">소득 비중 (WEIGHT_INCOME)</label>
                <input type="range" min="0" max="1" step="0.01" name="income_weight" value="{{ income_weight }}" id="rng_income" oninput="syncWeight()" style="width: 100%;">
                <input type="number" step="0.01" min="0" max="1" id="num_income" value="{{ income_weight }}" onchange="syncFromNum('income')" style="width: 100%; padding: 8px; margin-top: 6px; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
            </div>
            <div>
                <label style="display: block; font-weight: 600; margin-bottom: 8px; color: #10b981;">고용 안정성 (WEIGHT_JOB_STABILITY)</label>
                <input type="range" min="0" max="1" step="0.01" name="job_weight" value="{{ job_weight }}" id="rng_job" oninput="syncWeight()" style="width: 100%;">
                <input type="number" step="0.01" min="0" max="1" id="num_job" value="{{ job_weight }}" onchange="syncFromNum('job')" style="width: 100%; padding: 8px; margin-top: 6px; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
            </div>
            <div>
                <label style="display: block; font-weight: 600; margin-bottom: 8px; color: #f59e0b;">자산 비중 (WEIGHT_ESTATE_ASSET)</label>
                <input type="range" min="0" max="1" step="0.01" name="asset_weight" value="{{ asset_weight }}" id="rng_asset" oninput="syncWeight()" style="width: 100%;">
                <input type="number" step="0.01" min="0" max="1" id="num_asset" value="{{ asset_weight }}" onchange="syncFromNum('asset')" style="width: 100%; padding: 8px; margin-top: 6px; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
            </div>
        </div>
        <!-- 합계 표시 + 비율 바 -->
        <div style="margin-bottom: 0.5rem; font-size: 1.1rem; font-weight: 700;">합계: <span id="weightSum" style="color: {{ '#059669' if (income_weight + job_weight + asset_weight) | round(2) == 1.0 else '#dc2626' }};">{{ (income_weight + job_weight + asset_weight) | round(2) }}</span></div>
        <div style="display: flex; height: 24px; border-radius: 6px; overflow: hidden; border: 1px solid #e5e7eb;">
            <div id="bar_income" style="background: #3b82f6; transition: width 0.2s; width: {{ income_weight * 100 }}%;"></div>
            <div id="bar_job" style="background: #10b981; transition: width 0.2s; width: {{ job_weight * 100 }}%;"></div>
            <div id="bar_asset" style="background: #f59e0b; transition: width 0.2s; width: {{ asset_weight * 100 }}%;"></div>
        </div>
    </div>

    <!-- 섹션 2: 정규화 기준 -->
    <div style="background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; margin-bottom: 1.5rem;">
        <h3 style="margin-top: 0; color: #1e3a8a;">정규화 기준 (Normalization Ceiling)</h3>
        <p style="color: #6b7280; font-size: 0.85rem;">이 금액 이상이면 해당 항목 점수가 만점(1.0)이 됩니다.</p>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
            <div>
                <label style="display: block; font-weight: 600; margin-bottom: 8px;">소득 만점 기준 (원)</label>
                <input type="number" name="norm_income_ceiling" value="{{ norm_income_ceiling | int }}" step="10000000" style="width: 100%; padding: 10px; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
                <span style="font-size: 0.8rem; color: #6b7280;">현재: {{ "{:,.0f}".format(norm_income_ceiling) }}원</span>
            </div>
            <div>
                <label style="display: block; font-weight: 600; margin-bottom: 8px;">자산 만점 기준 (원)</label>
                <input type="number" name="norm_asset_ceiling" value="{{ norm_asset_ceiling | int }}" step="10000000" style="width: 100%; padding: 10px; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
                <span style="font-size: 0.8rem; color: #6b7280;">현재: {{ "{:,.0f}".format(norm_asset_ceiling) }}원</span>
            </div>
        </div>
    </div>

    <!-- 섹션 3: XAI 설명 임계값 -->
    <div style="background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; margin-bottom: 1.5rem;">
        <h3 style="margin-top: 0; color: #1e3a8a;">XAI 설명 임계값 (Explanation Thresholds)</h3>
        <p style="color: #6b7280; font-size: 0.85rem;">각 요소의 기여도가 이 값 이상이어야 추천 사유에 표시됩니다.</p>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem;">
            <div>
                <label style="display: block; font-weight: 600; margin-bottom: 8px;">소득 기여도 임계값</label>
                <input type="number" step="0.01" name="xai_threshold_income" value="{{ xai_threshold_income }}" style="width: 100%; padding: 10px; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
            </div>
            <div>
                <label style="display: block; font-weight: 600; margin-bottom: 8px;">고용 기여도 임계값</label>
                <input type="number" step="0.01" name="xai_threshold_job" value="{{ xai_threshold_job }}" style="width: 100%; padding: 10px; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
            </div>
            <div>
                <label style="display: block; font-weight: 600; margin-bottom: 8px;">자산 기여도 임계값</label>
                <input type="number" step="0.01" name="xai_threshold_asset" value="{{ xai_threshold_asset }}" style="width: 100%; padding: 10px; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
            </div>
        </div>
    </div>

    <button type="submit" style="padding: 12px 32px; background: #3b82f6; color: white; border: none; border-radius: 8px; font-weight: bold; font-size: 1rem; cursor: pointer;">설정 저장</button>
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
    el.style.color = Math.abs(parseFloat(sum) - 1.0) < 0.015 ? '#059669' : '#dc2626';
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
{% endblock %}
"""

# ==========================================================================
# [HTML] F3: 대출 추천 가중치 관리
# ==========================================================================
RECOMMEND_SETTINGS_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
<h1>대출 추천 알고리즘 설정</h1>
<p style="color: #6b7280; margin-bottom: 1.5rem;">추천 결과의 정렬, 필터링, 표시 방식을 관리합니다.</p>

<form method="post">
    <div style="background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; margin-bottom: 1.5rem;">
        <h3 style="margin-top: 0; color: #1e3a8a;">추천 파라미터</h3>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
            <div>
                <label style="display: block; font-weight: 600; margin-bottom: 8px;">최대 추천 수</label>
                <input type="number" name="max_count" value="{{ max_count }}" min="1" max="20" style="width: 100%; padding: 10px; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
                <p style="font-size: 0.8rem; color: #6b7280;">사용자에게 보여줄 최대 추천 상품 수 (1~20)</p>
            </div>
            <div>
                <label style="display: block; font-weight: 600; margin-bottom: 8px;">정렬 우선순위</label>
                <select name="sort_priority" style="width: 100%; padding: 10px; border: 1px solid #e5e7eb; border-radius: 6px; background: white;">
                    <option value="rate" {% if sort_priority == 'rate' %}selected{% endif %}>예상 금리 낮은 순 (rate)</option>
                    <option value="limit" {% if sort_priority == 'limit' %}selected{% endif %}>대출 한도 높은 순 (limit)</option>
                </select>
                <p style="font-size: 0.8rem; color: #6b7280;">추천 결과의 1차 정렬 기준</p>
            </div>
            <div>
                <label style="display: block; font-weight: 600; margin-bottom: 8px;">Fallback 모드</label>
                <select name="fallback_mode" style="width: 100%; padding: 10px; border: 1px solid #e5e7eb; border-radius: 6px; background: white;">
                    <option value="show_all" {% if fallback_mode == 'show_all' %}selected{% endif %}>전체 상품 표시 (show_all)</option>
                    <option value="show_none" {% if fallback_mode == 'show_none' %}selected{% endif %}>빈 결과 반환 (show_none)</option>
                </select>
                <p style="font-size: 0.8rem; color: #6b7280;">희망 대출액을 충족하는 상품이 없을 때 동작</p>
            </div>
            <div>
                <label style="display: block; font-weight: 600; margin-bottom: 8px;">금리 스프레드 민감도</label>
                <input type="number" step="0.1" name="rate_sensitivity" value="{{ rate_sensitivity }}" min="0.1" max="3.0" style="width: 100%; padding: 10px; border: 1px solid #e5e7eb; border-radius: 6px; box-sizing: border-box;">
                <p style="font-size: 0.8rem; color: #6b7280;">1.0 = 기본. 높을수록 신용점수가 금리에 미치는 영향 증가</p>
            </div>
        </div>
    </div>
    <button type="submit" style="padding: 12px 32px; background: #3b82f6; color: white; border: none; border-radius: 8px; font-weight: bold; font-size: 1rem; cursor: pointer;">설정 저장</button>
</form>
{% endblock %}
"""

# ==========================================================================
# [HTML] F4: 대출 상품 관리
# ==========================================================================
PRODUCTS_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
<h1>대출 상품 관리</h1>
<p style="color: #6b7280; margin-bottom: 1.5rem;">수집된 대출 상품의 서비스 노출 여부를 관리합니다.</p>

<div style="display: flex; gap: 1rem; margin-bottom: 1.5rem;">
    <div style="background: white; padding: 1rem 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; text-align: center; flex: 1;">
        <div style="color: #6b7280; font-size: 0.85rem; font-weight: 600;">전체 상품</div>
        <div style="font-size: 1.8rem; font-weight: 700; color: #1e3a8a;">{{ total_count }}</div>
    </div>
    <div style="background: white; padding: 1rem 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; text-align: center; flex: 1;">
        <div style="color: #6b7280; font-size: 0.85rem; font-weight: 600;">노출 중</div>
        <div style="font-size: 1.8rem; font-weight: 700; color: #059669;">{{ visible_count }}</div>
    </div>
    <div style="background: white; padding: 1rem 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; text-align: center; flex: 1;">
        <div style="color: #6b7280; font-size: 0.85rem; font-weight: 600;">비노출</div>
        <div style="font-size: 1.8rem; font-weight: 700; color: #dc2626;">{{ hidden_count }}</div>
    </div>
</div>

<div style="background: white; padding: 1rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow-x: auto;">
    <table style="width: 100%; border-collapse: collapse;">
        <thead><tr>
            <th style="background: #f3f4f6; padding: 10px; text-align: left; border-bottom: 2px solid #e5e7eb;">은행</th>
            <th style="background: #f3f4f6; padding: 10px; text-align: left; border-bottom: 2px solid #e5e7eb;">상품명</th>
            <th style="background: #f3f4f6; padding: 10px; text-align: right; border-bottom: 2px solid #e5e7eb;">최저 금리</th>
            <th style="background: #f3f4f6; padding: 10px; text-align: right; border-bottom: 2px solid #e5e7eb;">최고 금리</th>
            <th style="background: #f3f4f6; padding: 10px; text-align: right; border-bottom: 2px solid #e5e7eb;">대출 한도</th>
            <th style="background: #f3f4f6; padding: 10px; text-align: center; border-bottom: 2px solid #e5e7eb;">상태</th>
            <th style="background: #f3f4f6; padding: 10px; text-align: center; border-bottom: 2px solid #e5e7eb;">관리</th>
        </tr></thead>
        <tbody>
            {% for p in products %}
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6;">{{ p.bank_name }}</td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6; font-weight: 600;">{{ p.product_name }}</td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6; text-align: right;">{{ p.loan_rate_min }}%</td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6; text-align: right;">{{ p.loan_rate_max }}%</td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6; text-align: right;">{{ "{:,.0f}".format(p.loan_limit) }}원</td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6; text-align: center;">
                    {% if p.is_visible == 1 %}
                        <span style="background: #d1fae5; color: #065f46; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;">노출</span>
                    {% else %}
                        <span style="background: #fee2e2; color: #991b1b; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;">비노출</span>
                    {% endif %}
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6; text-align: center;">
                    <form action="/products/toggle_visibility" method="post" style="display:inline;">
                        <input type="hidden" name="bank_name" value="{{ p.bank_name }}">
                        <input type="hidden" name="product_name" value="{{ p.product_name }}">
                        <button type="submit" style="padding: 5px 14px; border: 1px solid {{ '#dc2626' if p.is_visible == 1 else '#059669' }}; background: {{ '#fef2f2' if p.is_visible == 1 else '#ecfdf5' }}; color: {{ '#dc2626' if p.is_visible == 1 else '#059669' }}; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.8rem;">
                            {{ '비노출 처리' if p.is_visible == 1 else '노출 처리' }}
                        </button>
                    </form>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="7" style="padding: 20px; text-align: center; color: #6b7280;">등록된 상품이 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
"""

# ==========================================================================
# [HTML] F5: 미션 관리
# ==========================================================================
MISSIONS_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
<h1>미션 관리</h1>
<p style="color: #6b7280; margin-bottom: 1.5rem;">AI가 사용자의 대출 목적과 상황에 맞게 생성한 미션을 모니터링합니다.</p>

<!-- 통계 카드 -->
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
    <div style="background: white; padding: 1rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; text-align: center;">
        <div style="color: #6b7280; font-size: 0.85rem; font-weight: 600;">전체 미션</div>
        <div style="font-size: 1.8rem; font-weight: 700; color: #1e3a8a;">{{ total }}</div>
    </div>
    <div style="background: white; padding: 1rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; text-align: center;">
        <div style="color: #6b7280; font-size: 0.85rem; font-weight: 600;">대기(pending)</div>
        <div style="font-size: 1.8rem; font-weight: 700; color: #6b7280;">{{ pending }}</div>
    </div>
    <div style="background: white; padding: 1rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; text-align: center;">
        <div style="color: #6b7280; font-size: 0.85rem; font-weight: 600;">진행(in_progress)</div>
        <div style="font-size: 1.8rem; font-weight: 700; color: #3b82f6;">{{ in_progress }}</div>
    </div>
    <div style="background: white; padding: 1rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; text-align: center;">
        <div style="color: #6b7280; font-size: 0.85rem; font-weight: 600;">완료(completed)</div>
        <div style="font-size: 1.8rem; font-weight: 700; color: #059669;">{{ completed }}</div>
    </div>
    <div style="background: white; padding: 1rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; text-align: center;">
        <div style="color: #6b7280; font-size: 0.85rem; font-weight: 600;">완료율</div>
        <div style="font-size: 1.8rem; font-weight: 700; color: #1e3a8a;">{{ "%.1f" | format(completion_rate) }}%</div>
    </div>
</div>

<!-- 유형별 분포 -->
<div style="background: white; padding: 1rem 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; margin-bottom: 1.5rem;">
    <h3 style="margin-top: 0; color: #1e3a8a; font-size: 1rem;">유형별 분포</h3>
    {% for type_name, count in type_counts.items() %}
    <div style="display: flex; align-items: center; margin-bottom: 0.5rem; gap: 10px;">
        <span style="width: 90px; font-size: 0.85rem; font-weight: 600;">{{ type_name }}</span>
        <div style="flex: 1; background: #f3f4f6; border-radius: 4px; height: 20px;">
            <div style="background: #3b82f6; height: 100%; border-radius: 4px; width: {{ (count / total * 100) if total > 0 else 0 }}%; min-width: 2px;"></div>
        </div>
        <span style="width: 30px; text-align: right; font-size: 0.85rem;">{{ count }}</span>
    </div>
    {% endfor %}
</div>

<!-- 필터 -->
<form method="get" style="background: #f9fafb; padding: 12px 15px; border-radius: 8px; margin-bottom: 1rem; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
    <span style="font-weight: bold; color: #4b5563;">필터:</span>
    <select name="status_filter" style="padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; background: white;">
        <option value="">전체 상태</option>
        <option value="pending" {% if status_filter == 'pending' %}selected{% endif %}>대기 (pending)</option>
        <option value="in_progress" {% if status_filter == 'in_progress' %}selected{% endif %}>진행 (in_progress)</option>
        <option value="completed" {% if status_filter == 'completed' %}selected{% endif %}>완료 (completed)</option>
        <option value="expired" {% if status_filter == 'expired' %}selected{% endif %}>만료 (expired)</option>
    </select>
    <select name="type_filter" style="padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; background: white;">
        <option value="">전체 유형</option>
        <option value="savings" {% if type_filter == 'savings' %}selected{% endif %}>savings</option>
        <option value="spending" {% if type_filter == 'spending' %}selected{% endif %}>spending</option>
        <option value="credit" {% if type_filter == 'credit' %}selected{% endif %}>credit</option>
        <option value="investment" {% if type_filter == 'investment' %}selected{% endif %}>investment</option>
        <option value="lifestyle" {% if type_filter == 'lifestyle' %}selected{% endif %}>lifestyle</option>
    </select>
    <button type="submit" style="padding: 8px 16px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">적용</button>
    {% if status_filter or type_filter %}
        <a href="/missions" style="padding: 8px 16px; background: #9ca3af; color: white; text-decoration: none; border-radius: 4px; font-weight: bold;">초기화</a>
    {% endif %}
</form>

<!-- 미션 목록 -->
<div style="background: white; padding: 1rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow-x: auto;">
    <table style="width: 100%; border-collapse: collapse;">
        <thead><tr>
            <th style="background: #f3f4f6; padding: 10px; border-bottom: 2px solid #e5e7eb;">ID</th>
            <th style="background: #f3f4f6; padding: 10px; border-bottom: 2px solid #e5e7eb;">유저</th>
            <th style="background: #f3f4f6; padding: 10px; border-bottom: 2px solid #e5e7eb;">미션 제목</th>
            <th style="background: #f3f4f6; padding: 10px; border-bottom: 2px solid #e5e7eb;">유형</th>
            <th style="background: #f3f4f6; padding: 10px; border-bottom: 2px solid #e5e7eb;">대출 목적</th>
            <th style="background: #f3f4f6; padding: 10px; border-bottom: 2px solid #e5e7eb;">상태</th>
            <th style="background: #f3f4f6; padding: 10px; border-bottom: 2px solid #e5e7eb;">난이도</th>
            <th style="background: #f3f4f6; padding: 10px; border-bottom: 2px solid #e5e7eb;">포인트</th>
            <th style="background: #f3f4f6; padding: 10px; border-bottom: 2px solid #e5e7eb;">마감일</th>
        </tr></thead>
        <tbody>
            {% for m in missions %}
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6;">{{ m.mission_id }}</td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6;">{{ m.user_id }}</td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6; font-weight: 600;">
                    <a href="/missions/{{ m.mission_id }}" style="color: #2563eb; text-decoration: none;">{{ m.mission_title }}</a>
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6;">
                    <span style="background: #eff6ff; color: #1e40af; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600;">{{ m.mission_type }}</span>
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6;">{{ m.loan_purpose or '-' }}</td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6;">
                    {% if m.status == 'completed' %}
                        <span style="background: #ecfdf5; color: #059669; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600;">completed</span>
                    {% elif m.status == 'in_progress' %}
                        <span style="background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600;">in_progress</span>
                    {% elif m.status == 'expired' %}
                        <span style="background: #fef2f2; color: #dc2626; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600;">expired</span>
                    {% else %}
                        <span style="background: #f3f4f6; color: #6b7280; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600;">pending</span>
                    {% endif %}
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6;">{{ m.difficulty }}</td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6;">{{ m.reward_points }}</td>
                <td style="padding: 10px; border-bottom: 1px solid #f3f4f6;">{{ m.due_date or '-' }}</td>
            </tr>
            {% else %}
            <tr><td colspan="9" style="padding: 20px; text-align: center; color: #6b7280;">미션이 없습니다.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
"""

MISSION_DETAIL_TEMPLATE = """
{% extends "base.html" %}
{% block content %}
<h1>미션 상세</h1>
<a href="/missions" style="color: #2563eb; text-decoration: none; font-weight: 600; margin-bottom: 1rem; display: inline-block;">목록으로 돌아가기</a>

<div style="background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb;">
    <table style="width: 100%; border-collapse: collapse;">
        <tr><td style="padding: 10px; font-weight: 600; color: #4b5563; width: 150px;">Mission ID</td><td style="padding: 10px;">{{ mission.mission_id }}</td></tr>
        <tr><td style="padding: 10px; font-weight: 600; color: #4b5563;">유저 ID</td><td style="padding: 10px;">{{ mission.user_id }}</td></tr>
        <tr><td style="padding: 10px; font-weight: 600; color: #4b5563;">미션 제목</td><td style="padding: 10px; font-weight: 700;">{{ mission.mission_title }}</td></tr>
        <tr><td style="padding: 10px; font-weight: 600; color: #4b5563;">미션 설명</td><td style="padding: 10px;">{{ mission.mission_description or '-' }}</td></tr>
        <tr><td style="padding: 10px; font-weight: 600; color: #4b5563;">유형</td><td style="padding: 10px;">{{ mission.mission_type }}</td></tr>
        <tr><td style="padding: 10px; font-weight: 600; color: #4b5563;">대출 목적</td><td style="padding: 10px;">{{ mission.loan_purpose or '-' }}</td></tr>
        <tr><td style="padding: 10px; font-weight: 600; color: #4b5563;">상태</td><td style="padding: 10px;">{{ mission.status }}</td></tr>
        <tr><td style="padding: 10px; font-weight: 600; color: #4b5563;">난이도</td><td style="padding: 10px;">{{ mission.difficulty }}</td></tr>
        <tr><td style="padding: 10px; font-weight: 600; color: #4b5563;">보상 포인트</td><td style="padding: 10px;">{{ mission.reward_points }}</td></tr>
        <tr><td style="padding: 10px; font-weight: 600; color: #4b5563;">마감일</td><td style="padding: 10px;">{{ mission.due_date or '-' }}</td></tr>
        <tr><td style="padding: 10px; font-weight: 600; color: #4b5563;">완료일</td><td style="padding: 10px;">{{ mission.completed_at or '-' }}</td></tr>
        <tr><td style="padding: 10px; font-weight: 600; color: #4b5563;">생성일</td><td style="padding: 10px;">{{ mission.created_at }}</td></tr>
    </table>
</div>
{% endblock %}
"""

# ==========================================================================
# [함수] 로그 테이블 생성기, 인증, 통계
# ==========================================================================

def generate_log_table():
    return """
    <div class="log-table-container">
        <table>
            <thead><tr>
                <th style="width: 30%;">실행 시간</th><th style="width: 15%;">상태</th>
                <th style="width: 15%;">건수</th><th style="width: 40%;">메시지</th>
            </tr></thead>
            <tbody>
                {% for log in logs %}
                <tr>
                    <td>{{ log.executed_at.strftime('%Y-%m-%d %H:%M:%S') if log.executed_at else '-' }}</td>
                    <td><span class="status-badge {{ 'status-fail' if log.status == 'FAIL' else 'status-success' }}">{{ log.status }}</span></td>
                    <td>{{ log.row_count }}</td>
                    <td title="{{ log.error_message if log.error_message else '' }}">
                        <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 250px; color: #6b7280; font-size: 0.9em;">{{ log.error_message if log.error_message else '-' }}</div>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="4" style="text-align: center; padding: 2rem; color: #9ca3af;">수집된 로그가 없습니다.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    """

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

        loan_last_run = loan_logs[0]['executed_at'].strftime('%Y-%m-%d %H:%M') if loan_logs and loan_logs[0].get('executed_at') else "-"
        economy_last_run = economy_logs[0]['executed_at'].strftime('%Y-%m-%d %H:%M') if economy_logs and economy_logs[0].get('executed_at') else "-"
        income_last_run = income_logs[0]['executed_at'].strftime('%Y-%m-%d %H:%M') if income_logs and income_logs[0].get('executed_at') else "-"

        return render_template_string(HTML_TEMPLATE,
            message=message, status=status,
            loan_log_table=render_template_string(generate_log_table(), logs=loan_logs),
            economy_log_table=render_template_string(generate_log_table(), logs=economy_logs),
            income_log_table=render_template_string(generate_log_table(), logs=income_logs),
            loan_last_run=loan_last_run, economy_last_run=economy_last_run, income_last_run=income_last_run,
            auto_refresh=session.get('auto_refresh', True), stats=stats)
    except Exception as e:
        empty_table = render_template_string(generate_log_table(), logs=[])
        return render_template_string(HTML_TEMPLATE,
            message=message or f"시스템 오류: {e}", status=status or "error",
            loan_last_run="-", economy_last_run="-", income_last_run="-",
            loan_log_table=empty_table, economy_log_table=empty_table, income_log_table=empty_table,
            auto_refresh=session.get('auto_refresh', True), stats={})

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
    return render_template_string(LOGIN_TEMPLATE)

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

        return render_template_string(COLLECTION_MGMT_TEMPLATE, sources=sources)
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
        return render_template_string(CREDIT_WEIGHTS_TEMPLATE, **template_vars)
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

        return render_template_string(RECOMMEND_SETTINGS_TEMPLATE,
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

        return render_template_string(PRODUCTS_TEMPLATE,
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

        return render_template_string(MISSIONS_TEMPLATE,
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
        return render_template_string(MISSION_DETAIL_TEMPLATE, mission=mission)
    except Exception as e:
        flash(f"미션 상세 로드 실패: {e}", 'error')
        return redirect(url_for('missions'))

# ==========================================================================
# [라우트] 데이터 조회, 시뮬레이터 (기존 기능 유지)
# ==========================================================================

@app.route('/data/<table_name>')
@login_required
def view_data(table_name):
    allowed_tables = ['raw_loan_products', 'raw_economic_indicators', 'raw_income_stats', 'collection_logs', 'service_config', 'missions']
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

        return render_template_string(DATA_VIEWER_TEMPLATE,
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

# ==========================================================================
# 실행
# ==========================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)
