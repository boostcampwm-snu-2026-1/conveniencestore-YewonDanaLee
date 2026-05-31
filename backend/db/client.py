"""
DB 클라이언트 — 모든 DB 접근은 이 모듈을 통해서만 한다.
"""

# TODO: DB 연결 설정 (PostgreSQL / SQLite 등)


def upsert_deals(store: str, products: list) -> None:
    """크롤링 결과를 DB에 upsert한다."""
    raise NotImplementedError
