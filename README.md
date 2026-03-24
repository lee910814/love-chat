# 연애 상담 AI — RAG + SSE 스트리밍

YouTube 연애 상담 유튜버의 영상을 Whisper로 전사 → Qdrant Cloud에 벡터 저장 → 사용자 질문에 GPT-4o RAG 답변을 SSE로 스트리밍하는 풀스택 앱입니다.

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| Frontend | React 18 + Vite + Emotion |
| Backend | FastAPI + SQLAlchemy (async) |
| Auth | JWT (python-jose + bcrypt) |
| DB | PostgreSQL (유저) |
| Vector DB | Qdrant Cloud |
| Embedding | OpenAI text-embedding-3-small |
| LLM | GPT-4o (스트리밍) |
| STT | OpenAI Whisper |
| Crawling | yt-dlp |

---

## 빠른 시작

### 1. 환경 설정

```bash
# 백엔드 .env 파일 생성
cp backend/.env.example backend/.env
# 값 채워 넣기: DATABASE_URL, JWT_SECRET_KEY, OPENAI_API_KEY, QDRANT_URL, QDRANT_API_KEY
```

### 2. 백엔드 실행

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173 접속
```

### 4. YouTube 크롤링 (데이터 수집)

```bash
# 크롤링 전용 패키지 설치 (ffmpeg도 필요)
pip install -r scripts/requirements_crawl.txt

# 단일 영상 수집
python scripts/crawl_and_ingest.py \
  --url "https://youtu.be/VIDEO_ID" \
  --channel "채널명" \
  --model small

# 일괄 수집
# scripts/urls_example.txt 참고하여 urls.txt 작성
python scripts/crawl_and_ingest.py --batch scripts/urls.txt --model small
```

> Whisper 모델 크기: `tiny` < `base` < `small` < `medium` < `large`
> 한국어 권장: `small` (속도/정확도 균형)

---

## 프로젝트 구조

```
javis/
├── backend/
│   ├── main.py              # FastAPI 앱 진입점
│   ├── auth.py              # JWT 유틸
│   ├── database.py          # SQLAlchemy async 설정
│   ├── models.py            # User 모델
│   ├── qdrant_utils.py      # Qdrant Cloud 연결/검색
│   ├── rag.py               # RAG + GPT-4o 스트리밍
│   ├── routes/
│   │   ├── auth_routes.py   # POST /auth/register, /auth/login, GET /auth/me
│   │   └── chat_routes.py   # POST /chat/stream (SSE)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # 라우터 + 전역 스타일
│   │   ├── main.jsx
│   │   ├── theme.js         # 컬러/폰트 토큰
│   │   ├── contexts/AuthContext.jsx   # JWT 상태 관리
│   │   ├── api/client.js             # axios + streamChat()
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   └── ChatPage.jsx
│   │   └── components/
│   │       └── MessageBubble.jsx
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
└── scripts/
    ├── crawl_and_ingest.py   # 크롤링 파이프라인
    ├── urls_example.txt
    └── requirements_crawl.txt
```

---

## API 엔드포인트

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | `/auth/register` | ✗ | 회원가입 → JWT 반환 |
| POST | `/auth/login` | ✗ | 로그인 → JWT 반환 |
| GET | `/auth/me` | ✓ | 현재 사용자 정보 |
| POST | `/chat/stream` | ✓ | SSE 스트리밍 답변 |

### SSE 응답 형식

```
data: {"delta": "안녕하세요"}
data: {"delta": " 고민을"}
...
data: {"delta": "\n\n💡 참고: 채널명"}
data: [DONE]
```
