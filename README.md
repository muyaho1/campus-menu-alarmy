# Campus Menu Alarm

부산대학교 양산캠퍼스 행림관 기숙사 식단을 매일 아침 디스코드로 알려주는 자동 알림 봇입니다.

## 기능

- Selenium으로 [부산대 대학생활원](https://dorm.pusan.ac.kr/dorm/ydorm) 페이지에서 행림관 식단 크롤링
- 오늘의 **점심 / 저녁** 메뉴를 디스코드 채널에 자동 전송
- Windows 작업 스케줄러를 이용한 매일 아침 자동 실행

## 미리보기

```
🍽 2026-03-12 (목) 양산 행림관 식단

📌 점심
- 백미밥/잡곡밥
- 뼈없는감자탕(P)
- 해물완자구이
- 미역줄기볶음
- 그린샐러드/D
- 배추김치

📌 저녁
- 백미밥/잡곡밥
- 육개장(B)
- 돼지고기숙주찜(P)
- 채어묵파프리카볶음(F)
- 짜사이무침
- 배추김치
```

## 설치

```bash
pip install selenium requests python-dotenv
```

Chrome 브라우저가 설치되어 있어야 합니다.

## 설정

1. 디스코드 서버에서 알림 받을 채널 → **채널 설정(톱니바퀴)** → **연동** → **웹후크 만들기**
2. 웹훅 URL을 복사하여 `.env` 파일 생성:

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/여기에_웹훅_URL
```

## 사용법

```bash
# 테스트 (즉시 식단 전송)
python meal_alarm.py --test

# Windows 작업 스케줄러에 매일 08:30 자동 실행 등록 (관리자 권한 필요)
python meal_alarm.py --install
```
