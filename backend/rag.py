import os
from openai import AsyncOpenAI
from qdrant_utils import get_qdrant_client, search_similar

_openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CHAT_MODEL = "gpt-4o-mini"

MBTI_TRAITS: dict[str, str] = {
    "INTJ": "상대방은 INTJ야. 감정적인 위로보다 논리적이고 전략적인 분석을 선호해. 직설적으로 핵심만 말해줘. 과한 공감 표현은 오히려 불편해할 수 있어.",
    "INTP": "상대방은 INTP야. 감정보다 상황을 객관적으로 분석해주길 원해. 논리적 모순을 짚어주고 다양한 가능성을 탐색해줘. 결론보다 사고 과정을 중시해.",
    "ENTJ": "상대방은 ENTJ야. 결단력 있는 사람이야. 실행 가능한 조언과 명확한 방향 제시를 원해. 망설임 없이 현실적인 해결책을 제시해줘.",
    "ENTP": "상대방은 ENTP야. 다양한 시각으로 상황을 바라보길 좋아해. 반전 있는 관점이나 새로운 해석을 던져줘. 단순한 위로보다 자극이 되는 대화를 원해.",
    "INFJ": "상대방은 INFJ야. 깊은 감정적 연결을 원하고 진심 어린 공감을 중시해. 표면적인 말 뒤에 숨겨진 감정까지 읽어줘. 상대방의 의도와 내면을 이해해주는 답변을 해줘.",
    "INFP": "상대방은 INFP야. 자신의 감정과 가치관을 이해받길 원해. 판단하지 말고 있는 그대로 받아줘. 이상적인 관계에 대한 기대가 높으니 현실과 감정 사이에서 균형 잡힌 이야기를 해줘.",
    "ENFJ": "상대방은 ENFJ야. 관계의 조화와 상대방의 감정을 중요시해. 따뜻한 격려와 함께 관계 회복에 초점을 맞춰줘. 상대방이 스스로 결정할 수 있도록 도와줘.",
    "ENFP": "상대방은 ENFP야. 열정적이고 감정 기복이 클 수 있어. 가능성과 희망을 보여주는 긍정적인 답변이 잘 맞아. 새로운 시각으로 상황을 재해석해줘.",
    "ISTJ": "상대방은 ISTJ야. 현실적이고 책임감이 강해. 구체적이고 실용적인 조언을 원해. 감정적 과잉 표현보다는 사실 기반의 명확한 이야기를 해줘.",
    "ISFJ": "상대방은 ISFJ야. 배려심이 깊고 안정적인 관계를 원해. 부드럽고 따뜻한 말투로 구체적인 실천 방법을 알려줘. 갈등을 피하려는 경향이 있으니 조심스럽게 접근해줘.",
    "ESTJ": "상대방은 ESTJ야. 체계적이고 결과를 중시해. 명확한 행동 계획과 직접적인 조언을 원해. 감정보다 사실과 논리로 이야기해줘.",
    "ESFJ": "상대방은 ESFJ야. 관계와 사람들의 감정을 매우 중요하게 생각해. 따뜻한 공감과 함께 관계 회복 방법을 중심으로 이야기해줘. 주변의 시선도 신경 쓰는 편이야.",
    "ISTP": "상대방은 ISTP야. 독립적이고 간결한 걸 좋아해. 핵심만 빠르게 짚어줘. 감정 표현을 과하게 하면 부담스러워할 수 있어. 실용적이고 즉각적인 해결에 집중해줘.",
    "ISFP": "상대방은 ISFP야. 감수성이 풍부하고 자유로운 영혼이야. 판단 없이 있는 그대로 받아들여줘. 자신만의 페이스를 존중해주고 강요하지 마.",
    "ESTP": "상대방은 ESTP야. 행동파야. 이론보다 즉각적인 행동 지침을 원해. 현실적이고 빠른 해결책을 제시해줘. 길고 감성적인 이야기보다 짧고 명쾌한 조언이 잘 맞아.",
    "ESFP": "상대방은 ESFP야. 활발하고 감정 표현이 자유로워. 밝고 에너지 넘치는 반응을 좋아해. 긍정적인 면을 먼저 짚어주고 가볍게 조언해줘.",
}

