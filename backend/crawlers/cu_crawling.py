"""
CU 편의점 행사상품 크롤러
대상: https://cu.bgfretail.com/event/plus.do?category=event&depth2=1&sf=N
행사 탭: 1+1 (goDepth('23')) / 2+1 (goDepth('24'))

실제 HTML 구조:
  탭:     <a href="javascript:goDepth('23');">1+1</a>
  카드:   <div class="prod_wrap"> ... </div>
  더보기: <a href="javascript:nextPage(1);">더보기</a>

설치:
    pip install selenium webdriver-manager
실행:
    python3 cu_crawling.py
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
BASE_URL = "https://cu.bgfretail.com/event/plus.do?category=event&depth2=1&sf=N"

# goDepth() 인자 → 행사 이름
TABS = {
    "23": "1+1",
    "24": "2+1",
}

WAIT_TIMEOUT = 15   # 초
LOAD_PAUSE   = 2.0  # 더보기 클릭 후 대기 시간(초)
MAX_PAGES    = 100  # nextPage() 최대 호출 횟수


# ─────────────────────────────────────────────
# 데이터 모델
# ─────────────────────────────────────────────
@dataclass
class Product:
    event_type: str   # 1+1 / 2+1
    name: str         # 상품명
    price: str        # 가격 (예: "900원")
    image_url: str    # 상품 이미지 URL
    barcode: str      # 이미지 파일명에서 추출한 바코드


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
def extract_barcode(image_url: str) -> str:
    """이미지 URL에서 바코드 추출.
    예: //...naverncp.com/product/8990800000053.png → 8990800000053
    """
    m = re.search(r"/(\d{8,14})\.(?:png|jpg|jpeg|webp)", image_url, re.IGNORECASE)
    return m.group(1) if m else ""


def parse_products(driver: webdriver.Chrome, event_type: str) -> list[Product]:
    """현재 DOM에 로드된 모든 prod_wrap 카드를 파싱한다."""
    products: list[Product] = []
    cards = driver.find_elements(By.CSS_SELECTOR, "div.prod_wrap")

    for card in cards:
        try:
            # 상품명: <div class="name"><p>농심)멘토스푸르티</p></div>
            try:
                name = card.find_element(By.CSS_SELECTOR, "div.name p").text.strip()
            except NoSuchElementException:
                name = ""

            # 가격: <div class="price"><strong>900</strong><span class="won">원</span></div>
            try:
                price_num = card.find_element(By.CSS_SELECTOR, "div.price strong").text.strip()
                price = price_num + "원"
            except NoSuchElementException:
                price = ""

            # 이미지: <img src="//...naverncp.com/product/8990800000053.png">
            try:
                img = card.find_element(By.CSS_SELECTOR, "div.prod_img img")
                image_url = img.get_attribute("src") or img.get_attribute("data-src") or ""
                if image_url.startswith("//"):
                    image_url = "https:" + image_url
            except NoSuchElementException:
                image_url = ""

            barcode = extract_barcode(image_url)

            # 빈 카드 제외
            if not name and not barcode:
                continue

            products.append(Product(
                event_type=event_type,
                name=name,
                price=price,
                image_url=image_url,
                barcode=barcode,
            ))

        except Exception as e:
            print(f"  [WARN] 카드 파싱 실패: {e}")
            continue

    return products


# ─────────────────────────────────────────────
# 탭별 크롤링
# ─────────────────────────────────────────────
def crawl_tab(driver: webdriver.Chrome, depth: str, event_type: str) -> list[Product]:
    print(f"\n[{event_type}] 탭 전환 중 (goDepth('{depth}'))...")

    # goDepth() 호출로 탭 전환
    driver.execute_script(f"goDepth('{depth}');")
    time.sleep(2)

    # 첫 번째 prod_wrap 카드 로드 대기
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.prod_wrap"))
        )
    except TimeoutException:
        print(f"  [WARN] 상품 로드 타임아웃 — goDepth('{depth}') 확인 필요")
        return []

    # nextPage() 반복 호출로 전체 상품 로드
    page = 1
    for i in range(MAX_PAGES):
        before = len(driver.find_elements(By.CSS_SELECTOR, "div.prod_wrap"))

        try:
            # 더보기 버튼: <a href="javascript:nextPage(1);">더보기</a>
            more_btn = driver.find_element(
                By.CSS_SELECTOR, "a[href*='nextPage']"
            )
            if not more_btn.is_displayed():
                print("  더보기 버튼 숨김. 로드 완료.")
                break
            driver.execute_script("arguments[0].click();", more_btn)
        except NoSuchElementException:
            # 버튼이 DOM에서 사라짐 = 마지막 페이지
            print("  더보기 버튼 없음. 로드 완료.")
            break

        time.sleep(LOAD_PAUSE)
        after = len(driver.find_elements(By.CSS_SELECTOR, "div.prod_wrap"))
        print(f"  더보기 {i+1}회 → {before}개 → {after}개")

        if after == before:
            print("  상품 수 변화 없음. 로드 완료.")
            break

        page += 1

    products = parse_products(driver, event_type)
    print(f"  → 총 {len(products)}개 수집 완료")
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

        # 초기 로드 대기
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(3)  # JS 초기화 대기

        for depth, event_type in TABS.items():
            products = crawl_tab(driver, depth, event_type)
            all_products.extend(products)

    except Exception as e:
        print(f"[ERROR] 크롤링 오류: {e}")
        raise
    finally:
        driver.quit()

    # 저장
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if save_format in ("json", "both"):
        save_json(all_products, f"cu_events_{ts}.json")
    if save_format in ("csv", "both"):
        save_csv(all_products, f"cu_events_{ts}.csv")

    # 요약
    print("\n=== 크롤링 결과 요약 ===")
    for event_type in TABS.values():
        count = sum(1 for p in all_products if p.event_type == event_type)
        print(f"  {event_type}: {count}개")
    print(f"  합계: {len(all_products)}개")

    return all_products


if __name__ == "__main__":
    main(headless=True, save_format="both")