"""
소상공인시장진흥공단 상가(상권)정보 API 수집 스크립트
──────────────────────────────────────────────────────────────────────────
목적: 서울/경기 "빈 상가(공실)" 맵의 데이터 파이프라인.

■ 중요한 사실(설계 근거)
  1) 이 공공 API는 '현재 영업 중인' 상가업소 목록만 제공합니다.
     → 공실/임대료/보증금/연락처/전용면적(평수) 항목은 애초에 없습니다.
     따라서 임대료·연락처를 랜덤으로 지어내지 않습니다(그건 허위정보).
  2) '빈 상가'는 스냅샷 차분(diff)으로 추정합니다.
     같은 지역을 주기적으로 조회해, 지난 스냅샷엔 있었지만 이번엔 사라진
     상가업소(bizesId)를 '폐업 → 공실 추정' 후보로 잡습니다.
     - 최초 실행에는 비교할 이전 스냅샷이 없으므로 공실은 0건입니다(정상).
     - 이 데이터는 분기 단위로 갱신되므로, 공실 신호는 분기마다 쌓입니다.
  3) 브라우저에서 data.go.kr를 직접 fetch하면 CORS로 실패합니다.
     그래서 수집은 서버(GitHub Actions)에서 하고, 결과 JSON만 정적으로 서빙합니다.
     (이 저장소의 국토부 실거래가 파이프라인과 동일한 구조)

■ 실행 준비
  - GitHub Actions secrets(또는 로컬 env)에 SEMAS_API_KEY 등록.
    · data.go.kr '일반 인증키(Decoding)'를 넣는 것을 권장합니다.
    · '%2F', '%2B', '%3D' 처럼 이미 URL 인코딩된 키(Encoding)를 넣어도
      아래 코드가 자동 판별해 처리합니다.
  - 하드코딩 금지(README 헌법 제2조). 반드시 본인 키를 secrets로 주입.
──────────────────────────────────────────────────────────────────────────
"""

import os
import json
import time
import urllib.parse
from datetime import datetime, timezone, timedelta

import requests

KST = timezone(timedelta(hours=9))

# ── 인증키 로드 (Encoding/Decoding 키 자동 판별) ──────────────────────────
_RAW_KEY = os.environ.get("SEMAS_API_KEY", "").strip()
if not _RAW_KEY:
    raise SystemExit(
        "SEMAS_API_KEY 미설정 — GitHub Actions secrets에 소상공인시장진흥공단 "
        "상가정보 API 인증키를 넣으세요. (Settings → Secrets and variables → Actions)"
    )
# '%'가 들어 있으면 이미 인코딩된 키로 보고 한번 디코딩해 원본으로 통일한다.
API_KEY = urllib.parse.unquote(_RAW_KEY) if "%" in _RAW_KEY else _RAW_KEY

# 이미지의 End Point: https://apis.data.go.kr/B553077/api/open/sdsc2
BASE = "https://apis.data.go.kr/B553077/api/open/sdsc2"

# ── 조회 대상: 서울/경기 주요 상권 중심점 (반경 조회) ─────────────────────
#   반경(radius) 조회는 좌표만 있으면 되고, 결과 크기가 자연스럽게 제한되어
#   지도 서비스에 가장 적합합니다. (행정동 코드가 틀릴 위험도 없음)
#   radius 단위: m (API 상한 대략 2000m). 필요 지역을 자유롭게 추가/편집하세요.
CENTERS = [
    # name,            경도(lon/cx), 위도(lat/cy),  반경(m)
    ("서울 강남역",      127.02758,   37.49794,    1000),
    ("서울 홍대입구",     126.92392,   37.55692,    1000),
    ("서울 성수동",       127.05602,   37.54467,    1000),
    ("서울 종로",        126.98955,   37.57037,    1000),
    ("수원역",          127.00060,   37.26586,    1200),
    ("수원 인계동",      127.03157,   37.27139,    1000),
    ("성남 서현역",      127.12480,   37.38542,    1000),
    ("성남 판교역",      127.11122,   37.39481,    1000),
    ("용인 수지 죽전",    127.10842,   37.32460,    1000),
    ("안양 범계역",      126.95090,   37.38996,    1000),
    ("부천 상동",        126.75470,   37.50390,    1000),
    ("평택역",          127.08469,   36.99236,    1200),
]

