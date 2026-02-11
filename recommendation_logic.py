import pandas as pd
from sqlalchemy import create_engine

def recommend_products(engine, user_profile):
    """
    사용자 프로필과 수집된 데이터를 기반으로 대출 상품을 추천합니다.
    
    Args:
        engine: SQLAlchemy DB Engine (DB 연결 객체)
        user_profile (dict): 사용자 입력 정보
            - annual_income (int): 연소득 (단위: 원)
            - desired_amount (int): 희망 대출 금액 (단위: 원)
            - credit_score (int, optional): 신용점수 (기본값: None)
            
    Returns:
        pd.DataFrame: 추천 상품 리스트 (예상 금리 낮은 순 정렬)
            - 컬럼: 은행명, 상품명, 한도, 최저금리, 최고금리, 예상금리
    """
    
    # 1. DB에서 수집된 대출 상품 전체 조회
    try:
        query = "SELECT * FROM raw_loan_products"
        products_df = pd.read_sql(query, engine)
    except Exception as e:
        print(f"데이터 조회 실패: {e}")
        return pd.DataFrame()
    
    if products_df.empty:
        return pd.DataFrame()

    # 2. 사용자 입력값 추출
    income = user_profile.get('annual_income', 0)
    desired_amt = user_profile.get('desired_amount', 0)
    
    # 3. 1차 필터링: 대출 한도 체크
    # 상품의 최대 한도가 사용자의 희망 대출액보다 커야 함
    filtered_df = products_df[products_df['loan_limit'] >= desired_amt].copy()
    
    # 조건에 맞는 상품이 하나도 없으면, 한도 조건 없이 전체 상품 중에서 추천 (Fallback)
    if filtered_df.empty:
        filtered_df = products_df.copy()

    # 4. 개인화된 예상 금리 계산 (Scoring Logic)
    # 로직: 소득이 높을수록 최저 금리에 가깝게, 낮을수록 최고 금리에 가깝게 배정
    def calculate_estimated_rate(row, user_income):
        min_rate = row['loan_rate_min']
        max_rate = row['loan_rate_max']
        
        # (예시 정책) 연소득 5,000만원 기준
        # 5,000만원 이상: 최저 금리 + (금리차의 20% 가산)
        # 5,000만원 미만: 최저 금리 + (금리차의 70% 가산)
        spread = max_rate - min_rate
        
        if user_income >= 50000000:
            estimated = min_rate + (spread * 0.2)
        else:
            estimated = min_rate + (spread * 0.7)
            
        return round(estimated, 2)

    filtered_df['estimated_rate'] = filtered_df.apply(
        lambda row: calculate_estimated_rate(row, income), axis=1
    )

    # 5. 정렬 및 상위 상품 추출
    # 1순위: 예상 금리 낮은 순, 2순위: 대출 한도 높은 순
    recommendations = filtered_df.sort_values(
        by=['estimated_rate', 'loan_limit'], 
        ascending=[True, False]
    )
    
    # 결과 정리 (필요한 컬럼만 선택)
    result_cols = [
        'bank_name', 'product_name', 'loan_limit', 
        'loan_rate_min', 'loan_rate_max', 'estimated_rate'
    ]
    
    return recommendations[result_cols].head(5)