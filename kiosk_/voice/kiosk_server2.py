# ============================================================
#  푸드코트 키오스크 백엔드 서버 v2
#  담당자: 오경택
#
#  하는 일:
#    1. 음성 → 텍스트 변환 (Whisper STT)
#    2. 텍스트에서 메뉴/의도 파악 (키워드 매칭)
#    3. 주문 내역 DB 저장
#    4. 개점/마감 정산 관리
#
#  실행:
#    cd ~/kiosk && ~/venv/bin/uvicorn kiosk_server2:app --host 0.0.0.0 --port 8001 &
# ============================================================

import re, json, csv, os, tempfile, subprocess
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from faster_whisper import WhisperModel
import mysql.connector


# ── DB 연결 ──
def get_db():
    return mysql.connector.connect(
        host="localhost", user="root", password="", database="kiosk_db"
    )


app = FastAPI(title="푸드코트 키오스크 서버 v2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ============================================================
# 메뉴 데이터
# ============================================================

RESTAURANT_MENU = {
    "한마루": {
        "main":  ["김치찌개", "된장찌개", "불고기", "제육볶음", "비빔밥", "갈비탕"],
        "side":  ["계란말이", "김치전", "잡채", "공기밥"],
        "drink": ["보리차", "콜라", "참이슬", "처음처럼"],
    },
    "스시로": {
        "main":  ["연어초밥", "광어초밥", "참치초밥", "우동", "돈카츠", "회덮밥"],
        "side":  ["새우튀김", "타코야키", "미소시루", "샐러드"],
        "drink": ["녹차", "콜라", "환타", "쥰마이사케"],
    },
    "만다린": {
        "main":  ["짜장면", "짬뽕", "탕수육", "볶음밥", "마파두부", "깐풍기"],
        "side":  ["군만두", "춘권", "양장피", "짜사이"],
        "drink": ["콜라", "사이다", "우롱차", "연태고량주"],
    },
}

# 결제 수단
PAYMENT_KEYWORDS = {
    "card": ["카드", "신용카드", "체크카드"],
    "cash": ["현금", "지폐"],
    "qr":   ["카카오", "카카오페이", "큐알", "QR", "페이"],
}

# ============================================================
# 텍스트 전처리
# ============================================================
class TextPreprocessor:
    FILLER = ["음", "어", "그", "저", "뭐", "아", "이제", "그냥", "좀", "혹시"]
    UNITS   = ["개", "그릇", "병", "잔", "인분"]
    KOREAN_NUMBERS = {
        "하나": "1", "한": "1", "둘": "2", "두": "2",
        "셋": "3", "세": "3", "넷": "4", "네": "4",
        "다섯": "5", "여섯": "6", "일곱": "7",
        "여덟": "8", "아홉": "9", "열": "10",
    }
    SYNONYMS = {
        # 취소 오인식
        "치소": "취소", "치솔": "취소", "취수": "취소", "취조": "취소",
        "치소해": "취소", "치솔해": "취소", "취수해": "취소",
        "취사": "취소", "츄소": "취소", "취쇼": "취소", "취사해": "취소",
        "취켜": "취소", "취서": "취소", "취세": "취소",
        # 공통
        "소주": "참이슬", "공깃밥": "공기밥",
        # 한마루
        "김치찌게": "김치찌개", "김치찌켸": "김치찌개", "김치지개": "김치찌개",
        "김치찌깨": "김치찌개", "김치찌계": "김치찌개",
        "된장찌게": "된장찌개", "된장지개": "된장찌개",
        "뿔고기": "불고기", "부고기": "불고기", "풀고기": "불고기",
        "제육": "제육볶음", "재육볶음": "제육볶음", "재육": "제육볶음",
        "제육복음": "제육볶음", "제육보끔": "제육볶음",
        "비빔": "비빔밥", "비빔바": "비빔밥", "비빔빱": "비빔밥",
        "갈비": "갈비탕", "갈빗탕": "갈비탕",
        "계란말": "계란말이", "게란말이": "계란말이",
        "잡체": "잡채",
        "공기": "공기밥", "공기바": "공기밥",
        "보리": "보리차",
        # 스시로
        "연어": "연어초밥", "연어초": "연어초밥",
        "광어": "광어초밥", "광어초": "광어초밥",
        "참치": "참치초밥", "참치초": "참치초밥",
        "돈까스": "돈카츠", "돈가스": "돈카츠", "돈까쓰": "돈카츠", "돈카스": "돈카츠",
        "회덥밥": "회덮밥", "회더밥": "회덮밥",
        "새우": "새우튀김", "새우튀": "새우튀김",
        "타코": "타코야키", "타코야끼": "타코야키",
        "미소": "미소시루", "미소국": "미소시루",
        "샐러": "샐러드",
        "준마이사케": "쥰마이사케", "준마이": "쥰마이사케",
        # 만다린
        "짜장": "짜장면", "자장면": "짜장면", "자장": "짜장면",
        "짬봉": "짬뽕", "짬퐁": "짬뽕", "잠뽕": "짬뽕",
        "탕수": "탕수육", "탕슈육": "탕수육",
        "볶음바": "볶음밥", "복음밥": "볶음밥", "보끔밥": "볶음밥",
        "마파": "마파두부", "마바두부": "마파두부",
        "깐풍": "깐풍기", "간풍기": "깐풍기",
        "군만": "군만두", "군만뚜": "군만두",
        "춘꿘": "춘권",
        "양장": "양장피",
        "짜사": "짜사이",
        "연태": "연태고량주", "고량주": "연태고량주",
        "녹자": "녹차", "녹챠": "녹차",
        "환타이": "환타", "화타": "환타",
        "사이다이": "사이다", "싸이다": "사이다",
        "우롱": "우롱차", "우룽차": "우롱차",
        "우동이": "우동", "우덩": "우동",
    }

    @staticmethod
    def process(raw: str) -> str:
        text = raw.strip()
        text = re.sub(r'[^\w\s]', '', text)
        for w in TextPreprocessor.FILLER:
            text = re.sub(rf'\b{w}\b', '', text)
        for k, v in TextPreprocessor.SYNONYMS.items():
            text = text.replace(k, v)
        for kor, num in TextPreprocessor.KOREAN_NUMBERS.items():
            if len(kor) == 1:
                for unit in TextPreprocessor.UNITS:
                    text = text.replace(f"{kor} {unit}", f"{num} {unit}")
                    text = text.replace(f"{kor}{unit}", f"{num}{unit}")
            else:
                text = text.replace(kor, num)
        text = re.sub(r'(\d+)\s*(개|그릇|병|잔|인분)', r'\1', text)
        text = re.sub(r'(주세요|줘요|줘|부탁해|할게요|해줘|해주세요)', '', text)
        return re.sub(r'\s+', ' ', text).strip()


# ============================================================
# STT
# ============================================================
print("Whisper 로딩 중...")
whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
print("Whisper 로딩 완료!")


class STTModule:
    @staticmethod
    def transcribe(audio_bytes: bytes) -> str:
        # 형식 모름 → .bin으로 저장 후 ffmpeg이 자동 감지해서 wav 변환
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
            tmp.write(audio_bytes)
            raw_path = tmp.name

        wav_path = raw_path + ".wav"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", raw_path, wav_path],
                capture_output=True
            )
            if not os.path.exists(wav_path) or os.path.getsize(wav_path) == 0:
                return ""
            wav_size = os.path.getsize(wav_path)
            print(f"[WAV크기] {wav_size} bytes")
            segments, info = whisper_model.transcribe(wav_path, language="ko", beam_size=1, vad_filter=True)
            text = "".join([seg.text for seg in segments])
            print(f"[STT결과] '{text}'")
            return text.strip()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"STT 오류: {e}")
        finally:
            if os.path.exists(raw_path): os.unlink(raw_path)
            if os.path.exists(wav_path): os.unlink(wav_path)