NUM_OF_ROWS = 1000          # 페이지당 최대
MAX_PAGES_PER_CENTER = 5    # 중심점당 최대 페이지 (과다 수집 방지)
MAX_OPERATING_OUTPUT = 25000  # 지도용 영업중 포인트 상한(파일 크기·렌더 성능)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SHOPS_JSON = os.path.join(DATA_DIR, "shops.json")           # 지도가 읽는 파일
SNAPSHOT_JSON = os.path.join(DATA_DIR, "shops_snapshot.json")  # 차분용 이전 스냅샷
VACANT_JSON = os.path.join(DATA_DIR, "vacant.json")         # 공실 후보 누적 상태

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; vacant-shop-map/1.0)",
    "Accept": "application/json, text/json, */*",
}


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _norm_item(it):
    """API item → 앱 내부 표준 레코드. 좌표 없으면 None."""
    lon = _to_float(it.get("lon"))
    lat = _to_float(it.get("lat"))
    if lon is None or lat is None:
        return None
    # 대한민국 범위 밖 좌표 방어
    if not (124 <= lon <= 132 and 33 <= lat <= 39):
        return None
    return {
        "id": (it.get("bizesId") or "").strip(),
        "name": (it.get("bizesNm") or "").strip(),
        "branch": (it.get("brchNm") or "").strip(),
        "indsL": (it.get("indsLclsNm") or "").strip(),   # 업종 대분류(예: 음식)
        "indsM": (it.get("indsMclsNm") or "").strip(),   # 중분류
        "indsS": (it.get("indsSclsNm") or "").strip(),   # 소분류
        "flr": (it.get("flrNo") or "").strip(),          # 층
        "signgu": (it.get("signguNm") or "").strip(),
        "adong": (it.get("adongNm") or "").strip(),
        "addr_jibun": (it.get("lnoAdr") or "").strip(),  # 지번주소
        "addr_road": (it.get("rdnmAdr") or "").strip(),  # 도로명주소
        "bld": (it.get("bldNm") or "").strip(),
        "lon": round(lon, 6),
        "lat": round(lat, 6),
    }


