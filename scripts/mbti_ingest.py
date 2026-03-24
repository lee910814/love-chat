"""
MBTI 연애 데이터 수집 → Qdrant 저장 파이프라인

두 가지 소스를 조합합니다:
  1. 정적 데이터셋 — 16유형 연애 특징 + 16×16 궁합표
  2. DC인사이드 MBTI 갤러리 — 실제 사람들의 경험담

사용법:
  # 정적 데이터만 (빠름, 인터넷 불필요)
  python scripts/mbti_ingest.py --source static

  # DC인사이드 MBTI 갤러리만 크롤링
  python scripts/mbti_ingest.py --source dcinside --pages 30

  # 둘 다
  python scripts/mbti_ingest.py --source all --pages 30
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

PROGRESS_FILE = Path(__file__).parent / ".processed_mbti_ids.json"
MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]


def load_processed() -> set:
    if PROGRESS_FILE.exists():
        return set(json.loads(PROGRESS_FILE.read_text(encoding="utf-8")))
    return set()


def save_processed(processed: set) -> None:
    PROGRESS_FILE.write_text(json.dumps(list(processed)), encoding="utf-8")


def make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


# ─────────────────────────────────────────────
# 1. 정적 MBTI 연애 데이터셋
# ─────────────────────────────────────────────

# 16유형 연애 특징 (연애스타일 / 장점 / 단점 / 갈등패턴 / 원하는것)
MBTI_LOVE_TRAITS = {
    "INTJ": {
        "연애스타일": "INTJ는 연애에서도 전략적이고 목적의식이 뚜렷해. 깊은 관계를 원하지만 먼저 다가가는 건 잘 안 해. 한번 마음을 열면 매우 헌신적이야.",
        "장점": "신뢰할 수 있고 약속을 잘 지켜. 파트너의 성장을 진심으로 응원하고 지적 대화를 즐겨.",
        "단점": "감정 표현이 서툴러서 차갑게 보일 수 있어. 완벽주의적 성향으로 파트너에게 높은 기준을 요구할 수 있어.",
        "갈등패턴": "논리로만 문제를 해결하려 해서 감정적 위로가 필요한 파트너와 충돌해. 비판적인 말이 상처가 될 수 있어.",
        "원하는것": "지적 자극, 독립적인 공간, 신뢰 기반의 깊은 유대감",
        "궁합좋음": ["ENFP", "ENTP"],
        "궁합나쁨": ["ESFP", "ESTP"],
    },
    "INTP": {
        "연애스타일": "INTP는 연애를 흥미로운 탐구로 여겨. 감정보다 지적 연결을 먼저 추구하고 관계가 깊어지면 서서히 감정을 열어.",
        "장점": "파트너의 아이디어를 진지하게 들어주고 창의적인 해결책을 제시해. 집착하지 않아서 파트너에게 자유를 줘.",
        "단점": "감정적으로 무뚝뚝하게 보일 수 있고 현실적인 연애 표현(기념일, 이벤트)에 서툴러.",
        "갈등패턴": "문제를 분석만 하고 행동으로 옮기지 않아서 파트너가 지칠 수 있어. 논쟁에서 이기려는 성향이 갈등을 키울 수 있어.",
        "원하는것": "지적 토론, 개인 시간 존중, 억압 없는 자유로운 관계",
        "궁합좋음": ["ENTJ", "ENFJ"],
        "궁합나쁨": ["ESFJ", "ISFJ"],
    },
    "ENTJ": {
        "연애스타일": "ENTJ는 연애에서도 리더십을 발휘해. 관계를 발전시키는 데 적극적이고 파트너와 함께 성장하는 걸 중요하게 생각해.",
        "장점": "결단력 있고 파트너를 이끌어주는 느낌이 강해. 문제가 생기면 적극적으로 해결하려 해.",
        "단점": "지배적인 성향이 강해서 파트너가 주눌릴 수 있어. 감정보다 효율을 우선시해서 냉정하게 느껴질 수 있어.",
        "갈등패턴": "내 방식이 옳다는 확신이 강해서 타협이 어려울 수 있어. 파트너의 감정을 '비효율'로 볼 때 상처를 줘.",
        "원하는것": "야망 있는 파트너, 함께하는 성장, 명확한 관계 방향",
        "궁합좋음": ["INTP", "INFP"],
        "궁합나쁨": ["ISFP", "INFP"],
    },
    "ENTP": {
        "연애스타일": "ENTP는 연애에서 자극과 새로움을 추구해. 지루한 관계는 금방 흥미를 잃고 파트너와 치열하게 토론하는 걸 즐겨.",
        "장점": "재미있고 유머 감각이 넘쳐. 파트너를 지루하게 내버려 두지 않고 항상 새로운 경험을 제공해.",
        "단점": "변덕스럽고 감정적 일관성이 부족할 수 있어. 논쟁을 즐기다 보니 불필요한 갈등을 만들기도 해.",
        "갈등패턴": "악마의 변호인 역할을 즐겨서 파트너가 무시당한다고 느낄 수 있어. 감정적 공감보다 반박부터 해.",
        "원하는것": "지적으로 대등한 파트너, 새로운 아이디어와 경험, 제약 없는 자유",
        "궁합좋음": ["INTJ", "INFJ"],
        "궁합나쁨": ["ISTJ", "ISFJ"],
    },
    "INFJ": {
        "연애스타일": "INFJ는 소울메이트 같은 깊은 연결을 원해. 상대방의 내면을 꿰뚫어 보는 능력이 있고 관계에 많은 에너지를 쏟아.",
        "장점": "파트너를 깊이 이해하고 공감해줘. 헌신적이고 파트너가 성장할 수 있도록 진심으로 응원해.",
        "단점": "이상적인 관계에 대한 기대가 너무 높아서 현실에 실망하기 쉬워. 상처받으면 마음의 문을 닫아버려.",
        "갈등패턴": "감정을 직접 표현하지 않고 혼자 삭이다가 폭발해. 관계를 위해 자신을 너무 희생해.",
        "원하는것": "진정성 있는 깊은 연결, 감정적 친밀감, 함께 성장하는 관계",
        "궁합좋음": ["ENFP", "ENTP"],
        "궁합나쁨": ["ESTP", "ISTP"],
    },
    "INFP": {
        "연애스타일": "INFP는 이상적인 사랑을 꿈꿔. 현실보다 감정과 가치관의 일치를 더 중요하게 여기고 파트너에게 깊이 헌신해.",
        "장점": "파트너를 있는 그대로 받아들여주고 판단하지 않아. 감정적으로 깊이 공감해주고 로맨틱한 면이 있어.",
        "단점": "현실적인 문제보다 이상에 집착하는 경향이 있어. 갈등을 회피하다 보니 문제가 쌓이기 쉬워.",
        "갈등패턴": "직접 말하지 않고 눈치를 주거나 감정을 숨겨. 비판에 매우 민감하게 반응해.",
        "원하는것": "감정적 안전감, 가치관의 일치, 자신을 이해해주는 파트너",
        "궁합좋음": ["ENFJ", "ENTJ"],
        "궁합나쁨": ["ESTJ", "ENTJ"],
    },
    "ENFJ": {
        "연애스타일": "ENFJ는 파트너를 위해 모든 걸 다 하려는 헌신형이야. 관계의 조화를 최우선으로 생각하고 파트너가 행복한 게 곧 자신의 행복이야.",
        "장점": "공감 능력이 뛰어나고 파트너가 필요한 걸 먼저 알아차려. 관계를 소중히 여기고 갈등 해결에 적극적이야.",
        "단점": "자신의 필요보다 파트너를 너무 챙기다 지쳐. 파트너의 문제를 자신의 책임으로 느껴서 번아웃이 올 수 있어.",
        "갈등패턴": "갈등을 평화롭게 해결하려다 자신의 진짜 감정을 억누를 수 있어. 인정받고 싶은 욕구가 강해.",
        "원하는것": "감정적 연결, 서로에 대한 헌신, 함께하는 성장",
        "궁합좋음": ["INFP", "INTP"],
        "궁합나쁨": ["ISTP", "ESTP"],
    },
    "ENFP": {
        "연애스타일": "ENFP는 연애에서 열정과 에너지가 넘쳐. 파트너에게 온 세상을 줄 것처럼 열렬히 사랑하고 관계에 흥분과 의미를 추구해.",
        "장점": "파트너를 특별하게 느끼게 해주고 항상 새로운 경험을 만들어줘. 감정 표현이 풍부해서 파트너가 사랑받는다고 느껴.",
        "단점": "처음의 열정이 식으면 관심이 분산될 수 있어. 충동적인 결정으로 파트너를 당황스럽게 할 때가 있어.",
        "갈등패턴": "갈등을 회피하거나 감정적으로 과잉 반응할 수 있어. 자유를 억압받으면 관계에서 도망치려 해.",
        "원하는것": "자유롭고 열정적인 관계, 감정적 연결, 모험과 성장",
        "궁합좋음": ["INTJ", "INFJ"],
        "궁합나쁨": ["ISTJ", "ESTJ"],
    },
    "ISTJ": {
        "연애스타일": "ISTJ는 안정적이고 믿을 수 있는 파트너야. 화려한 로맨스보다 꾸준한 행동으로 사랑을 표현하고 약속을 매우 중요하게 여겨.",
        "장점": "책임감 있고 신뢰할 수 있어. 관계에서 안정감을 주고 파트너와의 약속을 끝까지 지켜.",
        "단점": "변화에 저항하고 새로운 시도에 소극적이야. 감정 표현이 적어서 파트너가 애정을 느끼기 어려울 수 있어.",
        "갈등패턴": "'내가 옳다'는 생각이 강해서 타협이 힘들어. 과거의 방식을 고집해서 발전적인 변화를 거부해.",
        "원하는것": "안정적이고 예측 가능한 관계, 신뢰, 명확한 역할 분담",
        "궁합좋음": ["ESFP", "ESTP"],
        "궁합나쁨": ["ENFP", "ENTP"],
    },
    "ISFJ": {
        "연애스타일": "ISFJ는 헌신적이고 세심한 파트너야. 파트너의 작은 것들을 기억하고 챙겨주는 걸 사랑으로 표현해.",
        "장점": "따뜻하고 배려심이 넘쳐. 파트너가 힘들 때 묵묵히 곁에 있어주고 실질적인 도움을 줘.",
        "단점": "거절을 못해서 자신을 너무 희생해. 자신의 감정보다 파트너의 감정을 우선시해서 상처받기 쉬워.",
        "갈등패턴": "불만을 직접 말하지 않고 쌓아두다 한번에 폭발해. 과거의 상처를 잊지 않고 반추하는 경향이 있어.",
        "원하는것": "안정적인 관계, 인정과 감사, 서로 배려하는 관계",
        "궁합좋음": ["ESFP", "ESTP"],
        "궁합나쁨": ["ENTP", "INTP"],
    },
    "ESTJ": {
        "연애스타일": "ESTJ는 관계에 체계와 질서를 가져와. 역할이 명확하고 계획적인 연애를 선호하며 파트너에게 책임감 있는 모습을 보여줘.",
        "장점": "든든하고 믿음직스러워. 관계의 문제를 회피하지 않고 직접 해결하려 하고 파트너를 현실적으로 지원해.",
        "단점": "지나치게 통제적이거나 완고할 수 있어. 감정보다 논리와 규칙을 우선시해서 파트너가 차갑게 느낄 수 있어.",
        "갈등패턴": "자기 방식이 맞다는 확신이 강해서 파트너 의견을 무시하기 쉬워. 비판을 직접적으로 해서 상처를 줄 수 있어.",
        "원하는것": "명확한 관계 방향, 서로의 역할 존중, 신뢰와 성실함",
        "궁합좋음": ["ISFP", "INFP"],
        "궁합나쁨": ["INFP", "ENFP"],
    },
    "ESFJ": {
        "연애스타일": "ESFJ는 관계에 모든 걸 쏟아붓는 헌신형이야. 파트너와 주변 사람들의 조화를 위해 노력하고 사랑받고 싶은 욕구가 강해.",
        "장점": "따뜻하고 사교적이야. 관계를 위해 적극적으로 노력하고 파트너가 필요한 걸 먼저 챙겨줘.",
        "단점": "타인의 평가에 지나치게 신경 써서 파트너와의 관계보다 외부 시선을 의식할 수 있어.",
        "갈등패턴": "갈등을 무마하려고 진짜 문제를 덮어버릴 수 있어. 인정받지 못하면 크게 상처받아.",
        "원하는것": "따뜻한 관계, 서로 표현하는 애정, 사회적으로 인정받는 커플",
        "궁합좋음": ["ISFP", "INFP"],
        "궁합나쁨": ["INTP", "ISTP"],
    },
    "ISTP": {
        "연애스타일": "ISTP는 독립적이고 여유로운 연애를 원해. 파트너에게 집착하지 않고 함께 있어도 각자의 공간을 존중해.",
        "장점": "파트너에게 부담을 주지 않아. 위기 상황에서 침착하게 문제를 해결해주고 실용적인 도움을 잘 줘.",
        "단점": "감정 표현이 매우 서툴러서 파트너가 사랑받는다고 느끼기 어려워. 갑작스러운 거리두기로 파트너를 당황스럽게 해.",
        "갈등패턴": "감정적 대화를 극도로 불편해해서 회피해버려. 자유를 억압받으면 관계에서 이탈하려 해.",
        "원하는것": "개인 공간 존중, 실용적인 관계, 잔소리 없는 자유로운 연애",
        "궁합좋음": ["ESTJ", "ENTJ"],
        "궁합나쁨": ["ENFJ", "INFJ"],
    },
    "ISFP": {
        "연애스타일": "ISFP는 조용하지만 깊은 감정을 가진 연인이야. 말보다 행동으로 사랑을 표현하고 파트너와의 진실한 순간을 소중히 여겨.",
        "장점": "따뜻하고 수용적이야. 파트너를 판단하지 않고 있는 그대로 받아들여줘. 섬세하고 감각적인 면이 있어.",
        "단점": "자신의 감정을 잘 표현하지 않아서 파트너가 답답함을 느낄 수 있어. 갈등을 극도로 싫어해서 회피해.",
        "갈등패턴": "상처를 받으면 말없이 멀어져버려. 감정이 쌓이면 갑작스럽게 관계를 끝내기도 해.",
        "원하는것": "진실하고 평화로운 관계, 자유로운 감정 표현, 강요 없는 연애",
        "궁합좋음": ["ESTJ", "ESFJ"],
        "궁합나쁨": ["ENTJ", "ESTJ"],
    },
    "ESTP": {
        "연애스타일": "ESTP는 자극적이고 활동적인 연애를 즐겨. 현재를 즐기는 스타일로 파트너와 즉흥적인 모험을 함께해.",
        "장점": "연애를 신나고 즐겁게 만들어줘. 사교적이고 매력적이며 위기 상황에서 빠르게 행동해.",
        "단점": "미래보다 현재에 집중해서 관계의 깊이가 부족할 수 있어. 충동적인 행동이 파트너를 불안하게 만들어.",
        "갈등패턴": "감정적 대화를 지루하게 여기고 문제를 대수롭지 않게 넘기려 해. 장기적 계획보다 즉흥적 행동을 선호해.",
        "원하는것": "활동적이고 자유로운 관계, 새로운 경험, 집착 없는 연애",
        "궁합좋음": ["ISTJ", "ISFJ"],
        "궁합나쁨": ["INFJ", "INTJ"],
    },
    "ESFP": {
        "연애스타일": "ESFP는 연애에 온 에너지를 쏟아붓는 타입이야. 파트너를 행복하게 만드는 걸 즐기고 감정 표현이 매우 풍부해.",
        "장점": "밝고 에너지 넘쳐서 파트너를 즐겁게 해줘. 자발적이고 애정 표현이 확실해서 파트너가 사랑받는다고 느껴.",
        "단점": "감정 기복이 있고 충동적인 결정을 해. 깊이 있는 대화보다 즉각적인 즐거움을 선호해.",
        "갈등패턴": "갈등을 농담으로 넘기려 해서 진지한 문제가 해결 안 될 수 있어. 비판에 매우 민감하게 반응해.",
        "원하는것": "즐겁고 활기찬 관계, 풍부한 감정 표현, 현재를 즐기는 연애",
        "궁합좋음": ["ISTJ", "ISFJ"],
        "궁합나쁨": ["INTJ", "INTP"],
    },
}

# 16×16 궁합표 (핵심 설명만)
COMPATIBILITY = {
    ("INTJ", "ENFP"): "서로 다른 방식으로 세상을 보지만 그 차이가 매력이 돼. INTJ의 논리와 ENFP의 감성이 균형을 맞출 때 최고의 커플이 될 수 있어.",
    ("INTJ", "ENTP"): "지적 자극을 서로에게 주는 조합. 논쟁이 많지만 그 과정을 둘 다 즐겨. 감정 표현이 부족한 게 약점이야.",
    ("INFJ", "ENFP"): "깊은 감정적 연결과 가치관 공유가 강점. ENFP의 에너지가 INFJ를 세상으로 끌어내주고 INFJ의 깊이가 ENFP를 안정시켜줘.",
    ("INFP", "ENFJ"): "ENFJ가 INFP를 이해하고 이끌어주는 관계. 서로의 감정을 존중하는 따뜻한 커플이야.",
    ("ISTJ", "ESFP"): "안정과 활기의 조합. ISTJ의 든든함에 ESFP가 즐거움을 더해줘. 가치관 차이를 존중하면 잘 맞아.",
    ("ISFJ", "ESTP"): "ESTP가 ISFJ를 새로운 경험으로 이끌고 ISFJ가 ESTP에게 안정감을 줘. 서로 부족한 부분을 채워주는 관계야.",
    ("ESTJ", "ISFP"): "ESTJ의 계획성과 ISFP의 유연함이 보완 관계야. 서로 존중하면 균형 잡힌 관계가 돼.",
    ("ESFJ", "INFP"): "따뜻하고 감정적인 연결이 강한 조합. 서로 배려하는 마음이 관계의 핵심이야.",
    ("INTP", "ENTJ"): "지적으로 대등한 파트너십. ENTJ가 방향을 잡고 INTP가 아이디어를 제공하는 역할 분담이 자연스러워.",
    ("ENFJ", "INFP"): "서로를 깊이 이해하고 성장을 응원하는 관계. 감정적 연결이 매우 깊어.",
    ("ENTP", "INTJ"): "최강의 지적 파트너십. 서로 자극을 주고받으며 성장해. 감정 소통이 부족할 수 있어.",
    ("ESTP", "ISTJ"): "현실적이고 안정적인 관계. 서로 다른 속도를 맞춰가는 게 중요해.",
}


def build_static_docs() -> list[dict]:
    docs = []

    for mbti, traits in MBTI_LOVE_TRAITS.items():
        # 각 특징별로 문서 생성
        for trait_name, content in traits.items():
            if trait_name in ("궁합좋음", "궁합나쁨"):
                continue
            text = f"{mbti} {trait_name}: {content}"
            docs.append({
                "text": text,
                "metadata": {
                    "source": "mbti_static_dataset",
                    "channel": "MBTI 연애 데이터",
                    "title": f"{mbti} {trait_name}",
                    "mbti": mbti,
                    "category": "MBTI",
                },
            })

        # 궁합 좋음 문서
        good = traits.get("궁합좋음", [])
        if good:
            text = f"{mbti}의 연애 궁합이 좋은 유형: {', '.join(good)}. {mbti}는 {', '.join(good)}와 잘 맞아. 서로 보완적인 관계야."
            docs.append({
                "text": text,
                "metadata": {
                    "source": "mbti_static_dataset",
                    "channel": "MBTI 연애 데이터",
                    "title": f"{mbti} 궁합",
                    "mbti": mbti,
                    "category": "MBTI",
                },
            })

        # 궁합 나쁨 문서
        bad = traits.get("궁합나쁨", [])
        if bad:
            text = f"{mbti}와 갈등이 생기기 쉬운 유형: {', '.join(bad)}. 가치관이나 소통 방식 차이가 커서 노력이 필요해."
            docs.append({
                "text": text,
                "metadata": {
                    "source": "mbti_static_dataset",
                    "channel": "MBTI 연애 데이터",
                    "title": f"{mbti} 갈등 유형",
                    "mbti": mbti,
                    "category": "MBTI",
                },
            })

    # 궁합 상세 설명
    for (a, b), desc in COMPATIBILITY.items():
        text = f"{a}과 {b}의 궁합: {desc}"
        for mbti in (a, b):
            docs.append({
                "text": text,
                "metadata": {
                    "source": "mbti_static_dataset",
                    "channel": "MBTI 연애 데이터",
                    "title": f"{a}-{b} 궁합",
                    "mbti": mbti,
                    "category": "MBTI",
                },
            })

    print(f"정적 데이터셋: {len(docs)}개 문서 생성")
    return docs


# ─────────────────────────────────────────────
# 2. DC인사이드 MBTI 갤러리 크롤러
# ─────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

DC_MBTI_GALLERIES = [
    ("mbti_new", "MBTI 마이너갤"),
    ("lovelanguage", "사랑언어갤"),
]

DC_BASE = "https://gall.dcinside.com/mgallery/board/lists"
DC_POST_BASE = "https://gall.dcinside.com/mgallery/board/view"

PROFANITY_LIST = [
    "씨발", "씨바", "시발", "ㅅㅂ", "개새끼", "병신", "ㅂㅅ",
    "지랄", "미친놈", "미친년", "새끼", "ㅅㄲ", "꺼져", "닥쳐",
    "찐따", "창녀", "갈보", "느금마", "니애미",
]

SPAM_PATTERNS = [
    r"https?://\S+",
    r"ㅋ{4,}", r"ㅎ{4,}", r"ㅠ{4,}",
    r"\.{4,}", r"[ㄱ-ㅎ]{5,}",
    r"광고|홍보|이벤트|클릭|가입",
]


def detect_mbti(text: str) -> str | None:
    """텍스트에서 MBTI 유형 감지"""
    for mbti in MBTI_TYPES:
        if mbti in text.upper():
            return mbti
    return None


def preprocess(text: str) -> str:
    for word in PROFANITY_LIST:
        text = text.replace(word, "")
    for pattern in SPAM_PATTERNS:
        text = re.sub(pattern, "", text)
    return re.sub(r"\s+", " ", text).strip()


def is_valid(text: str) -> bool:
    if len(text) < 30:
        return False
    return len(re.findall(r"[가-힣]", text)) / max(len(text), 1) > 0.3


def get_soup(url: str, params: dict = None, delay: float = 1.0) -> BeautifulSoup | None:
    time.sleep(delay)
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  [ERR] {url} → {e}")
        return None


def crawl_dc_page(gallery_id: str, page: int) -> list[dict]:
    soup = get_soup(DC_BASE, params={"id": gallery_id, "page": page})
    if not soup:
        return []
    posts = []
    for row in soup.select("tr.ub-content"):
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


def crawl_dc_post(gallery_id: str, no: str, title: str) -> list[dict]:
    url = f"{DC_POST_BASE}/?id={gallery_id}&no={no}"
    soup = get_soup(url, delay=0.8)
    if not soup:
        return []

    docs = []
    mbti_in_title = detect_mbti(title)

    # 본문
    body_tag = soup.select_one(".write_div")
    if body_tag:
        body = preprocess(body_tag.get_text(separator=" ", strip=True))
        full = f"{title}. {body}"
        if is_valid(body):
            mbti = mbti_in_title or detect_mbti(body)
            docs.append({
                "text": full,
                "metadata": {
                    "source": url,
                    "channel": "DC인사이드 MBTI갤",
                    "title": title,
                    "mbti": mbti or "기타",
                    "category": "MBTI",
                },
            })

    # 댓글 (추천 1 이상)
    for cmt in soup.select(".cmt_info"):
        rec_tag = cmt.select_one(".reply_recommend_btn")
        rec = int(rec_tag.get_text(strip=True) or "0") if rec_tag else 0
        txt_tag = cmt.select_one(".usertxt")
        if not txt_tag:
            continue
        txt = preprocess(txt_tag.get_text(separator=" ", strip=True))
        if rec >= 1 and is_valid(txt):
            mbti = mbti_in_title or detect_mbti(txt)
            docs.append({
                "text": txt,
                "metadata": {
                    "source": url,
                    "channel": "DC인사이드 MBTI갤",
                    "title": title,
                    "mbti": mbti or "기타",
                    "category": "MBTI",
                },
            })

    return docs


async def run_dcinside(pages: int, processed: set) -> list[dict]:
    all_docs = []
    for gallery_id, gallery_name in DC_MBTI_GALLERIES:
        print(f"\n[DC인사이드] {gallery_name} — {pages}페이지")
        for page in range(1, pages + 1):
            print(f"  페이지 {page}/{pages}", end="\r")
            posts = crawl_dc_page(gallery_id, page)
            for post in posts:
                pid = f"dc_mbti_{gallery_id}_{post['no']}"
                if pid in processed:
                    continue
                docs = crawl_dc_post(post["gallery_id"], post["no"], post["title"])
                all_docs.extend(docs)
                processed.add(pid)
            save_processed(processed)
        print(f"  {gallery_name} 완료")
    return all_docs


# ─────────────────────────────────────────────
# Qdrant 업로드
# ─────────────────────────────────────────────
async def upload(docs: list[dict]) -> None:
    if not docs:
        print("업로드할 문서 없음")
        return
    client = get_qdrant_client()
    await ensure_collection(client)

    # mbti 페이로드 인덱스 추가
    from qdrant_client.models import PayloadSchemaType
    try:
        await client.create_payload_index(
            collection_name="love_counseling",
            field_name="mbti",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception:
        pass  # 이미 존재하면 무시

    batch_size = 10
    total = len(docs)
    print(f"\nQdrant 업로드: 총 {total}개 문서")
    for i in range(0, total, batch_size):
        batch = docs[i: i + batch_size]
        await upsert_documents(client, batch)
        print(f"  [{min(i + batch_size, total)}/{total}]", end="\r")
    await client.close()
    print(f"\n완료!")


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
async def main(source: str, pages: int) -> None:
    processed = load_processed()
    all_docs = []

    if source in ("static", "all"):
        docs = build_static_docs()
        all_docs.extend(docs)

    if source in ("dcinside", "all"):
        docs = await run_dcinside(pages, processed)
        print(f"DC인사이드 MBTI갤: {len(docs)}개 문서 수집")
        all_docs.extend(docs)

    print(f"\n총 {len(all_docs)}개 문서")
    await upload(all_docs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MBTI 연애 데이터 → Qdrant")
    parser.add_argument(
        "--source",
        required=True,
        choices=["static", "dcinside", "all"],
        help="데이터 소스 (static=정적데이터, dcinside=갤러리크롤링, all=둘다)",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=20,
        help="DC인사이드 크롤링 페이지 수 (기본: 20)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.source, args.pages))
