<p align="center"><img src="assets/banner.png" alt="시공 고객 문의를 정리하고 빠진 정보를 표시하는 Contractor Inquiry Intake" width="100%"></p>

<p align="center">
  <a href="https://github.com/kks0488/contractor-inquiry-intake/actions/workflows/ci.yml"><img src="https://github.com/kks0488/contractor-inquiry-intake/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB" alt="Python 3.11 이상">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-527a49" alt="MIT 라이선스"></a>
  <img src="https://img.shields.io/badge/no_API_key-offline_rules-d6a646" alt="API 키 없이 실행 가능">
</p>

<p align="center"><a href="README.md">English</a> · <strong>한국어</strong></p>

<h2 align="center">문의는 정리하고, 빠진 정보는 분명하게.</h2>

목공·인테리어·리모델링 고객 문의를 읽어 **연락처, 공사 종류, 현장 위치, 희망 일정, 예산 단서**를 정리하는 작은 데모입니다. 원문에 없는 내용은 만들어 넣지 않고 **MISSING**으로 표시합니다. 같은 문의는 한 번만 저장하고, 사장님이 확인할 요약을 보여 줍니다.

<table>
  <tr><td width="50%"><strong>원문을 근거로</strong><br>추출한 값이 원문에 있는지 확인합니다. 알 수 없는 주소나 예산은 채우지 않습니다.</td><td><strong>다음에 물어볼 것까지</strong><br>연락처·위치·공사 내용·일정·예산 중 빠진 항목을 표시합니다.</td></tr>
  <tr><td><strong>중복 문의 정리</strong><br>같은 내용을 다시 실행해도 CSV에 행이 늘어나지 않습니다.</td><td><strong>작게 시작</strong><br>CSV와 콘솔로 바로 실행합니다. Google Sheets와 Slack은 선택 사항입니다.</td></tr>
</table>

```text
이메일 원문 / 웹 폼 JSON → 정보 추출·근거 확인 → 중복 제거
                                                 ↓
                                   CSV 저장 → Google Sheets 선택 연결
                                                 ↓
                                   콘솔 요약 → Slack 선택 알림
```

## 바로 실행하기

Python 3.11 이상이 필요합니다. API 키 없이 실행할 수 있습니다.

```sh
git clone https://github.com/kks0488/contractor-inquiry-intake.git
cd contractor-inquiry-intake
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

contractor-intake samples --rules-only --local-only \
  --csv output/demo.csv --table output/demo.md
```

가상 문의 10건에서 **신규 9건, 중복 1건, 오류 0건**이 나옵니다. 같은 명령을 다시 실행하면 **신규 0건, 중복 10건**이며 기존 CSV 9행이 유지됩니다. `python -m contractor_inquiry_intake`로도 실행할 수 있습니다.

`--rules-only`는 키가 있어도 LLM을 호출하지 않습니다. `--local-only`는 Sheets와 Slack을 끕니다. 키를 설정하지 않으면 자동으로 규칙 기반 추출을 사용합니다. 기본 의존성은 HTTPX와 filelock이며, 데이터베이스나 웹 서버는 필요하지 않습니다.

## 실제 LLM 실행 결과

**2026-10-16**, Nebius Token Factory의 `nvidia/Nemotron-3_5-Lightning`으로 실행했습니다. 중복을 제외한 9건을 모델에 보냈고, 열 번째 문의는 호출 전에 제외했습니다. 아래는 CLI가 만든 결과표이며, 고객 정보를 수작업으로 채우지 않았습니다.

<!-- SAMPLE_OUTPUT_START -->

