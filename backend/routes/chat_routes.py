import asyncio
import json
import os
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from auth import get_optional_user, get_current_user
from database import SessionLocal
from limiter import limiter
from models import Conversation, DailyUsage
from rag import stream_rag_response, analyze_emotion

_openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

router = APIRouter(prefix="/chat", tags=["chat"])

MESSAGE_MAX_LENGTH = 500  # 최대 글자 수
HISTORY_MAX = 6           # 최대 전송 메시지 수 (토큰 절약)
HISTORY_LOAD = 50         # DB에서 불러올 최근 메시지 수
DAILY_LIMIT = 100         # 유저당 하루 최대 메시지 수


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


async def sse_generator(message: str, category: str | None, history: list[HistoryMessage], user_id: int | None, mbti: str | None = None):
    full_response = ""
    emotion_task = asyncio.create_task(analyze_emotion(message))
    try:
        if user_id:
            allowed = await check_and_increment_daily_usage(user_id)
            if not allowed:
                yield f"data: {json.dumps({'error': f'오늘 상담은 {DAILY_LIMIT}번까지야~ 내일 또 얘기하자!'}, ensure_ascii=False)}\n\n"
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
            "연애 상담, 남자친구, 여자친구, 썸, 고백, 이별, 권태기, 재회, 질투, 바람, 카톡, "
            "연락, 감정, 관계, 결혼, 프로포즈, 데이트, 헤어지다, 사귀다, 좋아하다"
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
    return StreamingResponse(
        sse_generator(req.message, req.category, trimmed_history, user_id, mbti),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
