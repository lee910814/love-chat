# JAVIS 시스템 아키텍처 문서

> 연애 상담 AI RAG 시스템 — YouTube 전문가 영상 기반 개인화 답변 서비스

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [기술 스택](#2-기술-스택)
3. [전체 아키텍처](#3-전체-아키텍처)
4. [백엔드 구조](#4-백엔드-구조)
5. [프론트엔드 구조](#5-프론트엔드-구조)
6. [통신 방식](#6-통신-방식)
7. [데이터 흐름](#7-데이터-흐름)
8. [보안](#8-보안)
9. [파일 구조](#9-파일-구조)

---

## 1. 프로젝트 개요

JAVIS는 YouTube 연애 상담 전문가의 영상을 RAG(Retrieval-Augmented Generation)로 활용하여,
사용자의 연애 고민에 전문가 기반의 개인화된 답변을 제공하는 풀스택 웹 애플리케이션이다.

**핵심 기능**:
- YouTube 영상 자동 크롤링 및 벡터 DB 적재
- 사용자 질문에 관련 전문가 발언 검색 후 GPT-4o 답변 생성
- 실시간 스트리밍 응답 (SSE)
- 음성 입력 지원 (Whisper STT)
- 카테고리별 필터링 (10개 카테고리)
- 비회원 채팅 지원

---

## 2. 기술 스택

### 백엔드

| 분류 | 기술 | 용도 |
|------|------|------|
| 프레임워크 | FastAPI 0.115 | REST API + SSE |
| 서버 | Uvicorn 0.30 | ASGI 웹 서버 |
| ORM | SQLAlchemy 2.0 (async) | PostgreSQL ORM |
| DB 드라이버 | asyncpg 0.29 | 비동기 PostgreSQL |
| 인증 | python-jose 3.3 + bcrypt | JWT HS256 + 비밀번호 해싱 |
| 검증 | Pydantic 2.8 | 요청/응답 스키마 |
| Rate Limiting | slowapi 0.1.9 | API 요청 제한 |
| HTTP 클라이언트 | httpx 0.27 | 비동기 HTTP |
| 환경변수 | python-dotenv | 설정 관리 |

### 프론트엔드

| 분류 | 기술 | 용도 |
|------|------|------|
| UI 라이브러리 | React 18.3 | 컴포넌트 |
| 번들러 | Vite 5.4 | 개발/빌드 |
| 라우팅 | React Router DOM 6 | SPA 라우팅 |
| 스타일링 | Emotion 11 | CSS-in-JS |
| HTTP | Axios 1.7 + Fetch API | REST + SSE |

### 외부 서비스

| 서비스 | 용도 |
|--------|------|
| OpenAI GPT-4o | 텍스트 생성 (스트리밍) |
| OpenAI Whisper | 음성→텍스트 변환 |
| OpenAI text-embedding-3-small | 문서/쿼리 임베딩 (1536차원) |
| Qdrant Cloud | 벡터 데이터베이스 |
| PostgreSQL | 사용자 계정 데이터 |

---

## 3. 전체 아키텍처

```
┌─────────────────────────────────────────────────┐
│              프론트엔드 (localhost:5173)          │
│                                                 │
│  App.jsx                                        │
│  ├─ /login      → LoginPage                     │
│  ├─ /register   → RegisterPage                  │
│  ├─ /chat       → ChatPage  (SSE 스트리밍)      │
│  └─ /mypage     → MyPage   (계정 관리)          │
│                                                 │
│  AuthContext.jsx  (JWT 상태: localStorage)      │
│  api/client.js    (Axios + Fetch SSE)           │
└────────────────────────┬────────────────────────┘
                         │ HTTP + SSE
                         │ Authorization: Bearer {JWT}
                         │
┌────────────────────────▼────────────────────────┐
│              백엔드 (localhost:8000)             │
│                                                 │
│  main.py  ─ CORS / Rate Limit / 라이프사이클    │
│                                                 │
│  /auth/*  ─ auth_routes.py                      │
│             register / login / me               │
│             password / delete                   │
│                                                 │
│  /chat/*  ─ chat_routes.py                      │
│             stream (SSE) / transcribe (STT)     │
│                                                 │
│  rag.py   ─ RAG 파이프라인                      │
│             1. Qdrant 벡터 검색                 │
│             2. 컨텍스트 구성                    │
│             3. GPT-4o 스트리밍                  │
│                                                 │
│  auth.py  ─ JWT 생성/검증, Bcrypt 해싱          │
└────┬──────────────────┬──────────────┬──────────┘
     │                  │              │
     ▼                  ▼              ▼
┌─────────┐    ┌──────────────┐  ┌───────────┐
│Postgres │    │ Qdrant Cloud │  │OpenAI API │
│         │    │              │  │           │
│ users   │    │love_counseling│  │ GPT-4o   │
│ ├─ id   │    │              │  │ Whisper   │
│ ├─ name │    │ vector: 1536d│  │ Embedding │
│ ├─ email│    │ payload:     │  └───────────┘
│ └─ pwd  │    │  text        │
└─────────┘    │  channel     │
               │  category    │
               │  source      │
               └──────────────┘
```

---

## 4. 백엔드 구조

### 4.1 진입점 — `main.py`

- FastAPI 앱 초기화, CORS 설정 (`localhost:5173` 허용)
- Rate Limiting 미들웨어 (slowapi)
- 시작 시 PostgreSQL 테이블 자동 생성
- `GET /health` 헬스 체크

### 4.2 인증 — `auth.py`

| 기능 | 구현 |
|------|------|
| 비밀번호 해싱 | Bcrypt (`get_password_hash`) |
| 비밀번호 검증 | `verify_password` |
| JWT 생성 | HS256, 24시간 유효 (`create_access_token`) |
| JWT 검증 | `get_current_user` (Bearer 토큰 추출) |
| 선택적 인증 | `get_optional_user` (비회원 허용) |
| 로그인 실패 제한 | 5회 실패 → 15분 잠금 (인메모리 `defaultdict`) |

**JWT 페이로드**:
```json
{
  "sub": "user_id",
  "username": "홍길동",
  "exp": 1234567890
}
```

### 4.3 인증 API — `routes/auth_routes.py`

| 엔드포인트 | 메서드 | 인증 필요 | 설명 |
|-----------|--------|----------|------|
| `/auth/register` | POST | X | 회원가입 (username 2~30자, password 6자+) |
| `/auth/login` | POST | X | 로그인, 실패 5회 시 잠금 |
| `/auth/me` | GET | O | 현재 사용자 정보 |
| `/auth/password` | PUT | O | 비밀번호 변경 |
| `/auth/me` | DELETE | O | 회원탈퇴 (비밀번호 재확인) |

### 4.4 채팅 API — `routes/chat_routes.py`

| 엔드포인트 | 메서드 | Rate Limit | 설명 |
|-----------|--------|-----------|------|
| `/chat/stream` | POST | 10/분 | RAG 답변 SSE 스트리밍 |
| `/chat/transcribe` | POST | 20/분 | Whisper 음성→텍스트 |

**`/chat/stream` 요청 스키마**:
```json
{
  "message": "고백해야 할까요?",
  "category": "고백",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

**SSE 응답 형식**:
```
data: {"delta": "그 상황"}
data: {"delta": "이라면"}
data: {"delta": "..."}
data: {"delta": "\n\n💡 참고: 채널명"}
data: [DONE]
```

### 4.5 벡터 DB — `qdrant_utils.py`

- `embed_text(text)` → OpenAI `text-embedding-3-small`으로 1536차원 벡터 생성
- `search_similar(query, top_k=3, category=None)` → Cosine Similarity 검색
- `upsert_documents(documents)` → Qdrant 컬렉션에 저장

**Qdrant 컬렉션 스키마**:
```
Collection: love_counseling
Vector: 1536차원, Cosine Similarity

Payload:
├─ text     : 문서 텍스트 (YouTube 영상 청크)
├─ source   : 출처 URL
├─ channel  : 채널명
└─ category : 썸 / 고백 / 이별 / 권태기 / 재회 /
              연락 / 질투·바람 / 결혼 / 기타
```

### 4.6 RAG 파이프라인 — `rag.py`

```
1. Qdrant에서 유사 문서 검색 (top-k=3, score > 0.3 필터링)
       ↓
2. 컨텍스트 포매팅
   "[채널명의 조언]\n문서 내용\n\n..."
       ↓
3. GPT-4o 호출
   messages = [
     {role: system, content: 연애 상담 시스템 프롬프트},
     ...대화 히스토리 (최근 10개),
     {role: user, content: 컨텍스트 + 질문}
   ]
   temperature=1.0, max_tokens=800, stream=True
       ↓
4. 청크를 SSE로 클라이언트에 전송
```

**시스템 프롬프트 핵심 지침**:
- 친한 친구처럼 구어체 사용
- 공감 먼저, 조언은 나중
- 번호/불릿 포인트 금지
- 참고 채널명 끝에 표시

### 4.7 데이터베이스 — `database.py` / `models.py`

```python
# users 테이블
class User(Base):
    id          : Integer PK
    username    : String, unique
    email       : String, unique
    hashed_password : String
    created_at  : DateTime (server default)
```

---

## 5. 프론트엔드 구조

### 5.1 라우팅 — `App.jsx`

```
/           → /chat (리다이렉트)
/login      → LoginPage
/register   → RegisterPage
/chat       → ChatPage
/mypage     → MyPage
```

### 5.2 인증 상태 — `contexts/AuthContext.jsx`

- JWT 토큰 및 사용자 정보를 `localStorage`에 저장
- `login(token, user)` / `logout()` 제공
- `localStorage` 키: `love_rag_token`, `love_rag_user`

### 5.3 API 클라이언트 — `api/client.js`

**Axios 인터셉터**:
- 요청: `Authorization: Bearer {token}` 자동 추가
- 응답 401: 토큰 삭제 + `/login` 리다이렉트

**SSE 스트리밍 (`streamChat`)**:
```javascript
// Fetch API로 SSE 처리 (EventSource 미사용)
fetch("/chat/stream", {method: "POST", body: JSON.stringify(...)})
  → response.body.getReader()
  → "data: " 줄 파싱 → onDelta(delta) 콜백
  → "[DONE]" → onDone() 콜백
```

### 5.4 주요 페이지

#### `ChatPage.jsx` — 메인 채팅

**UI 구성**:
- 헤더: 로고, 사용자명, 마이페이지/로그아웃
- 카테고리 바: 10개 카테고리 선택
- 메시지 영역: 채팅 버블 + 자동 스크롤
- 입력창: Textarea + 마이크 + 전송 버튼

**주요 기능**:

| 기능 | 동작 |
|------|------|
| 텍스트 전송 | Enter 전송 / Shift+Enter 줄바꿈 / 최대 500자 |
| 음성 입력 | MediaRecorder → WebM → `/chat/transcribe` → 자동 전송 |
| 스트리밍 | SSE delta 수신 → 메시지 누적 표시 |
| 카테고리 필터 | 선택 시 Qdrant 검색 범위 한정 |
| 대화 히스토리 | 메모리 유지 (최근 10개 전송) |

#### `LoginPage.jsx` / `RegisterPage.jsx`

- 클라이언트 검증 후 API 호출
- 성공 → `AuthContext.login()` + 채팅 페이지 이동

#### `MyPage.jsx`

- 닉네임 표시 + 로그아웃
- 비밀번호 변경
- 회원탈퇴 (모달 + 비밀번호 재확인)

### 5.5 디자인 토큰 — `theme.js`

```javascript
colors: {
  primary:    "#FF6B9D"  // 핑크
  secondary:  "#FF8C69"  // 코랄
  background: "#FFF5F8"  // 라이트 핑크
  userBubble: "#FF6B9D"
  aiBubble:   "#FFFFFF"
}
font: "Noto Sans KR"
```

---

## 6. 통신 방식

### 6.1 인증 흐름

```
클라이언트                         백엔드
   │                                │
   ├─ POST /auth/login ──────────→ │
   │  {email, password}             │
   │                                ├─ Bcrypt 검증
   │                                ├─ JWT 생성 (24h)
   │ ← {access_token, username} ── │
   │                                │
   └─ localStorage에 저장           │
      love_rag_token = "eyJ..."     │
```

### 6.2 채팅 (SSE 스트리밍) 흐름

```
클라이언트                         백엔드
   │                                │
   ├─ POST /chat/stream ──────────→│
   │  Authorization: Bearer {token} │
   │  {message, category, history}  │
   │                                ├─ Qdrant 벡터 검색 (top-3)
   │                                ├─ 컨텍스트 포매팅
   │                                ├─ GPT-4o 호출 (stream)
   │                                │
   │ ← data: {"delta": "그러면"}   │
   │ ← data: {"delta": " 일단"}    │
   │ ← data: ...                   │
   │ ← data: [DONE]                │
```

### 6.3 음성 입력 흐름

```
클라이언트                         백엔드
   │                                │
   ├─ MediaRecorder.start()         │
   ├─ 녹음 → WebM Blob              │
   ├─ POST /chat/transcribe ──────→│
   │  (multipart/form-data)         │
   │                                ├─ Whisper API 호출
   │ ← {"text": "고백해야 할까요?"} │
   │                                │
   └─ /chat/stream 자동 호출        │
```

### 6.4 HTTP 상태 코드

| 코드 | 의미 |
|------|------|
| 200 | 성공 |
| 201 | 리소스 생성 완료 |
| 400 | 요청 오류 (검증 실패) |
| 401 | 인증 실패 (토큰 만료/없음) |
| 429 | 요청 제한 초과 / 로그인 잠금 |

---

## 7. 데이터 흐름

### 7.1 크롤링 & 적재 (`scripts/crawl_and_ingest.py`)

```
YouTube URL
    ↓ yt-dlp
오디오 추출 (mp3)
    ↓ OpenAI Whisper
전사 텍스트
    ↓ 청크 분할
텍스트 청크
    ↓ text-embedding-3-small
1536차원 벡터
    ↓
Qdrant Cloud 저장
(vector + payload: text, channel, category, source)
```

### 7.2 RAG 검색 & 생성

```
사용자 질문 "고백하면 차일까?"
    ↓ text-embedding-3-small
쿼리 벡터 (1536d)
    ↓ Qdrant Cosine Similarity (top-3, score > 0.3)
관련 문서 3개
    ↓ 포매팅
컨텍스트 문자열
    ↓ GPT-4o (stream=True)
SSE 스트리밍 응답 → 클라이언트
```

---

## 8. 보안

### 8.1 인증 & 접근 제어

| 항목 | 구현 |
|------|------|
| 비밀번호 | Bcrypt 해싱 (복호화 불가) |
| 토큰 | JWT HS256, 24시간 만료 |
| 로그인 실패 | 5회 → 15분 잠금 |
| CORS | `localhost:5173`만 허용 |
| 비회원 채팅 | `get_optional_user`로 선택적 인증 |

### 8.2 API 보안

| 항목 | 구현 |
|------|------|
| Rate Limit | `/chat/stream` 10/분, `/chat/transcribe` 20/분 |
| 입력 검증 | Pydantic (메시지 500자 제한, 이메일 형식 등) |
| 환경변수 | `.env` 파일 (API 키, DB URL, SECRET_KEY) |

---

## 9. 파일 구조

```
javis/
├── backend/
│   ├── main.py              # FastAPI 앱 진입점
│   ├── auth.py              # JWT + Bcrypt 인증
│   ├── database.py          # SQLAlchemy async ORM
│   ├── models.py            # User 모델
│   ├── qdrant_utils.py      # 벡터 DB 관리
│   ├── rag.py               # RAG + GPT-4o 스트리밍
│   ├── limiter.py           # Rate Limiting 설정
│   ├── routes/
│   │   ├── auth_routes.py   # 인증 API
│   │   └── chat_routes.py   # 채팅 API + SSE
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx          # 라우터
│   │   ├── theme.js         # 디자인 토큰
│   │   ├── api/
│   │   │   └── client.js    # Axios + SSE 클라이언트
│   │   ├── contexts/
│   │   │   └── AuthContext.jsx
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   ├── ChatPage.jsx
│   │   │   └── MyPage.jsx
│   │   └── components/
│   │       └── MessageBubble.jsx
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
├── scripts/
│   ├── crawl_and_ingest.py  # YouTube 크롤링 & Qdrant 적재
│   └── requirements_crawl.txt
│
└── ARCHITECTURE.md
```

---

## 로컬 실행

```bash
# 백엔드
source venv/Scripts/activate
cd backend
uvicorn main:app --reload --port 8000

# 프론트엔드
cd frontend
npm run dev
```

| 서버 | 주소 |
|------|------|
| 프론트엔드 | http://localhost:5173 |
| 백엔드 | http://localhost:8000 |
| API 문서 | http://localhost:8000/docs |
