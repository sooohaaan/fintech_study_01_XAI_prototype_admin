import pandas as pd
import requests
import traceback
import json
try:
    import schedule
except ImportError:
    schedule = None
import time
from datetime import datetime
import os
from sqlalchemy import create_engine, text
import toml
from pathlib import Path

class DataCollector:
    def __init__(self, engine=None):
        # 외부에서 engine을 주입받으면 사용, 아니면 자체 생성 (Standalone 모드)
        if engine:
            self.engine = engine
        else:
            self.engine = self._create_default_engine()

    def _create_default_engine(self):
        """단독 실행 시 secrets.toml을 읽어 DB 엔진 생성"""
        try:
            base_dir = Path(__file__).parent
            candidates = [
                base_dir / ".streamlit" / "secrets.toml",
                base_dir / "secrets.toml",
                base_dir.parent / ".streamlit" / "secrets.toml",
            ]
            for secrets_path in candidates:
                if secrets_path.exists():
                    secrets = toml.load(secrets_path)
                    if "mysql" in secrets:
                        db_conf = secrets["mysql"]
                        db_url = f"mysql+mysqlconnector://{db_conf['user']}:{db_conf['password']}@{db_conf['host']}:{db_conf['port']}/{db_conf['database']}?connect_timeout=5"
                        return create_engine(db_url)
        except Exception as e:
            print(f"secrets.toml 로드 실패: {e}")

        if os.getenv("DB_HOST"):
            user = os.getenv("DB_USER", "root")
            password = os.getenv("DB_PASSWORD", "")
            host = os.getenv("DB_HOST", "localhost")
            port = os.getenv("DB_PORT", "3306")
            database = os.getenv("DB_DATABASE", "fintech_db")
            db_url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}?connect_timeout=5"
            return create_engine(db_url)

        raise ValueError("DB 연결 설정을 찾을 수 없습니다. (secrets.toml 또는 환경변수를 확인해주세요.)")

    def _log_status(self, source, status, row_count=0, error_msg=None, level='INFO'):
        """수집 결과를 collection_logs 테이블에 기록"""
        log_data = {
            'target_source': source,
            'status': status,
            'row_count': row_count,
            'error_message': error_msg,
            'level': level,
            'executed_at': datetime.now()
        }
        df = pd.DataFrame([log_data])
        
        try:
            df.to_sql('collection_logs', self.engine, if_exists='append', index=False)
        except Exception as e:
            # 컬럼이 없을 경우 자동 추가 (Self-Repair)
            if "Unknown column" in str(e) or "1054" in str(e):
                try:
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE collection_logs ADD COLUMN level VARCHAR(20) DEFAULT 'INFO'"))
                        conn.commit()
                    df.to_sql('collection_logs', self.engine, if_exists='append', index=False)
                except Exception:
                    print(f"로그 저장 실패: {e}")
            else:
                print(f"로그 저장 실패: {e}")

        print(f"[{source}] [{level}] {status} - Rows: {row_count}")

    def _replace_table(self, table_name, df):
        """기존 데이터를 삭제하고 새 데이터로 교체 (중복 적재 방지)
        raw_loan_products의 경우 is_visible 값을 보존함"""
        with self.engine.connect() as conn:
            if table_name == 'raw_loan_products':
                # is_visible 보존: 기존 매핑 저장
                visibility_map = {}
                try:
                    existing = pd.read_sql("SELECT bank_name, product_name, is_visible FROM raw_loan_products", self.engine)
                    for _, row in existing.iterrows():
                        visibility_map[(row['bank_name'], row['product_name'])] = row['is_visible']
                except Exception:
                    pass

                conn.execute(text(f"DELETE FROM {table_name}"))
                conn.commit()

                # 보존된 is_visible 복원 (신규 상품은 기본값 1)
                if 'is_visible' not in df.columns:
                    df['is_visible'] = df.apply(
                        lambda row: visibility_map.get((row['bank_name'], row['product_name']), 1), axis=1
                    )
            else:
                conn.execute(text(f"DELETE FROM {table_name}"))
                conn.commit()

        df.to_sql(table_name, self.engine, if_exists='append', index=False)

    def _is_source_enabled(self, config_key):
        """service_config에서 수집 소스 활성화 여부 확인"""
        try:
            with self.engine.connect() as conn:
                val = conn.execute(
                    text("SELECT config_value FROM service_config WHERE config_key = :k"),
                    {'k': config_key}
                ).scalar()
                return val != '0'  # '0'만 비활성, 나머지(None, '1' 등)는 활성
        except Exception:
            return True  # DB 오류 시 기본 활성

    def _fetch_with_retry(self, func, max_retries=3):
        """API 호출 실패 시 재시도 로직"""
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                print(f"Connection failed. Retrying... ({attempt + 1}/{max_retries})")
                time.sleep(2)

    def _get_config(self, config_key, default=None):
        """DB에서 설정값 조회"""
        try:
            with self.engine.connect() as conn:
                val = conn.execute(
                    text("SELECT config_value FROM service_config WHERE config_key = :k"),
                    {'k': config_key}
                ).scalar()
                return val if val is not None else default
        except Exception:
            return default

    def collect_fss_loan_products(self):
        """1. 금융감독원 API: 대출 상품 정보 수집"""
        source_name = "FSS_LOAN_API"
        if not self._is_source_enabled('COLLECTOR_FSS_LOAN_ENABLED'):
            self._log_status(source_name, "SKIPPED", 0, "Source disabled by admin", level='WARNING')
            return
        try:
            api_key = self._get_config('API_KEY_FSS')
            period = self._get_config('COLLECTION_PERIOD_FSS_LOAN', '0')
            
            if api_key:
                # 실제 API 호출 (예시 URL)
                url = "http://finlife.fss.or.kr/finlifeapi/creditLoanProductsSearch.json"
                params = {
                    'auth': api_key,
                    'topFinGrpNo': '020000',
                    'pageNo': 1
                }
                # response = self._fetch_with_retry(lambda: requests.get(url, params=params))
                # data = response.json()
                # if data['result']['err_cd'] == '000':
                #     products = data['result']['baseList']
                #     df = pd.DataFrame(products)
                #     self._replace_table('raw_loan_products', df)
                #     self._log_status(source_name, "SUCCESS", len(df))
                # else:
                #     raise Exception(f"API Error: {data['result']['err_msg']}")
                
                # [데모용] API Key가 있어도 실제 호출은 주석 처리하고 Mock 데이터 사용 (키가 유효하지 않을 수 있으므로)
                # 실제 구현 시 위 주석을 해제하고 아래 Mock 로직을 제거하세요.
                print(f"[{source_name}] API Key detected. Period: {period} months. (Simulating API Call...)")
                self._collect_fss_mock(source_name)
            else:
                print(f"[{source_name}] No API Key. Using Mock Data.")
                self._collect_fss_mock(source_name)
                
        except Exception:
            error_msg = traceback.format_exc()
            self._log_status(source_name, "FAIL", 0, error_msg, level='ERROR')

    def _collect_fss_mock(self, source_name):
        """금융감독원 가상 데이터 수집"""
        mock_data = [
            {'bank_name': '우리은행', 'product_name': 'WON직장인대출', 'loan_rate_min': 3.5, 'loan_rate_max': 4.5, 'loan_limit': 100000000},
            {'bank_name': '카카오뱅크', 'product_name': '신용대출', 'loan_rate_min': 3.2, 'loan_rate_max': 5.0, 'loan_limit': 150000000},
            {'bank_name': '토스뱅크', 'product_name': '토스신용대출', 'loan_rate_min': 3.8, 'loan_rate_max': 6.5, 'loan_limit': 200000000},
            {'bank_name': '신한은행', 'product_name': '쏠편한 직장인대출', 'loan_rate_min': 4.1, 'loan_rate_max': 5.2, 'loan_limit': 120000000},
            {'bank_name': 'KB국민은행', 'product_name': 'KB 직장인든든 신용대출', 'loan_rate_min': 3.9, 'loan_rate_max': 5.5, 'loan_limit': 200000000},
            {'bank_name': '하나은행', 'product_name': '하나원큐 신용대출', 'loan_rate_min': 4.0, 'loan_rate_max': 5.8, 'loan_limit': 150000000},
            {'bank_name': 'NH농협은행', 'product_name': 'NH직장인대출V', 'loan_rate_min': 3.7, 'loan_rate_max': 4.9, 'loan_limit': 180000000},
            {'bank_name': '케이뱅크', 'product_name': '신용대출 플러스', 'loan_rate_min': 4.5, 'loan_rate_max': 7.0, 'loan_limit': 100000000}
        ]
        df = pd.DataFrame(mock_data)
        self._replace_table('raw_loan_products', df)
        self._log_status(source_name, "SUCCESS (MOCK)", len(df))

    def collect_kosis_income_stats(self):
        """2. 통계청 API: 연령별/소득구간별 소득 통계 수집"""
        source_name = "KOSIS_INCOME_API"
        if not self._is_source_enabled('COLLECTOR_KOSIS_INCOME_ENABLED'):
            self._log_status(source_name, "SKIPPED", 0, "Source disabled by admin", level='WARNING')
            return
        print(f"--- {source_name} 수집 시작 ---")
        try:
            api_key = self._get_config('API_KEY_KOSIS')
            period = self._get_config('COLLECTION_PERIOD_KOSIS_INCOME', '0')
            if api_key:
                # 실제 API 호출 로직 (구현 필요)
                print(f"[{source_name}] API Key detected. Period: {period} months. (Simulating API Call...)")
                self._collect_kosis_mock(source_name)
            else:
                self._collect_kosis_mock(source_name)
        except Exception:
            error_msg = traceback.format_exc()
            self._log_status(source_name, "FAIL", 0, error_msg, level='ERROR')

    def _collect_kosis_mock(self, source_name):
        """통계청 가상 데이터 수집"""
        mock_data = [
            {'age_group': '20대', 'income_decile': 5, 'avg_income': 32000000},
            {'age_group': '30대', 'income_decile': 5, 'avg_income': 54000000},
            {'age_group': '40대', 'income_decile': 5, 'avg_income': 68000000},
            {'age_group': '50대', 'income_decile': 5, 'avg_income': 75000000}
        ]
        df = pd.DataFrame(mock_data)
        self._replace_table('raw_income_stats', df)
        self._log_status(source_name, "SUCCESS (MOCK)", len(df))

    def collect_economic_indicators(self):
        """3,4,5. 경제 지표 통합 수집 (부동산, 금리, 고용)"""
        source_name = "ECONOMIC_INDICATORS"
        if not self._is_source_enabled('COLLECTOR_ECONOMIC_ENABLED'):
            self._log_status(source_name, "SKIPPED", 0, "Source disabled by admin", level='WARNING')
            return
        try:
            api_key = self._get_config('API_KEY_ECOS')
            period = self._get_config('COLLECTION_PERIOD_ECONOMIC', '0')
            if api_key:
                # 실제 API 호출 로직 (구현 필요)
                print(f"[{source_name}] API Key detected. Period: {period} months. (Simulating API Call...)")
                self._collect_economic_mock(source_name)
            else:
                self._collect_economic_mock(source_name)
        except Exception:
            error_msg = traceback.format_exc()
            self._log_status(source_name, "FAIL", 0, error_msg, level='ERROR')

    def _collect_economic_mock(self, source_name):
        """경제지표 가상 데이터 수집"""
        indicators = [
            {'indicator_type': 'COFIX', 'region': 'NATIONWIDE', 'indicator_value': 3.85, 'reference_date': '2023-10-15'},
            {'indicator_type': 'ESTATE_PRICE_INDEX', 'region': 'SEOUL', 'indicator_value': 102.5, 'reference_date': '2023-10-01'},
            {'indicator_type': 'EMPLOYMENT_RATE', 'region': 'MANUFACTURING', 'indicator_value': 95.2, 'reference_date': '2023-09-01'}
        ]
        df = pd.DataFrame(indicators)
        self._replace_table('raw_economic_indicators', df)
        self._log_status(source_name, "SUCCESS (MOCK)", len(df))

    def verify_custom_source(self, endpoint, api_key):
        """커스텀 수집기 설정 검증 (API 호출 테스트)"""
        try:
            if not endpoint or not endpoint.startswith('http'):
                return False, "유효한 URL이 아닙니다."

            params = {}
            if api_key:
                # 일반적인 공공데이터 포털 파라미터명 시도
                params['auth'] = api_key
                params['serviceKey'] = api_key
                params['key'] = api_key
            
            # 검증용 요청 (Timeout 5초)
            response = requests.get(endpoint, params=params, timeout=5)
            
            if response.status_code == 200:
                return True, "연결 성공 (200 OK)"
            else:
                return False, f"연결 실패 (Status: {response.status_code})"
        except Exception as e:
            return False, f"오류 발생: {str(e)}"

    def collect_custom_source(self, source_key, endpoint):
        """커스텀 수집기 실행 (Generic JSON Collector)"""
        try:
            # 1. API Key 조회
            with self.engine.connect() as conn:
                row = conn.execute(text("SELECT api_key_config FROM collection_sources WHERE source_key = :k"), {'k': source_key}).fetchone()
                api_key_config = row[0] if row else None
            
            api_key = None
            if api_key_config:
                api_key = self._get_config(api_key_config)
            
            print(f"[{source_key}] Fetching from {endpoint}...")
            
            # 2. 실제 요청 (프로토타입용 단순화)
            if not endpoint or not endpoint.startswith('http'):
                # URL이 유효하지 않으면 Mock 처리 (테스트 편의성)
                self._log_status(source_key, "SUCCESS (MOCK)", 1, "Endpoint is not a valid URL, treated as mock success")
                return True, None

            params = {}
            if api_key:
                # 일반적인 공공데이터 포털 파라미터명 시도
                params['auth'] = api_key
                params['serviceKey'] = api_key
                params['key'] = api_key

            try:
                response = requests.get(endpoint, params=params, timeout=10)
                response.raise_for_status()
                
                # [New] JSON 데이터 파일 저장
                try:
                    data = response.json()
                except ValueError:
                    data = {"raw_text": response.text}

                base_dir = os.path.dirname(os.path.abspath(__file__))
                save_dir = os.path.join(base_dir, 'data', 'custom_sources')
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{source_key}_{timestamp}.json"
                filepath = os.path.join(save_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)

                self._log_status(source_key, "SUCCESS", 1, f"Data saved to {filename}")
                return True, None
            except Exception as req_e:
                self._log_status(source_key, "FAIL", 0, str(req_e), level='ERROR')
                return False, str(req_e)

        except Exception as e:
            error_msg = traceback.format_exc()
            self._log_status(source_key, "FAIL", 0, error_msg, level='ERROR')
            return False, str(e)

    def run_all(self):
        """모든 수집 작업 일괄 실행"""
        print("=== 수집 파이프라인 시작 ===")
        self.collect_fss_loan_products()
        self.collect_kosis_income_stats()
        self.collect_economic_indicators()
        print("=== 수집 파이프라인 종료 ===")

    def process_expired_points(self):
        """포인트 유효기간 만료 처리 (FIFO 방식)"""
        print("--- 포인트 소멸 처리 시작 ---")
        try:
            with self.engine.connect() as conn:
                # 1. 잔액이 있는 모든 유저 조회
                users = conn.execute(text("SELECT user_id FROM user_points WHERE balance > 0")).fetchall()
                
                for (user_id,) in users:
                    # 2. 해당 유저의 모든 트랜잭션 조회 (시간순)
                    txs = conn.execute(text("""
                        SELECT amount, expires_at 
                        FROM point_transactions 
                        WHERE user_id = :uid 
                        ORDER BY created_at ASC
                    """), {'uid': user_id}).fetchall()
                    
                    # 3. FIFO 로직으로 만료 대상 계산
                    total_spent = 0
                    earned_list = [] # (amount, expires_at)
                    
                    # 지출 총액과 획득 내역 분리
                    for amt, exp in txs:
                        if amt < 0:
                            total_spent += abs(amt)
                        else:
                            earned_list.append({'amount': amt, 'expires_at': exp})
                    
                    expired_amount = 0
                    now = datetime.now()
                    
                    for item in earned_list:
                        if total_spent >= item['amount']:
                            # 이미 사용된 포인트
                            total_spent -= item['amount']
                        else:
                            # 아직 사용되지 않은 잔여 포인트
                            remaining = item['amount'] - total_spent
                            total_spent = 0 # 지출액 모두 소진
                            
                            # 유효기간이 있고, 현재 시간보다 과거라면 만료 처리
                            if item['expires_at'] and item['expires_at'] < now:
                                expired_amount += remaining
                    
                    # 4. 만료된 포인트가 있다면 차감 트랜잭션 생성
                    if expired_amount > 0:
                        conn.execute(text("""
                            INSERT INTO point_transactions (user_id, amount, transaction_type, reason, admin_id)
                            VALUES (:uid, :amt, 'expired', '유효기간 만료 소멸', 'system')
                        """), {'uid': user_id, 'amt': -expired_amount})
                        
                        conn.execute(text("""
                            UPDATE user_points 
                            SET balance = balance - :amt 
                            WHERE user_id = :uid
                        """), {'uid': user_id, 'amt': expired_amount})
                        
                        print(f"[Expiration] User {user_id}: {expired_amount} points expired.")
                
                conn.commit()
                print("--- 포인트 소멸 처리 완료 ---")
        except Exception as e:
            print(f"포인트 소멸 처리 중 오류: {e}")
            traceback.print_exc()

    def check_mission_progress(self):
        """사용자 통계(user_stats) 기반 미션 자동 완료 처리"""
        print("--- 미션 달성 여부 확인 시작 ---")
        try:
            with self.engine.connect() as conn:
                # 1. 진행 중이거나 대기 중인 미션 중 추적 조건이 있는 것 조회
                missions = conn.execute(text("""
                    SELECT m.mission_id, m.user_id, m.mission_title, m.reward_points, 
                           m.tracking_key, m.tracking_operator, m.tracking_value
                    FROM missions m
                    WHERE m.status IN ('pending', 'in_progress') 
                      AND m.tracking_key IS NOT NULL
                """)).fetchall()

                for m in missions:
                    mid, uid, title, reward, key, op, val = m
                    
                    # 2. 유저 스탯 조회 (매핑)
                    db_col = key
                    if key == 'cardUsageRate': db_col = 'card_usage_rate'
                    elif key == 'salaryTransfer': db_col = 'salary_transfer'
                    elif key == 'highInterestLoan': db_col = 'high_interest_loan'
                    elif key == 'minusLimit': db_col = 'minus_limit'
                    elif key == 'openBanking': db_col = 'open_banking'
                    elif key == 'checkedCredit': db_col = 'checked_credit'
                    elif key == 'checkedMembership': db_col = 'checked_membership'
                    
                    try:
                        user_val = conn.execute(text(f"SELECT {db_col} FROM user_stats WHERE user_id = :uid"), {'uid': uid}).scalar()
                    except Exception:
                        continue
                        
                    if user_val is None:
                        continue

                    # 3. 조건 비교
                    passed = False
                    try:
                        if op == 'eq': passed = (float(user_val) == float(val))
                        elif op == 'gte': passed = (float(user_val) >= float(val))
                        elif op == 'lte': passed = (float(user_val) <= float(val))
                        elif op == 'gt': passed = (float(user_val) > float(val))
                        elif op == 'lt': passed = (float(user_val) < float(val))
                    except ValueError:
                        pass

                    if passed:
                        print(f"[Mission] User {uid} completed '{title}'")
                        
                        # 상태 업데이트
                        conn.execute(text("UPDATE missions SET status = 'completed', completed_at = NOW() WHERE mission_id = :mid"), {'mid': mid})
                        
                        # 포인트 지급
                        if reward > 0:
                            expires_at = datetime.now() + timedelta(days=365)
                            conn.execute(text("""
                                INSERT INTO point_transactions (user_id, amount, transaction_type, reason, admin_id, reference_id, expires_at)
                                VALUES (:uid, :amt, 'mission_reward', :reason, 'system', :ref, :exp)
                            """), {'uid': uid, 'amt': reward, 'reason': f"{title} 미션 자동 달성", 'ref': f"mission_{mid}", 'exp': expires_at})
                            
                            conn.execute(text("UPDATE user_points SET balance = balance + :amt, total_earned = total_earned + :amt WHERE user_id = :uid"), {'uid': uid, 'amt': reward})
                            
                        conn.execute(text("INSERT INTO notifications (user_id, message, type) VALUES (:uid, :msg, 'success')"), {'uid': uid, 'msg': f"축하합니다! '{title}' 미션을 달성하여 {reward}P를 받았습니다."})
                
                conn.commit()
        except Exception as e:
            print(f"미션 확인 중 오류: {e}")
            traceback.print_exc()
            
    def check_mission_expiration(self):
        """기한이 지난 미션을 expired 상태로 변경"""
        print("--- 미션 기한 만료 확인 시작 ---")
        try:
            with self.engine.connect() as conn:
                # 기한이 지났고(due_date < 오늘), 아직 진행중/대기중인 미션 조회 및 업데이트
                result = conn.execute(text("""
                    UPDATE missions 
                    SET status = 'expired', updated_at = NOW()
                    WHERE status IN ('pending', 'in_progress') 
                      AND due_date < CURDATE()
                """))
                if result.rowcount > 0:
                    print(f"[Mission] {result.rowcount} missions expired.")
                    conn.commit()
        except Exception as e:
            print(f"미션 기한 확인 중 오류: {e}")
            traceback.print_exc()
            self._log_status("MISSION_EXPIRATION", "FAIL", 0, str(e), level='ERROR')
            
            # [New] 예외 발생 시 시스템 로그 및 관리자 알림 전송
            try:
                error_msg = traceback.format_exc()
                self._log_status("MISSION_CHECK", "FAIL", 0, error_msg, level='ERROR')
                
                with self.engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO notifications (user_id, message, type) 
                        VALUES ('admin', :msg, 'error')
                    """), {'msg': f"미션 확인 프로세스 오류: {str(e)}"})
                    conn.commit()
            except Exception as inner_e:
                print(f"오류 알림 전송 실패: {inner_e}")

if __name__ == "__main__":
    print("Data Collector Scheduler Started...")
    print("Scheduled to run every day at 09:00 AM.")

    def job():
        collector = DataCollector()
        collector.run_all()

    if schedule:
        schedule.every().day.at("09:00").do(job)
        while True:
            schedule.run_pending()
            time.sleep(1)
    else:
        print("schedule 모듈이 설치되지 않아 스케줄러를 실행할 수 없습니다.")
        # 테스트를 위해 1회 실행
        job()
