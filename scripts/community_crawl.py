"""
커뮤니티 사이트 크롤링 → 전처리 → Qdrant 저장 파이프라인

지원 사이트:
  - DC인사이드 (연애/이별/썸 갤러리)
  - 에펨코리아 (연애 게시판)
  - 보배드림 (연애 게시판)

사용법:
  # DC인사이드 - 연애갤 크롤링 (최근 50페이지)
  python scripts/community_crawl.py --site dcinside --pages 50

  # 에펨코리아
  python scripts/community_crawl.py --site fmkorea --pages 30

  # 보배드림
  python scripts/community_crawl.py --site bobaedream --pages 30

  # 전체 사이트 한 번에
  python scripts/community_crawl.py --site all --pages 20
"""

import asyncio
import argparse
import json
import re
import sys
import time
import hashlib
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "backend" / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from qdrant_utils import get_qdrant_client, ensure_collection, upsert_documents

# ─────────────────────────────────────────────
# 진행 추적 (중복 방지)
# ─────────────────────────────────────────────
PROGRESS_FILE = Path(__file__).parent / ".processed_community_ids.json"


def load_processed() -> set:
    if PROGRESS_FILE.exists():
        return set(json.loads(PROGRESS_FILE.read_text(encoding="utf-8")))
    return set()


def save_processed(processed: set) -> None:
    PROGRESS_FILE.write_text(json.dumps(list(processed)), encoding="utf-8")


def make_id(url: str, text: str) -> str:
    """URL + 텍스트 앞 50자로 고유 ID 생성"""
    return hashlib.md5(f"{url}:{text[:50]}".encode()).hexdigest()


# ─────────────────────────────────────────────
# 공통 HTTP 헬퍼
# ─────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def get_soup(url: str, params: dict = None, delay: float = 1.0) -> BeautifulSoup | None:
    time.sleep(delay)
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  [ERR] 요청 실패: {url} → {e}")
        return None


# ─────────────────────────────────────────────
# 텍스트 전처리
# ─────────────────────────────────────────────
PROFANITY_LIST = [
    "씨발", "씨바", "시발", "ㅅㅂ", "시바",
    "개새끼", "개새", "ㄱㅅㄲ",
    "병신", "ㅂㅅ",
    "지랄", "ㅈㄹ",
    "미친놈", "미친년", "ㅁㅊ",
    "새끼", "ㅅㄲ",
    "좆", "보지", "자지",
    "꺼져", "닥쳐",
    "찐따", "창녀", "갈보",
    "느금마", "니애미",
]

SPAM_PATTERNS = [
    r"https?://\S+",             # URL
    r"ㅋ{4,}",                   # ㅋㅋㅋㅋ 과다
    r"ㅎ{4,}",                   # ㅎㅎㅎㅎ 과다
    r"ㅠ{4,}",                   # ㅠㅠㅠㅠ 과다
    r"\.{4,}",                   # .... 과다
    r"[ㄱ-ㅎ]{5,}",              # 자음만 5개 이상
    r"광고|홍보|이벤트|클릭|가입",  # 광고성
]


def preprocess(text: str) -> str:
    if not text:
        return ""
    # 비속어 제거
    for word in PROFANITY_LIST:
        text = text.replace(word, "")
    # 스팸 패턴 제거
    for pattern in SPAM_PATTERNS:
        text = re.sub(pattern, "", text)
    # 공백 정리
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_valid_text(text: str, min_len: int = 30) -> bool:
    """너무 짧거나 의미없는 텍스트 필터링"""
    if len(text) < min_len:
        return False
    korean_ratio = len(re.findall(r"[가-힣]", text)) / max(len(text), 1)
    return korean_ratio > 0.3


CATEGORIES = {
    "썸":      ["썸", "설레", "첫만남", "관심", "호감", "두근"],
    "고백":    ["고백", "사귀", "좋다고", "마음을 전", "용기"],
    "이별":    ["이별", "헤어", "차였", "끝났", "이별 통보"],
    "권태기":  ["권태기", "지루", "설레지 않", "매너리즘", "예전 같지"],
    "재회":    ["재회", "다시 만나", "다시 사귀", "돌아왔", "다시 연락"],
    "연락":    ["카톡", "답장", "읽씹", "연락", "문자", "메시지"],
    "질투/바람": ["질투", "바람", "외도", "불륜", "의심", "다른 이성"],
    "결혼":    ["결혼", "프로포즈", "동거", "약혼", "평생"],
}


def classify_category(text: str) -> str:
    scores = {cat: sum(1 for kw in kws if kw in text) for cat, kws in CATEGORIES.items()}
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "기타"


def build_document(text: str, source: str, site: str, title: str = "") -> dict:
    cleaned = preprocess(text)
    if not is_valid_text(cleaned):
        return None
    return {
        "text": cleaned,
        "metadata": {
            "source": source,
            "channel": site,
            "title": title,
            "category": classify_category(cleaned),
        },
    }


