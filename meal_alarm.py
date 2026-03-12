"""
부산대학교 양산캠퍼스 행림관 식단 알림 (디스코드 웹훅)

설정 방법:
1. 디스코드 서버에서 알림 받을 채널 → 설정(톱니바퀴) → 연동 → 웹후크 만들기
2. 웹훅 URL 복사 → .env 파일에 DISCORD_WEBHOOK_URL=웹훅URL 형태로 저장
3. 테스트: python meal_alarm.py --test
4. Windows 작업 스케줄러 등록: python meal_alarm.py --install

필요 패키지: pip install selenium requests python-dotenv
"""

import requests
import sys
import subprocess
import os
import io
import re
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# .env 파일에서 환경변수 로드
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

DORM_URL = "https://dorm.pusan.ac.kr/dorm/ydorm"


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
        driver.get(DORM_URL)
        time.sleep(6)

        body_text = driver.find_element("tag name", "body").text
        return parse_meals(body_text)
    finally:
        driver.quit()


def parse_meals(text):
    """페이지 텍스트에서 오늘 점심/저녁 식단을 추출한다."""
    today_date = datetime.now().strftime("%Y-%m-%d")
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday = weekdays[datetime.now().weekday()]

    lines = text.split("\n")

    # "오늘의 식단" 이후 텍스트에서 오늘 날짜 블록 찾기
    meal_start = None
    for i, line in enumerate(lines):
        if "오늘의 식단" in line:
            meal_start = i + 1
            break

    if meal_start is None:
        return {"date": today_date, "weekday": weekday, "lunch": None, "dinner": None}

    # 오늘 날짜 블록 시작 찾기
    today_block_start = None
    for i in range(meal_start, len(lines)):
        # 날짜 패턴: "2026. 03. 12" 또는 "2026. 3. 12"
        if re.match(r'\d{4}\.\s*\d{1,2}\.\s*\d{1,2}', lines[i].strip()):
            date_in_line = lines[i].strip()
            # 오늘 날짜인지 확인
            nums = re.findall(r'\d+', date_in_line)
            if len(nums) >= 3:
                y, m, d = int(nums[0]), int(nums[1]), int(nums[2])
                now = datetime.now()
                if y == now.year and m == now.month and d == now.day:
                    today_block_start = i + 1
                    break

    if today_block_start is None:
        return {"date": today_date, "weekday": weekday, "lunch": None, "dinner": None}

    # 다음 날짜 블록 또는 "식단 더보기" 전까지가 오늘 블록
    today_block_end = len(lines)
    for i in range(today_block_start, len(lines)):
        if re.match(r'\d{4}\.\s*\d{1,2}\.\s*\d{1,2}', lines[i].strip()) or "식단 더보기" in lines[i] or "주요일정" in lines[i]:
            today_block_end = i
            break

    # 오늘 블록에서 점심/저녁 추출
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
        "date": today_date,
        "weekday": weekday,
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


def install_task_scheduler():
    """Windows 작업 스케줄러에 매일 아침 8:30 실행 등록."""
    script_path = os.path.abspath(__file__)
    python_path = sys.executable

    task_name = "PNU_YangsanDorm_MealAlarm"

    # 한글/공백 경로 문제를 피하기 위해 bat 파일 생성
    bat_path = os.path.join(os.path.dirname(script_path), "run_meal_alarm.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(f'@echo off\n"{python_path}" "{script_path}"\n')

    cmd = [
        "schtasks", "/create",
        "/tn", task_name,
        "/tr", bat_path,
        "/sc", "daily",
        "/st", "08:30",
        "/f"
    ]

    print(f"BAT 파일 생성: {bat_path}")
    print()
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"작업 스케줄러 등록 완료! 매일 08:30에 식단 알림이 전송됩니다.")
        print(f"작업 이름: {task_name}")
    else:
        print(f"등록 실패: {result.stderr}")
        print("관리자 권한으로 실행해보세요.")


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            print("테스트 모드: 오늘 식단을 가져와서 전송합니다.")
        elif sys.argv[1] == "--install":
            install_task_scheduler()
            return

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
