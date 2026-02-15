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
*   **Database**: MySQL (via SQLAlchemy & mysql-connector-python)
*   **Data Processing**: Pandas (데이터 정제 및 분석)
*   **Frontend**: Jinja2 Templates, HTML5, CSS3 (Custom Design System)
*   **Scheduling**: Python `schedule` library (데이터 자동 수집)

## ✨ 주요 기능 (Key Features)

### 1. 대시보드 & 모니터링 (`/`)
*   **시스템 상태**: DB 연결, 수집기 활성 상태, 서버 리소스(메모리 등) 실시간 확인.
*   **데이터 요약**: 수집된 대출 상품, 경제 지표, 소득 통계 데이터의 총량 및 최근 수집 로그 시각화.
*   **로그 테이블**: 데이터 수집 성공/실패 이력 및 에러 메시지 확인.

### 2. 데이터 수집 관리 (`/collection-management`)
*   **수집기 제어**: 금융감독원(대출상품), 통계청(소득), 한국은행(경제지표) 등 소스별 수집기 ON/OFF 및 수동 실행(새로고침).
*   **API 설정**: 각 기관별 API Key 및 수집 기간/주기(매일, 매월 등)를 UI에서 직접 설정.
*   **상태 추적**: 최초/최근 실행 일시, 누적 수집 건수 등 상세 상태 모니터링.

### 3. 정책 및 알고리즘 설정
*   **신용평가 가중치 (`/credit-weights`)**: 소득, 고용 안정성, 자산 규모 등 핵심 평가 요소의 가중치를 슬라이더로 미세 조정.
*   **추천 알고리즘 (`/recommend-settings`)**: 최대 추천 개수, 정렬 우선순위(금리순/한도순), 금리 민감도 등 추천 로직 파라미터 설정.
*   **XAI 임계값**: 사용자에게 "소득 수준 우수", "고용 안정적" 등의 설명이 표시되는 기준점 설정.

### 4. 서비스 운영 관리
*   **회원 관리 (`/members`)**: 전체 회원 목록 조회, 상세 정보(포인트, 미션 이력) 확인, 상태 변경(활성/정지/탈퇴).
*   **상품 관리 (`/products`)**: 수집된 대출 상품의 서비스 노출 여부(Visible/Hidden) 제어.
*   **미션 관리 (`/missions`)**: AI가 생성한 유저별 금융 미션(신용점수 올리기 등) 현황 및 성공률 모니터링.
*   **포인트 관리 (`/points`)**: 유저 포인트 현황 조회 및 관리자 권한으로 포인트 수동 지급/차감.
*   **포인트 상품 (`/point-products`)**: 포인트로 교환 가능한 상품(쿠폰 등) 등록 및 재고 관리.

### 5. 시뮬레이터 & 데이터 조회
*   **대출 추천 시뮬레이터 (`/simulator`)**: 가상의 유저 프로필(소득, 자산, 직업 등)을 입력하여 현재 설정된 가중치로 어떤 상품이 추천되는지 즉시 테스트.
*   **Raw Data Viewer (`/data/*`)**: 수집된 원본 데이터를 테이블 형태로 조회 및 검색.

## 🎨 디자인 시스템 (Design System)
TrustFin 브랜드 아이덴티티를 반영한 커스텀 CSS를 적용했습니다.
*   **Colors**:
    *   `Visionary Black (#000000)` & `Pure White (#FFFFFF)`: 전문성과 명확성.
    *   `Insight Gold (#E5AA70)`: 통찰과 이로움을 상징하는 포인트 컬러.
    *   `Evidence Grey (#8E8E8E)` & `Slate Blue-Grey (#4A5568)`: 논리적이고 차분한 보조 컬러.
*   **UI Components**:
    *   **Narrative Grid**: 배경의 미세한 격자 패턴으로 시스템적 구조 강조.
    *   **Guide Card**: 각 페이지 상단에 기능의 설계 의도와 XAI 관점의 설명을 제공하는 가이드 카드 배치.
    *   **Dark Mode**: 시스템 설정에 따른 다크 모드 지원.

## 🚀 설치 및 실행 (Installation & Run)

### 1. 환경 설정
Python 3.12 이상 환경에서 필요한 라이브러리를 설치합니다.
```bash
pip install flask pandas sqlalchemy mysql-connector-python requests psutil schedule toml
```

### 2. 데이터베이스 설정
프로젝트 루트 또는 `.streamlit` 폴더에 `secrets.toml` 파일을 생성하거나 환경 변수를 설정하여 DB 연결 정보를 입력합니다.

**secrets.toml 예시:**
```toml
[mysql]
host = "localhost"
port = 3306
database = "fintech_db"
user = "root"
password = "your_password"
```

### 3. 서버 실행
```bash
python admin_flask.py
```
*   서버가 시작되면 브라우저에서 `http://localhost:5001`로 접속합니다.
*   초기 관리자 계정: `admin` / `admin1234` (환경변수로 변경 가능)

## 🗂️ 폴더 구조
```
📦 fintech_study_01_XAI_prototype_admin
 ┣ 📂 static              # CSS, JS, 이미지 등 정적 파일
 ┣ 📂 templates           # Jinja2 HTML 템플릿
 ┃ ┣ 📂 components        # 재사용 가능한 컴포넌트 (log_table 등)
 ┃ ┗ 📜 *.html            # 각 페이지별 템플릿 파일
 ┣ 📜 admin_flask.py      # Flask 메인 애플리케이션 및 라우팅
 ┣ 📜 collector.py        # 데이터 수집기 및 스케줄러 로직
 ┣ 📜 recommendation_logic.py # 신용 평가 및 추천 알고리즘 코어
 ┗ 📜 README.md           # 프로젝트 설명서
```
