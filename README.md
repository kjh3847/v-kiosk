# 🍽️ 푸드코트 음성 키오스크

음성 명령만으로 주문부터 결제까지 처리할 수 있는 AI 기반 푸드코트 키오스크 시스템입니다.  
고령자나 디지털 기기에 익숙하지 않은 사용자도 쉽게 사용할 수 있는 비접촉 주문 환경을 목표로 개발했습니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 음성 주문 | Faster-Whisper STT로 음성을 인식해 메뉴 자동 검색 및 장바구니 추가 |
| 터치 주문 | 기존 방식의 터치 키오스크 지원 |
| 취소 / 수량 조절 | "취소해줘", "빼줘" 등 자연어로 메뉴 제거 및 수량 수정 |
| 식당 / 카테고리 전환 | "만다린으로 줘", "스시로 초밥 보여줘" 등 음성으로 식당 및 카테고리 이동 |
| 결제 처리 | 카드 / 현금 / 카카오페이 선택 및 DB 저장 |
| 정산 관리 | 개점 / 마감, 매출 통계, 인기 메뉴 조회 |
| 음성 인식 로그 | 원본 음성 · 전처리 결과 · 인식 성공 여부 기록 |
| AI 음성 응답 | Web Speech API (SpeechSynthesis) 기반 TTS 출력 |

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| 백엔드 | Python, FastAPI, uvicorn |
| 음성 인식 | Faster-Whisper (OpenAI Whisper 기반), ffmpeg |
| 데이터베이스 | MySQL, mysql-connector-python |
| 프론트엔드 | HTML5, CSS3, JavaScript (Vanilla) |
| 음성 출력 | Web Speech API (SpeechSynthesis) |
| 클라우드 | AWS EC2, AWS CloudFront, AWS S3 |
| 기타 | REST API, CORS, FormData, MediaRecorder API |

---

## 프로젝트 구조

```
kiosk/
├── index.html                  # 메인 키오스크 화면
├── logs.html                   # 관리자 로그 / 정산 화면
├── css/
│   └── style.css               # 전체 스타일
├── js/
│   └── script.js               # 프론트엔드 로직 (음성 인식, 장바구니, 결제)
├── images/
│   ├── hanmaru/                # 한마루 메뉴 이미지
│   ├── sushiro/                # 스시로 메뉴 이미지
│   └── mandarin/               # 만다린 메뉴 이미지
└── voice/
    ├── kiosk_server2.py        # FastAPI 백엔드 서버
    └── init_db.sql             # DB 초기화 SQL
```

---

## 데이터 모델

### orders (주문)

| 필드명 | 타입 | 설명 |
|--------|------|------|
| order_id | INT | 주문 고유번호 (AUTO INCREMENT) |
| order_number | INT | 고객 주문 번호 |
| store | VARCHAR | 식당명 (한마루 / 스시로 / 만다린) |
| payment_method | VARCHAR | 결제 수단 (카드 / 현금 / QR) |
| total_price | INT | 총 주문 금액 |
| ordered_at | DATETIME | 주문 시각 |
| session_id | INT | 영업 세션 ID (FK) |

### order_detail (주문 상세)

| 필드명 | 타입 | 설명 |
|--------|------|------|
| detail_id | INT | 상세 고유번호 (AUTO INCREMENT) |
| order_id | INT | 주문 ID (FK) |
| menu_name | VARCHAR | 메뉴명 |
| quantity | INT | 수량 |
| price | INT | 단가 |

### business_sessions (영업 세션)

| 필드명 | 타입 | 설명 |
|--------|------|------|
| session_id | INT | 영업 세션 고유번호 |
| open_date | DATE | 개점 날짜 |
| status | ENUM | open / closed |
| total_revenue | INT | 총 매출 |
| total_orders | INT | 총 주문 수 |

---

## API 엔드포인트

