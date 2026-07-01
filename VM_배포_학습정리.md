# VM 배포 학습 정리 (초보자용)

> 2026-07-01, RFP RAG 프로젝트를 **GCP VM에 자체호스팅 배포**하며 배운 것 정리.
> "VM을 처음 만지는 사람"이 개념부터 실제 명령·오류해결까지 따라올 수 있게 정리한다.

---

## 0. 한눈에 — 오늘 우리가 한 일

```
내 노트북(Windows)                    GCP VM (리눅스 서버, 인터넷 어딘가)
  - 코드 작성/커밋                       - EXAONE 오픈소스 LLM 실행 (Ollama)
  - git push  ───────────────▶  git pull  - bge-m3 임베딩 + ChromaDB 검색
                                        - FastAPI (검색·질의응답 API)
                                        - 이 위에서 "RFP 추천/답변" 서비스가 돎
```

**핵심 개념**: 오픈소스 모델(EXAONE)은 OpenAI처럼 남의 서버에 요청하는 게 아니라,
**내가 빌린 컴퓨터(VM)에 직접 올려서 돌린다.** 그래서 "VM 세팅"이 필요하다.

---

## 1. VM이 뭐야?

- **VM(Virtual Machine, 가상머신)** = 클라우드(GCP 등)에서 빌리는 **인터넷 너머의 컴퓨터 한 대**.
- 우리 건 **GPU(L4)** 가 달린 리눅스(Ubuntu) 서버. GPU가 있어야 LLM이 빠르게 돈다.
- 내 노트북이 꺼져도 VM은 계속 켜져 있다 → **24시간 서비스**를 올릴 수 있다.
- 접속은 화면(모니터)이 아니라 **터미널(명령어)** 로 한다. 그래서 명령어를 배우는 것.

### 우리 VM의 정체 (오늘 알아낸 것)
- GCP Compute Engine 인스턴스: 프로젝트 `sprint-ai-chunk2-02`, 존 `us-central1-c`, 이름 `sprint-ai10-team2`
- **JupyterHub** 위에서 돌아감 → 우리는 **브라우저(JupyterLab)** 로 접속. (일반 SSH 대신)
- `sudo`(관리자 권한) 없음 → 시스템 폴더 설치 불가 → **우회법**을 많이 썼다(아래 참고).

---

## 2. 접속 방법 (오늘 쓴 것)

| 방법 | 설명 | 우리 상황 |
|------|------|-----------|
| **JupyterLab 웹** | 브라우저로 열리는 노트북+터미널 | ✅ 주 접속 |
| **GCP 브라우저 SSH** | GCP 콘솔에서 여는 터미널(`ssh.cloud.google.com`) | ✅ 가능 |
| 일반 SSH / gcloud | 내 노트북 터미널에서 직접 접속 | ❌ (gcloud 미설치, 공인IP 없음) |

> 교훈: 접속 방식에 따라 "외부에서 서비스에 접근하는 법"이 완전히 달라진다(§7).

---

## 3. 꼭 알아야 할 개념 8가지 (오늘 다 썼다)

### ① 가상환경 (venv) — `source ~/ragenv/bin/activate`
- 파이썬 패키지를 프로젝트별로 **격리**하는 상자. 켜면 프롬프트 앞에 `(ragenv)` 가 붙는다.
- **매번 새 터미널을 열면 꺼진다** → 명령 전에 `(ragenv)` 있는지 확인, 없으면 다시 activate.
- 오늘 오류: `ModuleNotFoundError: No module named 'pydantic_settings'`
  → **venv를 안 켜서** 시스템 파이썬을 쓴 것. `source ~/ragenv/bin/activate` 하면 해결.

### ② PATH / export — `export PATH=$HOME/ollama/bin:$PATH`
- **PATH** = "명령어를 어느 폴더에서 찾을지" 목록. Ollama를 홈에 깔아서, 그 위치를 PATH에 추가해야 `ollama` 명령이 먹는다.
- `export` 로 넣은 값도 **새 터미널이면 사라진다** → 다시 export.

### ③ Ollama — 오픈소스 LLM을 돌리는 프로그램
- `ollama serve` : 모델 서버를 켠다(포트 11434에서 대기).
- `ollama pull exaone3.5:7.8b` : 모델을 내려받는다.
- `ollama list` / `ollama ps` : 받은/실행중 모델 확인. `ollama stop <모델>` : 메모리에서 내림.
- **왜 우리 코드가 `provider=openai` 인데 Ollama가 되나?** → Ollama가 "OpenAI와 똑같은 모양의 API"를
  제공해서, **주소(`base_url`)만 Ollama(`localhost:11434`)로 바꾸면** 코드 변경 없이 그대로 쓴다.

