"""
크롤러 수동 즉시 실행 스크립트.

실행:
    python3 backend/scripts/crawl.py
    python3 backend/scripts/crawl.py --store gs25
    python3 backend/scripts/crawl.py --store cu
    python3 backend/scripts/crawl.py --store 7el
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawlers import run_all
import crawlers.gs25_crawling as gs25
import crawlers.cu_crawling as cu
import crawlers.seven_eleven_crawling as seven


def main() -> None:
    parser = argparse.ArgumentParser(description="편의점 행사 크롤러 수동 실행")
    parser.add_argument(
        "--store",
        choices=["gs25", "cu", "7el", "all"],
        default="all",
        help="크롤링할 편의점 (기본값: all)",
    )
    args = parser.parse_args()

    if args.store == "gs25":
        gs25.main()
    elif args.store == "cu":
        cu.main()
    elif args.store == "7el":
        seven.main()
    else:
        run_all()


if __name__ == "__main__":
    main()