# ============================================================
# 의도 감지 키워드
# ============================================================

CANCEL_ALL_KEYWORDS = ["다 취소", "전부 취소", "모두 취소", "처음부터", "다시 해", "전체 취소",
                       "다 빼", "전부 빼", "초기화", "비워줘", "다 지워"]

CANCEL_KEYWORDS     = ["취소해줘", "빼줘", "빼주세요", "없애줘", "지워줘", "삭제해줘",
                       "취소해주세요", "빼줄래요", "없애주세요", "지워주세요",
                       "치소해줘", "치솔해줘", "취소해", "취소줘", "취소해줄래", "취소"]

CHECKOUT_KEYWORDS   = ["결제", "주문할게", "계산해줘", "계산해", "결제할게", "결제해",
                       "주문완료", "그걸로 할게", "이걸로 할게"]

CART_QUERY_KEYWORDS = ["뭐 담았", "장바구니 보여", "뭐 시켰", "뭐 골랐", "지금 뭐",
                       "현재 주문", "담은 거", "담긴 거", "장바구니 확인"]

MENU_QUERY_KEYWORDS = ["메뉴 뭐 있", "뭐가 있", "어떤 메뉴", "메뉴 알려", "메뉴 보여",
                       "뭐 팔아", "메뉴 좀", "메뉴 추천"]

