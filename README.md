# 윤서온 — 홈 + 별자리 대시보드 (단일 페이지)

키 없는 공개 API 3개(환율 · 코인 · 서울 날씨)로 **수집 → 저장 → 정적 페이지에서 계산·표시** 를 재현한 뼈대.
홈(작가 페이지)과 대시보드가 `index.html` 한 파일 안에 있고, 프로젝트 카드나 상단 버튼을 누르면 페이지 이동 없이 대시보드 뷰로 전환된다.

```
index.html                      홈 + 대시보드(#dashboard). 서버 불필요
data/<id>.json                  지표별 시계열 저장본  ← Actions가 만들어 커밋
data/index.json                 지표 목록
collector/fetch.py              수집기 (파이썬 표준 라이브러리만)
.github/workflows/collect.yml   6시간마다 수집기 실행 후 data/ 커밋
```

## 주소 체계

- `…/`                      홈
- `…/#now`, `#books`, `#projects`, `#about`, `#taste`   홈의 각 섹션
- `…/#dashboard`             대시보드
- `…/#dashboard/btckrw`      특정 지표를 연 상태로 공유 (대시보드의 "이 화면 링크 복사" 버튼이 이 형식을 복사)

뒤로 가기·새로고침 모두 해시 기준으로 동작한다.

## 데이터 흐름

대시보드는 지표 그룹마다 이 순서로 시도한다.

1. `./data/<id>.json` — 저장본. GitHub Pages로 올리면 이게 잡힌다.
2. 공개 API 직접 호출 — 저장본이 없을 때(예: 파일을 로컬에서 바로 열었을 때).
3. 가상 샘플 — 둘 다 막힌 환경(외부 요청이 차단된 호스팅). 화면 형태 확인용이며 값은 의미 없다. 상단 상태 표시와 카드의 점 색으로 구분된다.

홈의 "지금" 위젯도 같은 원리(공개 API → 샘플)다. 홈 위젯이 끝나면 대시보드 데이터를 미리 받아 두므로, 카드를 눌렀을 때 바로 열린다.

계산(기간 필터 → 주/월 집계 → 지수화 → 겹쳐보기 → 통계 → CSV)은 전부 브라우저에서 배열 연산으로 한다. 서버는 없다.

## 공유하는 법

### 1) Claude 아티팩트로 게시 (바로 링크 공유)
`index.html`을 아티팩트로 게시하면 claude.ai 링크가 생기고, 공유 설정을 켜면 남에게 보낼 수 있다.
다만 그 호스팅은 외부 API 호출을 막으므로 위젯·대시보드는 **가상 샘플**로 뜬다. 디자인·동작 확인과 공유용.

### 2) GitHub Pages + Actions (실제 데이터)
1. 새 저장소 만들고 이 폴더 통째로 push.
2. 저장소 **Settings → Actions → General → Workflow permissions** 에서 *Read and write permissions* 선택 (커밋 권한).
3. **Actions** 탭 → `collect` → *Run workflow* 로 한 번 수동 실행. 끝나면 `data/*.json`이 커밋돼 있다.
4. **Settings → Pages** → Source: *Deploy from a branch*, Branch: `main` / `/ (root)`.
5. 잠시 뒤 `https://<아이디>.github.io/<저장소>/` 가 홈, `…/#dashboard` 가 대시보드. 대시보드 상단 상태가 "저장본 YYYY-MM-DD" 로 뜨면 완성.

이후에는 6시간마다 알아서 갱신된다. 주기는 `collect.yml`의 cron 한 줄.

## 로컬에서 확인

- `index.html` 더블클릭 → 저장본은 못 읽고(file:// 제약) API 직접 호출로 뜬다.
- 저장본까지 보려면 폴더에서 `python -m http.server 8000` 후 `http://localhost:8000`.
- 수집기만 돌려보기: `python collector/fetch.py` (표준 라이브러리만 씀).

## 지표 추가

`collector/fetch.py`의 `REGISTRY`와 `index.html`의 `INDICATORS`에 같은 `id`로 항목을 넣고, 해당 그룹의 fetch 함수가 그 id를 반환하게 하면 끝. 새 API를 붙일 때는 그룹 하나(`fetch_<group>` + `LIVE.<group>`)를 추가한다.

키가 필요한 API(한국은행 ECOS, 공공데이터포털 등)는 **수집기에서만** 호출하고 키는 저장소 *Settings → Secrets* 에 넣어 `os.environ`으로 읽는다. `index.html`에는 절대 넣지 않는다.

## 콘텐츠 바꾸기

이름·소개·책·프로젝트·링크는 `index.html` 안의 `SITE` 객체 한 곳에 모여 있다. `[이메일 주소]`, `[URL]` 자리는 실제 값으로 채운다. 배경은 항상 검푸른 밤하늘(별밭은 정적 캔버스, 애니메이션 없음)이고 시스템 라이트/다크 설정을 따르지 않는다.

## 주의

- CoinGecko 무료 티어는 분당 요청 제한이 있어 로컬에서 새로고침을 연타하면 잠시 실패한다. 저장본을 쓰면 무관.
- Open-Meteo 아카이브는 며칠 지연된다. 수집기가 `오늘-6일`까지만 요청하는 이유.
- 수집기는 0건이 오면 기존 파일을 덮어쓰지 않는다. 깨졌을 때 마지막 정상 데이터가 남는다.
