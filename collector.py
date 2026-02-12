import pandas as pd
import requests
import traceback
import schedule
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
                        db_url = f"mysql+mysqlconnector://{db_conf['user']}:{db_conf['password']}@{db_conf['host']}:{db_conf['port']}/{db_conf['database']}"
                        return create_engine(db_url)
        except Exception as e:
            print(f"secrets.toml 로드 실패: {e}")

        if os.getenv("DB_HOST"):
            user = os.getenv("DB_USER", "root")
            password = os.getenv("DB_PASSWORD", "")
            host = os.getenv("DB_HOST", "localhost")
            port = os.getenv("DB_PORT", "3306")
            database = os.getenv("DB_DATABASE", "fintech_db")
            db_url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
            return create_engine(db_url)

        raise ValueError("DB 연결 설정을 찾을 수 없습니다. (secrets.toml 또는 환경변수를 확인해주세요.)")

    def _log_status(self, source, status, row_count=0, error_msg=None):
        """수집 결과를 collection_logs 테이블에 기록"""
        log_data = {
            'target_source': source,
            'status': status,
            'row_count': row_count,
            'error_message': error_msg,
            'executed_at': datetime.now()
        }
        df = pd.DataFrame([log_data])
        df.to_sql('collection_logs', self.engine, if_exists='append', index=False)
        print(f"[{source}] {status} - Rows: {row_count}")

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

    def collect_fss_loan_products(self):
        """1. 금융감독원 API: 대출 상품 정보 수집"""
        source_name = "FSS_LOAN_API"
        if not self._is_source_enabled('COLLECTOR_FSS_LOAN_ENABLED'):
            self._log_status(source_name, "SKIPPED", 0, "Source disabled by admin")
            return
        try:
            mock_data = [
                {'bank_name': '우리은행', 'product_name': 'WON직장인대출', 'loan_rate_min': 3.5, 'loan_rate_max': 4.5, 'loan_limit': 100000000},
                {'bank_name': '카카오뱅크', 'product_name': '신용대출', 'loan_rate_min': 3.2, 'loan_rate_max': 5.0, 'loan_limit': 150000000}
            ]
            df = pd.DataFrame(mock_data)
            self._replace_table('raw_loan_products', df)
            self._log_status(source_name, "SUCCESS", len(df))
        except Exception:
            error_msg = traceback.format_exc()
            self._log_status(source_name, "FAIL", 0, error_msg)

    def collect_kosis_income_stats(self):
        """2. 통계청 API: 연령별/소득구간별 소득 통계 수집"""
        source_name = "KOSIS_INCOME_API"
        if not self._is_source_enabled('COLLECTOR_KOSIS_INCOME_ENABLED'):
            self._log_status(source_name, "SKIPPED", 0, "Source disabled by admin")
            return
        print(f"--- {source_name} 수집 시작 ---")
        try:
            mock_data = [
                {'age_group': '20대', 'income_decile': 5, 'avg_income': 32000000},
                {'age_group': '30대', 'income_decile': 5, 'avg_income': 54000000},
                {'age_group': '40대', 'income_decile': 5, 'avg_income': 68000000}
            ]
            df = pd.DataFrame(mock_data)
            self._replace_table('raw_income_stats', df)
            self._log_status(source_name, "SUCCESS", len(df))
        except Exception:
            error_msg = traceback.format_exc()
            self._log_status(source_name, "FAIL", 0, error_msg)

    def collect_economic_indicators(self):
        """3,4,5. 경제 지표 통합 수집 (부동산, 금리, 고용)"""
        source_name = "ECONOMIC_INDICATORS"
        if not self._is_source_enabled('COLLECTOR_ECONOMIC_ENABLED'):
            self._log_status(source_name, "SKIPPED", 0, "Source disabled by admin")
            return
        try:
            indicators = [
                {'indicator_type': 'COFIX', 'region': 'NATIONWIDE', 'indicator_value': 3.85, 'reference_date': '2023-10-15'},
                {'indicator_type': 'ESTATE_PRICE_INDEX', 'region': 'SEOUL', 'indicator_value': 102.5, 'reference_date': '2023-10-01'},
                {'indicator_type': 'EMPLOYMENT_RATE', 'region': 'MANUFACTURING', 'indicator_value': 95.2, 'reference_date': '2023-09-01'}
            ]
            df = pd.DataFrame(indicators)
            self._replace_table('raw_economic_indicators', df)
            self._log_status(source_name, "SUCCESS", len(df))
        except Exception:
            error_msg = traceback.format_exc()
            self._log_status(source_name, "FAIL", 0, error_msg)

    def run_all(self):
        """모든 수집 작업 일괄 실행"""
        print("=== 수집 파이프라인 시작 ===")
        self.collect_fss_loan_products()
        self.collect_kosis_income_stats()
        self.collect_economic_indicators()
        print("=== 수집 파이프라인 종료 ===")

if __name__ == "__main__":
    print("Data Collector Scheduler Started...")
    print("Scheduled to run every day at 09:00 AM.")

    def job():
        collector = DataCollector()
        collector.run_all()

    schedule.every().day.at("09:00").do(job)

    while True:
        schedule.run_pending()
        time.sleep(1)
