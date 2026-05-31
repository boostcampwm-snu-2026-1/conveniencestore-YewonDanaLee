# 편의점 할인행사 비교 사이트 — claude.md

## 1. 프로젝트 개요
- 목적: GS25 · CU · 세븐일레븐 3사의 행사 상품을 한눈에 비교
- 대상 유저: 한국 편의점 이용자
- 언어: 한국어 (UI 전체)

## 2. 기술 스택

```
Frontend  : Next.js 14 (App Router) + TypeScript
Styling   : Tailwind CSS
상태관리    : Zustand
데이터 패칭 : TanStack Query (React Query)
차트/UI    : 없음 (순수 Tailwind 컴포넌트)
배포       : Vercel
```

## 3. 디렉토리 구조

```
src/
├── app/
│   ├── page.tsx                  # 메인 (검색창 + 마감임박)
│   ├── search/
│   │   └── page.tsx              # 검색 결과 (/search?q=...)
│   └── product/
│       └── [id]/
│           └── page.tsx          # 상품 상세 (/product/:id)
├── components/
│   ├── SearchBar.tsx             # 최상단 검색창
│   ├── StoreFilter.tsx           # GS25 / CU / 세븐일레븐 필터 (multi-select)
│   ├── ExpiringSection.tsx       # 마감임박 섹션 (타이틀 + 카드 그리드)
│   ├── DealCard.tsx              # 마감임박 카드 (이미지·이름·배지·남은시간·가격)
│   ├── ProductCard.tsx           # 검색결과 카드 (DealCard보다 크고 평균가 표시)
│   ├── SearchResultGrid.tsx      # 검색어 + 총 N건 + ProductCard 그리드
│   ├── EmptyState.tsx            # 결과 없을 때 (일러스트 + 안내 문구)
│   ├── DealComparison.tsx        # 상품 상세 — 3사 나란히 비교 테이블
│   ├── PriceAvgBadge.tsx         # 3사 평균가 강조 배지
│   └── BestDealHighlight.tsx     # 최저가 편의점 하이라이트 카드
├── lib/
│   ├── api.ts                    # fetch 함수 모음
│   └── utils.ts                  # 가격 포맷, 남은 시간 계산 등
└── types/
    └── index.ts                  # Product, Deal, Category 타입 정의
```

## 4. 라우팅 규칙

```
/                         메인 (검색창 + 마감임박 목록)
/search?q={검색어}         검색 결과
/search?q={검색어}&store={GS25|CU|7EL}   필터 포함 검색
/product/{id}             상품 상세
```

## 5. 데이터 모델 (TypeScript 타입)

```ts
// types/index.ts

type Store = 'GS25' | 'CU' | '7EL'

type DealType = 'ONE_PLUS_ONE' | 'TWO_PLUS_ONE' | 'DISCOUNT' | 'GIFT'

interface Product {
  id: string
  name: string
  category: Category
  image_url: string | null   // null이면 PlaceholderImage 컴포넌트 사용
  base_price: number         // 정가 (원)
  avg_price: number          // 3사 행사가 평균 (원)
}

interface Deal {
  id: string
  product_id: string
  store: Store
  deal_type: DealType
  discount_pct: number | null  // DISCOUNT 타입일 때만 사용
  sale_price: number           // 행사가 (원)
  gift_item_name: string | null // GIFT 타입일 때만 사용
  expires_at: string           // ISO 8601
  is_expiring: boolean         // expires_at이 24시간 이내이면 true
}

interface Category {
  id: string
  label: string    // 예: '음료', '과자', '도시락', '아이스크림'
  icon: string     // Tabler icon 이름
}
```

## 6. API 엔드포인트

### 6-1. 마감임박 상품 목록
```
GET /api/deals/expiring
Query: limit?: number (default 20)
       store?: Store
Response: Deal[] — expires_at 오름차순 정렬
```

### 6-2. 상품 검색
```
GET /api/products/search
Query: q: string (최소 1자, 공백 제외)
       category?: string
       store?: Store
Response: {
  products: Product[]
  total: number
}
```

### 6-3. 상품 상세
```
GET /api/products/:id
Response: {
  product: Product
  deals: Deal[]          // 편의점별, 최대 3개
  avg_price: number      // 3사 행사가 평균
  cheapest_store: Store  // 최저가 편의점
}
```

### 6-4. 카테고리 목록
```
GET /api/categories
Response: Category[]
```

## 7. 할인 유형 — 표기 규칙

| deal_type | 배지 텍스트 | 배지 색상 (bg / text) |
|-----------|------------|----------------------|
| ONE_PLUS_ONE | 1+1 | #EAF3DE / #27500A |
| TWO_PLUS_ONE | 2+1 | #E6F1FB / #0C447C |
| DISCOUNT | N% 할인 | #FAEEDA / #633806 |
| GIFT | 증정 | #EEEDFE / #3C3489 |

