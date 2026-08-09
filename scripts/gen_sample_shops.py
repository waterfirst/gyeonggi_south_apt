"""
data/shops.json 샘플 데이터 생성기 (네트워크 불필요)
──────────────────────────────────────────────────────────────────────────
GitHub Actions에서 실데이터가 채워지기 전에도 shops.html 지도가 즉시 보이도록
하는 '샘플' 데이터를 만듭니다. 좌표는 실제 서울/경기 상권 위치를 사용하되,
상호/업종은 예시입니다. meta.sample=true 로 표시되어 지도 상단에 안내 배너가
뜨고, scripts/fetch_shops.py 를 한 번 실행하면 실데이터로 교체됩니다.

주의: 임대료/보증금/연락처/평수를 지어내지 않습니다. 그런 정보는 이 공공
데이터에 없으며, 지도에서는 매물 검색 링크로 안내합니다.
"""
import json
import os
import random

random.seed(20260809)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# (상권명, 중심 경도, 위도) — 실제 좌표
AREAS = [
    ("서울 강남역",   127.02758, 37.49794),
    ("서울 홍대입구",  126.92392, 37.55692),
    ("서울 성수동",    127.05602, 37.54467),
    ("수원 인계동",    127.03157, 37.27139),
    ("성남 서현역",    127.12480, 37.38542),
    ("용인 수지 죽전", 127.10842, 37.32460),
    ("안양 범계역",    126.95090, 37.38996),
    ("평택역",        127.08469, 36.99236),
]

INDS = [
    ("음식", "한식", "백반/한정식"),
    ("음식", "커피/음료", "카페"),
    ("소매", "의복/의류", "여성의류"),
    ("소매", "편의점", "편의점"),
    ("생활서비스", "이/미용/건강", "미용실"),
    ("학문/교육", "학원-보습교습입시", "입시학원"),
    ("음식", "제과/제빵/떡", "제과점"),
    ("소매", "가정/생활/편의", "생활용품"),
]

NAMES = ["행복", "새봄", "온기", "청춘", "한걸음", "모퉁이", "너른", "빛찬",
         "가온", "다올", "소소", "미소", "든든", "포근", "예그리나", "나린"]


def jitter(v, meters):
    # 대략 1도 ≈ 111km. meters 범위로 무작위 이동.
    return v + random.uniform(-meters, meters) / 111000.0


BLD_USES = ["제2종근린생활시설", "제1종근린생활시설", "판매시설", "업무시설"]


def make_shop(i, area):
    name_area, clon, clat = area
    L, M, S = random.choice(INDS)
    lon = round(jitter(clon, 700), 6)
    lat = round(jitter(clat, 700), 6)
    grnd = random.randint(3, 15)
    ugrnd = random.randint(0, 3)
    tot = round(random.uniform(300, 6000), 1)
    return {
        "id": f"SAMPLE{i:05d}",
        "name": f"{random.choice(NAMES)}{S[:2]}",
        "branch": "",
        "indsL": L, "indsM": M, "indsS": S,
        "flr": random.choice(["1", "1", "2", "3", "지하1"]),
        "signgu": name_area.split()[0] + ("시" if "서울" not in name_area else ""),
        "adong": name_area,
        "addr_jibun": f"{name_area} 일대 {random.randint(1, 400)}-{random.randint(1, 30)}",
        "addr_road": "",
        "bld": "",
        "lon": lon, "lat": lat,
        # 건축물대장(표제부) 결합 예시 — 실데이터에선 getBrTitleInfo로 채움
        "bld_use": random.choice(BLD_USES),
        "bld_totArea": tot,
        "bld_pyeong": round(tot / 3.3058, 1),
        "bld_grndFlr": str(grnd),
        "bld_ugrndFlr": str(ugrnd),
        "bld_useApr": f"{random.randint(1994, 2021)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
    }


def main():
    operating = []
    idx = 1
    for area in AREAS:
        for _ in range(random.randint(14, 22)):
            operating.append(make_shop(idx, area))
            idx += 1

    # 공실 추정 후보 샘플 (실데이터에선 스냅샷 차분으로 산출)
    vacant = []
    for area in AREAS:
        for _ in range(random.randint(2, 4)):
            s = make_shop(idx, area)
            idx += 1
            months = random.randint(2, 14)
            s["first_missing"] = "2026-06-30 09:00:00"
            s["months_vacant"] = months
            vacant.append(s)

    inds_counts = {}
    for r in operating:
        inds_counts[r["indsL"]] = inds_counts.get(r["indsL"], 0) + 1

    output = {
        "meta": {
            "generated_at": "샘플 데이터",
            "sample": True,
            "source": "샘플(예시) — 실제 값은 소상공인 상가정보 API 수집으로 대체",
            "method": "gen_sample_shops.py (네트워크 불필요, 데모용)",
            "centers": [a[0] for a in AREAS],
            "operating_count": len(operating),
            "vacant_count": len(vacant),
            "inds_counts": inds_counts,
            "note": (
                "이것은 샘플입니다. GitHub Actions에서 scripts/fetch_shops.py를 "
                "실행하면 실데이터로 교체됩니다. 임대료·연락처·평수는 공공데이터에 "
                "없어 매물 검색 링크로 안내합니다."
            ),
        },
        "operating": operating,
        "vacant": vacant,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "shops.json"), "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    # 시계열(지역별 공실 추이) 샘플 — 최근 6개월, 지역별로 증가 추세를 만들어 둠
    final = {}
    for v in vacant:
        rk = v["adong"]
        final[rk] = final.get(rk, 0) + 1
    months = ["2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01"]
    series = []
    for mi, date in enumerate(months):
        frac = (mi + 1) / len(months)  # 과거일수록 공실 적게
        regions = {}
        for rk, endc in final.items():
            base = max(0, round(endc * frac + random.uniform(-0.6, 0.6)))
            if mi == len(months) - 1:
                base = endc  # 마지막 지점은 현재값과 일치
            regions[rk] = base
        series.append({"date": date, "total": sum(regions.values()), "regions": regions})
    with open(os.path.join(DATA_DIR, "vacant_history.json"), "w", encoding="utf-8") as f:
        json.dump({"series": series}, f, ensure_ascii=False, separators=(",", ":"))

    print(f"샘플 생성: 영업중 {len(operating)}건 / 공실추정 {len(vacant)}건 → data/shops.json")
    print(f"시계열 샘플: {len(series)}개 시점 × {len(final)}개 지역 → data/vacant_history.json")


if __name__ == "__main__":
    main()
