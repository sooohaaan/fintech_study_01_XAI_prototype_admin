# TrustFin Admin - XAI 신용 평가 및 데이터 관리 시스템 (Prototype)

**TrustFin Admin**은 **'설명 가능한 AI(XAI) 대출 추천 서비스'**인 TrustFin의 백엔드 운영 및 데이터 관리를 위한 대시보드입니다.
관리자가 데이터 수집 파이프라인을 제어하고, 신용 평가 알고리즘의 가중치를 직접 조정하며, 그 결과를 시뮬레이션하여 AI의 판단 기준을 투명하게 관리하는 것을 목표로 합니다.

## 🎯 프로젝트 목적
*   **Transparency (투명성)**: 블랙박스(Blackbox)로 여겨지던 신용 평가 로직을 관리자가 직접 설정하고 검증할 수 있도록 시각화합니다.
*   **Control (제어권)**: 외부 데이터 수집부터 최종 추천 로직까지 서비스의 전 과정을 중앙에서 제어합니다.
*   **Simulation (검증)**: 정책 변경이 실제 사용자에게 미칠 영향을 미리 시뮬레이션하여 안정적인 서비스를 제공합니다.

## 🛠 기술 스택 (Tech Stack)
*   **Language**: Python 3.12+
*   **Web Framework**: Flask (Server-side Rendering)
*   **Analytics Dashboard**: Streamlit (Flask 내 iframe으로 임베딩)
*   **Database**: MySQL (via SQLAlchemy & mysql-connector-python)
*   **Data Processing**: Pandas (데이터 정제 및 분석)
*   **Frontend**: Jinja2 Templates + Macros, HTML5, CSS3 (Custom Design System)
*   **Scheduling**: Python `schedule` library (데이터 자동 수집, 백그라운드 스레드)

## ✨ 주요 기능 (Key Features)

### 1. 대시보드 & 모니터링 (`/`)
*   **시스템 상태**: DB 연결, 수집기 활성 상태, 서버 리소스(메모리 등) 실시간 확인.
*   **데이터 요약**: 수집된 대출 상품, 경제 지표, 소득 통계 데이터의 총량 및 최근 수집 로그 시각화.
*   **로그 테이블**: 데이터 수집 성공/실패 이력 및 에러 메시지 확인.

### 2. 데이터 수집 관리 (`/collection-management`)
*   **수집기 제어**: 금융감독원(대출상품), 통계청(소득), 한국은행(경제지표) 등 소스별 수집기 ON/OFF 및 수동 실행.
*   **커스텀 수집기 추가/삭제**: UI에서 새 수집기 등록 및 기존 수집기 삭제.
*   **API 설정**: 각 기관별 API Key 및 수집 기간/주기(매일, 매월 등)를 UI에서 직접 설정 및 검증.
*   **상태 추적**: 최초/최근 실행 일시, 누적 수집 건수 등 상세 상태 모니터링.

### 3. 정책 및 알고리즘 설정
*   **신용평가 가중치 (`/credit-weights`)**: 소득, 고용 안정성, 자산 규모 등 핵심 평가 요소의 가중치를 슬라이더로 미세 조정.
*   **추천 알고리즘 (`/recommend-settings`)**: 최대 추천 개수, 정렬 우선순위(금리순/한도순), 금리 민감도 등 추천 로직 파라미터 설정.
*   **XAI 임계값**: 사용자에게 "소득 수준 우수", "고용 안정적" 등의 설명이 표시되는 기준점 설정.

### 4. 서비스 운영 관리
*   **회원 관리 (`/members`)**: 전체 회원 목록 조회, 상세 정보(포인트, 미션 이력) 확인, 회원 추가, 상태 변경(활성/정지/탈퇴), 삭제.
*   **유저 스탯 관리 (`/user-stats`)**: 미션 자동 달성 판단 기준이 되는 유저별 금융 데이터(신용점수, DSR, 카드사용률, 연체 여부 등) 조회 및 수정.
*   **상품 관리 (`/products`)**: 수집된 대출 상품의 서비스 노출 여부(Visible/Hidden) 제어.
*   **미션 관리 (`/missions`)**: AI가 생성한 유저별 금융 미션 현황 및 상세 조회. 미션 제목·설명·유형·상태·보상·마감일 등 인라인 수정 및 일괄 처리. 미션 삭제 이력 로그 조회(`/missions/deletion-logs`).
*   **포인트 관리 (`/points`)**: 유저 포인트 현황 조회 및 관리자 권한으로 포인트 수동 지급/차감.
*   **포인트 상품 (`/point-products`)**: 포인트로 교환 가능한 상품(쿠폰 등) 등록·수정·활성화/비활성화, 재고 관리. 구매 내역 조회(`/point-products/purchases`).

### 5. 시뮬레이터 & 데이터 조회
*   **대출 추천 시뮬레이터 (`/simulator`)**: 가상의 유저 프로필(소득, 자산, 직업 등)을 입력하여 현재 설정된 가중치로 어떤 상품이 추천되는지 즉시 테스트.
*   **Raw Data Viewer (`/data/<table_name>`)**: 수집된 원본 데이터를 테이블 형태로 조회 및 검색.
*   **수집 파일 뷰어 (`/data-files`)**: 커스텀 수집기가 저장한 JSON 파일 목록 및 내용 조회, 파일 삭제.

### 6. 시스템 & 분석
*   **시스템 정보 (`/system-info`)**: 서버 OS·Python·Flask 버전, 메모리 사용량, DB 연결 상태 및 테이블 목록 확인.
*   **애널리틱스 (`/analytics`)**: Streamlit 대시보드(`admin_app.py`)를 iframe으로 임베딩하여 심층 데이터 분석 제공.

## 🎨 디자인 시스템 (Design System)
TrustFin 브랜드 아이덴티티를 반영한 커스텀 CSS를 적용했습니다.
*   **Colors**:
    *   `Visionary Black (#000000)` & `Pure White (#FFFFFF)`: 전문성과 명확성.
    *   `Insight Gold (#E5AA70)`: 통찰과 이로움을 상징하는 포인트 컬러.
    *   `Evidence Grey (#8E8E8E)` & `Slate Blue-Grey (#4A5568)`: 논리적이고 차분한 보조 컬러.
*   **UI Components**:
    *   **Narrative Grid**: 배경의 미세한 격자 패턴으로 시스템적 구조 강조.
    *   **Guide Card (Jinja2 매크로)**: `macros.html`에 정의된 `guide_card` 매크로를 통해 각 페이지 상단에 기능의 설계 의도와 XAI 관점의 설명을 표준화된 형태로 제공.
    *   **Filter Form (Jinja2 매크로)**: `filter_form` 매크로로 목록 페이지의 검색·필터 UI를 일관되게 렌더링.
    *   **Cache Busting**: 정적 파일 URL에 `mtime` 기반 버전 파라미터를 자동 추가하여 캐시 문제를 방지.
    *   **Dark Mode**: 시스템 설정에 따른 다크 모드 지원.

## 🚀 설치 및 실행 (Installation & Run)

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 데이터베이스 설정
프로젝트 루트에 `secrets.toml` 파일을 생성하거나 환경 변수를 설정하여 DB 연결 정보를 입력합니다.

**secrets.toml 예시:**
```toml
[mysql]
host = "localhost"
port = 3306
database = "fintech_db"
user = "root"
password = "your_password"
```

**환경 변수로 설정하는 경우:**
```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=your_password
export DB_DATABASE=fintech_db
```

### 3. 보안 환경변수 설정 (필수)
아래 환경변수를 반드시 설정해야 합니다. 미설정 시 서버 로그에 경고가 출력되며, 프로덕션 환경에서는 보안 위협이 됩니다.

