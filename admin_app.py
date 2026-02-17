import streamlit as st
import pandas as pd
import sys
import os
import toml
from pathlib import Path
from sqlalchemy import create_engine, text

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
            
    db_url = f"mysql+mysqlconnector://{db_conf['user']}:{db_conf['password']}@{db_conf['host']}:{db_conf['port']}/{db_conf['database']}"
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
    st.set_page_config(page_title="Fintech Admin", layout="wide")

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
        /* 전체 배경 및 폰트 설정 */
        .stApp {
            background-color: var(--bg-page, #f8f9fa);
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
        }
        .stButton > button:hover {
            background-color: var(--md-sys-color-primary-container, #FFF8E1);
            border-color: var(--primary, #E5AA70);
            color: var(--md-sys-color-on-primary-container, #5C3A00);
            transform: translateY(-1px);
            box-shadow: var(--shadow-md);
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
        </style>
    """, unsafe_allow_html=True)

    st.title("🛠️ Fintech Service Admin Dashboard")
    
    # [M3 Guide Card] 대시보드 개요
    st.markdown("""
    <div style='background-color: var(--bg-card); padding: 1.5rem; border-radius: 16px; border: 1px solid var(--border); margin-bottom: 2rem; box-shadow: none;'>
        <h4 style='margin-top:0; color: var(--text-main); display: flex; align-items: center; gap: 8px;'>👋 관리자 대시보드 가이드</h4>
        <p style='color: var(--text-sub); font-size: 0.9rem; margin-bottom: 1rem; line-height: 1.5;'>
            이 대시보드는 <strong>TrustFin 서비스의 데이터 파이프라인과 정책을 총괄하는 관제탑</strong>입니다. 데이터 수집부터 신용 평가 로직 설정까지 서비스의 핵심 기능을 제어합니다.
        </p>
        <div style='display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; font-size: 0.85rem; color: var(--text-sub);'>
            <div style='background: var(--bg-page); padding: 10px; border-radius: 8px;'><strong>📊 수집 현황 (Health)</strong><br>데이터 수집 상태 모니터링 및 로그 조회</div>
            <div style='background: var(--bg-page); padding: 10px; border-radius: 8px;'><strong>⚙️ 정책 설정 (Config)</strong><br>신용 평가 가중치 및 알고리즘 조정</div>
            <div style='background: var(--bg-page); padding: 10px; border-radius: 8px;'><strong>🚀 수동 제어 (Trigger)</strong><br>긴급 데이터 갱신 및 수집기 실행</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

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

    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["📊 수집 현황 (Health)", "⚙️ 정책 설정 (Config)", "🚀 수동 제어 (Trigger)"])

    # --- Tab 1: 수집 모니터링 ---
    with tab1:
        # 요약 카드 예시 (실제 데이터 연동 가능)
        col1, col2, col3 = st.columns(3)
        with col1:
            m3_metric_card("수집 로그", "Checking...", "최근 24시간 기준")
        with col2:
            m3_metric_card("활성 수집기", "3 / 3", "정상 작동 중", value_color="var(--success-fg)")
        with col3:
            m3_metric_card("시스템 상태", "Good", "에러 없음", value_color="var(--success-fg)")
        
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

    # --- Tab 2: 평가 정책 관리 ---
    with tab2:
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

    # --- Tab 3: 수동 제어 ---
    with tab3:
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

if __name__ == "__main__":
    admin_dashboard()
