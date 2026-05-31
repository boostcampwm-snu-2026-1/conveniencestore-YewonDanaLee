"""
매월 1일 자정에 크롤러를 실행하는 스케줄러.

설치:
    pip install apscheduler
실행:
    python3 backend/index.py
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from crawlers import run_all


def crawl_job() -> None:
    print("[Scheduler] 월간 크롤링 시작")
    results = run_all()
    total = sum(len(v) for v in results.values())
    print(f"[Scheduler] 월간 크롤링 완료 — 총 {total}개")


def start() -> None:
    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    # 매월 1일 00:00 (KST)
    scheduler.add_job(crawl_job, CronTrigger(day=1, hour=0, minute=0))
    print("[Scheduler] 등록 완료 — 매월 1일 자정(KST)에 크롤링 실행")
    scheduler.start()
