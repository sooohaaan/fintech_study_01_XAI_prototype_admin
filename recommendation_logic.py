import pandas as pd
from sqlalchemy import create_engine  # noqa: F401 - 향후 standalone 실행 시 사용

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

    # F4: 서비스 노출 상품만 필터링
    if 'is_visible' in products_df.columns:
        products_df = products_df[products_df['is_visible'] == 1].copy()

    if products_df.empty:
        return pd.DataFrame()

    # 2. DB에서 설정 로드 (설정이 없으면 기본값 사용)
    try:
        cfg_df = pd.read_sql("SELECT * FROM service_config", engine)
        configs = dict(zip(cfg_df['config_key'], cfg_df['config_value']))
    except Exception:
        configs = {}

    # F2: 핵심 가중치
    w_income = float(configs.get('WEIGHT_INCOME', 0.5))
    w_job = float(configs.get('WEIGHT_JOB_STABILITY', 0.3))
    w_asset = float(configs.get('WEIGHT_ESTATE_ASSET', 0.2))

    # F2: 정규화 기준 (하드코딩 제거 → 설정 기반)
    norm_income_ceiling = float(configs.get('NORM_INCOME_CEILING', 100000000))
    norm_asset_ceiling = float(configs.get('NORM_ASSET_CEILING', 500000000))

    # F2: XAI 설명 임계값 (하드코딩 제거 → 설정 기반)
    xai_threshold_income = float(configs.get('XAI_THRESHOLD_INCOME', 0.15))
    xai_threshold_job = float(configs.get('XAI_THRESHOLD_JOB', 0.1))
    xai_threshold_asset = float(configs.get('XAI_THRESHOLD_ASSET', 0.05))

    # F3: 추천 파라미터 (하드코딩 제거 → 설정 기반)
    max_recommendations = int(configs.get('RECOMMEND_MAX_COUNT', 5))
    sort_priority = configs.get('RECOMMEND_SORT_PRIORITY', 'rate')
    fallback_mode = configs.get('RECOMMEND_FALLBACK_MODE', 'show_all')
    rate_sensitivity = float(configs.get('RECOMMEND_RATE_SPREAD_SENSITIVITY', 1.0))

    # 3. 사용자 입력값 및 점수화 (Scoring)
    income = float(user_profile.get('annual_income', 0))
    desired_amt = float(user_profile.get('desired_amount', 0))
    job_score = float(user_profile.get('job_score', 0.5))
    asset_amt = float(user_profile.get('asset_amount', 0))

    # 4. 1차 필터링: 대출 한도 체크
    filtered_df = products_df[products_df['loan_limit'] >= desired_amt].copy()

    # F3: Fallback 모드 적용
    if filtered_df.empty:
        if fallback_mode == 'show_all':
            filtered_df = products_df.copy()
        else:
            return pd.DataFrame()

    # 5. 종합 신용 점수 계산 (0.0 ~ 1.0)
    score_income = min(income / norm_income_ceiling, 1.0) if norm_income_ceiling > 0 else 0.0
    score_asset = min(asset_amt / norm_asset_ceiling, 1.0) if norm_asset_ceiling > 0 else 0.0

    # 가중 평균 계산
    final_score = (score_income * w_income) + (job_score * w_job) + (score_asset * w_asset)
    final_score = max(0.0, min(final_score, 1.0))

    # 6. 개인화된 예상 금리 및 설명 생성 (XAI)
    def calculate_details(row, score):
        min_r = row['loan_rate_min']
        max_r = row['loan_rate_max']

        # F3: rate_sensitivity 적용 - 민감도가 높을수록 점수 영향 증가
        spread = (max_r - min_r) * score * rate_sensitivity
        spread = min(spread, max_r - min_r)  # 최저금리 이하로 내려가지 않도록 보정
        estimated = max_r - spread

        # F2: XAI 추천 사유 생성 (설정 가능한 임계값 적용)
        reasons = []
        if score_income * w_income >= xai_threshold_income:
            reasons.append("소득수준 우수")
        if job_score * w_job >= xai_threshold_job:
            reasons.append("고용 안정적")
        if score_asset * w_asset >= xai_threshold_asset:
            reasons.append("자산 보유")

        if not reasons:
            reasons.append("기본 심사 통과")

        explanation = f"종합점수 {score:.2f}점 ({', '.join(reasons)})"
        return pd.Series([round(estimated, 2), explanation])

    filtered_df[['estimated_rate', 'explanation']] = filtered_df.apply(
        lambda row: calculate_details(row, final_score), axis=1
    )

    # 7. F3: 정렬 우선순위 적용
    if sort_priority == 'limit':
        recommendations = filtered_df.sort_values(
            by=['loan_limit', 'estimated_rate'], ascending=[False, True]
        )
    else:  # 'rate' (기본값)
        recommendations = filtered_df.sort_values(
            by=['estimated_rate', 'loan_limit'], ascending=[True, False]
        )

    # 결과 정리 (필요한 컬럼만 선택)
    result_cols = [
        'bank_name', 'product_name', 'estimated_rate', 'explanation',
        'loan_limit', 'loan_rate_min', 'loan_rate_max'
    ]

    # F3: 최대 추천 수 적용
    return recommendations[result_cols].head(max_recommendations)
