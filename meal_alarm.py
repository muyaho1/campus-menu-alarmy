"""
부산대학교 양산캠퍼스 행림관 식단 알림 (디스코드 웹훅)

설정 방법:
1. 디스코드 서버에서 알림 받을 채널 → 설정(톱니바퀴) → 연동 → 웹후크 만들기
2. 웹훅 URL 복사 → .env 파일에 DISCORD_WEBHOOK_URL=웹훅URL 형태로 저장
3. 테스트: python meal_alarm.py --test

필요 패키지: pip install selenium requests python-dotenv
"""

import requests
import sys
import os
import io
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# .env 파일에서 환경변수 로드
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

DORM_URL = "https://dorm.pusan.ac.kr/dorm/ydorm"
KST = ZoneInfo("Asia/Seoul")
DATE_LINE_RE = re.compile(r"^(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})$")
MEAL_SECTION_END_MARKERS = ("식단 더보기", "주요일정")


def now_kst():
    return datetime.now(KST)


def empty_meal_result(now=None):
    now = now or now_kst()
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    return {
        "date": now.strftime("%Y-%m-%d"),
        "weekday": weekdays[now.weekday()],
        "lunch": None,
        "dinner": None,
    }


def find_meal_section(lines):
    meal_start = None
    for i, line in enumerate(lines):
        if "오늘의 식단" in line:
            meal_start = i + 1
            break

    if meal_start is None:
        return None, None

    meal_end = len(lines)
    for i in range(meal_start, len(lines)):
        if any(marker in lines[i] for marker in MEAL_SECTION_END_MARKERS):
            meal_end = i
            break

    return meal_start, meal_end


def parse_date_line(line):
    match = DATE_LINE_RE.match(line.strip())
    if not match:
        return None
    return tuple(int(value) for value in match.groups())


def get_meal_data():
    """Selenium으로 행림관 식단을 크롤링한다."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--log-level=3")

    driver = webdriver.Chrome(options=options)
    try:
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
        except Exception:
            pass

        driver.get(DORM_URL)
        time.sleep(3)
        driver.refresh()
        time.sleep(3)

        body_text = driver.find_element("tag name", "body").text
        return parse_meals(body_text)
    finally:
        driver.quit()


def parse_meals(text):
    """페이지 텍스트에서 오늘 점심/저녁 식단을 추출한다."""
    now = now_kst()
    empty_result = empty_meal_result(now)
    lines = text.splitlines()
    meal_start, meal_end = find_meal_section(lines)

    if meal_start is None:
        return empty_result

    today_block_start = None
    for i in range(meal_start, meal_end):
        date_parts = parse_date_line(lines[i])
        if date_parts == (now.year, now.month, now.day):
            today_block_start = i + 1
            break

    if today_block_start is None:
        return empty_result

    # 오늘 날짜 블록 안에서만 점심/저녁을 추출한다.
    today_block_end = meal_end
    for i in range(today_block_start, meal_end):
        if parse_date_line(lines[i]):
            today_block_end = i
            break

    today_lines = lines[today_block_start:today_block_end]
    current_meal = None
    lunch_items = []
    dinner_items = []

    for line in today_lines:
        line = line.strip()
        if not line:
            continue
        if line == "점심":
            current_meal = "lunch"
            continue
        elif line == "저녁":
            current_meal = "dinner"
            continue
        elif line in ("조기", "아침"):
            current_meal = "skip"
            continue

        # "백미밥/잡곡밥 육개장(B) ..." 형태를 개별 메뉴로 분리
        menu_items = line.split(" ")
        menu_items = [m.strip() for m in menu_items if m.strip()]

        if current_meal == "lunch":
            lunch_items.extend(menu_items)
        elif current_meal == "dinner":
            dinner_items.extend(menu_items)

    return {
        "date": empty_result["date"],
        "weekday": empty_result["weekday"],
        "lunch": lunch_items if lunch_items else None,
        "dinner": dinner_items if dinner_items else None,
    }


def format_meal_message(result):
    """식단 데이터를 디스코드 메시지로 포맷한다."""
    lines = [f"# 🍽 {result['date']} ({result['weekday']}) 양산 행림관 식단"]
    lines.append("")

    for label, key in [("점심", "lunch"), ("저녁", "dinner")]:
        items = result.get(key)
        lines.append(f"### 📌 {label}")
        if items:
            for item in items:
                lines.append(f"- {item}")
        else:
            lines.append("등록된 식단이 없습니다.")
        lines.append("")

    return "\n".join(lines)


def send_discord(message):
    """디스코드 웹훅으로 메시지를 보낸다."""
    for attempt in range(3):
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=15)
            resp.raise_for_status()
            return resp.status_code
        except requests.exceptions.ConnectionError:
            if attempt < 2:
                time.sleep(3)
            else:
                raise


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            print("테스트 모드: 오늘 식단을 가져와서 전송합니다.")

    print("행림관 식단 크롤링 중...")
    result = get_meal_data()
    message = format_meal_message(result)

    print(message)
    print()

    if not DISCORD_WEBHOOK_URL or not DISCORD_WEBHOOK_URL.startswith("https://"):
        print("⚠️  DISCORD_WEBHOOK_URL 을 설정해주세요.")
        print("설정 방법은 파일 상단 주석을 참고하세요.")
        return

    status = send_discord(message)
    if status == 204:
        print("✅ 디스코드 전송 완료!")
    else:
        print(f"❌ 전송 실패 (status: {status})")


if __name__ == "__main__":
    main()
