import streamlit as st
import pandas as pd
import sys
import os
import toml
from pathlib import Path
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# --------------------------------------------------------------------------
# [설정] collector.py 위치 찾기
# collector.py가 상위 폴더나 같은 폴더에 있어야 합니다.
# --------------------------------------------------------------------------
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

try:
    # 같은 폴더에 있다면 바로 import, 없다면 경로 탐색 후 import 시도
    from collector import DataCollector
except ImportError:
    # 만약 상위 폴더에도 없다면 현재 폴더에서 찾기 시도
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from collector import DataCollector
    except ImportError:
        st.error("❌ 'collector.py'를 찾을 수 없습니다. admin_app.py와 같은 폴더에 두거나 상위 폴더에 위치시켜주세요.")
        st.stop()

# --------------------------------------------------------------------------
# [설정] 데이터베이스 연결
# --------------------------------------------------------------------------
@st.cache_resource
def get_db_connection():
    # 1. Streamlit Secrets (st.secrets) 시도
    try:
        if "mysql" in st.secrets:
            db_conf = st.secrets["mysql"]
        else:
            raise KeyError("mysql key missing in st.secrets")
    except Exception:
        # 2. 실패 시 직접 파일 로드 (Fallback)
        base_path = Path(__file__).parent.resolve()
        
        # 탐색할 후보 경로들 (우선순위: .streamlit 폴더 -> 현재 폴더 -> 상위 폴더)
        candidates = [
            base_path / ".streamlit" / "secrets.toml",
            base_path / "secrets.toml",
            base_path.parent / ".streamlit" / "secrets.toml"
        ]
        
        db_conf = None
        for path in candidates:
            if path.exists():
                try:
                    secrets = toml.load(path)
                    if "mysql" in secrets:
                        db_conf = secrets["mysql"]
                        break
                except Exception:
                    continue
        
        if db_conf is None:
            checked_paths = "\n".join([str(p) for p in candidates])
            raise FileNotFoundError(f"Secrets file not found or '[mysql]' section missing.\nChecked paths:\n{checked_paths}")
            
    db_url = f"mysql+mysqlconnector://{db_conf['user']}:{db_conf['password']}@{db_conf['host']}:{db_conf['port']}/{db_conf['database']}?connect_timeout=5"
    return create_engine(db_url)

try:
    engine = get_db_connection()
except Exception as e:
    st.error(f"❌ 데이터베이스 연결 실패: {e}")
    st.stop()