| 기능 | 메서드 | URL |
|------|--------|-----|
| 서버 상태 확인 | GET | `/` |
| 음성 주문 처리 | POST | `/voice-order` |
| 텍스트 주문 처리 | POST | `/text-order` |
| 주문 저장 | POST | `/save-order` |
| 주문 목록 조회 | GET | `/orders` |
| 세션 조회 | GET | `/session/{session_id}` |
| 세션 삭제 | DELETE | `/session/{session_id}` |
| 개점 | POST | `/open-day` |
| 마감 | POST | `/close-day` |
| 현재 세션 조회 | GET | `/current-day` |
| 정산 이력 조회 | GET | `/settlement-history` |
| 음성 인식 로그 조회 | GET | `/logs` |
| 음성 인식 로그 삭제 | DELETE | `/logs` |

---

## 음성 처리 흐름

```
사용자 음성
    ↓
MediaRecorder (브라우저)
    ↓
FastAPI /voice-order (AWS EC2)
    ↓
ffmpeg → WAV 변환
    ↓
Faster-Whisper STT → 텍스트 변환
    ↓
TextPreprocessor (오인식 보정, 동의어 매핑, 수사 변환)
    ↓
의도 감지 (주문 / 취소 / 결제 / 식당 전환 / 메뉴 문의)
    ↓
장바구니 처리 및 MySQL 저장
    ↓
JSON 응답 → Web Speech API TTS 음성 출력
```

---

## 텍스트 전처리 시스템

Whisper의 한국어 오인식 문제를 보완하기 위한 전처리 파이프라인입니다.

| 처리 단계 | 예시 |
|-----------|------|
| 필러 단어 제거 | "음 김치찌개 주세요" → "김치찌개 주세요" |
| 동의어 매핑 | "치소해줘" → "취소", "짜장" → "짜장면" |
| 한국어 수사 변환 | "세 개" → "3", "하나" → "1" |
| 주문 어미 정규화 | "주세요", "줘요", "해줘" 제거 |

---

## 주요 문제 해결

**Whisper 오인식 문제**  
"취소해줘"를 "치솔해줘", "치소해줘" 등으로 오인식하는 문제를 SYNONYMS 딕셔너리와 raw_text / processed_text 이중 확인 방식으로 해결했습니다.

**복수 메뉴 수량 파싱 오류**  
"제육볶음 3개 김치찌개 2개" 주문 시 첫 번째 숫자가 모든 메뉴에 적용되던 버그를 각 메뉴명 뒤의 숫자를 개별 파싱하는 방식으로 수정했습니다.

**HTTPS / HTTP Mixed Content 문제**  
CloudFront(HTTPS) 환경에서 EC2(HTTP) API 호출 시 브라우저가 요청을 차단하는 문제를 Chrome 정책 범위 내에서 CloudFront HTTPS 서빙을 유지하는 방식으로 해결했습니다.

**세션 장바구니 이월 문제**  
"처음부터 다시" 클릭 시 프론트엔드만 초기화되고 서버 세션이 유지되던 문제를 `/text-order`에 "초기화" 텍스트를 전송해 서버 세션을 함께 초기화하는 방식으로 해결했습니다.

**식당 + 카테고리 동시 음성 전환**  
"스시로 초밥 보여줘"처럼 식당 이동과 카테고리 탐색을 한 문장으로 말할 경우 발화에서 식당명과 카테고리 키워드를 순차 추출해 식당 전환 → 카테고리 이동 순으로 처리하는 파이프라인을 구현했습니다.

---

## 실행 방법

### 백엔드 서버 (AWS EC2)

```bash
cd ~/kiosk
~/venv/bin/uvicorn kiosk_server2:app --host 0.0.0.0 --port 8001 &
```

### 프론트엔드

AWS CloudFront 또는 로컬 환경에서 `index.html` 실행

---

## 배포 주소

🌐 https://df7bqj7yb2nuf.cloudfront.net
