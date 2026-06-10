[README.md](https://github.com/user-attachments/files/28783039/README.md)
# 🍽️ 푸드코트 음성 키오스크

사용자가 **음성 명령으로 메뉴를 주문**할 수 있는 AI 기반 푸드코트 키오스크 시스템입니다.  
한마루(한식), 스시로(일식), 만다린(중식) 3개 식당을 지원하며, 음성으로 메뉴 선택부터 결제까지 전 과정을 처리합니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 음성 주문 | Whisper STT로 음성 인식 후 메뉴 자동 장바구니 추가 |
| 터치 주문 | 기존 터치 방식 키오스크 병행 지원 |
| 음성 취소 | "취소해줘", "빼줘" 등 자연어로 메뉴 제거 및 수량 조절 |
| 식당 전환 | "만다린으로 옮겨줘" 등 음성으로 식당/카테고리 이동 |
| 결제 처리 | 카드 / 현금 / 카카오페이 선택 및 DB 저장 |
| 정산 관리 | 개점/마감, 매출 통계, 인기 메뉴 집계 |
| 인식 로그 | 음성 인식 원본·전처리 결과·성공 여부 CSV 기록 |
| AI 음성 응답 | Web Speech API 기반 TTS로 AI 응답 음성 출력 |

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | Python, FastAPI, uvicorn |
| 음성 인식 | Faster-Whisper (OpenAI Whisper 기반), ffmpeg |
| Database | MySQL, mysql-connector-python |
| Frontend | HTML5, CSS3, JavaScript (Vanilla) |
| 음성 출력 | Web Speech API (SpeechSynthesis) |
| Cloud | AWS EC2, AWS CloudFront |

---

## 데이터 모델

### orders

| 필드명 | 타입 | 설명 |
|--------|------|------|
| order_id | INT | 주문 고유 번호 (자동 증가) |
| order_number | INT | 영업일 내 주문 번호 |
| store | VARCHAR | 식당명 (한마루/스시로/만다린) |
| payment_method | VARCHAR | 결제 수단 (card/cash/qr) |
| total_price | INT | 주문 총액 |
| ordered_at | DATETIME | 주문 시각 |
| session_id | INT | 영업일 세션 ID |

### order_detail

| 필드명 | 타입 | 설명 |
|--------|------|------|
| detail_id | INT | 상세 고유 번호 |
| order_id | INT | 주문 ID (FK) |
| menu_name | VARCHAR | 메뉴명 |
| quantity | INT | 수량 |
| price | INT | 단가 |

### business_sessions

| 필드명 | 타입 | 설명 |
|--------|------|------|
| session_id | INT | 영업일 세션 ID |
| open_date | DATE | 영업일 날짜 |
| status | ENUM | open / closed |
| total_revenue | INT | 총 매출 |
| total_orders | INT | 총 주문 수 |

---

## 프로젝트 구조

```
kiosk_/
├── index.html                  # 메인 키오스크 화면
├── logs.html                   # 관리자 로그/정산 화면
├── css/
│   └── style.css               # 전체 스타일
├── js/
│   └── script.js               # 프론트엔드 로직 (음성인식, 장바구니, 결제)
├── images/
│   ├── hanmaru/                # 한마루 메뉴 이미지
│   ├── sushiro/                # 스시로 메뉴 이미지
│   └── mandarin/               # 만다린 메뉴 이미지
└── voice/
    ├── kiosk_server2.py        # FastAPI 백엔드 서버
    └── init_db.sql             # DB 초기화 SQL
```

---

## API 엔드포인트

| 기능 | 방식 | URL |
|------|------|-----|
| 서버 상태 확인 | GET | `/` |
| 음성 주문 처리 | POST | `/voice-order` |
| 텍스트 주문 처리 | POST | `/text-order` |
| 주문 저장 | POST | `/save-order` |
| 주문 목록 조회 | GET | `/orders` |
| 세션 조회 | GET | `/session/{session_id}` |
| 세션 초기화 | DELETE | `/session/{session_id}` |
| 개점 | POST | `/open-day` |
| 마감 | POST | `/close-day` |
| 현재 영업일 조회 | GET | `/current-day` |
| 정산 이력 | GET | `/settlement-history` |
| 인식 로그 조회 | GET | `/logs` |
| 인식 로그 초기화 | DELETE | `/logs` |

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
의도 감지 (주문 / 취소 / 결제 / 식당전환 / 메뉴문의)
    ↓
장바구니 처리 및 MySQL 저장
    ↓
JSON 응답 → Web Speech API TTS 음성 출력
```

---

## 텍스트 전처리 시스템

Whisper의 한국어 오인식 문제를 해결하기 위한 전처리 파이프라인입니다.

| 처리 단계 | 예시 |
|-----------|------|
| 필러 단어 제거 | "음 김치찌개 주세요" → "김치찌개 주세요" |
| 동의어 매핑 | "치소해줘" → "취소", "짜장" → "짜장면" |
| 한국어 수사 변환 | "세 개" → "3", "하나" → "1" |
| 주문 어미 제거 | "주세요", "줘요", "해줘" 제거 |

---

## 주요 오류 및 해결 사례

**Whisper 오인식 문제**
- 원인: "취소해줘"를 "치솔해줘", "치소해줘" 등으로 오인식
- 해결: SYNONYMS 딕셔너리 구축, raw_text/processed_text 양쪽에서 키워드 감지

**복수 메뉴 수량 파싱 오류**
- 원인: "제육볶음 3개 김치찌개 2개" 주문 시 첫 번째 숫자(3)가 모든 메뉴에 적용
- 해결: 각 메뉴명 이후 인접한 숫자를 개별 파싱하는 방식으로 수정

**장바구니 세션 이월 문제**
- 원인: "처음부터 다시" 클릭 시 JS 장바구니만 초기화, 서버 세션 유지
- 해결: `/text-order`에 "초기화" 전송으로 서버 세션 동시 초기화

**HTTPS / HTTP Mixed Content 문제**
- 원인: CloudFront(HTTPS) 페이지에서 EC2(HTTP) API 호출 시 브라우저 차단
- 해결: 마이크 접근을 위한 CloudFront HTTPS 유지, Chrome 환경에서 운영

---

## 실행 방법

### 백엔드 서버 (AWS EC2)

```bash
cd ~/kiosk
~/venv/bin/uvicorn kiosk_server2:app --host 0.0.0.0 --port 8001 &
```

### 프론트엔드

AWS CloudFront 또는 로컬에서 `index.html` 실행

---

## 배포 주소

🌐 **https://df7bqj7yb2nuf.cloudfront.net**
