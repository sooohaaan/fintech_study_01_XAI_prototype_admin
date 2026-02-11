import pandas as pd
import requests
import traceback
import schedule
import time
from datetime import datetime
import os
from sqlalchemy import create_engine
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
            # 현재 파일(collector.py)이 있는 폴더 기준 .streamlit/secrets.toml 탐색
            base_dir = Path(__file__).parent
            secrets_path = base_dir / ".streamlit" / "secrets.toml"
            
            # 파일이 없으면 상위 폴더도 한 번 확인 (프로젝트 루트 실행 대비)
            if not secrets_path.exists():
                secrets_path = base_dir.parent / ".streamlit" / "secrets.toml"
            
            if secrets_path.exists():
                secrets = toml.load(secrets_path)
                if "mysql" in secrets:
                    db_conf = secrets["mysql"]
                    db_url = f"mysql+mysqlconnector://{db_conf['user']}:{db_conf['password']}@{db_conf['host']}:{db_conf['port']}/{db_conf['database']}"
                    return create_engine(db_url)
        except Exception as e:
            print(f"⚠️ secrets.toml 로드 실패: {e}")

        # 실패 시 하드코딩된 기본값 사용 (개발용 Fallback)
        print("⚠️ 기본 하드코딩 설정으로 DB에 연결합니다.")
        return create_engine('mysql+mysqlconnector://user:password@localhost/fintech_db')

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

    def _fetch_with_retry(self, func, max_retries=3):
        """API 호출 실패 시 재시도 로직"""
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                print(f"⚠️ Connection failed. Retrying... ({attempt + 1}/{max_retries})")
                time.sleep(2)

    def collect_fss_loan_products(self):
        """1. 금융감독원 API: 대출 상품 정보 수집"""
        source_name = "FSS_LOAN_API"
        try:
            # API 호출 로직 (예시)
            # url = "http://finlife.fss.or.kr/..."
            # response = requests.get(url, params={...})
            # data = response.json()
            
            # Mock Data (실제 구현 시 API 응답 파싱으로 대체)
            mock_data = [
                {'bank_name': '우리은행', 'product_name': 'WON직장인대출', 'loan_rate_min': 3.5, 'loan_rate_max': 4.5, 'loan_limit': 100000000},
                {'bank_name': '카카오뱅크', 'product_name': '신용대출', 'loan_rate_min': 3.2, 'loan_rate_max': 5.0, 'loan_limit': 150000000}
            ]
            df = pd.DataFrame(mock_data)
            
            # DB 적재
            df.to_sql('raw_loan_products', self.engine, if_exists='append', index=False)
            self._log_status(source_name, "SUCCESS", len(df))
            
        except Exception:
            error_msg = traceback.format_exc()
            self._log_status(source_name, "FAIL", 0, error_msg)

    def collect_kosis_income_stats(self):
        """2. 통계청 API: 연령별/소득구간별 소득 통계 수집"""
        source_name = "KOSIS_INCOME_API"
        print(f"--- {source_name} 수집 시작 ---")
        try:
            # Mock Data (실제로는 self._fetch_with_retry(requests.get, ...) 형태로 사용)
            mock_data = [
                {'age_group': '20대', 'income_decile': 5, 'avg_income': 32000000},
                {'age_group': '30대', 'income_decile': 5, 'avg_income': 54000000},
                {'age_group': '40대', 'income_decile': 5, 'avg_income': 68000000}
            ]
            df = pd.DataFrame(mock_data)
            df.to_sql('raw_income_stats', self.engine, if_exists='append', index=False)
            self._log_status(source_name, "SUCCESS", len(df))
        except Exception:
            error_msg = traceback.format_exc()
            self._log_status(source_name, "FAIL", 0, error_msg)

    def collect_economic_indicators(self):
        """3,4,5. 경제 지표 통합 수집 (부동산, 금리, 고용)"""
        source_name = "ECONOMIC_INDICATORS"
        try:
            # 여러 API에서 데이터를 가져와 통합한다고 가정
            indicators = [
                {'indicator_type': 'COFIX', 'region': 'NATIONWIDE', 'indicator_value': 3.85, 'reference_date': '2023-10-15'},
                {'indicator_type': 'ESTATE_PRICE_INDEX', 'region': 'SEOUL', 'indicator_value': 102.5, 'reference_date': '2023-10-01'},
                {'indicator_type': 'EMPLOYMENT_RATE', 'region': 'MANUFACTURING', 'indicator_value': 95.2, 'reference_date': '2023-09-01'}
            ]
            df = pd.DataFrame(indicators)
            
            df.to_sql('raw_economic_indicators', self.engine, if_exists='append', index=False)
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
    print("🚀 Data Collector Scheduler Started...")
    print("🕒 Scheduled to run every day at 09:00 AM.")

    def job():
        collector = DataCollector()
        collector.run_all()

    schedule.every().day.at("09:00").do(job)

    while True:
        schedule.run_pending()
        time.sleep(1)
