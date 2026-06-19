"""
국토교통부 아파트 매매 실거래가 수집 스크립트
- 서울 25개 구 전체
- 최근 12개월
- 25억 이하, 전용면적 84㎡ 이상 필터
- Naver Local Search API로 좌표 조회 → 정확한 위치 링크 생성
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

NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "0QrM73nSAb9WQg_rysfa")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "Rao5GYcu0i")

_naver_cache = {}


def get_naver_info(apt_name, gu_name):
    """Naver Local Search API로 아파트 place ID / 좌표 / 단지번호 조회"""
    key = f"{apt_name}_{gu_name}"
    if key in _naver_cache:
        return _naver_cache[key]

    result = {"네이버ID": "", "네이버좌표": "", "네이버단지번호": ""}

    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/local.json",
            params={"query": f"{apt_name} {gu_name}", "display": 5},
            headers={
                "X-Naver-Client-Id": NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            for item in items:
                link = item.get("link", "")

                # ① Naver 부동산 단지 링크에서 단지번호 직접 추출
                if "land.naver.com/complexes/" in link and not result["네이버단지번호"]:
                    cn = link.split("/complexes/")[1].split("?")[0].strip()
                    if cn.isdigit():
                        result["네이버단지번호"] = cn

                # ② Naver Maps place ID 추출
                if "/entry/place/" in link and not result["네이버ID"]:
                    place_id = link.split("/entry/place/")[1].split("?")[0].strip()
                    if place_id.isdigit():
                        result["네이버ID"] = place_id

                # ③ 좌표 추출 (mapx/mapy: WGS84 × 10,000,000)
                mapx = item.get("mapx", "")
                mapy = item.get("mapy", "")
                if mapx and mapy and not result["네이버좌표"]:
                    try:
                        lat_t = round(int(mapy) / 10000000, 6)
                        lng_t = round(int(mapx) / 10000000, 6)
                        if 33 <= lat_t <= 40 and 124 <= lng_t <= 133:
                            result["네이버좌표"] = f"{lat_t},{lng_t}"
                    except (ValueError, TypeError):
                        pass

        time.sleep(0.12)  # rate limit 준수
    except Exception as e:
        print(f"  Naver API 오류 [{apt_name}]: {e}")

    # 단지번호가 없으면 Naver Land 내부 검색 API 추가 시도
    if not result["네이버단지번호"]:
        result["네이버단지번호"] = _get_land_complex_no(apt_name, gu_name)

    _naver_cache[key] = result
    return result


def _get_land_complex_no(apt_name, gu_name):
    """Naver Land 내부 검색 API로 단지번호 조회 (비공개 API, 실패 시 "" 반환)"""
    try:
        resp = requests.get(
            "https://new.land.naver.com/api/search",
            params={"query": f"{gu_name} {apt_name}"},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://new.land.naver.com/",
                "Accept": "application/json, text/plain, */*",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            # 여러 가능한 응답 구조 대응
            complexes = (
                data.get("complexList")
                or data.get("result", {}).get("complex", [])
                or data.get("body", {}).get("complexList", [])
                or []
            )
            for c in complexes:
                cn = str(c.get("complexNo") or c.get("hscpNo") or "")
                name = c.get("complexName") or c.get("hscpNm") or ""
                # 이름 앞 4자 일치 시 해당 단지로 판정
                if cn.isdigit() and apt_name[:4] in name:
                    return cn
        time.sleep(0.05)
    except Exception:
        pass
    return ""

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

    # ── Naver 좌표/ID 조회 (고유 단지별 1회) ──
    print("\n[Naver] 아파트 좌표 조회 중...")
    unique_keys = {}
    for t in all_transactions:
        k = (t["단지명"], t["구"])
        if k not in unique_keys:
            unique_keys[k] = None

    total = len(unique_keys)
    for i, (apt_name, gu_name) in enumerate(unique_keys.keys(), 1):
        unique_keys[(apt_name, gu_name)] = get_naver_info(apt_name, gu_name)
        if i % 200 == 0 or i == total:
            print(f"  {i}/{total} 처리...")

    for t in all_transactions:
        info = unique_keys.get((t["단지명"], t["구"]), {})
        t["네이버ID"] = info.get("네이버ID", "")
        t["네이버좌표"] = info.get("네이버좌표", "")
        t["네이버단지번호"] = info.get("네이버단지번호", "")

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
