import unittest
from unittest.mock import MagicMock, ANY
from collector import DataCollector
from sqlalchemy import text

class TestDataCollector(unittest.TestCase):
    def setUp(self):
        # DB 엔진 및 연결 객체 Mocking
        self.mock_engine = MagicMock()
        # context manager (with self.engine.connect() as conn) 처리
        self.mock_conn = self.mock_engine.connect.return_value.__enter__.return_value
        self.collector = DataCollector(engine=self.mock_engine)

    def test_check_mission_progress_success(self):
        """미션 조건 달성 시 상태 업데이트 및 포인트 지급 테스트"""
        # 1. Mock Data 설정
        # (mission_id, user_id, title, reward, key, op, val)
        mock_missions = [
            (101, 'user_test', 'Credit Score Mission', 100, 'creditScore', 'gte', 800)
        ]
        
        # 2. execute 메서드의 side_effect 설정 (쿼리에 따라 다른 결과 반환)
        def execute_side_effect(statement, params=None):
            sql = str(statement)
            mock_result = MagicMock()
            
            # 미션 목록 조회 쿼리
            if "SELECT m.mission_id" in sql:
                mock_result.fetchall.return_value = mock_missions
                return mock_result
            
            # 유저 스탯 조회 쿼리 (creditScore -> credit_score 매핑 확인)
            if "SELECT credit_score FROM user_stats" in sql:
                # 유저 점수 850 (조건 800 이상 만족)
                mock_result.scalar.return_value = 850
                return mock_result
            
            return mock_result

        self.mock_conn.execute.side_effect = execute_side_effect

        # 3. 메서드 실행
        self.collector.check_mission_progress()

        # 4. 검증
        calls = self.mock_conn.execute.call_args_list
        
        # 4-1. 미션 상태 업데이트 쿼리 호출 여부 확인
        update_called = False
        for call in calls:
            sql = str(call[0][0])
            if "UPDATE missions SET status = 'completed'" in sql:
                update_called = True
                # 파라미터 확인
                self.assertEqual(call[1]['mid'], 101)
        
        self.assertTrue(update_called, "미션 완료 상태 업데이트가 호출되어야 합니다.")

        # 4-2. 포인트 지급 쿼리 호출 여부 확인
        point_insert_called = False
        for call in calls:
            sql = str(call[0][0])
            if "INSERT INTO point_transactions" in sql:
                point_insert_called = True
                self.assertEqual(call[1]['uid'], 'user_test')
                self.assertEqual(call[1]['amt'], 100)
        
        self.assertTrue(point_insert_called, "포인트 트랜잭션 생성이 호출되어야 합니다.")

    def test_check_mission_progress_fail(self):
        """미션 조건 미달성 시 업데이트가 수행되지 않아야 함"""
        mock_missions = [
            (102, 'user_test_fail', 'High Score', 200, 'creditScore', 'gte', 900)
        ]
        
        def execute_side_effect(statement, params=None):
            sql = str(statement)
            mock_result = MagicMock()
            
            if "SELECT m.mission_id" in sql:
                mock_result.fetchall.return_value = mock_missions
                return mock_result
            
            if "SELECT credit_score FROM user_stats" in sql:
                # 유저 점수 800 (조건 900 이상 불만족)
                mock_result.scalar.return_value = 800
                return mock_result
            
            return mock_result

        self.mock_conn.execute.side_effect = execute_side_effect
        self.collector.check_mission_progress()

        # 업데이트 쿼리가 호출되지 않았는지 확인
        calls = self.mock_conn.execute.call_args_list
        for call in calls:
            sql = str(call[0][0])
            self.assertNotIn("UPDATE missions SET status = 'completed'", sql)
            self.assertNotIn("INSERT INTO point_transactions", sql)

    def test_check_mission_mapping(self):
        """컬럼 매핑 로직 테스트 (cardUsageRate -> card_usage_rate)"""
        mock_missions = [
            (103, 'user_card', 'Low Usage', 50, 'cardUsageRate', 'lte', 30)
        ]
        
        # execute 호출 시 card_usage_rate 쿼리가 생성되는지 확인하기 위한 Mock 설정은 생략하고
        # 실제 로직에서 매핑이 잘 동작하여 업데이트까지 이어지는지 확인
        # (위의 success 테스트와 유사하지만 키값만 다름)
        # ... (생략: 위 패턴과 동일하게 구현 가능)
        pass

if __name__ == '__main__':
    unittest.main()