| Source | Status | Contact | Project | Location | Timeline | Budget hint | MISSING | Extractor |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01_kitchen.txt | ADDED | Maya Ellis / maya.ellis@example.com / 202-555-0101 | Kitchen renovation | Cedar Hollow, OR | next month | $18,000-$22,000 | — | llm |
| 02_bookshelves.json | ADDED | Jonah Reed / jonah.reed@example.com | custom bookshelves | Maple Crossing, WA | within 6 weeks | $4,500 | — | llm |
| 03_deck_messy.txt | ADDED | Theo Park / 202.555.0103 | deck repair | Birch Cove, ME | ASAP | $2k max | — | llm |
| 04_bathroom.txt | ADDED | Elena Moss / elena.moss@example.com | Bathroom remodel | Pine Harbor, VT | before December 2026 | MISSING | budget_hint | llm |
| 05_missing_location.txt | ADDED | Sam Rivera / sam.rivera@example.com | built-in wardrobe with sliding doors | MISSING | within 8 weeks | around $6,000 | location | llm |
| 06_flooring.json | ADDED | Priya Lane / 202-555-0106 | flooring installation | Willow Bend, CO | MISSING | $9,000 | timeline | llm |
| 07_basement_messy.txt | ADDED | Owen Vale / owen.vale@example.com | basement finishing | Ash Grove, MN | next month | 15000 USD | — | llm |
| 08_door_no_contact.json | ADDED | Avery Stone | door repair | Elm Ridge, NC | next week | $500 | contact | llm |
| 09_vague_messy.txt | ADDED | Riley Finch / riley.finch@example.com | MISSING | Fox Hollow, PA | MISSING | MISSING | project_type, timeline, budget_hint | llm |
| 10_kitchen_duplicate.txt | DUPLICATE | — | — | — | — | — | — | — |

<!-- SAMPLE_OUTPUT_END -->

`samples/`의 인물과 문의는 모두 가상입니다. 이메일은 `example.com`, 전화번호는 가상 번호용 555-01xx를 사용합니다. 오타와 줄임말, 위치·예산·일정·연락처·공사 내용 누락, 중복 문의를 포함합니다. 실제 실행은 CSV와 콘솔만 사용했습니다. Sheets·Slack은 모의 호출 테스트로 확인했습니다.

## LLM 연결하기