- `DISCOUNT` 배지의 N은 반드시 API 응답의 `discount_pct` 값을 사용한다. 직접 계산하지 않는다.
- 배지 텍스트는 위 표에서 벗어나지 않는다. "1+1행사", "할인" 등으로 임의 변경 금지.

## 8. 편의점 브랜드 토큰

| store 값 | 표시명 | 브랜드 컬러 | 로고 배경 |
|----------|--------|------------|---------|
| GS25 | GS25 | #00A650 | #EAF3DE |
| CU | CU | #5B2D8E | #EEEDFE |
| 7EL | 세븐일레븐 | #E31837 | #FCEBEB |

- store 값이 `7EL`이어도 UI 표시명은 반드시 **세븐일레븐**으로 표기한다.
- 편의점명을 "세븐", "GS", "씨유" 등으로 줄여쓰지 않는다.

## 9. 유틸 함수 규칙 (lib/utils.ts)

```ts
// 가격 포맷 — 반드시 이 함수를 사용할 것
formatPrice(price: number): string
// 예: formatPrice(1500) → "1,500원"
// 규칙: 천 단위 comma 필수, 뒤에 "원" 붙임, 소수점 없음

// 남은 시간 포맷 — 절대 시각 표기 금지
formatExpiry(expires_at: string): string
// 예: "3시간 후 마감", "23분 후 마감"
// 24시간 초과이면: "D일 후 마감"
// 만료됨: "마감"
```

## 10. 컴포넌트별 세부 스펙

### SearchBar
- 페이지 최상단, autofocus
- Enter 키 또는 검색 아이콘 클릭 시 `/search?q=...` 이동
- 빈 문자열(공백 포함) 검색 차단 — 버튼 비활성화
- placeholder: "상품명을 입력하세요 (예: 삼각김밥, 바나나맛우유)"

### DealCard
- 이미지 영역: `image_url`이 null이면 `PlaceholderImage` 컴포넌트 렌더링 (깨진 img 태그 금지)
- 할인 배지: 좌상단 절대 위치
- 남은 시간: `formatExpiry()` 사용, `is_expiring: true`이면 빨간 텍스트
- 가격: `formatPrice()` 사용, 정가와 행사가 함께 표시 (정가는 취소선)
- 편의점 로고: 우하단, 브랜드 컬러 배경

### DealComparison (상품 상세)
- 3사를 가로 3열로 나란히 나열
- 행사 없는 편의점은 "행사 없음" 회색 텍스트로 표시 (열 자체는 유지)
- `cheapest_store`에 해당하는 열에 border accent 적용
- 평균가는 `PriceAvgBadge` 컴포넌트로 상단에 별도 표시

### EmptyState
- 검색 결과 0건일 때 렌더링
- 문구: "{검색어}에 대한 행사 상품이 없어요"
- 하단에 "전체 상품 보기" 버튼 → `/` 로 이동

## 11. 레이아웃 — 반응형 규칙

```
카드 그리드:
  모바일 (< 640px)  : 2열
  태블릿 (640~1024px): 3열
  데스크톱 (> 1024px): 4열

상품 상세 DealComparison:
  모바일: 세로 스택 (3사 순서대로)
  태블릿+: 가로 3열
```

## 12. 금지 사항 (Claude에게)

```
❌ 가격에 comma 없이 표기 — 1500원 (x) → 1,500원 (o)
❌ formatPrice(), formatExpiry() 우회하여 직접 문자열 생성
❌ 만료 시각을 "2025-05-25 18:00" 형태로 절대 표기
❌ image_url이 null일 때 <img src={null}> 렌더링
❌ 편의점명 임의 축약 — "세븐", "GS", "씨유"
❌ 할인율 직접 계산 — API의 discount_pct 값만 사용
❌ 컴포넌트 이름을 위 목록과 다르게 임의 생성
❌ DealType 값 외의 문자열을 deal_type으로 사용
```

## 13. 강제 사항 (Claude에게)

```
✅ 모든 가격 표기는 formatPrice() 통과
✅ 모든 마감 시각 표기는 formatExpiry() 통과
✅ 이미지 없는 상품은 PlaceholderImage 컴포넌트 사용
✅ store === '7EL'이면 UI 표시는 항상 "세븐일레븐"
✅ 검색 최소 조건: 공백 제거 후 1자 이상
✅ 행사 없는 편의점 열도 DealComparison에 유지 (숨기지 말 것)
✅ 신규 컴포넌트 추가 시 components/ 아래에 위치
✅ API 호출은 반드시 lib/api.ts 함수를 통해서만
```