HELP_KEYWORDS       = ["어떻게 주문", "어떻게 해", "도움", "모르겠어", "사용법",
                       "주문 방법", "어떻게 시켜"]

RESTAURANT_KEYWORDS = {
    "한마루": ["한마루", "한식", "한국식", "한국 음식"],
    "스시로": ["스시로", "일식", "일본식", "초밥", "스시"],
    "만다린": ["만다린", "만다리", "만나린", "중식", "중국식"],
}

SWITCH_KEYWORDS = ["옮겨줘", "옮겨", "넘어가", "이동해줘", "이동할게", "바꿔줘", "변경해줘", "가줘", "가고싶어", "가볼게"]


def detect_payment(text: str) -> str:
    for method, kws in PAYMENT_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return method
    return ""

def detect_restaurant_in_text(text: str) -> str:
    for rest, kws in RESTAURANT_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return rest
    return ""

def find_menus_in_text(text: str) -> list:
    """텍스트에서 메뉴 이름과 수량을 파싱 - 각 메뉴 뒤의 숫자를 개별 적용"""
    found = []
    for rest, cats in RESTAURANT_MENU.items():
        for cat, menus in cats.items():
            for menu in menus:
                if menu in text and menu not in [f["menu"] for f in found]:
                    idx = text.index(menu) + len(menu)
                    # 메뉴명 바로 뒤에 오는 숫자 찾기 (10자 이내)
                    nearby = text[idx:idx+10]
                    qty_match = re.search(r'(\d+)', nearby)
                    if qty_match:
                        qty = int(qty_match.group(1))
                    else:
                        # 메뉴명 앞에서 찾기
                        before = text[max(0, idx-len(menu)-5):idx-len(menu)]
                        qty_match = re.search(r'(\d+)', before)
                        qty = int(qty_match.group(1)) if qty_match else 1
                    found.append({"menu": menu, "qty": qty, "restaurant": rest})
    return found


# ============================================================
# 세션 & 장바구니
# ============================================================
STEP_MAIN    = "main"
STEP_PAYMENT = "payment"

sessions: dict = {}

def get_session(session_id: str) -> dict:
    if session_id not in sessions:
        sessions[session_id] = {"step": STEP_MAIN, "cart": []}
    return sessions[session_id]

def reset_session(session_id: str):
    sessions[session_id] = {"step": STEP_MAIN, "cart": []}