# ─────────────────────────────────────────────
# 1. DC인사이드 크롤러
# ─────────────────────────────────────────────
# 연애 관련 갤러리 목록
DC_GALLERIES = [
    ("love", "연애갤"),
    ("lovestory", "연애이야기갤"),
    ("heartbreak", "이별갤"),
]

DC_BASE = "https://gall.dcinside.com/board/lists"
DC_POST_BASE = "https://gall.dcinside.com/board/view"


def crawl_dcinside_page(gallery_id: str, page: int) -> list[dict]:
    """갤러리 한 페이지의 게시글 목록 수집"""
    soup = get_soup(DC_BASE, params={"id": gallery_id, "page": page})
    if not soup:
        return []

    posts = []
    for row in soup.select("tr.ub-content"):
        # 공지, 설문 제외
        if row.select_one(".icon_notice, .icon_survey"):
            continue
        title_tag = row.select_one("td.gall_tit a:first-child")
        if not title_tag:
            continue
        href = title_tag.get("href", "")
        no_match = re.search(r"no=(\d+)", href)
        if not no_match:
            continue
        posts.append({
            "no": no_match.group(1),
            "title": title_tag.get_text(strip=True),
            "gallery_id": gallery_id,
        })
    return posts


def crawl_dcinside_post(gallery_id: str, no: str, title: str) -> list[dict]:
    """게시글 본문 + 댓글 수집"""
    url = f"{DC_POST_BASE}/?id={gallery_id}&no={no}"
    soup = get_soup(url, delay=0.8)
    if not soup:
        return []

    docs = []
    site_label = "DC인사이드"

    # 본문
    body_tag = soup.select_one(".write_div")
    if body_tag:
        body = body_tag.get_text(separator=" ", strip=True)
        doc = build_document(f"{title}. {body}", url, site_label, title)
        if doc:
            docs.append(doc)

    # 댓글 (추천 1 이상만)
    for cmt in soup.select(".cmt_info"):
        rec_tag = cmt.select_one(".reply_recommend_btn")
        rec = int(rec_tag.get_text(strip=True) or "0") if rec_tag else 0
        txt_tag = cmt.select_one(".usertxt")
        if not txt_tag:
            continue
        txt = txt_tag.get_text(separator=" ", strip=True)
        if rec >= 1:
            doc = build_document(txt, url, site_label, title)
            if doc:
                docs.append(doc)

    return docs


async def run_dcinside(pages: int, processed: set) -> list[dict]:
    all_docs = []
    for gallery_id, gallery_name in DC_GALLERIES:
        print(f"\n[DC인사이드] {gallery_name} ({gallery_id}) — {pages}페이지")
        for page in range(1, pages + 1):
            print(f"  페이지 {page}/{pages}", end="\r")
            posts = crawl_dcinside_page(gallery_id, page)
            for post in posts:
                pid = f"dc_{gallery_id}_{post['no']}"
                if pid in processed:
                    continue
                docs = crawl_dcinside_post(post["gallery_id"], post["no"], post["title"])
                all_docs.extend(docs)
                processed.add(pid)
            save_processed(processed)
        print(f"  {gallery_name} 완료")
    return all_docs


# ─────────────────────────────────────────────
# 2. 에펨코리아 크롤러
# ─────────────────────────────────────────────
FM_BOARDS = [
    ("523", "연애/결혼"),
    ("15149", "썸/고백"),
    ("16906", "이별/재회"),
]

FM_BASE = "https://www.fmkorea.com"


def crawl_fmkorea_page(board_id: str, page: int) -> list[dict]:
    url = f"{FM_BASE}/index.php?mid={board_id}&page={page}"
    soup = get_soup(url)
    if not soup:
        return []

    posts = []
    for row in soup.select("li.li_pe_1"):
        title_tag = row.select_one("h3.title a")
        if not title_tag:
            continue
        href = title_tag.get("href", "")
        if not href.startswith("/"):
            continue
        posts.append({
            "url": FM_BASE + href,
            "title": title_tag.get_text(strip=True),
        })
    return posts


def crawl_fmkorea_post(url: str, title: str) -> list[dict]:
    soup = get_soup(url, delay=0.8)
    if not soup:
        return []

    docs = []
    site_label = "에펨코리아"

    # 본문
    body_tag = soup.select_one(".xe_content")
    if body_tag:
        body = body_tag.get_text(separator=" ", strip=True)
        doc = build_document(f"{title}. {body}", url, site_label, title)
        if doc:
            docs.append(doc)

    # 댓글 (베스트/일반)
    for cmt in soup.select(".comment_content .xe_content"):
        txt = cmt.get_text(separator=" ", strip=True)
        doc = build_document(txt, url, site_label, title)
        if doc:
            docs.append(doc)

    return docs


