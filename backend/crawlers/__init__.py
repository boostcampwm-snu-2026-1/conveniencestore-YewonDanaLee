"""
크롤러 패키지 진입점 — 3사 크롤러를 일괄 실행한다.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

import gs25_crawling
import cu_crawling
import seven_eleven_crawling


def run_all() -> dict:
    """GS25·CU·세븐일레븐 크롤러를 병렬 실행하고 결과를 합산한다."""
    crawlers = {
        "GS25": gs25_crawling.main,
        "CU": cu_crawling.main,
        "7EL": seven_eleven_crawling.main,
    }

    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fn): store for store, fn in crawlers.items()}
        for future in as_completed(futures):
            store = futures[future]
            try:
                results[store] = future.result()
                print(f"[{store}] 완료 — {len(results[store])}개")
            except Exception as e:
                print(f"[{store}] 실패: {e}")
                results[store] = []

    return results


if __name__ == "__main__":
    run_all()
