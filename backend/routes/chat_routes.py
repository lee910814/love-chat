import asyncio
import json
import os
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from auth import get_optional_user, get_current_user
from database import SessionLocal
from limiter import limiter
from models import Conversation, DailyUsage, EmotionScore
from rag import stream_rag_response, analyze_emotion

SCORE_EXPIRE_DAYS = int(os.getenv("EMOTION_SCORE_EXPIRE_DAYS", "30"))

_openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

router = APIRouter(prefix="/chat", tags=["chat"])

MESSAGE_MAX_LENGTH = 500  # 최대 글자 수
HISTORY_MAX = 6           # 최대 전송 메시지 수 (토큰 절약)
HISTORY_LOAD = 50         # DB에서 불러올 최근 메시지 수
DAILY_LIMIT = 50          # 로그인 유저 하루 최대 메시지 수
GUEST_DAILY_LIMIT = int(os.getenv("GUEST_DAILY_LIMIT", "5"))   # 비회원 하루 최대 메시지 수

# 비회원 IP별 사용량 추적 (ip -> (날짜, 횟수))
_guest_usage: dict[str, tuple[str, int]] = {}


class HistoryMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    category: str | None = None
    history: list[HistoryMessage] = []

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("메시지를 입력해주세요")
        if len(v) > MESSAGE_MAX_LENGTH:
            raise ValueError(f"메시지는 {MESSAGE_MAX_LENGTH}자 이하여야 합니다")
        return v


STREAM_DELAY = 0.01  # 청크당 딜레이 (초)


async def check_and_increment_daily_usage(user_id: int) -> bool:
    """오늘 사용량 확인 후 증가. 한도 초과 시 False 반환."""
    today = date.today().isoformat()
    async with SessionLocal() as db:
        result = await db.execute(
            select(DailyUsage).where(
                DailyUsage.user_id == user_id,
                DailyUsage.date == today,
            )
        )
        usage = result.scalar_one_or_none()

        if usage is None:
            db.add(DailyUsage(user_id=user_id, date=today, count=1))
            await db.commit()
            return True

        if usage.count >= DAILY_LIMIT:
            return False

        usage.count += 1
        await db.commit()
        return True


def check_guest_usage(ip: str) -> bool:
    """비회원 IP별 일일 사용량 확인 및 증가. 한도 초과 시 False 반환."""
    today = date.today().isoformat()
    entry = _guest_usage.get(ip)
    if entry is None or entry[0] != today:
        _guest_usage[ip] = (today, 1)
        return True
    if entry[1] >= GUEST_DAILY_LIMIT:
        return False
    _guest_usage[ip] = (today, entry[1] + 1)
    return True


async def sse_generator(message: str, category: str | None, history: list[HistoryMessage], user_id: int | None, client_ip: str, mbti: str | None = None):
    full_response = ""
    emotion_task = asyncio.create_task(analyze_emotion(message))
    try:
        if user_id:
            allowed = await check_and_increment_daily_usage(user_id)
            if not allowed:
                yield f"data: {json.dumps({'error': f'오늘 상담은 {DAILY_LIMIT}번까지야~ 내일 또 얘기하자!'}, ensure_ascii=False)}\n\n"
                return
        else:
            allowed = check_guest_usage(client_ip)
            if not allowed:
                yield f"data: {json.dumps({'error': f'비회원은 하루 {GUEST_DAILY_LIMIT}번까지 상담할 수 있어~ 로그인하면 더 많이 얘기할 수 있어!'}, ensure_ascii=False)}\n\n"
                return

        if user_id:
            async with SessionLocal() as db:
                db.add(Conversation(user_id=user_id, role="user", content=message))
                await db.commit()

        async for chunk in stream_rag_response(message, category, history, mbti):
            full_response += chunk
            data = json.dumps({"delta": chunk}, ensure_ascii=False)
            yield f"data: {data}\n\n"
            await asyncio.sleep(STREAM_DELAY)

        if user_id and full_response:
            async with SessionLocal() as db:
                db.add(Conversation(user_id=user_id, role="assistant", content=full_response))
                await db.commit()

        try:
            emotion = await emotion_task
            yield f"data: {json.dumps({'emotion': emotion}, ensure_ascii=False)}\n\n"
            # 로그인 유저만 감정 점수 저장
            if user_id and emotion:
                async with SessionLocal() as db:
                    db.add(EmotionScore(
                        user_id=user_id,
                        score=emotion.get("score", 5),
                        emotion_label=emotion.get("label", ""),
                        emotion_emoji=emotion.get("emoji", ""),
                        message_snippet=message[:100],
                        expires_at=datetime.now(timezone.utc) + timedelta(days=SCORE_EXPIRE_DAYS),
                    ))
                    await db.commit()
        except Exception:
            pass

    except Exception as e:
        emotion_task.cancel()
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    finally:
        yield "data: [DONE]\n\n"