SYSTEM_PROMPT = """너는 연애 고민을 들어주는 친한 친구야. 상담 전문가의 지식을 갖고 있지만, 말투는 편하고 따뜻해.

말투 규칙:
- 친한 친구한테 카톡 보내듯이 자연스럽게 말해
- "~입니다", "~해야 합니다" 같은 딱딱한 말투는 절대 쓰지 마
- "그렇구나", "진짜 많이 힘들었겠다", "솔직히 말하면" 같은 구어체를 써
- 문장을 짧게 끊어서 대화하듯이 써. 한 번에 길게 쏟아내지 마
- 공감 먼저, 조언은 그 다음이야

답변 흐름:
1. 상대방 감정에 먼저 공감해줘 (판단하지 말고)
2. 상황을 더 파악해야 할 것 같으면 질문 한 개만 해
3. 조언할 때는 "내 생각엔~", "솔직히~" 같은 말로 자연스럽게 꺼내
4. 너무 교과서적인 말은 하지 마. 현실적으로 말해줘

절대 하지 마:
- 번호 매기기(1. 2. 3.)
- 불릿 포인트(-, *, •)
- "결론적으로", "따라서", "요약하면" 같은 발표 말투
- 한 번에 모든 조언 다 쏟아내기"""

# 인사/단순 메시지 패턴 (RAG 스킵)
_GREETING_KEYWORDS = {
    "안녕", "안뇽", "ㅎㅇ", "ㅎㅎ", "hi", "hello",
    "고마워", "감사해", "고맙", "ㄳ", "감사",
    "잘 있어", "잘가", "bye", "바이",
    "응", "ㅇ", "ㄴ", "맞아", "그래", "알겠어", "알았어", "오케이", "ok",
}

def _should_skip_rag(message: str) -> bool:
    """짧거나 인사성 메시지는 RAG 불필요"""
    stripped = message.strip()
    if len(stripped) < 12:
        return True
    lower = stripped.lower()
    return any(kw in lower for kw in _GREETING_KEYWORDS)


async def _rewrite_query(message: str) -> str:
    """검색 품질 향상을 위해 쿼리를 벡터 검색에 최적화된 형태로 변환"""
    response = await _openai.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "사용자의 연애 고민 메시지를 벡터 검색에 최적화된 키워드 형태로 변환해줘. "
                    "핵심 감정, 상황, 관계 키워드 위주로 15단어 이내로 압축해. "
                    "설명 없이 변환된 쿼리만 출력해."
                ),
            },
            {"role": "user", "content": message},
        ],
        temperature=0.0,
        max_tokens=60,
    )
    return response.choices[0].message.content.strip()


EMOTIONS = [
    {"label": "슬픔",   "emoji": "😢"},
    {"label": "불안",   "emoji": "😰"},
    {"label": "분노",   "emoji": "😤"},
    {"label": "상처",   "emoji": "💔"},
    {"label": "혼란",   "emoji": "😵"},
    {"label": "그리움", "emoji": "🥺"},
    {"label": "외로움", "emoji": "🌧️"},
    {"label": "설렘",   "emoji": "💓"},
    {"label": "희망",   "emoji": "🌱"},
    {"label": "속상함", "emoji": "😞"},
]

_EMOTION_LIST = ", ".join(f"{e['label']}({e['emoji']})" for e in EMOTIONS)


async def analyze_emotion(message: str) -> dict:
    """사용자 메시지의 주된 감정 하나를 분석"""
    import json as _json
    response = await _openai.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    f"사용자의 연애 고민 메시지에서 주된 감정 하나를 골라줘.\n"
                    f"감정 목록: {_EMOTION_LIST}\n"
                    f'JSON으로만 답해: {{"label": "감정명", "emoji": "이모지"}}'
                ),
            },
            {"role": "user", "content": message},
        ],
        temperature=0.0,
        max_tokens=30,
        response_format={"type": "json_object"},
    )
    return _json.loads(response.choices[0].message.content)


async def stream_rag_response(user_message: str, category: str | None = None, history: list = [], mbti: str | None = None):
    """RAG 검색 후 GPT-4o-mini 스트리밍 제너레이터"""
    relevant = []

    if not _should_skip_rag(user_message):
        # 카테고리가 이미 지정된 경우 쿼리 재작성 스킵 (~500ms 절감)
        search_query = user_message if category else await _rewrite_query(user_message)
        client = get_qdrant_client()
        try:
            contexts = await search_similar(client, search_query, top_k=3, category=category)
        finally:
            await client.close()
        relevant = [c for c in contexts if c["score"] > 0.3]

    if relevant:
        context_text = "\n\n".join(
            f"[{c['channel']}의 조언]\n{c['text']}" for c in relevant
        )
        user_prompt = (
            f"다음은 연애 상담 전문가들의 관련 조언입니다:\n\n{context_text}\n\n"
            f"위 조언을 참고해서 이 고민에 답변해 주세요: {user_message}"
        )
    else:
        user_prompt = user_message

    system_content = SYSTEM_PROMPT
    if mbti and mbti.upper() in MBTI_TRAITS:
        system_content += f"\n\n[사용자 MBTI 참고]\n{MBTI_TRAITS[mbti.upper()]}"

    messages = [{"role": "system", "content": system_content}]
    for h in history:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": user_prompt})

    stream = await _openai.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=1.0,
        max_tokens=500,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta

