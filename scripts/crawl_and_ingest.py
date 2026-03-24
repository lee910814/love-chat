"""
YouTube 연애 상담 영상 크롤링 → Whisper STT → Qdrant Cloud 저장 파이프라인

사용법:
  # 단일 영상
  python scripts/crawl_and_ingest.py --url "https://youtu.be/VIDEO_ID"

  # 채널 전체 (모든 영상 자동 수집)
  python scripts/crawl_and_ingest.py --url "https://www.youtube.com/@채널명"

  # 플레이리스트 전체
  python scripts/crawl_and_ingest.py --url "https://www.youtube.com/playlist?list=..."

  # 채널 이름을 직접 지정하고 싶을 때
  python scripts/crawl_and_ingest.py --url "https://www.youtube.com/@채널명" --channel "내가 붙일 이름"

  # 최대 영상 수 제한 (테스트용)
  python scripts/crawl_and_ingest.py --url "https://www.youtube.com/@채널명" --max 5

Whisper 모델: tiny < base < small(권장) < medium < large
"""

import asyncio
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import yt_dlp
import whisper
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "backend" / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from qdrant_utils import get_qdrant_client, ensure_collection, upsert_documents

# 처리 완료된 video_id 추적 파일
PROGRESS_FILE = Path(__file__).parent / ".processed_ids.json"


# ─────────────────────────────────────────────
# 진행 상황 추적 (재시작 시 중복 처리 방지)
# ─────────────────────────────────────────────
def load_processed() -> set[str]:
    if PROGRESS_FILE.exists():
        return set(json.loads(PROGRESS_FILE.read_text()))
    return set()


def save_processed(processed: set[str]) -> None:
    PROGRESS_FILE.write_text(json.dumps(list(processed)))


