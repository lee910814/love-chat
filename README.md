# 연애 상담 AI

YouTube 연애 상담 영상 + 커뮤니티 게시글을 데이터로 활용하는 RAG 기반 연애 상담 챗봇입니다.
사용자의 고민을 입력하면 전문가 조언 데이터를 검색해 GPT-4o-mini가 친구처럼 답변합니다.

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ChatPage  ──SSE 스트리밍──▶  /chat/stream                  │
│  AdminPage ──REST──────────▶  /admin/emotion-scores         │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP / SSE
┌───────────────────────▼─────────────────────────────────────┐
│                     Backend (FastAPI)                        │
│                                                              │
│  /auth/*          JWT 인증 (회원가입·로그인·비밀번호 변경)    │
│  /chat/stream     RAG 검색 → GPT-4o-mini SSE 스트리밍        │
│  /chat/transcribe Whisper STT (음성 → 텍스트)                │
│  /admin/*         감정 점수 조회 (관리자 전용)                │
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────┐  │
│  │  PostgreSQL  │   │ Qdrant Cloud │   │   OpenAI API    │  │
│  │  유저·대화   │   │  벡터 DB     │   │ GPT-4o-mini     │  │
│  │  감정점수    │   │  RAG 검색    │   │ Whisper STT     │  │
│  └──────────────┘   └──────────────┘   │ Embedding 3-sm  │  │
└────────────────────────────────────────┴─────────────────────┘

데이터 수집 파이프라인
  YouTube 영상  ──yt-dlp──▶ Whisper STT ──▶ 청킹·전처리 ──▶ Qdrant
  커뮤니티 게시글 ──requests+bs4──▶ 전처리 ──────────────▶ Qdrant
  MBTI 연애 데이터 ──정적 데이터셋──────────────────────▶ Qdrant
```

---

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| **Frontend** | React 18, Vite, Emotion (CSS-in-JS) |
| **Backend** | FastAPI, SQLAlchemy (async), Pydantic v2 |
| **인증** | JWT (python-jose + bcrypt), Refresh-less 24h 토큰 |
| **DB** | PostgreSQL (유저·대화·감정점수) |
| **Vector DB** | Qdrant Cloud (cosine similarity) |
| **Embedding** | OpenAI text-embedding-3-small (1536차원) |
| **LLM** | GPT-4o-mini (SSE 스트리밍) |
| **STT** | OpenAI Whisper (음성 입력·사투리·구어체 지원) |
| **Rate Limit** | slowapi (IP 기반) + DB 기반 일일 사용량 추적 |
| **크롤링** | yt-dlp, requests, BeautifulSoup4 |

---

## 주요 기능

### 채팅
- GPT-4o-mini 기반 RAG 답변 (SSE 스트리밍)
- 전문가 YouTube 영상 발언 + 커뮤니티 게시글 벡터 검색
- MBTI별 맞춤 답변 톤 조정
- 대화 기록 저장 및 불러오기 (로그인 유저)

### 음성 입력
- 스페이스바 누르고 있으면 녹음 → 떼면 자동 전송 (Push-to-Talk)
- OpenAI Whisper STT (구어체·사투리·경상도·전라도·충청도 지원)

### 감정 분석
- 메시지마다 감정 자동 분석 (슬픔·불안·분노·상처·혼란·그리움·외로움·설렘·희망·속상함)
- 감정 이모지 말풍선 표시

### 사용 제한
| 구분 | 하루 제한 |
|------|-----------|
| 비회원 | 5회 (IP 기반) |
| 회원 | 50회 (DB 기반) |

### 관리자 대시보드 (`/admin`)
- 유저별 감정 점수 요약 (평균·최저·최고·위험도)
- 전체 감정 점수 기록 열람
- 점수는 **30일 후 자동 삭제** (사용자에게 비공개)
- 환경변수로 관리자 이메일 지정 (`ADMIN_EMAILS`)

---

## 프로젝트 구조

```
love-chat/
├── backend/
│   ├── main.py                  # FastAPI 앱 진입점·라우터 등록
│   ├── auth.py                  # JWT 발급·검증·관리자 권한 의존성
│   ├── database.py              # SQLAlchemy async 엔진·세션
│   ├── models.py                # User·Conversation·EmotionScore·DailyUsage
│   ├── qdrant_utils.py          # Qdrant 연결·컬렉션 생성·임베딩·검색
│   ├── rag.py                   # RAG 파이프라인·감정 분석·MBTI 프롬프트
│   ├── limiter.py               # slowapi 설정
│   ├── routes/
│   │   ├── auth_routes.py       # 회원가입·로그인·비밀번호·탈퇴
│   │   ├── chat_routes.py       # SSE 스트리밍·STT·대화기록·감정점수 저장
│   │   └── admin_routes.py      # 감정 점수 조회 (관리자 전용)
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # 라우터·전역 스타일
│   │   ├── main.jsx
│   │   ├── theme.js             # 디자인 토큰 (색상·폰트·그림자)
│   │   ├── contexts/
│   │   │   └── AuthContext.jsx  # JWT 상태 관리 (localStorage)
│   │   ├── api/
│   │   │   └── client.js        # axios 인스턴스·streamChat()·adminAPI
│   │   ├── pages/
│   │   │   ├── ChatPage.jsx     # 메인 채팅 (PTT 음성입력 포함)
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   ├── MyPage.jsx       # 비밀번호 변경·회원탈퇴
│   │   │   └── AdminPage.jsx    # 감정 점수 대시보드
│   │   └── components/
│   │       └── MessageBubble.jsx
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
└── scripts/
    ├── crawl_and_ingest.py      # YouTube 영상 → Whisper → Qdrant 파이프라인
    ├── community_crawl.py       # DC인사이드·에펨코리아·보배드림 크롤러
    ├── mbti_ingest.py           # MBTI 연애 데이터셋 + MBTI 갤러리 크롤러
    ├── urls_example.txt
    └── requirements_crawl.txt
```

---

## 환경 변수

`.env.example`을 복사해서 `.env`로 만들고 값을 채워주세요.

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/love_rag
JWT_SECRET_KEY=최소-32자-랜덤-시크릿키
OPENAI_API_KEY=sk-...
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key
EMOTION_SCORE_EXPIRE_DAYS=30   # 감정 점수 보관 기간 (일)
GUEST_DAILY_LIMIT=5            # 비회원 하루 상담 횟수
ADMIN_EMAILS=your@email.com    # 관리자 이메일 (쉼표로 여러 명 가능)
```

---

## 빠른 시작

### 백엔드

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 프론트엔드

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

---

## 데이터 수집

### YouTube 영상 크롤링

```bash
pip install -r scripts/requirements_crawl.txt

# 단일 영상
python scripts/crawl_and_ingest.py --url "https://youtu.be/VIDEO_ID" --model small

# 채널 전체
python scripts/crawl_and_ingest.py --url "https://www.youtube.com/@채널명" --model small
```

> Whisper 모델: `tiny` < `base` < `small`(권장) < `medium` < `large`

### 커뮤니티 크롤링

```bash
# DC인사이드 연애·이별갤
python scripts/community_crawl.py --site dcinside --pages 50

# 에펨코리아
python scripts/community_crawl.py --site fmkorea --pages 30

# 보배드림
python scripts/community_crawl.py --site bobaedream --pages 30

# 전체
python scripts/community_crawl.py --site all --pages 20
```

### MBTI 데이터 수집

```bash
# 정적 데이터셋 (16유형 연애특징 + 16×16 궁합표)
python scripts/mbti_ingest.py --source static

# DC인사이드 MBTI 갤러리
python scripts/mbti_ingest.py --source dcinside --pages 30

# 둘 다
python scripts/mbti_ingest.py --source all --pages 30
```

---

## API 엔드포인트

### 인증
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/auth/register` | 회원가입 → JWT |
| POST | `/auth/login` | 로그인 → JWT |
| GET | `/auth/me` | 내 정보 조회 |
| PUT | `/auth/password` | 비밀번호 변경 |
| DELETE | `/auth/me` | 회원탈퇴 |

### 채팅
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/chat/stream` | SSE 스트리밍 답변 |
| POST | `/chat/transcribe` | 음성 → 텍스트 (Whisper) |
| GET | `/chat/history` | 대화 기록 조회 |
| DELETE | `/chat/history` | 대화 기록 삭제 |

### 관리자 (관리자 JWT 필요)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/admin/emotion-scores` | 전체 감정 점수 기록 |
| GET | `/admin/emotion-scores/summary` | 유저별 감정 요약·위험도 |
| GET | `/admin/emotion-scores/user/{id}` | 특정 유저 감정 이력 |

### SSE 응답 형식

```
data: {"delta": "많이 힘들었겠다"}
data: {"delta": "..."}
data: {"emotion": {"label": "슬픔", "emoji": "😢", "score": 2}}
data: [DONE]
```

---

## 관리자 설정

DB 작업 없이 `.env`에 이메일만 추가하면 됩니다.

```env
ADMIN_EMAILS=your@email.com
```

해당 이메일로 로그인하면 자동으로 `/admin` 접근 권한이 부여됩니다.
