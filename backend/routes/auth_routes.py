import os
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, field_validator

from database import get_db
from models import User
from auth import verify_password, get_password_hash, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

# 환경변수로 관리자 이메일 목록 지정 (쉼표 구분)
_ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv("ADMIN_EMAILS", "").split(",")
    if e.strip()
}


def _is_admin(email: str) -> bool:
    return email.lower() in _ADMIN_EMAILS

# 로그인 실패 추적 (이메일 기준)
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

_failed: dict[str, list[datetime]] = defaultdict(list)  # email → 실패 시각 목록


def _check_lockout(email: str) -> None:
    """5회 실패 시 15분 잠금. 오래된 기록은 자동 제거."""
    cutoff = datetime.now() - timedelta(minutes=LOCKOUT_MINUTES)
    _failed[email] = [t for t in _failed[email] if t > cutoff]

    if len(_failed[email]) >= MAX_ATTEMPTS:
        unlock_at = _failed[email][0] + timedelta(minutes=LOCKOUT_MINUTES)
        remaining = int((unlock_at - datetime.now()).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=429,
            detail=f"로그인 시도가 너무 많습니다. {remaining}분 후 다시 시도해주세요.",
        )


def _record_failure(email: str) -> int:
    """실패 기록 추가. 남은 시도 횟수 반환."""
    _failed[email].append(datetime.now())
    return MAX_ATTEMPTS - len(_failed[email])


def _clear_failures(email: str) -> None:
    _failed.pop(email, None)


VALID_MBTI = {
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
}


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    mbti: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 2 or len(v) > 30:
            raise ValueError("사용자 이름은 2~30자여야 합니다")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("비밀번호는 6자 이상이어야 합니다")
        return v

    @field_validator("mbti")
    @classmethod
    def validate_mbti(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper().strip()
        if v not in VALID_MBTI:
            raise ValueError("올바른 MBTI 유형이 아닙니다")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="이미 사용 중인 이메일입니다")

    result = await db.execute(select(User).where(User.username == req.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="이미 사용 중인 사용자 이름입니다")

    user = User(
        username=req.username,
        email=str(req.email),
        hashed_password=get_password_hash(req.password),
        mbti=req.mbti,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id), "username": user.username, "mbti": user.mbti, "is_admin": _is_admin(str(req.email))})
    return TokenResponse(access_token=token, token_type="bearer", username=user.username)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    email = str(req.email)

    # 잠금 여부 확인
    _check_lockout(email)

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        remaining = _record_failure(email)
        msg = "이메일 또는 비밀번호가 올바르지 않습니다"
        if remaining > 0:
            msg += f" (남은 시도: {remaining}회)"
        else:
            msg += f" 계정이 {LOCKOUT_MINUTES}분 동안 잠깁니다."
        raise HTTPException(status_code=401, detail=msg)

    # 로그인 성공 시 실패 기록 초기화
    _clear_failures(email)
    token = create_access_token({"sub": str(user.id), "username": user.username, "mbti": user.mbti, "is_admin": _is_admin(email)})
    return TokenResponse(access_token=token, token_type="bearer", username=user.username)


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("새 비밀번호는 6자 이상이어야 합니다")
        return v


@router.put("/password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == int(current_user["user_id"])))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    if not verify_password(req.current_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다")

    if req.current_password == req.new_password:
        raise HTTPException(status_code=400, detail="새 비밀번호가 현재 비밀번호와 같습니다")

    user.hashed_password = get_password_hash(req.new_password)
    await db.commit()
    return {"message": "비밀번호가 변경되었습니다"}


class DeleteAccountRequest(BaseModel):
    password: str


@router.delete("/me")
async def delete_account(
    req: DeleteAccountRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == int(current_user["user_id"])))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")

    await db.delete(user)
    await db.commit()
    return {"message": "회원탈퇴가 완료되었습니다"}
