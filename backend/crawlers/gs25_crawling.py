"""
GS25 편의점 행사상품 크롤러
대상: http://gs25.gsretail.com/gscvs/ko/products/event-goods
행사 탭: 1+1 행사 (#ONE_TO_ONE) / 2+1 행사 (#TWO_TO_ONE) / 덤증정 행사 (#GIFT)

실제 HTML 구조:
  탭:     <a href="#;" id="ONE_TO_ONE">1+1 행사</a>
  카드:   <div class="prod_box"> ... </div>
  다음:   <a href="#next;" onclick="goodsPageController.moveControl(1)">

설치:
    pip install selenium webdriver-manager
실행:
    python3 gs25_crawling.py
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException

try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WEBDRIVER_MANAGER = True
except ImportError:
    USE_WEBDRIVER_MANAGER = False


# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
BASE_URL = "http://gs25.gsretail.com/gscvs/ko/products/event-goods"

# 탭 id → 행사 이름
TABS = {
    "ONE_TO_ONE": "1+1",
    "TWO_TO_ONE": "2+1",
    "GIFT":       "덤증정",
}

WAIT_TIMEOUT = 15
PAGE_PAUSE   = 2.0   # 페이지 이동 후 대기(초)
MAX_PAGES    = 200   # 최대 페이지 수


# ─────────────────────────────────────────────
# 데이터 모델
# ─────────────────────────────────────────────
@dataclass
class Product:
    event_type: str   # 1+1 / 2+1 / 덤증정
    name: str         # 상품명
    price: str        # 가격 (예: "10,500원")
    image_url: str    # 상품 이미지 URL


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
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")

    if USE_WEBDRIVER_MANAGER:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


# ─────────────────────────────────────────────
# 상품 카드 파싱
# ─────────────────────────────────────────────
def parse_products(driver: webdriver.Chrome, event_type: str) -> list[Product]:
    """현재 페이지의 prod_box 카드를 모두 파싱한다."""
    products: list[Product] = []
    cards = driver.find_elements(By.CSS_SELECTOR, "div.prod_box")

    for card in cards:
        try:
            # 상품명: <p class="tit">쏘피)안심숙면팬티4P(L)</p>
            try:
                name = card.find_element(By.CSS_SELECTOR, "p.tit").text.strip()
            except NoSuchElementException:
                name = ""

            # 가격: <span class="cost">10,500<span>원</span></span>
            try:
                cost_el = card.find_element(By.CSS_SELECTOR, "span.cost")
                # inner <span>원</span> 을 제외한 숫자 텍스트만 추출
                price_num = cost_el.text.replace("원", "").strip()
                price = price_num + "원"
            except NoSuchElementException:
                price = ""

            # 이미지: <p class="img"><img src="..."></p>
            try:
                img = card.find_element(By.CSS_SELECTOR, "p.img img")
                image_url = img.get_attribute("src") or img.get_attribute("data-src") or ""
            except NoSuchElementException:
                image_url = ""

            if not name:
                continue

            products.append(Product(
                event_type=event_type,
                name=name,
                price=price,
                image_url=image_url,
            ))

        except Exception as e:
            print(f"  [WARN] 카드 파싱 실패: {e}")
            continue

    return products


# ─────────────────────────────────────────────
# 탭별 크롤링
# ─────────────────────────────────────────────
def crawl_tab(driver: webdriver.Chrome, tab_id: str, event_type: str) -> list[Product]:
    print(f"\n[{event_type}] 탭 클릭 중 (id='{tab_id}')...")

    # 탭 클릭: <a id="ONE_TO_ONE">
    try:
        tab_btn = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.element_to_be_clickable((By.ID, tab_id))
        )
        driver.execute_script("arguments[0].click();", tab_btn)
    except TimeoutException:
        print(f"  [WARN] 탭 버튼 찾기 실패 (id={tab_id})")
        return []

    time.sleep(2)

    # 첫 카드 로드 대기
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.prod_box"))
        )
    except TimeoutException:
        print(f"  [WARN] 상품 로드 타임아웃")
        return []

    all_products: list[Product] = []
    page_num = 1

    while page_num <= MAX_PAGES:
        products = parse_products(driver, event_type)
        all_products.extend(products)
        print(f"  페이지 {page_num} → {len(products)}개 수집 (누계 {len(all_products)}개)")

        # 다음 페이지 버튼 확인
        # <a class="next" onclick="goodsPageController.moveControl(1)">
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "a.next")

            # 비활성화 여부 확인 (disabled 클래스 or aria-disabled)
            btn_class = next_btn.get_attribute("class") or ""
            aria_disabled = next_btn.get_attribute("aria-disabled") or ""
            if "disabled" in btn_class or aria_disabled == "true":
                print("  마지막 페이지 도달.")
                break

            driver.execute_script("arguments[0].click();", next_btn)
            time.sleep(PAGE_PAUSE)

            # 페이지 전환 완료 대기 (카드 재로드)
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.prod_box"))
            )
            page_num += 1

        except NoSuchElementException:
            print("  다음 페이지 버튼 없음. 완료.")
            break

    print(f"  → [{event_type}] 총 {len(all_products)}개 수집 완료")
    return all_products


# ─────────────────────────────────────────────
# 저장
# ─────────────────────────────────────────────
def save_json(products: list[Product], filepath: str) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in products], f, ensure_ascii=False, indent=2)
    print(f"JSON 저장: {filepath}")


def save_csv(products: list[Product], filepath: str) -> None:
    if not products:
        print("저장할 데이터 없음.")
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
    """
    Parameters
    ----------
    headless    : True → 창 없이 실행 / False → 브라우저 창 표시
    save_format : "json" | "csv" | "both"
    """
    driver = init_driver(headless=headless)
    all_products: list[Product] = []

    try:
        print(f"페이지 로드 중: {BASE_URL}")
        driver.get(BASE_URL)

        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(3)  # JS 초기화 대기

        for tab_id, event_type in TABS.items():
            products = crawl_tab(driver, tab_id, event_type)
            all_products.extend(products)

    except Exception as e:
        print(f"[ERROR] 크롤링 오류: {e}")
        raise
    finally:
        driver.quit()

    # 저장
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if save_format in ("json", "both"):
        save_json(all_products, f"gs25_events_{ts}.json")
    if save_format in ("csv", "both"):
        save_csv(all_products, f"gs25_events_{ts}.csv")

    # 요약
    print("\n=== 크롤링 결과 요약 ===")
    for event_type in TABS.values():
        count = sum(1 for p in all_products if p.event_type == event_type)
        print(f"  {event_type}: {count}개")
    print(f"  합계: {len(all_products)}개")

    return all_products


if __name__ == "__main__":
    main(headless=True, save_format="both")