async def run_fmkorea(pages: int, processed: set) -> list[dict]:
    all_docs = []
    for board_id, board_name in FM_BOARDS:
        print(f"\n[에펨코리아] {board_name} — {pages}페이지")
        for page in range(1, pages + 1):
            print(f"  페이지 {page}/{pages}", end="\r")
            posts = crawl_fmkorea_page(board_id, page)
            for post in posts:
                pid = make_id(post["url"], post["title"])
                if pid in processed:
                    continue
                docs = crawl_fmkorea_post(post["url"], post["title"])
                all_docs.extend(docs)
                processed.add(pid)
            save_processed(processed)
        print(f"  {board_name} 완료")
    return all_docs


# ─────────────────────────────────────────────
# 3. 보배드림 크롤러
# ─────────────────────────────────────────────
BOBA_BOARDS = [
    ("romance", "연애/사랑"),
]

BOBA_BASE = "https://www.bobaedream.co.kr"


def crawl_bobaedream_page(board: str, page: int) -> list[dict]:
    url = f"{BOBA_BASE}/list?code={board}&page={page}"
    soup = get_soup(url)
    if not soup:
        return []

    posts = []
    for row in soup.select("table.bbs_new1 tr"):
        title_tag = row.select_one("td.title a")
        if not title_tag:
            continue
        href = title_tag.get("href", "")
        if not href:
            continue
        full_url = BOBA_BASE + href if href.startswith("/") else href
        posts.append({
            "url": full_url,
            "title": title_tag.get_text(strip=True),
        })
    return posts


def crawl_bobaedream_post(url: str, title: str) -> list[dict]:
    soup = get_soup(url, delay=0.8)
    if not soup:
        return []

    docs = []
    site_label = "보배드림"

    # 본문
    body_tag = soup.select_one(".bodyCont")
    if body_tag:
        body = body_tag.get_text(separator=" ", strip=True)
        doc = build_document(f"{title}. {body}", url, site_label, title)
        if doc:
            docs.append(doc)

    # 댓글
    for cmt in soup.select(".coment-box .coment"):
        txt = cmt.get_text(separator=" ", strip=True)
        doc = build_document(txt, url, site_label, title)
        if doc:
            docs.append(doc)

    return docs


async def run_bobaedream(pages: int, processed: set) -> list[dict]:
    all_docs = []
    for board, board_name in BOBA_BOARDS:
        print(f"\n[보배드림] {board_name} — {pages}페이지")
        for page in range(1, pages + 1):
            print(f"  페이지 {page}/{pages}", end="\r")
            posts = crawl_bobaedream_page(board, page)
            for post in posts:
                pid = make_id(post["url"], post["title"])
                if pid in processed:
                    continue
                docs = crawl_bobaedream_post(post["url"], post["title"])
                all_docs.extend(docs)
                processed.add(pid)
            save_processed(processed)
        print(f"  {board_name} 완료")
    return all_docs


# ─────────────────────────────────────────────
# Qdrant 업로드
# ─────────────────────────────────────────────
async def upload_to_qdrant(docs: list[dict]) -> None:
    if not docs:
        print("업로드할 문서 없음")
        return

    client = get_qdrant_client()
    await ensure_collection(client)

    batch_size = 10
    total = len(docs)
    print(f"\nQdrant 업로드 시작: 총 {total}개 문서")

    for i in range(0, total, batch_size):
        batch = docs[i: i + batch_size]
        await upsert_documents(client, batch)
        print(f"  [{min(i + batch_size, total)}/{total}] 업로드 완료", end="\r")

    await client.close()
    print(f"\n업로드 완료!")


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
async def main(site: str, pages: int) -> None:
    processed = load_processed()
    all_docs = []

    if site in ("dcinside", "all"):
        docs = await run_dcinside(pages, processed)
        all_docs.extend(docs)
        print(f"DC인사이드: {len(docs)}개 문서 수집")

    if site in ("fmkorea", "all"):
        docs = await run_fmkorea(pages, processed)
        all_docs.extend(docs)
        print(f"에펨코리아: {len(docs)}개 문서 수집")

    if site in ("bobaedream", "all"):
        docs = await run_bobaedream(pages, processed)
        all_docs.extend(docs)
        print(f"보배드림: {len(docs)}개 문서 수집")

    print(f"\n총 {len(all_docs)}개 문서 수집 완료")
    await upload_to_qdrant(all_docs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="커뮤니티 연애 게시글/댓글 크롤링 → Qdrant")
    parser.add_argument(
        "--site",
        required=True,
        choices=["dcinside", "fmkorea", "bobaedream", "all"],
        help="크롤링할 사이트",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=20,
        help="크롤링할 페이지 수 (기본: 20)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.site, args.pages))