def add_to_cart(session: dict, items: list):
    for new in items:
        existing = next((i for i in session["cart"] if i["menu"] == new["menu"]), None)
        if existing:
            existing["qty"] += new["qty"]
        else:
            session["cart"].append({"menu": new["menu"], "qty": new["qty"]})

def remove_from_cart(session: dict, text: str) -> tuple:
    """(제거된 메뉴명 목록, 언급됐지만 없는 메뉴명) 반환"""
    qty_match = re.search(r'(\d+)', text)
    qty_to_remove = int(qty_match.group(1)) if qty_match else None

    # 텍스트에서 언급된 메뉴 전부 찾기 (여러 개 동시 취소)
    mentioned = []
    for rest, cats in RESTAURANT_MENU.items():
        for cat, menus in cats.items():
            for menu in menus:
                if menu in text and menu not in mentioned:
                    mentioned.append(menu)

    if mentioned:
        removed = []
        not_found = []
        for menu in mentioned:
            for item in session["cart"]:
                if item["menu"] == menu:
                    if qty_to_remove and item["qty"] > qty_to_remove:
                        item["qty"] -= qty_to_remove  # 수량만 줄이기
                        removed.append(f"{menu} {qty_to_remove}개")
                    else:
                        session["cart"].remove(item)  # 전체 제거
                        removed.append(menu)
                    break
            else:
                not_found.append(menu)
        if removed:
            return (", ".join(removed), "")
        return ("", ", ".join(not_found))

    # 메뉴 언급 없이 "빼줘" → 마지막 항목 제거
    if session["cart"]:
        removed = session["cart"].pop()
        return (removed["menu"], "")
    return ("", "")

def cart_summary(session: dict) -> str:
    if not session["cart"]:
        return "장바구니가 비어있습니다"
    return ", ".join([f"{i['menu']} {i['qty']}개" for i in session["cart"]])

def get_menu_list_message(restaurant: str = "") -> str:
    """메뉴 목록 안내 메시지"""
    if restaurant and restaurant in RESTAURANT_MENU:
        cats = RESTAURANT_MENU[restaurant]
        msg = f"{restaurant} 메뉴: "
        msg += f"메인 {', '.join(cats['main'][:3])} 등 / "
        msg += f"사이드 {', '.join(cats['side'][:2])} 등 / "
        msg += f"음료 {', '.join(cats['drink'][:2])} 등"
        return msg
    else:
        parts = []
        for rest, cats in RESTAURANT_MENU.items():
            parts.append(f"{rest}: {', '.join(cats['main'][:2])} 등")
        return "각 식당 메뉴입니다. " + " / ".join(parts) + " — 화면에서 전체 메뉴를 확인하세요."


