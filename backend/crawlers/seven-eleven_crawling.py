"""
7-Eleven 행사상품 크롤러
대상: https://www.7-eleven.co.kr/product/presentList.asp
행사 탭: 1+1(탭1) / 2+1(탭2) / 증정행사(탭3) / 할인행사(탭4)

실제 HTML 구조:
  탭:  <a href="javascript: fncTab('4');">할인행사</a>
  카드: <a href="javascript: fncGoView('060716');" class="btn_product_01">

설치:
    pip install selenium webdriver-manager
실행:
    python3 seven-eleven_crawling.py
"""

import re
import time
import json
import csv
from datetime import datetime
from dataclasses import dataclass, fields, asdict

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WEBDRIVER_MANAGER = True
except ImportError:
    USE_WEBDRIVER_MANAGER = False


# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
BASE_URL = "https://www.7-eleven.co.kr/product/presentList.asp"

# fncTab() 인자 → 행사 이름
TABS = {
    "1": "1+1",
    "2": "2+1",
    "3": "증정행사",
    "4": "할인행사",
}

WAIT_TIMEOUT = 15   # 초
SCROLL_PAUSE  = 2.0  # 초
MAX_LOAD_MORE = 1000   # 더보기 최대 클릭 횟수


# ─────────────────────────────────────────────
# 데이터 모델
# ─────────────────────────────────────────────
@dataclass
class Product:
    event_type: str   # 1+1 / 2+1 / 증정행사 / 할인행사
    product_id: str   # fncGoView('060716') → '060716'
    name: str
    price: str
    image_url: str
    detail_url: str   # https://...presentView.asp?pCd=060716


# ─────────────────────────────────────────────
# 드라이버 초기화
# ─────────────────────────────────────────────
def init_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    if USE_WEBDRIVER_MANAGER:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    return driver


# ─────────────────────────────────────────────
# 상품 카드 파싱
# ─────────────────────────────────────────────
def extract_product_id(href: str) -> str:
    """'javascript: fncGoView('060716');' → '060716'"""
    m = re.search(r"fncGoView\('(\w+)'\)", href or "")
    return m.group(1) if m else ""


def parse_products(driver: webdriver.Chrome, event_type: str) -> list[Product]:
    products: list[Product] = []

    # btn_product_01 이 있는 li 카드 전체 수집
    # (카드 컨테이너가 ul > li 구조로 추정, btn_product_01 기준으로 부모 탐색)
    btns = driver.find_elements(By.CSS_SELECTOR, "a.btn_product_01")

    for btn in btns:
        try:
            href = btn.get_attribute("href") or ""
            product_id = extract_product_id(href)

            # 버튼의 부모 li(카드) 안에서 나머지 정보 추출
            card = btn.find_element(By.XPATH, "./ancestor::li[1]")

            # 상품명
            try:
                name = card.find_element(
                    By.CSS_SELECTOR,
                    ".name, .tit, .prod_name, p.name, .item_name"
                ).text.strip()
            except NoSuchElementException:
                name = ""

            # 가격
            try:
                price = card.find_element(
                    By.CSS_SELECTOR,
                    ".price, .cost, span.price, strong.price"
                ).text.strip()
            except NoSuchElementException:
                price = ""

            # 이미지
            try:
                img = card.find_element(By.CSS_SELECTOR, "img")
                image_url = img.get_attribute("src") or img.get_attribute("data-src") or ""
            except NoSuchElementException:
                image_url = ""

            detail_url = (
                f"https://www.7-eleven.co.kr/product/presentView.asp?pCd={product_id}"
                if product_id else ""
            )

            products.append(Product(
                event_type=event_type,
                product_id=product_id,
                name=name,
                price=price,
                image_url=image_url,
                detail_url=detail_url,
            ))

        except Exception as e:
            print(f"  [WARN] 카드 파싱 실패: {e}")
            continue

    return products


# ─────────────────────────────────────────────
# 탭별 크롤링
# ─────────────────────────────────────────────
def crawl_tab(driver: webdriver.Chrome, tab_no: str, event_type: str) -> list[Product]:
    print(f"\n[{event_type}] 탭 전환 중 (fncTab('{tab_no}'))...")

    # fncTab() 호출로 탭 전환
    driver.execute_script(f"fncTab('{tab_no}');")
    time.sleep(2)

    # btn_product_01 이 최소 1개 나타날 때까지 대기
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.btn_product_01"))
        )
    except TimeoutException:
        print(f"  [WARN] 상품 로드 타임아웃 — 탭 {tab_no} 건너뜀")
        return []

    # fncMore() 반복 호출로 전체 상품 로드
    # fncMore('1') 인자는 탭 번호와 동일하게 사용
    page = 1
    for i in range(MAX_LOAD_MORE):
        before = len(driver.find_elements(By.CSS_SELECTOR, "a.btn_product_01"))

        try:
            # MORE 버튼이 DOM에 있으면 클릭, 없으면 JS 직접 호출
            more_btn = driver.find_element(
                By.CSS_SELECTOR, f"a[href*='fncMore']"
            )
            if not more_btn.is_displayed():
                break
            driver.execute_script("arguments[0].click();", more_btn)
        except NoSuchElementException:
            # 버튼이 DOM에 없으면 JS 직접 호출
            driver.execute_script(f"fncMore('{tab_no}');")

        time.sleep(SCROLL_PAUSE)
        after = len(driver.find_elements(By.CSS_SELECTOR, "a.btn_product_01"))
        print(f"  MORE {i+1}회 → 상품 {before}개 → {after}개")

        if after == before:
            print("  더 이상 상품 없음. 로드 완료.")
            break
        page += 1

    products = parse_products(driver, event_type)
    print(f"  → {len(products)}개 수집 완료")
    return products


# ─────────────────────────────────────────────
# 저장
# ─────────────────────────────────────────────
def save_json(products: list[Product], filepath: str) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in products], f, ensure_ascii=False, indent=2)
    print(f"JSON 저장: {filepath}")


def save_csv(products: list[Product], filepath: str) -> None:
    if not products:
        return
    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[f.name for f in fields(Product)])
        writer.writeheader()
        writer.writerows([asdict(p) for p in products])
    print(f"CSV 저장: {filepath}")


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
def main(headless: bool = True, save_format: str = "both") -> list[Product]:
    driver = init_driver(headless=headless)
    all_products: list[Product] = []

    try:
        print(f"페이지 로드 중: {BASE_URL}")
        driver.get(BASE_URL)

        # 페이지 초기 로드 대기 — body 기준으로 느슨하게 잡고 JS 렌더링 시간 확보
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(3)  # JS 초기화 대기

        for tab_no, event_type in TABS.items():
            products = crawl_tab(driver, tab_no, event_type)
            all_products.extend(products)

    except Exception as e:
        print(f"[ERROR] 크롤링 중 오류: {e}")
        raise
    finally:
        driver.quit()

    # 저장
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if save_format in ("json", "both"):
        save_json(all_products, f"7eleven_events_{ts}.json")
    if save_format in ("csv", "both"):
        save_csv(all_products, f"7eleven_events_{ts}.csv")

    # 요약
    print("\n=== 크롤링 결과 요약 ===")
    for event_type in TABS.values():
        count = sum(1 for p in all_products if p.event_type == event_type)
        print(f"  {event_type}: {count}개")
    print(f"  합계: {len(all_products)}개")

    return all_products


if __name__ == "__main__":
    main(headless=True, save_format="both")