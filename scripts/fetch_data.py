"""
국토교통부 아파트 매매 실거래가 수집 스크립트
- 서울 25개 구 전체
- 최근 12개월
- 25억 이하, 전용면적 84㎡ 이상 필터
"""

import os
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

API_KEY = os.environ.get("MOLIT_API_KEY", "FNRUoAx54GnO18NkzyJFWX1fLrmw4CmB5dsVtAkF6NFV6jbuJUqEhcG9VzCO0WkGHkerkCKrObHQGSBxEXHcpQ==")
BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

# 서울 25개 구 법정동코드
SEOUL_DISTRICTS = {
    "종로구": "11110",
    "중구": "11140",
    "용산구": "11170",
    "성동구": "11200",
    "광진구": "11215",
    "동대문구": "11230",
    "중랑구": "11260",
    "성북구": "11290",
    "강북구": "11305",
    "도봉구": "11320",
    "노원구": "11350",
    "은평구": "11380",
    "서대문구": "11410",
    "마포구": "11440",
    "양천구": "11470",
    "강서구": "11500",
    "구로구": "11530",
    "금천구": "11545",
    "영등포구": "11560",
    "동작구": "11590",
    "관악구": "11620",
    "서초구": "11650",
    "강남구": "11680",
    "송파구": "11710",
    "강동구": "11740",
}

# 한강 인근 지역
HANGANG_DISTRICTS = {"마포구", "용산구", "영등포구", "성동구", "광진구", "동작구", "강동구", "강남구", "서초구", "송파구"}

MAX_PRICE = 250000  # 25억 (만원 단위)
MIN_AREA = 84.0     # 84㎡


def get_yearmonths(months=12):
    """최근 N개월의 YYYYMM 리스트 반환"""
    result = []
    now = datetime.now()
    for i in range(months):
        d = now - relativedelta(months=i)
        result.append(d.strftime("%Y%m"))
    return result


def fetch_transactions(lawd_cd, deal_ymd):
    """국토부 API에서 특정 구/월 데이터 수집"""
    # serviceKey를 params 딕셔너리에 넣으면 requests가 ==를 %3D%3D로
    # 이중인코딩해 500 에러 발생 → URL에 직접 붙여서 회피
    url = f"{BASE_URL}?serviceKey={API_KEY}&LAWD_CD={lawd_cd}&DEAL_YMD={deal_ymd}&numOfRows=1000&pageNo=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/xml, text/xml, */*",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        result_code = root.findtext(".//resultCode", "").strip()
        if result_code not in ("00", "000"):
            return []

        items = []
        for item in root.findall(".//item"):
            def get(tag):
                el = item.find(tag)
                return el.text.strip() if el is not None and el.text else ""

            # 거래금액 파싱 (쉼표 제거 후 정수)
            try:
                price_str = get("dealAmount").replace(",", "").replace(" ", "")
                price = int(price_str)
            except (ValueError, AttributeError):
                continue

            # 면적 파싱
            try:
                area = float(get("excluUseAr"))
            except (ValueError, AttributeError):
                continue

            # 필터 적용
            if price > MAX_PRICE:
                continue
            if area < MIN_AREA:
                continue

            year  = get("dealYear")
            month = get("dealMonth").zfill(2)
            day   = get("dealDay").zfill(2)

            # 지번주소 조합 (예: "홍파동 199") → index.html에서 구와 합쳐 "서울 종로구 홍파동 199"
            jibun = get("jibun").lstrip("0") or ""

            items.append({
                "단지명": get("aptNm"),
                "구": "",  # 상위에서 채움
                "법정동": get("umdNm"),
                "지번": jibun,
                "전용면적": area,
                "층": get("floor"),
                "건축연도": get("buildYear"),
                "거래금액": price,
                "거래금액_억": round(price / 10000, 2),
                "년": year,
                "월": month,
                "일": day,
                "거래일": f"{year}-{month}-{day}",
                "지역코드": lawd_cd,
            })
        return items

    except Exception as e:
        print(f"  오류 [{lawd_cd} {deal_ymd}]: {e}")
        return []


def main():
    print("=== 국토부 아파트 매매 실거래가 수집 시작 ===")
    yearmonths = get_yearmonths(12)
    all_transactions = []

    for gu_name, lawd_cd in SEOUL_DISTRICTS.items():
        print(f"\n[{gu_name}] 수집 중...")
        gu_count = 0
        for ym in yearmonths:
            items = fetch_transactions(lawd_cd, ym)
            for item in items:
                item["구"] = gu_name
                item["한강인근"] = gu_name in HANGANG_DISTRICTS
            all_transactions.extend(items)
            gu_count += len(items)
            time.sleep(0.2)  # API 과부하 방지
        print(f"  → {gu_count}건 수집")

    # 거래일 기준 내림차순 정렬
    all_transactions.sort(key=lambda x: x.get("거래일", ""), reverse=True)

    # 구별 통계 계산
    stats = {}
    for t in all_transactions:
        gu = t["구"]
        if gu not in stats:
            stats[gu] = {"거래수": 0, "총금액": 0, "최저가": float("inf"), "최고가": 0, "한강인근": t["한강인근"]}
        stats[gu]["거래수"] += 1
        stats[gu]["총금액"] += t["거래금액"]
        stats[gu]["최저가"] = min(stats[gu]["최저가"], t["거래금액"])
        stats[gu]["최고가"] = max(stats[gu]["최고가"], t["거래금액"])

    district_stats = []
    for gu, s in stats.items():
        avg = round(s["총금액"] / s["거래수"] / 10000, 2) if s["거래수"] > 0 else 0
        district_stats.append({
            "구": gu,
            "거래수": s["거래수"],
            "평균가_억": avg,
            "최저가_억": round(s["최저가"] / 10000, 2),
            "최고가_억": round(s["최고가"] / 10000, 2),
            "한강인근": s["한강인근"],
        })
    district_stats.sort(key=lambda x: x["거래수"], reverse=True)

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": len(all_transactions),
        "filter": {"max_price_억": MAX_PRICE / 10000, "min_area_㎡": MIN_AREA},
        "district_stats": district_stats,
        "transactions": all_transactions,
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "transactions.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n=== 완료: 총 {len(all_transactions)}건 수집 → data/transactions.json 저장 ===")


if __name__ == "__main__":
    main()