# ============================================================
# DB 초기화
# ============================================================
def init_db():
    db = get_db(); cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS business_sessions (
            session_id INT NOT NULL AUTO_INCREMENT,
            open_date DATE NOT NULL,
            opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            closed_at DATETIME DEFAULT NULL,
            status ENUM('open','closed') DEFAULT 'open',
            total_revenue INT DEFAULT 0,
            total_orders INT DEFAULT 0,
            PRIMARY KEY (session_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INT NOT NULL AUTO_INCREMENT,
            order_number INT NOT NULL,
            store VARCHAR(50) NOT NULL,
            payment_method VARCHAR(20) NOT NULL,
            total_price INT NOT NULL,
            ordered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_id INT DEFAULT NULL,
            PRIMARY KEY (order_id),
            FOREIGN KEY (session_id) REFERENCES business_sessions(session_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_detail (
            detail_id INT NOT NULL AUTO_INCREMENT,
            order_id INT NOT NULL,
            menu_id VARCHAR(100) NOT NULL,
            menu_name VARCHAR(100) NOT NULL,
            quantity INT NOT NULL,
            price INT NOT NULL,
            PRIMARY KEY (detail_id),
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
    db.commit(); cursor.close(); db.close()
    print("DB 초기화 완료!")

init_db()


# ============================================================
# 로그
# ============================================================
LOG_FILE = os.path.join(os.path.dirname(__file__), "recognition_log.csv")

def save_log(raw_text, processed_text, understood, ai_message):
    os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["시간", "원본", "전처리", "인식성공", "AI응답"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            raw_text, processed_text,
            "성공" if understood else "실패",
            ai_message[:60],
        ])


# ============================================================
# 핵심 처리 로직
# ============================================================
class VoiceResponse(BaseModel):
    raw_text: str
    processed_text: str
    ai_message: str
    cart: list
    step: str
    understood: bool = False
    confirmed: bool = False
    payment_method: str = ""
    switch_restaurant: str = ""


async def process_voice(raw_text: str, session_id: str) -> VoiceResponse:
    session   = get_session(session_id)
    processed = TextPreprocessor.process(raw_text)
    step      = session["step"]

    def resp(msg, understood=True, confirmed=False, payment="", switch_restaurant=""):
        return VoiceResponse(
            raw_text=raw_text, processed_text=processed,
            ai_message=msg, cart=session["cart"],
            step=session["step"], understood=understood,
            confirmed=confirmed, payment_method=payment,
            switch_restaurant=switch_restaurant,
        )

    # ── 결제 단계 ──
    if step == STEP_PAYMENT:
        payment = detect_payment(processed)
        if payment:
            method_name = {"card": "카드", "cash": "현금", "qr": "카카오페이"}[payment]
            reset_session(session_id)
            return resp(f"{method_name} 결제를 진행합니다. 감사합니다!", confirmed=True, payment=payment)
        return resp("결제 방법을 말씀해주세요. 카드, 현금, 카카오페이 중 선택해주세요.")

    # ── 식당 전환 (카테고리 키워드 없을 때만) ──
    CATEGORY_KEYWORDS = ["메인", "사이드", "음료", "드링크", "주메뉴", "곁들임"]
    if any(kw in processed for kw in SWITCH_KEYWORDS) and not any(kw in processed for kw in CATEGORY_KEYWORDS):
        target = detect_restaurant_in_text(processed)
        if target:
            return resp(f"{target}으로 이동합니다!", switch_restaurant=target)
        return resp("어느 식당으로 이동할까요? 한마루, 스시로, 만다린 중 말씀해주세요.")

    # ── 전체 취소 ──
    if any(kw in processed for kw in CANCEL_ALL_KEYWORDS):
        session["cart"] = []
        session["step"] = STEP_MAIN
        return resp("전체 취소했습니다. 처음부터 주문해주세요!", understood=True)

    # ── 개별 취소 ──
    if any(kw in raw_text for kw in CANCEL_KEYWORDS) or any(kw in processed for kw in CANCEL_KEYWORDS):
        removed, mentioned = remove_from_cart(session, processed)
        if removed:
            summary = cart_summary(session)
            msg = f"{removed}을(를) 뺐습니다. 현재 {summary}." if session["cart"] else f"{removed}을(를) 뺐습니다. 장바구니가 비었습니다."
            return resp(msg)
        elif mentioned:
            return resp(f"장바구니에 {mentioned}이(가) 없습니다.")
        else:
            return resp("취소할 메뉴가 없습니다.")

    # ── 결제 요청 ──
    if any(kw in processed for kw in CHECKOUT_KEYWORDS):
        if session["cart"]:
            session["step"] = STEP_PAYMENT
            summary = cart_summary(session)
            return resp(f"{summary} 주문하시겠어요? 결제 방법을 말씀해주세요. 카드, 현금, 카카오페이가 있습니다.")
        return resp("장바구니가 비어있습니다. 먼저 메뉴를 선택해주세요.")

    # ── 장바구니 확인 ──
    if any(kw in processed for kw in CART_QUERY_KEYWORDS):
        summary = cart_summary(session)
        return resp(f"현재 {summary}입니다.")

    # ── 메뉴 문의 ──
    if any(kw in processed for kw in MENU_QUERY_KEYWORDS):
        restaurant = detect_restaurant_in_text(processed)
        return resp(get_menu_list_message(restaurant))

    # ── 도움말 ──
    if any(kw in processed for kw in HELP_KEYWORDS):
        return resp("메뉴 이름을 말씀하시면 장바구니에 담아드립니다. 예: 김치찌개 2개 주세요. 취소는 빼줘, 결제는 결제해줘 라고 말씀해주세요.")

    # ── 메뉴 이름 직접 감지 ──
    found_items = find_menus_in_text(processed)
    if found_items:
        add_to_cart(session, found_items)
        names = ", ".join([f"{f['menu']} {f['qty']}개" for f in found_items])
        return resp(f"{names}를 담았습니다!")

    # ── 인식 실패 ──
    return resp(
        "다시 한번 말씀해주세요.",
        understood=False
    )


# ============================================================
# API 엔드포인트
# ============================================================

@app.get("/")
def root():
    return {"status": "키오스크 서버 실행 중"}


@app.post("/voice-order", response_model=VoiceResponse)
async def voice_order(
    file: UploadFile = File(...),
    session_id: str = Form(default="default"),
):
    audio_bytes = await file.read()
    raw_text    = STTModule.transcribe(audio_bytes)
    result      = await process_voice(raw_text, session_id)
    save_log(raw_text, result.processed_text, result.understood, result.ai_message)
    return result


class TextRequest(BaseModel):
    text: str
    session_id: str = "default"

@app.post("/text-order", response_model=VoiceResponse)
async def text_order(req: TextRequest):
    return await process_voice(req.text, req.session_id)


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    reset_session(session_id)
    return {"message": f"{session_id} 세션 초기화"}

@app.get("/session/{session_id}")
def get_session_info(session_id: str):
    s = get_session(session_id)
    return {"session_id": session_id, "step": s["step"], "cart": s["cart"]}


# ── 주문 저장 ──
class OrderItem(BaseModel):
    menu_id: str
    menu_name: str
    quantity: int
    price: int

class OrderRequest(BaseModel):
    store: str
    payment_method: str
    total_price: int
    items: list[OrderItem]

@app.post("/save-order")
def save_order(req: OrderRequest):
    try:
        db = get_db(); cursor = db.cursor()
        cursor.execute("SELECT session_id FROM business_sessions WHERE status='open' ORDER BY session_id DESC LIMIT 1")
        row = cursor.fetchone()
        session_id = row[0] if row else None

        if session_id:
            cursor.execute("SELECT COUNT(*) FROM orders WHERE session_id = %s", (session_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM orders")
        order_number = cursor.fetchone()[0] + 1

        cursor.execute(
            "INSERT INTO orders (order_number, store, payment_method, total_price, session_id) VALUES (%s,%s,%s,%s,%s)",
            (order_number, req.store, req.payment_method, req.total_price, session_id)
        )
        order_id = cursor.lastrowid
        for item in req.items:
            cursor.execute(
                "INSERT INTO order_detail (order_id, menu_id, menu_name, quantity, price) VALUES (%s,%s,%s,%s,%s)",
                (order_id, item.menu_id, item.menu_name, item.quantity, item.price)
            )
        db.commit(); cursor.close(); db.close()
        return {"success": True, "order_number": order_number, "order_id": order_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/orders")
def get_orders():
    try:
        db = get_db(); cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT o.order_id, o.order_number, o.store, o.payment_method, o.total_price, o.ordered_at,
                   d.menu_name, d.quantity, d.price
            FROM orders o JOIN order_detail d ON o.order_id = d.order_id
            ORDER BY o.order_id DESC
        """)
        rows = cursor.fetchall(); cursor.close(); db.close()
        return rows
    except Exception as e:
        return {"error": str(e)}


# ── 개점 / 마감 ──
class OpenDayRequest(BaseModel):
    open_date: str

@app.post("/open-day")
def open_day(req: OpenDayRequest):
    try:
        db = get_db(); cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM business_sessions WHERE status='open'")
        existing = cursor.fetchone()
        if existing:
            cursor.close(); db.close()
            return {"success": False, "message": f"{existing['open_date']} 영업일이 아직 마감되지 않았습니다."}
        cursor.execute("INSERT INTO business_sessions (open_date) VALUES (%s)", (req.open_date,))
        sid = cursor.lastrowid
        db.commit(); cursor.close(); db.close()
        return {"success": True, "session_id": sid, "open_date": req.open_date, "message": f"{req.open_date} 개점 완료!"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/close-day")
def close_day():
    try:
        db = get_db(); cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM business_sessions WHERE status='open' ORDER BY session_id DESC LIMIT 1")
        session = cursor.fetchone()
        if not session:
            cursor.close(); db.close()
            return {"success": False, "message": "열린 영업일이 없습니다."}
        sid = session["session_id"]
        cursor.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_price),0) as revenue FROM orders WHERE session_id=%s", (sid,))
        totals = cursor.fetchone()
        cursor.execute("SELECT store, COUNT(*) as orders, SUM(total_price) as revenue FROM orders WHERE session_id=%s GROUP BY store", (sid,))
        by_store = cursor.fetchall()
        cursor.execute("SELECT payment_method, COUNT(*) as cnt, SUM(total_price) as revenue FROM orders WHERE session_id=%s GROUP BY payment_method", (sid,))
        by_payment = cursor.fetchall()
        cursor.execute("""
            SELECT d.menu_name, SUM(d.quantity) as total_qty
            FROM order_detail d JOIN orders o ON d.order_id=o.order_id
            WHERE o.session_id=%s GROUP BY d.menu_name ORDER BY total_qty DESC LIMIT 5
        """, (sid,))
        top_menus = cursor.fetchall()
        cursor.execute(
            "UPDATE business_sessions SET status='closed', closed_at=NOW(), total_orders=%s, total_revenue=%s WHERE session_id=%s",
            (totals["cnt"], totals["revenue"], sid)
        )
        db.commit(); cursor.close(); db.close()
        return {
            "success": True,
            "open_date": str(session["open_date"]),
            "total_orders": totals["cnt"],
            "total_revenue": totals["revenue"],
            "by_store": by_store,
            "by_payment": by_payment,
            "top_menus": top_menus,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/current-day")
def current_day():
    try:
        db = get_db(); cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM business_sessions WHERE status='open' ORDER BY session_id DESC LIMIT 1")
        s = cursor.fetchone(); cursor.close(); db.close()
        if s:
            return {"is_open": True, "open_date": str(s["open_date"]), "session_id": s["session_id"]}
        return {"is_open": False}
    except Exception as e:
        return {"error": str(e)}


@app.get("/settlement-history")
def settlement_history():
    try:
        db = get_db(); cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM business_sessions ORDER BY session_id DESC")
        rows = cursor.fetchall(); cursor.close(); db.close()
        return rows
    except Exception as e:
        return {"error": str(e)}


@app.get("/logs")
def get_logs():
    if not os.path.exists(LOG_FILE):
        return {"message": "로그 없음", "logs": [], "stats": {}}
    logs = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            logs.append(row)
    total   = len(logs)
    success = sum(1 for l in logs if l["인식성공"] == "성공")
    return {
        "stats": {
            "총횟수": total, "성공": success, "실패": total - success,
            "인식률": f"{success/total*100:.1f}%" if total else "0%",
        },
        "logs": logs[-30:],
    }

@app.delete("/logs")
def clear_logs():
    if os.path.exists(LOG_FILE): os.remove(LOG_FILE)
    return {"message": "로그 초기화 완료"}
