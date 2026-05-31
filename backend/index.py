"""
백엔드 진입점 — 스케줄러를 등록하고 프로세스를 유지한다.

실행:
    python3 backend/index.py
"""

from scheduler.monthly import start

if __name__ == "__main__":
    start()
