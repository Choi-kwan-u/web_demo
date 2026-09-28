#!/usr/bin/env python3
"""
수집기 — 공개 API에서 시계열을 받아 data/<id>.json 으로 저장한다.

- 표준 라이브러리만 사용 (requests 불필요)
- 처음 실행: 약 2년치 전체 수집
- 이후 실행: 마지막 저장 날짜 7일 전부터 다시 받아 병합 (수정치 반영)
- 결과 파일 형식은 index.html(대시보드 뷰)이 읽는 형식과 동일:
    {"id", "name", "unit", "source", "updated", "points": [["YYYY-MM-DD", value], ...]}

새 지표를 추가하려면:
  1) REGISTRY 에 항목 추가 (id 는 index.html 의 INDICATORS 와 같게)
  2) 해당 group 의 fetch_<group>() 이 그 id 를 반환하도록 수정
"""
import json
import sys
import datetime as dt
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = "agro-demo-collector (github actions; contact: repo owner)"
FULL_DAYS = 730          # 첫 수집 범위
OVERLAP_DAYS = 7         # 증분 수집 시 되돌아가는 일수

REGISTRY = [
    {"id": "usdkrw",     "name": "원/달러",        "unit": "원",  "group": "fx",      "source": "Frankfurter (ECB)"},
    {"id": "jpykrw",     "name": "원/100엔",       "unit": "원",  "group": "fx",      "source": "Frankfurter (ECB)"},
    {"id": "eurkrw",     "name": "원/유로",        "unit": "원",  "group": "fx",      "source": "Frankfurter (ECB)"},
    {"id": "btckrw",     "name": "비트코인",       "unit": "원",  "group": "coin",    "source": "CoinGecko"},
    {"id": "ethkrw",     "name": "이더리움",       "unit": "원",  "group": "coin",    "source": "CoinGecko"},
    {"id": "seoul_temp", "name": "서울 일평균 기온", "unit": "°C", "group": "weather", "source": "Open-Meteo 아카이브"},
    {"id": "seoul_rain", "name": "서울 일강수량",   "unit": "mm",  "group": "weather", "source": "Open-Meteo 아카이브"},
]


# ───────────── 공통 ─────────────
def get(url: str, timeout: int = 40):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def load_existing(ind_id: str):
    p = DATA / f"{ind_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def start_date_for(ids) -> dt.date:
    """그룹 내 지표들의 마지막 날짜 중 가장 이른 것 - OVERLAP_DAYS. 없으면 FULL_DAYS 전."""
    lasts = []
    for i in ids:
        ex = load_existing(i)
        if ex and ex.get("points"):
            lasts.append(dt.date.fromisoformat(ex["points"][-1][0]))
    if not lasts:
        return today() - dt.timedelta(days=FULL_DAYS)
    return min(lasts) - dt.timedelta(days=OVERLAP_DAYS)


def merge(old_points, new_points):
    m = {d: v for d, v in (old_points or [])}
    for d, v in new_points:
        if v is not None:
            m[d] = v
    return [[d, m[d]] for d in sorted(m)]


def save(ind: dict, points):
    DATA.mkdir(parents=True, exist_ok=True)
    ex = load_existing(ind["id"])
    merged = merge(ex["points"] if ex else [], points)
    out = {
        "id": ind["id"], "name": ind["name"], "unit": ind["unit"], "source": ind["source"],
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "points": merged,
    }
    (DATA / f"{ind['id']}.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  {ind['id']:12s} {len(points):5d}건 수신 → 총 {len(merged):5d}건, 마지막 {merged[-1][0] if merged else '-'}")


# ───────────── 그룹별 수집 ─────────────
def fetch_fx(start: dt.date) -> dict:
    d = get(f"https://api.frankfurter.dev/v1/{start.isoformat()}..?base=USD&symbols=KRW,JPY,EUR")
    dates = sorted(d["rates"])
    return {
        "usdkrw": [[t, d["rates"][t]["KRW"]] for t in dates],
        "jpykrw": [[t, round(d["rates"][t]["KRW"] / d["rates"][t]["JPY"] * 100, 4)] for t in dates],
        "eurkrw": [[t, round(d["rates"][t]["KRW"] / d["rates"][t]["EUR"], 4)] for t in dates],
    }


def fetch_coin(start: dt.date) -> dict:
    days = min(365, max(2, (today() - start).days + 1))   # 무료 티어: 365일 이내가 안전

    def one(coin):
        d = get(f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=krw&days={days}")
        m = {}
        for ts, v in d["prices"]:                          # 하루에 여러 점이면 마지막 값
            m[dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc).date().isoformat()] = round(v, 2)
        return [[k, m[k]] for k in sorted(m)]

    return {"btckrw": one("bitcoin"), "ethkrw": one("ethereum")}


def fetch_weather(start: dt.date) -> dict:
    end = today() - dt.timedelta(days=6)                   # 아카이브는 며칠 지연
    d = get("https://archive-api.open-meteo.com/v1/archive?latitude=37.5665&longitude=126.978"
            f"&start_date={start.isoformat()}&end_date={end.isoformat()}"
            "&daily=temperature_2m_mean,precipitation_sum&timezone=Asia%2FSeoul")
    t = d["daily"]["time"]
    return {
        "seoul_temp": [[t[i], v] for i, v in enumerate(d["daily"]["temperature_2m_mean"]) if v is not None],
        "seoul_rain": [[t[i], v] for i, v in enumerate(d["daily"]["precipitation_sum"]) if v is not None],
    }


FETCHERS = {"fx": fetch_fx, "coin": fetch_coin, "weather": fetch_weather}


# ───────────── 실행 ─────────────
def main() -> int:
    failures = 0
    for group, fn in FETCHERS.items():
        inds = [i for i in REGISTRY if i["group"] == group]
        start = start_date_for([i["id"] for i in inds])
        print(f"[{group}] {start} 부터")
        try:
            got = fn(start)
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TimeoutError) as e:
            failures += 1
            print(f"  실패: {e!r} — 기존 저장본 유지")
            continue
        for ind in inds:
            pts = got.get(ind["id"], [])
            if not pts:                                    # 0건이면 기존 파일을 덮어쓰지 않는다
                failures += 1
                print(f"  {ind['id']}: 0건 — 건너뜀")
                continue
            save(ind, pts)

    index = {
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "indicators": [{k: i[k] for k in ("id", "name", "unit", "group", "source")} for i in REGISTRY
                       if (DATA / f"{i['id']}.json").exists()],
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"index.json: {len(index['indicators'])}개 지표, 실패 {failures}건")
    return 0                                               # 일부 실패해도 나머지는 커밋되게 0 반환


if __name__ == "__main__":
    sys.exit(main())
