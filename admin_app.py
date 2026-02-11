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
    st.markdown("""
        <style>
        /* 전체 배경 및 폰트 설정 */
        .stApp {
            background-color: #f8f9fa;
        }
        /* 헤더 스타일 */
        h1 {
            color: #1e3a8a; /* Dark Blue */
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }
        h3 {
            color: #374151;
            margin-top: 20px;
        }
        /* 버튼 스타일 커스터마이징 */
        .stButton > button {
            width: 100%;
            border-radius: 8px;
            font-weight: 600;
            border: 1px solid #e5e7eb;
            transition: all 0.2s ease;
        }
        .stButton > button:hover {
            background-color: #eff6ff;
            border-color: #3b82f6;
            color: #1d4ed8;
            transform: translateY(-2px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        /* 탭 스타일 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            margin-bottom: 20px;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #ffffff;
            border-radius: 6px;
            padding: 10px 20px;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }
        .stTabs [aria-selected="true"] {
            background-color: #dbeafe; /* Light Blue */
            color: #1e40af;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("🛠️ Fintech Service Admin Dashboard")
    st.markdown("시스템 상태 모니터링 및 신용 평가 정책 관리 페이지입니다.")

    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["📊 수집 현황 (Health)", "⚙️ 정책 설정 (Config)", "🚀 수동 제어 (Trigger)"])

    # --- Tab 1: 수집 모니터링 ---
    with tab1:
        st.subheader("최근 데이터 수집 로그")
        st.caption("`collection_logs` 테이블의 최근 20건 데이터를 조회합니다.")
        
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
        st.caption("슬라이더를 조절하여 신용 평가 로직의 가중치를 실시간으로 변경합니다.")
        
        try:
            # 현재 설정값 불러오기
            config_df = pd.read_sql("SELECT * FROM service_config", engine)
            configs = dict(zip(config_df['config_key'], config_df['config_value']))
            
            with st.form("config_form"):
                col1, col2, col3 = st.columns(3)
                # DB에 값이 없으면 기본값(0.5, 0.3, 0.2) 사용
                with col1:
                    new_income_w = st.slider("소득 비중 (WEIGHT_INCOME)", 0.0, 1.0, float(configs.get('WEIGHT_INCOME', 0.5)))
                with col2:
                    new_job_w = st.slider("고용 안정성 (WEIGHT_JOB_STABILITY)", 0.0, 1.0, float(configs.get('WEIGHT_JOB_STABILITY', 0.3)))
                with col3:
                    new_asset_w = st.slider("부동산 자산 (WEIGHT_ESTATE_ASSET)", 0.0, 1.0, float(configs.get('WEIGHT_ESTATE_ASSET', 0.2)))
                
                submitted = st.form_submit_button("설정 저장 (Update)")
                
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
        st.write("긴급하게 데이터를 갱신해야 할 경우 사용하세요. (스케줄러와 별개로 동작)")
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            if st.button("🏦 금감원 대출상품 갱신"):
                with st.spinner("API 호출 및 데이터 적재 중..."):
                    try:
                        collector = DataCollector(engine=engine)
                        collector.collect_fss_loan_products()
                        st.success("대출상품 수집 완료!")
                    except Exception as e:
                        st.error(f"실행 실패: {e}")
                
        with col_b:
            if st.button("📈 경제 지표 갱신"):
                with st.spinner("지표 데이터 수집 중..."):
                    try:
                        collector = DataCollector(engine=engine)
                        collector.collect_economic_indicators()
                        st.success("경제 지표 수집 완료!")
                    except Exception as e:
                        st.error(f"실행 실패: {e}")

        with col_c:
            if st.button("📊 통계청 소득정보 갱신"):
                with st.spinner("소득 통계 수집 중..."):
                    try:
                        collector = DataCollector(engine=engine)
                        collector.collect_kosis_income_stats()
                        st.success("소득 통계 수집 완료!")
                    except Exception as e:
                        st.error(f"실행 실패: {e}")

if __name__ == "__main__":
    admin_dashboard()