# --------------------------------------------------------------------------
# [메인] 관리자 대시보드 UI
# --------------------------------------------------------------------------
def admin_dashboard():
    st.set_page_config(page_title="Fintech Admin", layout="wide", initial_sidebar_state="collapsed")

    # --------------------------------------------------------------------------
    # [디자인] Custom CSS 적용
    # --------------------------------------------------------------------------
    
    # [Self-Repair] CSS 캐싱 방지: 파일을 직접 읽어 <style> 태그로 주입
    # 이렇게 하면 브라우저가 CSS 파일을 캐싱하지 않고 매번 HTML과 함께 로드합니다.
    def local_css(file_name):
        try:
            # admin_app.py와 같은 위치의 static 폴더 참조
            css_path = os.path.join(os.path.dirname(__file__), file_name)
            with open(css_path, encoding='utf-8') as f:
                st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
        except Exception:
            pass # 파일이 없으면 무시 (기본 스타일 적용)

    # 1. 공통 M3 테마 로드 (Flask 앱과 공유하는 style.css)
    local_css("static/style.css")

    # 2. Streamlit 전용 오버라이드 (M3 변수 활용)
    st.markdown("""
        <style>
        /* Hide Streamlit Branding & Footer for cleaner embedding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stAppDeployButton {display: none;}

        /* 전체 배경 및 폰트 설정 */
        .stApp {
            background-color: var(--bg-page, #F3F3F3);
            color: var(--text-main, #000000);
            font-family: "Roboto", "Pretendard", sans-serif;
        }
        /* 헤더 스타일 */
        h1 {
            color: var(--text-main, #000000);
            border-bottom: 2px solid var(--primary, #E5AA70);
            padding-bottom: 15px;
            margin-bottom: 20px;
            font-weight: 400;
        }
        h3 {
            color: var(--text-sub, #374151);
            margin-top: 20px;
            font-weight: 500;
        }
        /* 버튼 스타일 커스터마이징 */
        .stButton > button {
            width: 100%;
            border-radius: var(--radius-btn, 20px);
            font-weight: 500;
            border: 1px solid var(--border, #e5e7eb);
            transition: var(--transition, all 0.2s ease);
            background-color: transparent;
            color: var(--text-primary-color, #000000);
            position: relative;
            overflow: hidden;
            transform: translate3d(0, 0, 0);
        }
        .stButton > button:hover {
            background-color: var(--md-sys-color-primary-container, #FFF8E1);
            border-color: var(--primary, #E5AA70);
            color: var(--md-sys-color-on-primary-container, #5C3A00);
            transform: translateY(-1px);
            box-shadow: var(--shadow-md);
        }
        /* M3 Ripple Effect */
        .stButton > button::after {
            content: "";
            display: block;
            position: absolute;
            width: 100%;
            height: 100%;
            top: 0;
            left: 0;
            pointer-events: none;
            background-image: radial-gradient(circle, var(--primary, #E5AA70) 10%, transparent 10.01%);
            background-repeat: no-repeat;
            background-position: 50%;
            transform: scale(10, 10);
            opacity: 0;
            transition: transform .5s, opacity 1s;
        }
        .stButton > button:active::after {
            transform: scale(0, 0);
            opacity: 0.2;
            transition: 0s;
        }
        /* 탭 스타일 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            margin-bottom: 20px;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: var(--bg-card, #ffffff);
            border-radius: 8px;
            padding: 10px 20px;
            box-shadow: none;
            border: 1px solid var(--border, #e5e7eb);
            color: var(--text-sub);
        }
        .stTabs [aria-selected="true"] {
            background-color: var(--md-sys-color-primary-container, #FFF8E1);
            color: var(--md-sys-color-on-primary-container, #5C3A00);
            font-weight: 600;
            border-color: var(--primary);
        }
        /* M3 Card Style */
        .m3-card {
            background-color: var(--bg-card, #FFFFFF);
            border-radius: var(--radius-card, 16px);
            padding: 24px;
            box-shadow: none;
            border: 1px solid var(--border, #E0E0E0);
            margin-bottom: 16px;
            transition: var(--transition);
        }
        .m3-card:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
        }
        .m3-card-title {
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text-sub, #4A5568);
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .m3-card-value {
            font-size: 2rem;
            font-weight: 600;
            color: var(--text-main);
            line-height: 1.2;
        }
        .m3-card-sub {
            font-size: 0.8rem;
            color: var(--text-muted, #717171);
            margin-top: 8px;
        }
        /* Sidebar Styling (M3 Navigation Drawer) */
        section[data-testid="stSidebar"] {
            background-color: var(--md-sys-color-surface-container-low, #F7F9FA);
            border-right: 1px solid var(--border, #E0E0E0);
        }
        /* Hide Radio Buttons */
        [data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
            display: none;
        }
        /* Style Radio Labels */
        [data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] > label {
            padding: 12px 20px !important;
            border-radius: 28px !important;
            margin-bottom: 4px !important;
            transition: all 0.2s;
            color: var(--text-sub, #4A5568);
            font-weight: 500;
        }
        /* Active State */
        [data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
            background-color: var(--md-sys-color-secondary-container, #E8DEF8) !important;
            color: var(--md-sys-color-on-secondary-container, #1D192B) !important;
            font-weight: 700;
        }
        </style>
    """, unsafe_allow_html=True)

    # Sidebar Navigation
    with st.sidebar:
        st.title("TrustFin Admin")
        st.markdown("---")
        selected_page = st.radio(
            "Navigation", 
            ["📊 수집 현황 (Health)", "⚙️ 정책 설정 (Config)", "🚀 수동 제어 (Trigger)", "💰 포인트 관리 (Points)"],
            label_visibility="collapsed"
        )
        st.markdown("---")
        st.caption("© 2024 TrustFin")

    st.title("🛠️ Fintech Service Admin Dashboard")

    # M3 Card Helper Function
    def m3_metric_card(title, value, sub_text=None, value_color=None):
        color_style = f' style="color: {value_color};"' if value_color else ''
        st.markdown(f"""
        <div class="m3-card">
            <div class="m3-card-title">{title}</div>
            <div class="m3-card-value"{color_style}>{value}</div>
            {f'<div class="m3-card-sub">{sub_text}</div>' if sub_text else ''}
        </div>
        """, unsafe_allow_html=True)

    # [M3 Guide Card] 대시보드 개요 (Conditional)
    if selected_page == "📊 수집 현황 (Health)":
        st.markdown("""
        <div style='background-color: var(--bg-card); padding: 1.5rem; border-radius: 16px; border: 1px solid var(--border); margin-bottom: 2rem; box-shadow: none;'>
            <h4 style='margin-top:0; color: var(--text-main); display: flex; align-items: center; gap: 8px;'>👋 관리자 대시보드 가이드</h4>
            <p style='color: var(--text-sub); font-size: 0.9rem; margin-bottom: 1rem; line-height: 1.5;'>
                이 대시보드는 <strong>TrustFin 서비스의 데이터 파이프라인과 정책을 총괄하는 관제탑</strong>입니다.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # 요약 카드 예시 (실제 데이터 연동 가능)
        col1, col2, col3 = st.columns(3)
        with col1:
            m3_metric_card("수집 로그", "Checking...", "최근 24시간 기준")
        with col2:
            m3_metric_card("활성 수집기", "3 / 3", "정상 작동 중", value_color="var(--success-fg)")
        with col3:
            m3_metric_card("시스템 상태", "Good", "에러 없음", value_color="var(--success-fg)")
        
        st.divider()

        # [New] 수집기별 상세 현황 (Next Run Time 포함)
        st.subheader("수집기별 상세 현황")
        try:
            with engine.connect() as conn:
                # 수집기 목록 및 설정 조회
                sources = pd.read_sql("SELECT * FROM collection_sources ORDER BY id", conn).to_dict('records')
                cfg_df = pd.read_sql("SELECT * FROM service_config", conn)
                configs = dict(zip(cfg_df['config_key'], cfg_df['config_value']))
                
                # 최근 실행 로그 조회
                logs_df = pd.read_sql("SELECT target_source, MAX(executed_at) as last_run FROM collection_logs GROUP BY target_source", conn)
                last_runs = dict(zip(logs_df['target_source'], logs_df['last_run']))

            if sources:
                cols = st.columns(3)
                for idx, src in enumerate(sources):
                    with cols[idx % 3]:
                        # 활성 상태 확인
                        enabled = configs.get(src['config_key_enabled'], '1') == '1'
                        status_text = "Active" if enabled else "Inactive"
                        status_color = "var(--success-fg)" if enabled else "var(--text-muted)"
                        
                        # 최근 실행 시간
                        last_run = last_runs.get(src['log_source'])
                        last_run_str = last_run.strftime('%m-%d %H:%M') if last_run else "-"
                        
                        # 다음 실행 예정 시간 계산
                        next_run_str = "-"
                        if enabled:
                            try:
                                freq = configs.get(src['freq_key'], 'daily')
                                run_time = configs.get(f"COLLECTION_TIME_{src['source_key']}", '09:00')
                                now = datetime.now()
                                
                                if freq == 'daily':
                                    target_time = datetime.strptime(run_time, "%H:%M").time()
                                    next_run = datetime.combine(now.date(), target_time)
                                    if next_run <= now:
                                        next_run += timedelta(days=1)
                                    next_run_str = next_run.strftime('%m-%d %H:%M')
                                else:
                                    # 주간/월간 등은 복잡하므로 단순 표시 (프로토타입)
                                    next_run_str = f"Scheduled ({freq})"
                            except Exception:
                                next_run_str = "Calc Error"
                        else:
                            next_run_str = "Disabled"

                        st.markdown(f"""
                        <div class="m3-card">
                            <div class="m3-card-title">{src['label']}</div>
                            <div class="m3-card-value" style="font-size: 1.4rem; color: {status_color};">{status_text}</div>
                            <div class="m3-card-sub">최근: {last_run_str}</div>
                            <div class="m3-card-sub" style="color: var(--primary);"><strong>예정: {next_run_str}</strong></div>
                        </div>
                        """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"수집기 상태 조회 중 오류: {e}")

        st.divider()

        st.subheader("최근 데이터 수집 로그")
        st.caption("시스템이 수행한 데이터 수집 작업의 성공/실패 이력을 실시간으로 확인합니다. (최근 20건)")
        
        if st.button("새로고침", key="refresh_logs"):
            st.rerun()

        try:
            query = "SELECT * FROM collection_logs ORDER BY executed_at DESC LIMIT 20"
            logs_df = pd.read_sql(query, engine)

            if not logs_df.empty:
                # 스타일링: FAIL인 경우 빨간색 배경 표시
                def highlight_fail(row):
                    return ['background-color: #ffcccc' if row['status'] == 'FAIL' else '' for _ in row]
                
                st.dataframe(logs_df.style.apply(highlight_fail, axis=1), use_container_width=True)
            else:
                st.info("수집 이력이 없습니다.")
        except Exception as e:
            st.error(f"로그 조회 중 오류 발생: {e}")

    elif selected_page == "⚙️ 정책 설정 (Config)":
        st.subheader("신용 평가 가중치 설정")
        st.info("💡 **작동 로직**: 각 요소의 가중치를 조절하면, AI가 대출 추천 시 해당 요소를 얼마나 중요하게 반영할지 결정합니다. 세 값의 합은 **1.0**이 되어야 합니다.")
        
        try:
            # 현재 설정값 불러오기
            config_df = pd.read_sql("SELECT * FROM service_config", engine)
            configs = dict(zip(config_df['config_key'], config_df['config_value']))
            
            with st.form("config_form"):
                col1, col2, col3 = st.columns(3)
                # DB에 값이 없으면 기본값(0.5, 0.3, 0.2) 사용
                with col1:
                    new_income_w = st.slider(
                        "소득 비중 (Income)", 0.0, 1.0, float(configs.get('WEIGHT_INCOME', 0.5)),
                        help="사용자의 연 소득이 신용 점수에 미치는 영향력입니다. 값이 클수록 소득이 높은 사용자가 유리해집니다."
                    )
                with col2:
                    new_job_w = st.slider(
                        "고용 안정성 (Job)", 0.0, 1.0, float(configs.get('WEIGHT_JOB_STABILITY', 0.3)),
                        help="직업군(대기업, 공무원, 프리랜서 등)에 따른 고용 안정성 점수의 반영 비율입니다."
                    )
                with col3:
                    new_asset_w = st.slider(
                        "자산 비중 (Asset)", 0.0, 1.0, float(configs.get('WEIGHT_ESTATE_ASSET', 0.2)),
                        help="보유 자산(부동산 등) 규모가 평가에 미치는 영향력입니다."
                    )
                
                submitted = st.form_submit_button(
                    "설정 저장 (Update)",
                    help="변경된 가중치를 데이터베이스에 저장하고, 즉시 서비스에 반영합니다."
                )
                
                if submitted:
                    # 합계 검증
                    total_weight = new_income_w + new_job_w + new_asset_w
                    if abs(total_weight - 1.0) > 0.01:
                        st.warning(f"⚠️ 가중치 합계가 1.0이 아닙니다. (현재: {total_weight:.2f}) - 의도한 것이 아니라면 조정해주세요.")
                    
                    # DB 업데이트
                    with engine.connect() as conn:
                        updates = [
                            {'key': 'WEIGHT_INCOME', 'val': new_income_w},
                            {'key': 'WEIGHT_JOB_STABILITY', 'val': new_job_w},
                            {'key': 'WEIGHT_ESTATE_ASSET', 'val': new_asset_w}
                        ]
                        for item in updates:
                            # MySQL의 경우 ON DUPLICATE KEY UPDATE 구문을 쓰거나, 
                            # 여기서는 간단히 UPDATE만 수행 (키가 이미 있다고 가정)
                            conn.execute(
                                text("UPDATE service_config SET config_value = :val WHERE config_key = :key"),
                                item
                            )
                        conn.commit()
                    st.success("✅ 정책 설정이 데이터베이스에 반영되었습니다!")
                    st.rerun()
        except Exception as e:
            st.error(f"설정 로드/저장 중 오류 발생: {e}")

    elif selected_page == "🚀 수동 제어 (Trigger)":
        st.subheader("데이터 수집기 수동 실행")
        st.warning("⚠️ **주의**: 수동 실행은 정해진 스케줄과 무관하게 즉시 데이터를 수집합니다. API 호출 제한 횟수에 유의하세요.")
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            if st.button("🏦 금감원 대출상품 갱신", help="금융감독원 API를 호출하여 최신 대출 상품 정보를 가져옵니다."):
                with st.spinner("API 호출 및 데이터 적재 중..."):
                    try:
                        collector = DataCollector(engine=engine)
                        collector.collect_fss_loan_products()
                        st.success("대출상품 수집 완료!")
                    except Exception as e:
                        st.error(f"실행 실패: {e}")
                
        with col_b:
            if st.button("📈 경제 지표 갱신", help="한국은행 ECOS API 등을 통해 기준 금리, 물가 지수 등을 갱신합니다."):
                with st.spinner("지표 데이터 수집 중..."):
                    try:
                        collector = DataCollector(engine=engine)
                        collector.collect_economic_indicators()
                        st.success("경제 지표 수집 완료!")
                    except Exception as e:
                        st.error(f"실행 실패: {e}")

        with col_c:
            if st.button("📊 통계청 소득정보 갱신", help="KOSIS API를 통해 연령별/소득구간별 평균 소득 데이터를 갱신합니다."):
                with st.spinner("소득 통계 수집 중..."):
                    try:
                        collector = DataCollector(engine=engine)
                        collector.collect_kosis_income_stats()
                        st.success("소득 통계 수집 완료!")
                    except Exception as e:
                        st.error(f"실행 실패: {e}")

    elif selected_page == "💰 포인트 관리 (Points)":
        st.subheader("포인트 시스템 관리")
        st.info("💡 유저들의 포인트 현황을 조회하고, 관리자 권한으로 포인트를 지급하거나 차감할 수 있습니다.")

        # 1. 전체 현황 요약
        try:
            with engine.connect() as conn:
                total_balance = conn.execute(text("SELECT SUM(balance) FROM user_points")).scalar() or 0
                total_minted = conn.execute(text("SELECT SUM(total_earned) FROM user_points")).scalar() or 0
                total_spent = conn.execute(text("SELECT SUM(total_spent) FROM user_points")).scalar() or 0
        except Exception as e:
            st.error(f"데이터 조회 실패: {e}")
            total_balance, total_minted, total_spent = 0, 0, 0

        col1, col2, col3 = st.columns(3)
        with col1:
            m3_metric_card("총 유통량 (Circulating)", f"{int(total_balance):,} P", "현재 유저 보유 총액", value_color="var(--primary)")
        with col2:
            m3_metric_card("누적 발행량 (Minted)", f"{int(total_minted):,} P", "총 지급된 포인트", value_color="var(--success-fg)")
        with col3:
            m3_metric_card("누적 사용량 (Burned)", f"{int(total_spent):,} P", "사용/소멸된 포인트", value_color="var(--danger-fg)")

        st.divider()

        # [New] 일별 추이 차트
        st.markdown("#### 📈 일별 포인트 변동 추이 (Daily Trends)")
        try:
            chart_query = """
                SELECT 
                    DATE(created_at) as date, 
                    SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as '획득 (Earned)',
                    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as '사용 (Spent)'
                FROM point_transactions 
                GROUP BY DATE(created_at) 
                ORDER BY date ASC
                LIMIT 30
            """
            chart_df = pd.read_sql(chart_query, engine)
            
            if not chart_df.empty:
                chart_df.set_index('date', inplace=True)
                st.line_chart(chart_df, color=["#10B981", "#BA1A1A"])
            else:
                st.info("차트를 표시할 데이터가 충분하지 않습니다.")
        except Exception as e:
            st.error(f"차트 데이터 조회 실패: {e}")

        st.divider()

        # 2. 포인트 수동 조정 (지급/차감)
        st.markdown("#### 🛠️ 포인트 수동 조정")
        with st.expander("포인트 지급/차감 패널 열기"):
            with st.form("point_adjust_form"):
                c1, c2, c3 = st.columns([2, 2, 3])
                with c1:
                    target_user = st.text_input("유저 ID", placeholder="예: user_001")
                with c2:
                    amount = st.number_input("조정 금액 (양수:지급, 음수:차감)", step=100, value=0)
                with c3:
                    reason = st.text_input("사유 (Audit Log)", placeholder="예: 이벤트 보상, 오류 정정")
                
                submitted = st.form_submit_button("실행 (Execute)")
                
                if submitted:
                    if not target_user or amount == 0 or not reason:
                        st.warning("모든 필드를 입력해주세요.")
                    else:
                        try:
                            with engine.connect() as conn:
                                # 유저 존재 확인 및 생성
                                exists = conn.execute(text("SELECT 1 FROM user_points WHERE user_id = :uid"), {'uid': target_user}).scalar()
                                if not exists:
                                    if amount < 0:
                                        st.error("존재하지 않는 유저의 포인트를 차감할 수 없습니다.")
                                        st.stop()
                                    conn.execute(text("INSERT INTO user_points (user_id, balance, total_earned, total_spent) VALUES (:uid, 0, 0, 0)"), {'uid': target_user})
                                
                                # 트랜잭션 기록
                                conn.execute(text("""
                                    INSERT INTO point_transactions (user_id, amount, transaction_type, reason, admin_id)
                                    VALUES (:uid, :amt, 'manual', :reason, 'admin')
                                """), {'uid': target_user, 'amt': amount, 'reason': reason})
                                
                                # 잔액 업데이트
                                if amount > 0:
                                    conn.execute(text("UPDATE user_points SET balance = balance + :amt, total_earned = total_earned + :amt WHERE user_id = :uid"), {'amt': amount, 'uid': target_user})
                                else:
                                    conn.execute(text("UPDATE user_points SET balance = balance + :amt, total_spent = total_spent + :abs_amt WHERE user_id = :uid"), {'amt': amount, 'abs_amt': abs(amount), 'uid': target_user})
                                
                                conn.commit()
                            st.success(f"{target_user}님에게 {amount:,} P 조정 완료!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"처리 중 오류 발생: {e}")

        st.divider()

        # 3. 유저별 포인트 현황 조회
        st.markdown("#### 📋 유저별 포인트 현황")
        search_query = st.text_input("유저 검색", placeholder="유저 ID로 검색...")
        
        try:
            sql = "SELECT user_id, balance, total_earned, total_spent, updated_at FROM user_points"
            params = {}
            if search_query:
                sql += " WHERE user_id LIKE :q"
                params['q'] = f"%{search_query}%"
            sql += " ORDER BY balance DESC LIMIT 50"
            
            df = pd.read_sql(sql, engine, params=params)
            
            # 포맷팅
            st.dataframe(
                df,
                column_config={
                    "user_id": "유저 ID",
                    "balance": st.column_config.NumberColumn("현재 잔액", format="%d P"),
                    "total_earned": st.column_config.NumberColumn("누적 획득", format="%d P"),
                    "total_spent": st.column_config.NumberColumn("누적 사용", format="%d P"),
                    "updated_at": st.column_config.DatetimeColumn("최근 변동일", format="YYYY-MM-DD HH:mm:ss"),
                },
                use_container_width=True,
                hide_index=True
            )
        except Exception as e:
            st.error(f"목록 조회 실패: {e}")

        st.divider()

        # 4. 최근 포인트 거래 내역 (Transaction History)
        st.markdown("#### 📜 최근 거래 내역 (Transactions)")
        
        # [New] 필터링 기능 추가
        tx_search_user = st.text_input("거래 내역 검색 (유저 ID)", placeholder="유저 ID 입력...", key="tx_search")

        try:
            base_query = """
                SELECT transaction_id, user_id, amount, transaction_type, reason, created_at 
                FROM point_transactions 
            """
            params = {}
            if tx_search_user:
                base_query += " WHERE user_id LIKE :uid"
                params['uid'] = f"%{tx_search_user}%"
            base_query += " ORDER BY created_at DESC LIMIT 50"

            tx_df = pd.read_sql(base_query, engine, params=params)
            
            st.dataframe(
                tx_df,
                column_config={
                    "transaction_id": "ID",
                    "user_id": "유저 ID",
                    "amount": st.column_config.NumberColumn("금액", format="%d P"),
                    "transaction_type": "유형",
                    "reason": "사유",
                    "created_at": st.column_config.DatetimeColumn("일시", format="YYYY-MM-DD HH:mm:ss"),
                },
                use_container_width=True,
                hide_index=True
            )
        except Exception as e:
            st.error(f"거래 내역 조회 실패: {e}")

if __name__ == "__main__":
    admin_dashboard()
