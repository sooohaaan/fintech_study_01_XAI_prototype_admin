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
            - job_score (float): 고용 안정성 점수 (0.0 ~ 1.0)
            - asset_amount (int): 보유 자산 (단위: 원)
            
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

    # 2. DB에서 가중치 설정 로드 (설정이 없으면 기본값 사용)
    try:
        cfg_df = pd.read_sql("SELECT * FROM service_config", engine)
        configs = dict(zip(cfg_df['config_key'], cfg_df['config_value']))
    except Exception:
        configs = {}

    w_income = float(configs.get('WEIGHT_INCOME', 0.5))
    w_job = float(configs.get('WEIGHT_JOB_STABILITY', 0.3))
    w_asset = float(configs.get('WEIGHT_ESTATE_ASSET', 0.2))

    # 3. 사용자 입력값 및 점수화 (Scoring)
    income = float(user_profile.get('annual_income', 0))
    desired_amt = float(user_profile.get('desired_amount', 0))
    job_score = float(user_profile.get('job_score', 0.5)) # 0.0(불안정) ~ 1.0(안정)
    asset_amt = float(user_profile.get('asset_amount', 0))
    
    # 4. 1차 필터링: 대출 한도 체크
    # 상품의 최대 한도가 사용자의 희망 대출액보다 커야 함
    filtered_df = products_df[products_df['loan_limit'] >= desired_amt].copy()
    
    # 조건에 맞는 상품이 하나도 없으면, 한도 조건 없이 전체 상품 중에서 추천 (Fallback)
    if filtered_df.empty:
        filtered_df = products_df.copy()

    # 5. 종합 신용 점수 계산 (0.0 ~ 1.0)
    # - 소득 점수: 연소득 1억원 이상이면 만점(1.0)으로 정규화
    score_income = min(income / 100000000.0, 1.0)
    # - 자산 점수: 자산 5억원 이상이면 만점(1.0)으로 정규화
    score_asset = min(asset_amt / 500000000.0, 1.0)
    
    # 가중 평균 계산
    final_score = (score_income * w_income) + (job_score * w_job) + (score_asset * w_asset)
    
    # 점수 범위 보정 (0.0 ~ 1.0) - 가중치 합이 1이 아닐 경우를 대비하여 안전장치 추가
    final_score = max(0.0, min(final_score, 1.0))

    # 6. 개인화된 예상 금리 및 설명 생성 (XAI)
    def calculate_details(row, score):
        min_r = row['loan_rate_min']
        max_r = row['loan_rate_max']
        
        # 점수가 높을수록(1.0에 가까울수록) 최저 금리에 가깝게 배정
        estimated = max_r - ((max_r - min_r) * score)
        
        # 추천 사유 생성 (기여도가 높은 항목 표시)
        reasons = []
        if score_income * w_income >= 0.15: reasons.append("소득수준 우수")
        if job_score * w_job >= 0.1: reasons.append("고용 안정적")
        if score_asset * w_asset >= 0.05: reasons.append("자산 보유")
        
        if not reasons: reasons.append("기본 심사 통과")
        
        explanation = f"종합점수 {score:.2f}점 ({', '.join(reasons)})"
        return pd.Series([round(estimated, 2), explanation])

    filtered_df[['estimated_rate', 'explanation']] = filtered_df.apply(
        lambda row: calculate_details(row, final_score), axis=1
    )

    # 7. 정렬 및 상위 상품 추출
    # 1순위: 예상 금리 낮은 순, 2순위: 대출 한도 높은 순
    recommendations = filtered_df.sort_values(
        by=['estimated_rate', 'loan_limit'], 
        ascending=[True, False]
    )
    
    # 결과 정리 (필요한 컬럼만 선택)
    result_cols = [
        'bank_name', 'product_name', 'estimated_rate', 'explanation',
        'loan_limit', 'loan_rate_min', 'loan_rate_max'
    ]
    
    return recommendations[result_cols].head(5)