기본값은 [Nebius 공식 안내](https://docs.tokenfactory.nebius.com/quickstart)의 주소를 사용합니다.

```sh
export LLM_BASE_URL=https://api.tokenfactory.nebius.com/v1
export LLM_MODEL=nvidia/Nemotron-3_5-Lightning
# LLM_API_KEY는 셸이나 비밀 관리 도구로 설정합니다.
contractor-intake samples --local-only --csv output/llm.csv --table output/llm.md
```

macOS 키체인에 이미 저장한 키라면 다음처럼 실행할 수 있습니다.

```sh
LLM_API_KEY="$(security find-generic-password -s nebius-token-factory -a kks0488 -w)" \
  contractor-intake samples --local-only --csv output/llm.csv
```

앱은 키를 파일에 쓰지 않으며 `.env`를 자동으로 읽지 않습니다. 지원하는 설정은 [`.env.example`](.env.example)에 있습니다. 키가 있으면 문의 원문을 설정된 LLM 주소로 보냅니다. 규칙 모드는 로컬에서 처리합니다.

응답은 [Chat Completions의 JSON 형식](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)으로 받고, 항목과 값의 형태를 검사합니다. 원문에서 찾을 수 없는 값은 버립니다. 대소문자·공백 차이는 허용하고, CSV의 `evidence`에 원문 근거를 남깁니다. 웹 폼의 명시된 값이 우선입니다. 기본 Nemotron 모델에는 긴 설명 대신 JSON을 받도록 `enable_thinking: false` 설정을 보내며, 실제 호출로 확인했습니다. 다른 모델 이름에는 일반 요청만 보냅니다.

시간 초과, API 오류, 잘못된 JSON·응답 형태, 잘린 응답은 `rules-fallback`으로 기록하고 규칙 추출로 이어 갑니다. 유료 호출을 자동 재시도하지 않습니다. 규칙은 영어의 흔한 공사 표현, `Location:`·`Timeline:`·`Budget:` 같은 표기, 이메일, 미국식 전화번호와 일부 일정·금액 표현을 지원합니다. 알아보지 못하는 표현은 누락으로 남습니다.

## 내 문의 넣기

파일 하나나 폴더를 지정합니다. 폴더는 이름순으로 읽으며 하위 폴더는 읽지 않습니다. UTF-8 `.txt`, 일반 텍스트 `.eml`, 파일당 웹 폼 객체 하나인 `.json`을 지원합니다. 첨부파일·HTML 메일 해석, 메일함 수집, 공개 웹 폼 서버는 포함하지 않습니다.

```json
{
  "name": "Jonah Reed",
  "email": "jonah.reed@example.com",
  "phone": null,
  "project_type": "custom bookshelves",
  "location": "Maple Crossing, WA",
  "timeline": "within 6 weeks",
  "budget_hint": "$4,500",
  "message": "Two alcoves beside the fireplace."
}
```

모든 항목은 선택 사항이며 문자열이나 `null`입니다. 빈 값·미정은 누락으로 처리하고, 지원하지 않는 항목은 무시합니다. `message`에는 자유롭게 문의를 적습니다. 잘못된 파일은 `ERROR`로 표시하고 나머지를 계속 처리하며, 입력 오류가 있으면 종료 코드 1을 반환합니다.

```sh
contractor-intake path/to/inquiry.json --csv data/inquiries.csv
contractor-intake path/to/email.txt --rules-only --local-only
```

| 출력 항목 | 의미 |
| --- | --- |
| `name`, `email`, `phone` | 고객 이름과 연락처. 이름만 있고 이메일·전화가 없으면 연락처 누락입니다. |
| `project_type`, `location`, `timeline`, `budget_hint` | 고객이 쓴 공사 내용·위치·일정·예산 단서. 주소를 완성하거나 날짜·예산을 계산하지 않습니다. |
| `missing` | 연락처·공사 내용·위치·일정·예산 중 빠진 항목. 이름은 필수가 아닙니다. |
| `evidence`, `extractor`, `warnings` | 원문 근거, 추출 방식, 버린 값이나 대체 처리 여부. |
| `inquiry_id`, `source`, `received_at` | 내용의 SHA-256 식별값, 입력 파일명, UTC 처리 시각. |

중복은 유니코드·대소문자·공백을 정리한 내용으로 판단합니다. JSON 항목 순서는 무관합니다. 같은 CSV를 써야 이전 기록과 비교합니다. 표현이 달라진 문의·전달 메일·내용이 바뀐 공사는 새 문의로 봅니다. 사람 이름으로 비슷한 문의를 합치지는 않습니다. CSV를 지우거나 바꾸면 중복 기록도 초기화됩니다. 파일 잠금으로 동시 저장 충돌을 막고, 수식으로 실행될 수 있는 CSV 값에는 작은따옴표를 붙입니다. `evidence`는 원문을 유지합니다.

## Google Sheets 선택 연결

CSV를 먼저 저장하고, 새 행을 [Google Sheets API](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append)로 추가합니다. 서비스 계정을 사용하며 값은 수식으로 해석하지 않는 `RAW`로 보냅니다.

1. Google Cloud에서 Sheets API를 켜고 서비스 계정을 만듭니다. JSON 인증 파일은 **저장소 밖**에 둡니다.
2. 스프레드시트에 `Inquiries` 탭을 만들고, 인증 파일의 `client_email`에 편집 권한을 줍니다.
3. A–N열 첫 행에 아래 항목을 넣습니다. 쉼표 구분이므로 붙여넣은 뒤 열 분리에서 쉼표를 선택하거나, 로컬 CSV 첫 행을 복사합니다.

```text
inquiry_id,source,name,email,phone,project_type,location,timeline,budget_hint,missing,extractor,evidence,warnings,received_at
```

```sh
python -m pip install -e '.[sheets]'
export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/outside/repo/credentials.json
export GOOGLE_SHEET_ID=your-spreadsheet-id
export GOOGLE_SHEET_RANGE='Inquiries!A:N'
contractor-intake path/to/new-inquiries --csv data/inquiries.csv
```

앱이 스프레드시트나 탭을 만들지는 않습니다. 인증·설치·통신 오류가 나도 CSV는 남습니다. 이미 저장한 문의를 다시 실행해도 Sheets에 재전송하지 않으므로, 실패한 경우 보관된 CSV를 직접 가져오면 됩니다. 자동 재전송·Sheets 대조 기능은 포함하지 않습니다.

## 사장님 알림

실행할 때마다 연락처·공사·위치·일정·예산·빠진 항목을 콘솔에 요약합니다. 환경변수 `SLACK_WEBHOOK_URL`을 설정하면 새 문의가 저장됐을 때 [Slack 웹훅](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)으로 요약 한 건도 보냅니다. 고객 문구는 일반 텍스트로 보내고, 알림이 실패해도 CSV는 유지합니다. Slack은 2,900자까지 보내며 전체 요약은 콘솔에서 확인합니다. 고객에게 자동 답장을 보내지는 않습니다.

## 실제 업체에서는 이렇게 연결합니다

| 현장에서 생기는 일 | 데모가 하는 일 |
| --- | --- |
| 작업 중 이메일·웹 문의가 들어옵니다. | 기존 수집 도구가 파일로 저장하고 이 CLI를 실행하도록 연결합니다. 수집 도구는 별도로 붙입니다. |
| 문의를 고객 목록에 옮겨야 합니다. | CSV와 선택 연결한 Google Sheet에 행을 만듭니다. |
| 현장 위치나 예산이 빠졌습니다. | 방문·견적 전에 물어볼 항목을 MISSING으로 표시합니다. |
| 고객이 제출 버튼을 두 번 누릅니다. | 같은 내용은 한 행으로 저장하고 새 문의 요약에도 한 번만 넣습니다. |
| 사장님이 하루 문의를 확인합니다. | 콘솔이나 Slack에서 새 문의와 확인할 내용을 봅니다. |

예산 단서는 고객이 말한 금액이며 업체의 견적이 아닙니다. 공사 범위·방문 가능 지역·일정·가격은 담당자가 검토합니다. 원문 확인은 없는 정보를 만드는 일을 막지만 항목 분류까지 완벽하게 보장하지는 않으므로 견적 전에 원문을 확인합니다. 실제 운영에는 문의 수집 연결, 접근 권한, 재전송·대조 절차를 더하면 됩니다. 로컬 기록에는 연락처와 원문 근거가 들어가며 `data/`·`output/`·환경 파일·일반적인 인증 파일명은 Git에서 제외합니다.

## 테스트와 개발

```sh
python -m pip install -e '.[dev,sheets]'
pytest -q
ruff check .
ruff format --check .
```

추출·누락·미정 표시·없는 근거 거절·API 오류·중복·동시 CSV 저장·수식 방지·잘못된 입력·CLI·Sheets/Slack 모의 호출을 검사합니다. CI는 Python 3.11·3.13에서 테스트와 오프라인 샘플 실행, Gitleaks 검사를 합니다. 테스트에 키나 외부 계정은 필요 없습니다. 첫 공개 푸시 전에 Git 전체 이력의 Gitleaks 검사를 마쳤습니다.

배너의 [HTML](assets/banner.html)과 [Playwright 렌더러](assets/render_banner.py)도 포함합니다. 배너를 다시 만들 때만 아래 도구가 필요합니다.

```sh
python -m pip install playwright
python -m playwright install chromium
python assets/render_banner.py
```

공개된 1600 × 720 배너는 기존 로컬 Playwright Python 환경에서 렌더링했습니다. 기여할 때는 가상 문의와 테스트를 넣고 두 README를 함께 갱신해 주세요.

## 라이선스

[MIT](LICENSE) © 2026 Kyoungsoo Kim.
