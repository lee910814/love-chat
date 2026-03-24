from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, delete
from auth import get_admin_user
from database import SessionLocal
from models import EmotionScore, User

router = APIRouter(prefix="/admin", tags=["admin"])


async def _purge_expired(db) -> None:
    """만료된 감정 점수 삭제"""
    now = datetime.now(timezone.utc)
    await db.execute(delete(EmotionScore).where(EmotionScore.expires_at < now))
    await db.commit()


@router.get("/emotion-scores")
async def get_emotion_scores(_: dict = Depends(get_admin_user)):
    """
    전체 유저의 감정 점수 목록 (관리자 전용)
    만료된 데이터는 조회 시 자동 삭제됨
    """
    async with SessionLocal() as db:
        await _purge_expired(db)

        result = await db.execute(
            select(
                EmotionScore.id,
                EmotionScore.user_id,
                EmotionScore.score,
                EmotionScore.emotion_label,
                EmotionScore.emotion_emoji,
                EmotionScore.message_snippet,
                EmotionScore.created_at,
                EmotionScore.expires_at,
                User.username,
                User.mbti,
            )
            .join(User, User.id == EmotionScore.user_id)
            .order_by(EmotionScore.created_at.desc())
            .limit(500)
        )
        rows = result.all()

    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "username": r.username,
            "mbti": r.mbti,
            "score": r.score,
            "emotion_label": r.emotion_label,
            "emotion_emoji": r.emotion_emoji,
            "message_snippet": r.message_snippet,
            "created_at": r.created_at.isoformat(),
            "expires_at": r.expires_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/emotion-scores/summary")
async def get_emotion_summary(_: dict = Depends(get_admin_user)):
    """
    유저별 감정 점수 요약 (평균, 최저, 최고, 기록 수)
    관리자 전용
    """
    async with SessionLocal() as db:
        await _purge_expired(db)

        result = await db.execute(
            select(
                EmotionScore.user_id,
                User.username,
                User.mbti,
                func.avg(EmotionScore.score).label("avg_score"),
                func.min(EmotionScore.score).label("min_score"),
                func.max(EmotionScore.score).label("max_score"),
                func.count(EmotionScore.id).label("count"),
                func.max(EmotionScore.created_at).label("last_at"),
            )
            .join(User, User.id == EmotionScore.user_id)
            .group_by(EmotionScore.user_id, User.username, User.mbti)
            .order_by(func.avg(EmotionScore.score).asc())  # 낮은 점수(위험) 먼저
        )
        rows = result.all()

    return [
        {
            "user_id": r.user_id,
            "username": r.username,
            "mbti": r.mbti,
            "avg_score": round(float(r.avg_score), 1),
            "min_score": r.min_score,
            "max_score": r.max_score,
            "count": r.count,
            "last_at": r.last_at.isoformat(),
            "risk_level": (
                "위험" if float(r.avg_score) < 3
                else "주의" if float(r.avg_score) < 5
                else "보통" if float(r.avg_score) < 7
                else "양호"
            ),
        }
        for r in rows
    ]


@router.get("/emotion-scores/user/{user_id}")
async def get_user_emotion_scores(user_id: int, _: dict = Depends(get_admin_user)):
    """특정 유저의 감정 점수 상세 이력"""
    async with SessionLocal() as db:
        await _purge_expired(db)

        result = await db.execute(
            select(EmotionScore, User.username, User.mbti)
            .join(User, User.id == EmotionScore.user_id)
            .where(EmotionScore.user_id == user_id)
            .order_by(EmotionScore.created_at.desc())
        )
        rows = result.all()

    return [
        {
            "id": r.EmotionScore.id,
            "username": r.username,
            "mbti": r.mbti,
            "score": r.EmotionScore.score,
            "emotion_label": r.EmotionScore.emotion_label,
            "emotion_emoji": r.EmotionScore.emotion_emoji,
            "message_snippet": r.EmotionScore.message_snippet,
            "created_at": r.EmotionScore.created_at.isoformat(),
            "expires_at": r.EmotionScore.expires_at.isoformat(),
        }
        for r in rows
    ]