### ④ 포트(port)와 주소 — `localhost`, `127.0.0.1`, `0.0.0.0`
- **포트** = 한 컴퓨터 안에서 프로그램마다 붙는 번호(문 번호). 예: Ollama 11434, 우리 API 8500, JupyterHub 8000.
- `localhost` = `127.0.0.1` = **"이 컴퓨터 자신"**. VM에서 `localhost`는 VM, 내 노트북에서 `localhost`는 내 노트북.
- `0.0.0.0` = "모든 네트워크에서 접속 받음"(외부 노출). `127.0.0.1` = "내 컴퓨터 안에서만".
- 오늘 최대 삽질: **노트북 데모가 "연결 거부"** → 데모를 **로컬 PC**에서 돌려서 `localhost:8500`이
  내 PC를 가리킨 것. API는 VM에 있으니 당연히 없다. → **VM 안(JupyterLab)에서 노트북을 돌려야** 맞다.

### ⑤ 백그라운드 실행 — `nohup ... > 로그 2>&1 & disown`
- 터미널을 닫아도 프로그램이 **계속 돌게** 하는 주문.
  - `nohup` : 터미널이 닫혀도(HUP 신호) 죽지 말라
  - `> ~/api.log 2>&1` : 출력을 로그 파일로 보냄
  - `&` : 백그라운드로
  - `disown` : 현재 셸과의 연결 끊기
- 왜? JupyterHub 서버가 자주 "not running" 되며 터미널이 끊겨도 **작업(모델 실험/서버)이 살아있게** 하려고.

### ⑥ 프로세스 관리 — `ps`, `pkill`, `curl`로 확인
- `ps aux | grep uvicorn` : 그 프로그램이 돌고 있나 확인
- `pkill -f "uvicorn src.api"` : 그 프로그램 종료
- `curl -s localhost:8500/health` : 서버가 살아있나 HTTP로 찔러보기

### ⑦ 메모리(RAM/GPU) — 왜 "한 개씩"?
- LLM은 메모리를 많이 먹는다. 여러 개를 동시에 올리면 **메모리 부족으로 VM이 멈춘다**(오늘 실제 발생).
- 대책: **모델 1개씩 실행 + 끝나면 `ollama stop`** 으로 회수. `free -h` 로 여유 확인.

### ⑧ 방화벽 / 외부 노출
- VM은 보안상 **정해진 포트만 인터넷에 열려 있다**. 우리 VM은 **8000(JupyterHub)** 과 22(SSH)만 열림.
- 그래서 우리 API(8500)를 **외부 브라우저에서 직접** 열 수는 없었다(§7에서 우회).

---

## 4. 실전 명령어 모음 (복붙용 runbook)

### (A) 접속 후 항상 하는 "환경 복구" — 새 터미널마다
```bash
cd ~/rfp-rag-extractor                 # 프로젝트 폴더로
source ~/ragenv/bin/activate           # 가상환경 켜기 → (ragenv) 확인
export PATH=$HOME/ollama/bin:$PATH      # ollama 명령 인식
```

### (B) Ollama 서버 확인/켜기
```bash
curl -s localhost:11434/api/tags >/dev/null && echo "ollama OK" \
  || (nohup ollama serve > ~/ollama.log 2>&1 & disown)
ollama list                            # 받은 모델 확인
```

### (C) 최신 코드/설정 받기
```bash
git pull                               # 내 노트북에서 push한 것 받기
cp .env.ollama.example .env            # EXAONE 배포 설정 적용
```

### (D) 검색 인덱스 적재 (한 번)
```bash
python -m scripts.ingest               # chunks.csv → bge-m3 임베딩 → ChromaDB
```

### (E) 빠른 동작 테스트
```bash
python -m scripts.ask "이 사업의 예산과 과업기간은?"
```

### (F) API 상시 구동 (서비스)
```bash
pkill -f "uvicorn src.api"; sleep 2    # 기존 있으면 종료
nohup uvicorn src.api.main:app --host 127.0.0.1 --port 8500 > ~/api.log 2>&1 & disown
sleep 6; curl -s localhost:8500/health # {"status":"ok"}
```

### (G) 라이브 데모 (JupyterLab에서 `notebooks/demo.ipynb` 실행)
- VM JupyterLab에서 노트북을 열고 셀 실행 → `localhost:8500`(같은 VM의 EXAONE API) 호출.

