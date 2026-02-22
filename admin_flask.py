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
import subprocess
import atexit
import uuid
import json

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

app = Flask(__name__, static_folder=static_dir, static_url_path='/static', template_folder=template_dir)
_secret_key = os.getenv('FLASK_SECRET_KEY')
if not _secret_key:
    import secrets as _secrets
    _secret_key = _secrets.token_hex(32)
    print("[WARNING] FLASK_SECRET_KEY 환경변수가 설정되지 않았습니다. 임시 랜덤 키를 사용합니다. 서버 재시작 시 세션이 초기화됩니다.")
app.secret_key = _secret_key

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

            # [New] Feature: Dynamic Collection Sources
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS collection_sources (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_key VARCHAR(50) NOT NULL UNIQUE,
                    label VARCHAR(100) NOT NULL,
                    api_desc VARCHAR(255),
                    trigger_val VARCHAR(50) NOT NULL,
                    log_source VARCHAR(50) NOT NULL,
                    config_key_enabled VARCHAR(100),
                    api_key_config VARCHAR(100),
                    period_key VARCHAR(100),
                    freq_key VARCHAR(100),
                    is_default TINYINT(1) DEFAULT 0,
                    endpoint VARCHAR(255),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # [Self-Repair] collection_sources 테이블에 is_default 컬럼 추가 (없을 경우)
            try:
                conn.execute(text("SELECT is_default FROM collection_sources LIMIT 0"))
            except Exception:
                try:
                    conn.execute(text("ALTER TABLE collection_sources ADD COLUMN is_default TINYINT(1) DEFAULT 0"))
                except Exception:
                    pass

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
print("⏳ DB 스키마 초기화 및 연결 확인 중...")
try:
    _init_collector = get_collector()
    init_schema(_init_collector.engine)
    print("✅ DB 초기화 완료")
except Exception as e:
    print(f"⚠️ DB 초기화 건너뜀 (연결 실패): {e}")

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

        # [New] 최근 가입 회원 조회
        recent_users = []
        try:
            with collector.engine.connect() as conn:
                # users 테이블 존재 여부 확인 (안전하게)
                rows = conn.execute(text("SELECT user_id, user_name, join_date, status FROM users ORDER BY created_at DESC LIMIT 5")).fetchall()
                recent_users = [dict(zip(['user_id', 'user_name', 'join_date', 'status'], row)) for row in rows]
        except Exception:
            pass

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
            recent_users=recent_users,
            auto_refresh=session.get('auto_refresh', True), stats=stats,
            system_status=system_status,
            sort_by=sort_by, order=order, status_filter=status_filter)
    except Exception as e:
        system_status_error = {'db': False, 'collectors_active': 0, 'collectors_total': 3, 'now': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'recent_errors': 0}
        return render_template('index.html',
            message=message or f"시스템 오류: {e}", status=status or "error",
            loan_last_run="-", economy_last_run="-", income_last_run="-",
            recent_users=[],
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

        _admin_user = os.getenv('ADMIN_USER', 'admin')
        _admin_password = os.getenv('ADMIN_PASSWORD', 'admin1234')
        if _admin_user == 'admin' or _admin_password == 'admin1234':
            print("[WARNING] ADMIN_USER 또는 ADMIN_PASSWORD가 기본값입니다. 환경변수로 반드시 변경하세요.")
        if username == _admin_user and password == _admin_password:
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

        sources = []
        with collector.engine.connect() as conn:
            # [Self-Repair] 1. 테이블 생성 (없을 경우 대비)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS collection_sources (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_key VARCHAR(50) NOT NULL UNIQUE,
                    label VARCHAR(100) NOT NULL,
                    api_desc VARCHAR(255),
                    trigger_val VARCHAR(50) NOT NULL,
                    log_source VARCHAR(50) NOT NULL,
                    config_key_enabled VARCHAR(100),
                    api_key_config VARCHAR(100),
                    period_key VARCHAR(100),
                    freq_key VARCHAR(100),
                    is_default TINYINT(1) DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # [Self-Repair] 2. is_default 컬럼 확인 및 추가 (기존 테이블에 컬럼이 없을 경우 대비)
            try:
                conn.execute(text("SELECT is_default FROM collection_sources LIMIT 0"))
            except Exception:
                try:
                    conn.execute(text("ALTER TABLE collection_sources ADD COLUMN is_default TINYINT(1) DEFAULT 0"))
                except Exception:
                    pass

            # [Self-Repair] endpoint 컬럼 확인 및 추가
            try:
                conn.execute(text("SELECT endpoint FROM collection_sources LIMIT 0"))
            except Exception:
                try:
                    conn.execute(text("ALTER TABLE collection_sources ADD COLUMN endpoint VARCHAR(255)"))
                except Exception:
                    pass

            # DB에서 수집기 목록 조회 (명시적 컬럼 지정으로 매핑 오류 방지)
            query = """
                SELECT source_key, label, api_desc, trigger_val, log_source, 
                       config_key_enabled, api_key_config, period_key, freq_key, is_default, endpoint 
                FROM collection_sources 
                ORDER BY is_default DESC, id ASC
            """
            rows = conn.execute(text(query)).fetchall()
            
            for row in rows:
                # 인덱스로 매핑하여 안전하게 딕셔너리 생성
                src = {
                    'source_key': row[0],
                    'label': row[1],
                    'api_desc': row[2],
                    'trigger_val': row[3],
                    'log_source': row[4],
                    'config_key_enabled': row[5],
                    'api_key_config': row[6],
                    'period_key': row[7],
                    'freq_key': row[8],
                    'is_default': row[9],
                    'endpoint': row[10]
                }
                
                logs = get_recent_logs(collector.engine, source=src['log_source'], limit=1)
                last_log = logs[0] if logs else {}
            
                # [New] Calculate Next Run Time
                next_run_str = "-"
                if configs.get(src['config_key_enabled'], '1') == '1':
                    try:
                        freq = configs.get(src['freq_key'], 'daily')
                        now = datetime.now()
                        
                        if freq == 'daily':
                            run_time_str = configs.get(f"COLLECTION_TIME_{src['source_key']}", '09:00')
                            run_time = datetime.strptime(run_time_str, "%H:%M").time()
                            next_run = datetime.combine(now.date(), run_time)
                            if next_run <= now:
                                next_run += timedelta(days=1)
                            next_run_str = next_run.strftime('%m-%d %H:%M')
                        else:
                            next_run_str = f"Scheduled ({freq})"
                    except Exception:
                        next_run_str = "계산 오류"
                else:
                    next_run_str = "비활성"

                # 집계 데이터 조회 (최초 실행, 누적 건수)
                try:
                        agg = conn.execute(text("""
                            SELECT MIN(executed_at), SUM(row_count) 
                            FROM collection_logs 
                            WHERE target_source = :s
                        """), {'s': src['log_source']}).fetchone()
                        first_run = agg[0].strftime('%Y-%m-%d %H:%M') if agg[0] else '-'
                        total_count = int(agg[1]) if agg[1] else 0
                except Exception:
                    first_run = '-'
                    total_count = 0

                sources.append({
                    'key': src['source_key'],
                    'label': src['label'],
                    'trigger_val': src['trigger_val'],
                    'log_source': src['log_source'],
                    'enabled': configs.get(src['config_key_enabled'], '1') == '1',
                    'last_run': last_log.get('executed_at', '-') if not last_log.get('executed_at') else last_log['executed_at'].strftime('%Y-%m-%d %H:%M'),
                    'last_status': last_log.get('status', '-'),
                    'api_field': f"api_key_{src['source_key']}", # 동적 필드명 생성
                    'api_value': configs.get(src['api_key_config'], ''),
                    'api_desc': src['api_desc'],
                    'endpoint': src['endpoint'],
                    'period_field': f"period_{src['source_key']}",
                    'period_value': configs.get(src['period_key'], '0'),
                    'freq_field': f"freq_{src['source_key']}",
                    'freq_value': configs.get(src['freq_key'], 'daily'),
                    'day_value': configs.get(f"COLLECTION_DAY_{src['source_key']}", '1'),
                    'is_last_day': configs.get(f"COLLECTION_IS_LAST_DAY_{src['source_key']}", '0') == '1',
                    'weekday_value': configs.get(f"COLLECTION_WEEKDAY_{src['source_key']}", 'mon'),
                    'time_value': configs.get(f"COLLECTION_TIME_{src['source_key']}", '09:00'),
                    'first_run': first_run,
                    'next_run': next_run_str,
                    'total_count': "{:,}".format(total_count),
                    'is_default': src['is_default'] == 1
                })

        return render_template('collection_management.html', sources=sources)
    except Exception as e:
        flash(f"수집 관리 페이지 로드 실패: {e}", "error")
        return redirect(url_for('index'))

@app.route('/toggle_collector', methods=['POST'])
@login_required
def toggle_collector():
    source = request.form.get('source')

    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            # DB에서 config_key 조회
            config_key = conn.execute(text("SELECT config_key_enabled FROM collection_sources WHERE source_key = :k"), {'k': source}).scalar()
            
            if not config_key:
                flash('잘못된 수집 소스입니다.', 'error')
                return redirect(url_for('collection_management'))

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
        collector = get_collector()
        with collector.engine.connect() as conn:
            # 모든 수집기 설정 키 조회
            sources = conn.execute(text("SELECT source_key, api_key_config, period_key, freq_key FROM collection_sources")).fetchall()
            
            key_map = {}
            for s in sources:
                key_map[f"api_key_{s.source_key}"] = s.api_key_config
                key_map[f"period_{s.source_key}"] = s.period_key
                key_map[f"freq_{s.source_key}"] = s.freq_key
                key_map[f"day_{s.source_key}"] = f"COLLECTION_DAY_{s.source_key}"
                key_map[f"is_last_day_{s.source_key}"] = f"COLLECTION_IS_LAST_DAY_{s.source_key}"
                key_map[f"weekday_{s.source_key}"] = f"COLLECTION_WEEKDAY_{s.source_key}"
                key_map[f"time_{s.source_key}"] = f"COLLECTION_TIME_{s.source_key}"

            for form_key, db_key in key_map.items():
                val = None
                if form_key in request.form:
                    val = request.form[form_key]
                elif form_key.startswith('is_last_day_'):
                    val = '0'
                
                if val is not None:
                    exists = conn.execute(text("SELECT 1 FROM service_config WHERE config_key = :k"), {'k': db_key}).scalar()
                    if exists:
                        conn.execute(text("UPDATE service_config SET config_value = :v WHERE config_key = :k"), {'v': val, 'k': db_key})
                    else:
                        conn.execute(text("INSERT INTO service_config (config_key, config_value) VALUES (:k, :v)"), {'k': db_key, 'v': val})
            
            # Update endpoints in collection_sources
            for s in sources:
                ep_key = f"endpoint_{s.source_key}"
                desc_key = f"description_{s.source_key}"
                if ep_key in request.form:
                    conn.execute(text("UPDATE collection_sources SET endpoint = :ep WHERE source_key = :k"), {'ep': request.form[ep_key], 'k': s.source_key})
                if desc_key in request.form:
                    conn.execute(text("UPDATE collection_sources SET api_desc = :desc WHERE source_key = :k"), {'desc': request.form[desc_key], 'k': s.source_key})
            conn.commit()
        flash("수집 설정이 저장되었습니다.", "success")
    except Exception as e:
        flash(f"설정 저장 실패: {e}", "error")
    return redirect(url_for('collection_management'))

@app.route('/collection-management/verify', methods=['POST'])
@login_required
def verify_collection_source():
    endpoint = request.form.get('endpoint')
    api_key = request.form.get('api_key')
    
    collector = get_collector()
    success, message = collector.verify_custom_source(endpoint, api_key)
    
    return {'success': success, 'message': message}

@app.route('/collection-management/add', methods=['POST'])
@login_required
def add_collection_source():
    try:
        label = request.form['label']
        desc = request.form['description']
        endpoint = request.form.get('endpoint', '')
        
        # [New] Additional Configs
        api_key_val = request.form.get('api_key', '')
        freq_val = request.form.get('frequency', 'daily')
        period_val = request.form.get('period', '0')
        
        # 고유 키 생성
        unique_id = str(uuid.uuid4())[:8].upper()
        source_key = f"CUSTOM_{unique_id}"
        trigger_val = f"custom_{unique_id.lower()}"
        log_source = f"CUSTOM_{unique_id}_API"
        
        # 설정 키 자동 생성
        config_key_enabled = f"COLLECTOR_{source_key}_ENABLED"
        api_key_config = f"API_KEY_{source_key}"
        period_key = f"COLLECTION_PERIOD_{source_key}"
        freq_key = f"COLLECTION_FREQUENCY_{source_key}"
        
        collector = get_collector()
        with collector.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO collection_sources (source_key, label, api_desc, trigger_val, log_source, config_key_enabled, api_key_config, period_key, freq_key, is_default, endpoint)
                VALUES (:key, :label, :desc, :trig, :log, :conf_en, :conf_key, :per_key, :freq_key, 0, :endp)
            """), {
                'key': source_key, 'label': label, 'desc': desc, 
                'trig': trigger_val, 'log': log_source,
                'conf_en': config_key_enabled, 'conf_key': api_key_config,
                'per_key': period_key, 'freq_key': freq_key, 'endp': endpoint
            })
            
            # 기본 설정값 추가
            conn.execute(text("INSERT INTO service_config (config_key, config_value) VALUES (:k, '0')"), {'k': config_key_enabled})
            conn.execute(text("INSERT INTO service_config (config_key, config_value) VALUES (:k, :v)"), {'k': api_key_config, 'v': api_key_val})
            conn.execute(text("INSERT INTO service_config (config_key, config_value) VALUES (:k, :v)"), {'k': period_key, 'v': period_val})
            conn.execute(text("INSERT INTO service_config (config_key, config_value) VALUES (:k, :v)"), {'k': freq_key, 'v': freq_val})
            
            conn.commit()
            
        flash(f"새로운 수집기 '{label}'이(가) 추가되었습니다.", "success")
    except Exception as e:
        flash(f"추가 실패: {e}", "error")
    return redirect(url_for('collection_management'))

@app.route('/collection-management/delete', methods=['POST'])
@login_required
def delete_collection_source():
    source_key = request.form['source_key']
    try:
        collector = get_collector()
        with collector.engine.connect() as conn:
            # 설정값 삭제 (선택사항)
            row = conn.execute(text("SELECT config_key_enabled, api_key_config, period_key, freq_key FROM collection_sources WHERE source_key = :k"), {'k': source_key}).fetchone()
            if row:
                for key in row:
                    conn.execute(text("DELETE FROM service_config WHERE config_key = :k"), {'k': key})
            
            conn.execute(text("DELETE FROM collection_sources WHERE source_key = :k"), {'k': source_key})
            conn.commit()
            flash("수집기가 삭제되었습니다.", "success")
    except Exception as e:
        flash(f"삭제 실패: {e}", "error")
    return redirect(url_for('collection_management'))

@app.route('/trigger', methods=['POST'])
@login_required
def trigger_job():
    job_type = request.form.get('job')
    try:
        collector = get_collector()
        configs = get_all_configs(collector.engine)
        with collector.engine.connect() as conn:
            row = conn.execute(text("SELECT source_key, config_key_enabled, endpoint, log_source FROM collection_sources WHERE trigger_val = :t"), {'t': job_type}).fetchone()
        
        if not row:
            flash(f"알 수 없는 수집 작업입니다: {job_type}", "error")
            return redirect(url_for('index'))
        
        source_key, config_key, endpoint, log_source = row
        
        if config_key and configs.get(config_key, '1') != '1':
            flash(f"'{source_key}' 수집기가 비활성화 상태입니다. 수집 관리에서 활성화해주세요.", "warning")
            return redirect(url_for('collection_management'))

        if job_type == 'loan':
            collector.collect_fss_loan_products()
            flash("대출상품 수집 작업이 요청되었습니다. 잠시 후 로그를 확인하세요.", "success")
        elif job_type == 'economy':
            collector.collect_economic_indicators()
            flash("경제 지표 수집 작업이 요청되었습니다. 잠시 후 로그를 확인하세요.", "success")
        elif job_type == 'income':
            collector.collect_kosis_income_stats()
            flash("소득 통계 수집 작업이 요청되었습니다. 잠시 후 로그를 확인하세요.", "success")
        else:
            flash(f"'{source_key}' 수집 작업이 요청되었습니다. 잠시 후 로그를 확인하세요.", "success")
            collector.collect_custom_source(source_key, endpoint)

    except Exception as e:
        flash(f"실행 실패: {e}", "error")
    return redirect(url_for('index'))

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

@app.route('/data-files')
@login_required
def data_file_viewer():
    data_dir = os.path.join(basedir, 'data', 'custom_sources')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    files = []
    try:
        for f in os.listdir(data_dir):
            if f.endswith('.json'):
                path = os.path.join(data_dir, f)
                stats = os.stat(path)
                size_str = f"{stats.st_size / 1024:.1f} KB" if stats.st_size > 1024 else f"{stats.st_size} B"
                files.append({
                    'name': f,
                    'size': size_str,
                    'mtime': datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M')
                })
        files.sort(key=lambda x: x['name'], reverse=True)
    except Exception as e:
        flash(f"파일 목록 조회 실패: {e}", "error")
    
    selected_file = request.args.get('file')
    file_content = None
    if selected_file:
        if '..' in selected_file or '/' in selected_file or '\\' in selected_file:
            flash("잘못된 파일명입니다.", "error")
        else:
            try:
                path = os.path.join(data_dir, selected_file)
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        content = json.load(f)
                        file_content = json.dumps(content, indent=4, ensure_ascii=False)
                else:
                    flash("파일을 찾을 수 없습니다.", "error")
            except Exception as e:
                flash(f"파일 읽기 실패: {e}", "error")

    return render_template('data_file_viewer.html', files=files, selected_file=selected_file, file_content=file_content)

@app.route('/data-files/delete', methods=['POST'])
@login_required
def delete_data_file():
    filename = request.form.get('filename')
    if not filename:
        flash("파일명이 없습니다.", "error")
        return redirect(url_for('data_file_viewer'))
    
    # Security check (Directory Traversal 방지)
    if '..' in filename or '/' in filename or '\\' in filename:
        flash("잘못된 파일명입니다.", "error")
        return redirect(url_for('data_file_viewer'))
        
    try:
        data_dir = os.path.join(basedir, 'data', 'custom_sources')
        path = os.path.join(data_dir, filename)
        if os.path.exists(path):
            os.remove(path)
            flash(f"파일 '{filename}'이(가) 삭제되었습니다.", "success")
        else:
            flash("파일을 찾을 수 없습니다.", "error")
    except Exception as e:
        flash(f"파일 삭제 실패: {e}", "error")
    return redirect(url_for('data_file_viewer'))

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

@app.route('/analytics')
@login_required
def analytics():
    """Streamlit 대시보드를 Iframe으로 임베딩하여 보여주는 페이지"""
    return render_template('streamlit_embed.html')

# ==========================================================================
# 실행
# ==========================================================================

streamlit_process = None

def cleanup_streamlit():
    """종료 시 Streamlit 서브프로세스 정리"""
    global streamlit_process
    if streamlit_process:
        print("🛑 Stopping Streamlit Dashboard...")
        streamlit_process.terminate()
        try:
            streamlit_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            streamlit_process.kill()
        streamlit_process = None

def start_streamlit():
    """Streamlit 대시보드를 서브프로세스로 실행"""
    global streamlit_process
    app_path = os.path.join(basedir, 'admin_app.py')
    if os.path.exists(app_path):
        print(f"🚀 Starting Streamlit Dashboard on http://localhost:8501")
        # headless=true: 브라우저 자동 열림 방지 (Flask 내 임베딩용)
        cmd = [
            sys.executable, "-m", "streamlit", "run", app_path, 
            "--server.port=8501", "--server.headless=true", "--server.address=127.0.0.1"
        ]
        streamlit_process = subprocess.Popen(cmd, cwd=basedir)
        
        # 프로그램 종료 시 정리 함수 등록
        atexit.register(cleanup_streamlit)

if __name__ == '__main__':
    # Flask 리로더가 실행되기 전(메인 프로세스)에 Streamlit 실행
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        start_streamlit()

    # Flask의 리로더가 활성화된 경우 메인 프로세스에서만 스케줄러 실행
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        start_scheduler()
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    if debug_mode:
        print("[WARNING] FLASK_DEBUG=true: 디버그 모드가 활성화되어 있습니다. 프로덕션 환경에서는 반드시 비활성화하세요.")
    app.run(host='0.0.0.0', debug=debug_mode, port=5001)