# ─────────────────────────────────────────────
# 1. 채널/플레이리스트/단일 영상 목록 조회
# ─────────────────────────────────────────────
def get_video_list(url: str, max_videos: int | None = None) -> list[dict]:
    """
    URL에서 영상 목록을 조회한다.
    반환: [{id, title, url, channel}]
    단일 영상 URL이면 길이 1짜리 리스트 반환.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",  # 다운로드 없이 메타만 수집
        "playlist_items": f"1:{max_videos}" if max_videos else None,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # 채널/플레이리스트인 경우
    if "entries" in info:
        channel_name = info.get("channel") or info.get("uploader") or info.get("title", "알 수 없음")
        videos = []
        for entry in info["entries"]:
            if entry is None:
                continue
            vid_id = entry.get("id")
            if not vid_id:
                continue
            videos.append({
                "id": vid_id,
                "title": entry.get("title", vid_id),
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "channel": channel_name,
            })
        return videos

    # 단일 영상인 경우
    return [{
        "id": info["id"],
        "title": info.get("title", info["id"]),
        "url": f"https://www.youtube.com/watch?v={info['id']}",
        "channel": info.get("channel") or info.get("uploader", "알 수 없음"),
    }]


# ─────────────────────────────────────────────
# 2. 오디오 다운로드
# ─────────────────────────────────────────────
def download_audio(video_url: str, video_id: str, output_dir: str) -> str:
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, f"{video_id}.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    mp3_path = os.path.join(output_dir, f"{video_id}.mp3")
    if not os.path.exists(mp3_path):
        candidates = list(Path(output_dir).glob("*.mp3"))
        if not candidates:
            raise FileNotFoundError(f"mp3 파일 없음: {output_dir}")
        mp3_path = str(candidates[0])
    return mp3_path


# ─────────────────────────────────────────────
# 3. 카테고리 분류
# ─────────────────────────────────────────────

CATEGORIES = {
    "썸": ["썸", "설레", "첫만남", "관심", "좋아하는", "좋아하는 것 같", "호감", "두근"],
    "고백": ["고백", "사귀", "좋다고", "마음을 전", "표현", "용기", "말하기가", "사귀어"],
    "이별": ["이별", "헤어", "차였", "차이", "끝났", "마무리", "이별 통보", "헤어지자"],
    "권태기": ["권태기", "지루", "설레지 않", "밋밋", "익숙해", "매너리즘", "예전 같지"],
    "재회": ["재회", "다시 만나", "다시 사귀", "돌아왔", "연락이 왔", "다시 연락"],
    "연락": ["카톡", "답장", "읽씹", "연락", "문자", "전화", "메시지", "카카오"],
    "질투/바람": ["질투", "바람", "외도", "불륜", "의심", "다른 이성", "浮気", "배신"],
    "결혼": ["결혼", "프로포즈", "동거", "약혼", "미래", "같이 살", "평생"],
}

def classify_category(text: str) -> str:
    """키워드 기반으로 카테고리를 분류한다. 해당 없으면 '기타'."""
    scores = {cat: 0 for cat in CATEGORIES}
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                scores[cat] += 1
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "기타"


# ─────────────────────────────────────────────
# 4. 텍스트 전처리 & 청킹
# ─────────────────────────────────────────────

# 비속어/욕설 목록 (마스킹 처리)
PROFANITY_LIST = [
    "씨발", "씨바", "시발", "ㅅㅂ", "시바",
    "개새끼", "개새", "ㄱㅅㄲ",
    "병신", "ㅂㅅ",
    "지랄", "ㅈㄹ",
    "미친", "미친놈", "미친년", "ㅁㅊ",
    "새끼", "ㅅㄲ",
    "좆", "보지", "자지",
    "꺼져", "닥쳐",
    "찐따", "찐찐",
    "창녀", "갈보",
    "느금마", "니애미",
]

def remove_profanity(text: str) -> str:
    """비속어/욕설을 제거한다."""
    for word in PROFANITY_LIST:
        text = text.replace(word, "")
    return text


def remove_repeated_words(text: str) -> str:
    """연속으로 중복된 단어를 제거한다. (예: '진짜 진짜 진짜' → '진짜')"""
    # 같은 단어가 2회 이상 연속 반복되면 1회로 줄임
    text = re.sub(r'\b(\S+)(\s+\1){2,}\b', r'\1', text)
    return text


def preprocess(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[.]{3,}", "...", text)
    text = remove_profanity(text)
    text = remove_repeated_words(text)
    text = re.sub(r"\s+", " ", text).strip()  # 제거 후 공백 재정리
    return text


# 강의체 패턴 — 이런 문장이 많으면 RAG 참고 시 딱딱해짐
LECTURE_PATTERNS = [
    r"첫\s*번째[는,]?", r"두\s*번째[는,]?", r"세\s*번째[는,]?",
    r"결론적으로", r"따라서", r"요약하면", r"정리하면",
    r"오늘은.*알아보", r"이번\s*영상에서", r"구독과\s*좋아요",
    r"안녕하세요.*입니다", r"채널.*오신",
]

def is_lecture_style(text: str) -> bool:
    """강의/발표체 문장이 많으면 True."""
    matches = sum(1 for p in LECTURE_PATTERNS if re.search(p, text))
    return matches >= 2


def split_sentences(text: str) -> list[str]:
    """한국어 문장 단위로 분리."""
    # 마침표/물음표/느낌표 뒤에서 분리 (단, 숫자+마침표는 제외)
    sentences = re.split(r'(?<=[.?!])\s+|(?<=요)\s+|(?<=다)\s+|(?<=죠)\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(text: str, max_chars: int = 400, overlap_sents: int = 1) -> list[str]:
    """문장 단위 청킹 — 의미 단위를 유지하고 강의체 문장은 제거."""
    cleaned = preprocess(text)
    sentences = split_sentences(cleaned)

    # 강의체/광고성 문장 제거
    sentences = [
        s for s in sentences
        if not any(re.search(p, s) for p in LECTURE_PATTERNS)
        and len(s) > 10
    ]

    chunks = []
    current = []
    current_len = 0

    for sent in sentences:
        if current_len + len(sent) > max_chars and current:
            chunk = " ".join(current)
            if not is_lecture_style(chunk):
                chunks.append(chunk)
            # 오버랩: 마지막 문장 유지
            current = current[-overlap_sents:]
            current_len = sum(len(s) for s in current)
        current.append(sent)
        current_len += len(sent)

    if current:
        chunk = " ".join(current)
        if not is_lecture_style(chunk):
            chunks.append(chunk)

    return chunks


# ─────────────────────────────────────────────
# 4. 단일 영상 처리
# ─────────────────────────────────────────────
async def process_video(
    video: dict,
    whisper_model,
    qdrant_client,
    idx: int,
    total: int,
) -> bool:
    """영상 1개를 다운로드 → 전사 → 청킹 → Qdrant 저장. 성공 시 True 반환."""
    print(f"\n[{idx}/{total}] {video['title'][:60]}")
    print(f"  채널: {video['channel']}  |  URL: {video['url']}")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 다운로드
            print("  [↓]  오디오 다운로드 중...")
            audio_path = download_audio(video["url"], video["id"], tmpdir)

            # Whisper STT
            print("  [STT]  전사 중...")
            result = whisper_model.transcribe(audio_path, language="ko", fp16=False)
            transcript = result["text"]
            print(f"  [OK]  전사 완료 ({len(transcript):,}자)")

            # 청킹 (강의체 자동 필터링 포함)
            raw_sentences = split_sentences(preprocess(transcript))
            chunks = chunk_text(transcript)
            filtered = len(raw_sentences) - sum(len(split_sentences(c)) for c in chunks)
            print(f"  [OK]  {len(chunks)}개 청크 생성 (강의체 문장 {filtered}개 제거)")

            # Qdrant 업로드
            documents = [
                {
                    "text": chunk,
                    "metadata": {
                        "source": video["url"],
                        "channel": video["channel"],
                        "title": video["title"],
                        "chunk_index": i,
                        "category": classify_category(chunk),
                    },
                }
                for i, chunk in enumerate(chunks)
            ]

            batch_size = 10
            for i in range(0, len(documents), batch_size):
                await upsert_documents(qdrant_client, documents[i : i + batch_size])

            print(f"  [OK]  Qdrant 저장 완료")
        return True

    except Exception as e:
        print(f"  [ERR]  오류 발생, 건너뜀: {e}")
        return False


# ─────────────────────────────────────────────
# 5. 메인 파이프라인
# ─────────────────────────────────────────────
async def run(url: str, channel_override: str | None, model_size: str, max_videos: int | None) -> None:
    # 영상 목록 조회
    print(f"영상 목록 조회 중: {url}")
    videos = get_video_list(url, max_videos)
    total = len(videos)
    print(f"총 {total}개 영상 발견")

    if channel_override:
        for v in videos:
            v["channel"] = channel_override

    # 이전에 처리한 영상 제외
    processed = load_processed()
    pending = [v for v in videos if v["id"] not in processed]
    skipped = total - len(pending)
    if skipped:
        print(f"이미 처리된 영상 {skipped}개 건너뜀 → 남은 영상: {len(pending)}개")
    if not pending:
        print("처리할 영상이 없습니다.")
        return

    # Whisper 모델 한 번만 로드
    print(f"\nWhisper 모델 로딩: {model_size}")
    wmodel = whisper.load_model(model_size)

    # Qdrant 연결
    client = get_qdrant_client()
    await ensure_collection(client)

    success_count = 0
    for idx, video in enumerate(pending, start=skipped + 1):
        ok = await process_video(video, wmodel, client, idx, total)
        if ok:
            processed.add(video["id"])
            save_processed(processed)
            success_count += 1

    await client.close()

    print(f"\n{'=' * 50}")
    print(f"완료!  성공: {success_count}개  실패: {len(pending) - success_count}개")
    print(f"{'=' * 50}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="YouTube 채널/플레이리스트/단일 영상 → Whisper → Qdrant"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="YouTube URL (단일 영상, 채널, 플레이리스트 모두 가능)",
    )
    parser.add_argument(
        "--channel",
        default=None,
        help="채널 이름 직접 지정 (생략 시 YouTube 채널명 자동 사용)",
    )
    parser.add_argument(
        "--model",
        default="small",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper 모델 크기 (기본: small)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="최대 처리 영상 수 (테스트용, 생략 시 전체)",
    )
    args = parser.parse_args()

    asyncio.run(run(args.url, args.channel, args.model, args.max))