```bash
# Flask 세션 서명 키 (충분히 길고 무작위한 값으로 설정)
export FLASK_SECRET_KEY="your-random-secret-key"

# 관리자 계정
export ADMIN_USER="your_admin_id"
export ADMIN_PASSWORD="your_strong_password"

# 개발 환경에서만 활성화 (프로덕션에서는 설정하지 않음)
# export FLASK_DEBUG=true
```

### 3. 서버 실행

**실행 스크립트 사용 (권장):**
```bash
bash run.sh
```
스크립트 실행 후 모드를 선택합니다.
*   `1`: Flask Admin Dashboard 단독 실행 (Port 5001)
*   `2`: Streamlit Data App 단독 실행 (Port 8501)

**직접 실행:**
```bash
# Flask 대시보드 (Streamlit을 서브프로세스로 자동 실행 포함)
python admin_flask.py
```
*   브라우저에서 `http://localhost:5001`로 접속합니다.
*   관리자 계정은 반드시 환경변수로 설정하세요 (미설정 시 서버 로그에 경고 출력).
*   Flask 실행 시 `admin_app.py`(Streamlit)가 Port 8501에 서브프로세스로 자동 시작됩니다.

## 🗂️ 폴더 구조
```
📦 fintech_study_01_XAI_prototype_admin
 ┣ 📂 static                    # 정적 파일
 ┃ ┣ 📜 style.css               # 메인 커스텀 CSS (디자인 시스템)
 ┃ ┗ 📜 login.css               # 로그인 페이지 전용 CSS
 ┣ 📂 templates                 # Jinja2 HTML 템플릿
 ┃ ┣ 📂 components              # 재사용 컴포넌트
 ┃ ┃ ┗ 📜 log_table.html        # 수집 로그 테이블 컴포넌트
 ┃ ┣ 📜 macros.html             # guide_card, filter_form 등 Jinja2 매크로 정의
 ┃ ┣ 📜 base.html               # 공통 레이아웃 (네비게이션, 헤더)
 ┃ ┣ 📜 login.html              # 로그인 페이지
 ┃ ┣ 📜 index.html              # 메인 대시보드
 ┃ ┣ 📜 collection_management.html
 ┃ ┣ 📜 credit_weights.html
 ┃ ┣ 📜 recommend_settings.html
 ┃ ┣ 📜 products.html
 ┃ ┣ 📜 members.html / member_detail.html / member_form.html
 ┃ ┣ 📜 missions.html / mission_detail.html / mission_deletion_logs.html
 ┃ ┣ 📜 points.html / point_detail.html
 ┃ ┣ 📜 point_products.html / point_product_form.html / point_purchases.html
 ┃ ┣ 📜 user_stats.html / user_stats_form.html
 ┃ ┣ 📜 simulator.html
 ┃ ┣ 📜 data_viewer.html        # DB 테이블 Raw Data 조회
 ┃ ┣ 📜 data_file_viewer.html   # JSON 파일 뷰어
 ┃ ┣ 📜 system_info.html        # 시스템/DB 상태 정보
 ┃ ┗ 📜 streamlit_embed.html    # Streamlit iframe 임베딩
 ┣ 📜 admin_flask.py            # Flask 메인 앱 (라우팅, 인증, 스케줄러)
 ┣ 📜 admin_app.py              # Streamlit 분석 대시보드
 ┣ 📜 collector.py              # DataCollector 클래스 (수집 로직 및 스케줄링)
 ┣ 📜 recommendation_logic.py   # 신용 평가 및 대출 추천 알고리즘 코어
 ┣ 📜 requirements.txt          # Python 의존성 목록
 ┣ 📜 run.sh                    # Flask / Streamlit 실행 선택 스크립트
 ┣ 📜 secrets.toml              # DB 연결 정보 (git에서 제외 권장)
 ┗ 📜 README.md                 # 프로젝트 설명서
```