def fetch_radius(cx, cy, radius):
    """storeListInRadius: 중심 좌표 반경 내 상가업소 목록 (페이지네이션)."""
    out = []
    for page in range(1, MAX_PAGES_PER_CENTER + 1):
        # serviceKey는 이미 원본(디코딩) 상태 → requests의 params 인코딩에 맡긴다.
        params = {
            "serviceKey": API_KEY,
            "radius": int(radius),
            "cx": cx,
            "cy": cy,
            "numOfRows": NUM_OF_ROWS,
            "pageNo": page,
            "type": "json",
        }
        try:
            resp = requests.get(
                f"{BASE}/storeListInRadius",
                params=params, headers=HEADERS, timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except ValueError:
            # JSON이 아니면(에러 XML 등) 본문 앞부분을 찍어 원인 파악을 돕는다.
            print(f"    ! JSON 파싱 실패 (page {page}). 응답: {resp.text[:300]}")
            break
        except Exception as e:
            print(f"    ! 요청 실패 (page {page}): {e}")
            break

        header = data.get("header", {}) or {}
        code = str(header.get("resultCode", "")).strip()
        if code and code not in ("00", "000"):
            print(f"    ! API 오류 resultCode={code} msg={header.get('resultMsg')}")
            break

        body = data.get("body", {}) or {}
        items = body.get("items", []) or []
        if isinstance(items, dict):  # 단건일 때 dict로 오는 경우 방어
            items = [items]
        for it in items:
            rec = _norm_item(it)
            if rec and rec["id"]:
                out.append(rec)

        total = int(body.get("totalCount", 0) or 0)
        if page * NUM_OF_ROWS >= total or not items:
            break
        time.sleep(0.15)  # rate limit 배려
    return out


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def main():
    now = datetime.now(KST)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print("=== 소상공인 상가정보 수집 시작 ===")

    # 1) 현재 영업 상가 수집 (중심점별, 중복 제거)
    operating = {}
    for name, cx, cy, radius in CENTERS:
        recs = fetch_radius(cx, cy, radius)
        for r in recs:
            operating[r["id"]] = r  # bizesId 기준 dedup
        print(f"  [{name}] {len(recs)}건 (누적 고유 {len(operating)}건)")
        time.sleep(0.2)

    cur_ids = set(operating.keys())
    if not cur_ids:
        print("수집 0건 — 인증키/네트워크/파라미터를 확인하세요. shops.json 미변경.")
        return

    # 2) 이전 스냅샷과 차분 → 공실(폐업) 후보 갱신
    prev_snap = load_json(SNAPSHOT_JSON, {})
    prev_ids = set(prev_snap.get("shops", {}).keys())
    vacant_state = load_json(VACANT_JSON, {})  # id -> vacant record

    disappeared = prev_ids - cur_ids            # 지난번엔 있었는데 사라짐 = 공실 추정
    reappeared = cur_ids & set(vacant_state)    # 다시 영업 = 공실 해제

    for vid in reappeared:
        vacant_state.pop(vid, None)

    prev_shops = prev_snap.get("shops", {})
    for vid in disappeared:
        if vid in vacant_state:
            continue  # 이미 공실로 추적 중
        last = prev_shops.get(vid)
        if not last:
            continue
        rec = dict(last)
        rec["first_missing"] = now_str        # 공실 최초 감지 시점
        vacant_state[vid] = rec

    # 공실 경과(개월) 계산
    vacant_list = []
    for vid, rec in vacant_state.items():
        try:
            fm = datetime.strptime(rec["first_missing"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
            months = max(0, round((now - fm).days / 30.4))
        except Exception:
            months = 0
        item = dict(rec)
        item["months_vacant"] = months
        vacant_list.append(item)
    vacant_list.sort(key=lambda x: x.get("first_missing", ""), reverse=True)

    # 3) 지도용 shops.json 작성
    operating_list = list(operating.values())
    if len(operating_list) > MAX_OPERATING_OUTPUT:
        operating_list = operating_list[:MAX_OPERATING_OUTPUT]

    # 업종 대분류 집계(필터 UI용)
    inds_counts = {}
    for r in operating_list:
        inds_counts[r["indsL"] or "기타"] = inds_counts.get(r["indsL"] or "기타", 0) + 1

    output = {
        "meta": {
            "generated_at": now_str,
            "sample": False,
            "source": "소상공인시장진흥공단 상가(상권)정보 API (data.go.kr B553077)",
            "method": "storeListInRadius 반경 조회 + 스냅샷 차분 공실 추정",
            "centers": [c[0] for c in CENTERS],
            "operating_count": len(operating_list),
            "vacant_count": len(vacant_list),
            "inds_counts": inds_counts,
            "note": (
                "공실은 이전 조회 대비 사라진 업소를 추정한 값입니다. "
                "임대료·보증금·연락처·전용면적은 본 공공데이터에 포함되지 않아 "
                "매물 검색 링크로 안내합니다."
            ),
        },
        "operating": operating_list,
        "vacant": vacant_list,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SHOPS_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    # 4) 스냅샷/공실 상태 저장 (다음 차분용)
    snap = {
        "generated_at": now_str,
        "shops": {
            r["id"]: {
                "id": r["id"], "name": r["name"], "indsL": r["indsL"],
                "flr": r["flr"], "signgu": r["signgu"], "adong": r["adong"],
                "addr_jibun": r["addr_jibun"], "addr_road": r["addr_road"],
                "lon": r["lon"], "lat": r["lat"],
            }
            for r in operating.values()
        },
    }
    with open(SNAPSHOT_JSON, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, separators=(",", ":"))
    with open(VACANT_JSON, "w", encoding="utf-8") as f:
        json.dump(vacant_state, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n=== 완료: 영업중 {len(operating_list)}건 / 공실추정 {len(vacant_list)}건 ===")
    print(f"  이번 사라짐(신규 공실): {len(disappeared - reappeared)}건, "
          f"영업재개(공실 해제): {len(reappeared)}건")
    if not prev_ids:
        print("  (최초 실행: 비교할 이전 스냅샷이 없어 공실 0건은 정상입니다.)")


if __name__ == "__main__":
    main()