@router.get("/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    """로그인 유저의 대화 기록 조회"""
    user_id = int(current_user["user_id"])
    async with SessionLocal() as db:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
            .limit(HISTORY_LOAD)
        )
        rows = result.scalars().all()

    return [
        {"id": r.id, "role": r.role, "content": r.content, "created_at": r.created_at.isoformat()}
        for r in reversed(rows)
    ]


@router.delete("/history")
async def clear_history(current_user: dict = Depends(get_current_user)):
    """로그인 유저의 대화 기록 전체 삭제"""
    user_id = int(current_user["user_id"])
    async with SessionLocal() as db:
        rows = await db.execute(
            select(Conversation).where(Conversation.user_id == user_id)
        )
        for row in rows.scalars().all():
            await db.delete(row)
        await db.commit()
    return {"message": "대화 기록이 삭제되었습니다"}


@router.post("/transcribe")
@limiter.limit("20/minute")
async def transcribe(
    request: Request,
    file: UploadFile = File(...),
):
    audio_bytes = await file.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="빈 오디오 파일입니다")

    transcript = await _openai.audio.transcriptions.create(
        model="whisper-1",
        file=(file.filename or "audio.webm", audio_bytes, file.content_type or "audio/webm"),
        language="ko",
        prompt=(
            "그 애, 걔, 그 사람, 그 오빠, 그 언니, 그 남자, 그 여자, 우리 남자친구, 우리 여자친구, "
            "연애 상담, 남자친구, 여자친구, 썸, 고백, 이별, 권태기, 재회, 질투, 바람, 카톡, "
            "연락, 감정, 관계, 결혼, 프로포즈, 데이트, 헤어지다, 사귀다, 좋아하다, "
            "어떡하지, 모르겠어, 힘들어, 보고 싶어, 연락이 없어, 읽씹, 답장, "
            "경상도: 가가, 니, 내, 와, 우야노, 우째, 머라카노, 아이가, 아이다, 마, 뭐하노, 어데, 억수로, 겁나, 와카노, 맞제, 그렇제, 했는교, 모르겠는교, "
            "전라도: 거시기, 잉, 워메, 허벌나게, 징하다, 랑께, 구만, 잖소, 허다, 이라고, "
            "충청도: 머여, 왜유, 그려, 겨, 유, 슈, 뭐유, 했슈, 모르겠슈, "
            "제주도: 하우다, 마씀, 게우다, 혼저, "
            "강원도: 그래유, 뭐여, 했어유"
        ),
    )
    return {"text": transcript.text}


@router.post("/stream")
@limiter.limit("5/minute")
@limiter.limit("100/day")
async def chat_stream(
    request: Request,
    req: ChatRequest,
    current_user: dict = Depends(get_optional_user),
):
    user_id = int(current_user["user_id"]) if current_user else None
    mbti = current_user.get("mbti") if current_user else None
    trimmed_history = req.history[-HISTORY_MAX:]
    client_ip = request.client.host if request.client else "unknown"
    return StreamingResponse(
        sse_generator(req.message, req.category, trimmed_history, user_id, client_ip, mbti),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