---

## 5. 오늘 만난 오류 & 해결 (트러블슈팅 사전)

| 증상 | 원인 | 해결 |
|------|------|------|
| `not a git repository` | 프로젝트 폴더 밖에서 실행 | `cd ~/rfp-rag-extractor` |
| `local changes would be overwritten by merge` | VM 로컬 파일이 pull과 충돌 | `git stash` 후 `git pull` / 필요없으면 `rm 그파일` 후 pull |
| `ModuleNotFoundError: pydantic_settings` | 가상환경 안 켬 | `source ~/ragenv/bin/activate` |
| `No module named scripts` | 프로젝트 루트가 아닌 곳에서 실행 | 루트(`~/rfp-rag-extractor`)에서 `python -m scripts.xxx` |
| `address already in use (8000)` | 8000은 JupyterHub가 이미 씀 | 다른 포트(예 8500)로 띄우기 |
| `permission denied` (pip 설치) | 공용 venv라 쓰기 권한 없음, `--user`도 막힘 | 설치가 필요없게 우회(표준 라이브러리 `urllib` 사용) |
| 노트북 `연결 거부` (터미널 curl은 됨) | 노트북을 **로컬 PC**에서 돌려 `localhost`가 내 PC | **VM JupyterLab**에서 노트북 실행 |
| `/recommend` `HTTP 500` | VM에 `corpus_clean.csv` 없음(gitignore) | 그 파일을 VM `data/processed/`에 업로드 후 API 재기동 |
| VM이 멈춤/멎음 | 메모리 부족(모델 여러 개) | 모델 1개씩 + `ollama stop`으로 회수, `free -h` 확인 |

---

## 6. 외부에서 서비스 접근하기 (개념 + 우리 선택)

우리 API는 VM의 `127.0.0.1:8500`(내부 전용)에 떠 있다. 외부에서 쓰려면 세 방법:

1. **방화벽 포트 오픈** — 관리자가 GCP에서 8500을 연다. (우리는 `sudo`/권한 없어 불가)
2. **SSH 터널** — 내 노트북에서 `ssh -L 8500:localhost:8500 ...` 로 VM 포트를 끌어옴.
   (우리는 웹 접속만 가능·gcloud 미설치라 보류)
3. **노트북 라이브 데모** ✅ — 데모 노트북을 **VM 안에서** 돌리면 `localhost:8500`이 VM을 가리켜
   터널·방화벽 없이 바로 된다. **우리가 선택한 방법.**

> 배운 점: 제약(웹전용·무sudo·JupyterHub)이 있을 땐 "정석 배포"를 고집하기보다
> **환경 안에서 되는 방법**(노트북 데모)으로 목표(실동작 시연)를 달성하는 게 현명하다.

---

## 7. 다음에 VM을 다시 켤 때 체크리스트

```
□ cd ~/rfp-rag-extractor
□ source ~/ragenv/bin/activate        # (ragenv) 떴나?
□ export PATH=$HOME/ollama/bin:$PATH
□ ollama 서버 켜졌나? (curl 11434)     # 아니면 nohup ollama serve
□ .env 가 EXAONE 설정인가? (cp .env.ollama.example .env)
□ ChromaDB 인덱스 있나? (ls chroma_db) # 없으면 python -m scripts.ingest
□ corpus_clean.csv 있나? (ls data/processed) # 추천 기능에 필요
□ API 띄우기 (nohup uvicorn ... :8500)
□ demo.ipynb 를 VM JupyterLab에서 실행
```

---

## 용어 한 줄 사전

- **VM**: 클라우드에서 빌린 원격 컴퓨터.  **SSH**: 원격 컴퓨터에 터미널로 접속하는 방법.
- **포트**: 프로그램마다 붙는 번호(문 번호).  **localhost/127.0.0.1**: 이 컴퓨터 자신.
- **venv(가상환경)**: 프로젝트별 파이썬 패키지 격리 상자.  **PATH**: 명령어를 찾는 폴더 목록.
- **Ollama**: 오픈소스 LLM을 로컬에서 돌리는 서버.  **ChromaDB**: 임베딩 벡터 검색 저장소.
- **nohup/&/disown**: 터미널을 닫아도 프로그램을 계속 돌리는 주문.  **방화벽**: 어떤 포트를 외부에 열지 통제.
- **sudo**: 관리자 권한(우리 VM엔 없음).  **JupyterHub/Lab**: 브라우저로 쓰는 노트북·터미널 환경.
