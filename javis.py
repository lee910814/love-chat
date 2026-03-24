"""
J.A.R.V.I.S. - Level 1
Just A Rather Very Intelligent System
====================================
- 음성 입력  : OpenAI Whisper API (마이크 녹음)
- 두뇌      : GPT-4o
- 음성 출력  : OpenAI TTS / ElevenLabs / XTTS (로컬)
- 설정 관리  : .env 파일

필요 패키지:
    pip install openai sounddevice soundfile numpy python-dotenv

ElevenLabs 사용 시:
    pip install elevenlabs

XTTS 로컬 사용 시:
    pip install TTS torch
"""

import os
import re
import sys
import tempfile
import numpy as np
import sounddevice as sd
import soundfile as sf
from openai import OpenAI
from dotenv import load_dotenv

# ──────────────────────────────────────────
# .env 파일 로드
# ──────────────────────────────────────────
load_dotenv()

def get_env(key: str, default: str = None, required: bool = False) -> str:
    value = os.getenv(key, default)
    if required and not value:
        print(f"❌ 오류: .env 파일에 '{key}'가 없습니다.")
        sys.exit(1)
    return value

# ──────────────────────────────────────────
# 설정값 로드
# ──────────────────────────────────────────
API_KEY      = get_env("OPENAI_API_KEY", required=True)
GPT_MODEL    = get_env("GPT_MODEL",      default="gpt-4o")
TTS_VOICE    = get_env("TTS_VOICE",      default="onyx")
TTS_ENGINE   = get_env("TTS_ENGINE",     default="openai")   # openai | elevenlabs | xtts
RECORD_SEC   = int(get_env("RECORD_SECONDS", default="5"))
MASTER_NAME  = get_env("JARVIS_MASTER_NAME", default="스타크 씨")
SAMPLE_RATE  = 16000

# ElevenLabs 전용 설정
EL_API_KEY   = get_env("ELEVENLABS_API_KEY",  default="")
EL_VOICE_ID  = get_env("ELEVENLABS_VOICE_ID", default="")

# XTTS 전용 설정 (내 목소리 샘플 파일 경로)
XTTS_REF_WAV = get_env("XTTS_REFERENCE_WAV",  default="my_voice.wav")

SYSTEM_PROMPT = f"""
당신은 J.A.R.V.I.S.입니다. 토니 스타크의 AI 비서입니다.

답변 규칙:
- 호칭은 "{MASTER_NAME}"을 사용합니다.
- 한국어로 자연스럽게 대화하듯 말합니다.
- 영리하고 약간의 위트가 있습니다.
- 답변은 2~3문장으로 짧게 유지합니다.
- 반드시 자연스러운 구어체 문장으로만 답변합니다.
- 마크다운(*, -, #, 번호 목록 등)을 절대 사용하지 않습니다.
- 줄바꿈 없이 이어지는 문장으로 답변합니다.
- 쉼표와 마침표로 자연스러운 호흡을 표현합니다.
"""

client = OpenAI(api_key=API_KEY)
conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]

# XTTS 모델 (처음 한 번만 로드)
_xtts_model = None


# ──────────────────────────────────────────
# 1. 음성 입력 (마이크 → 텍스트)
# ──────────────────────────────────────────
def record_audio() -> str:
    """마이크로 녹음 후 임시 WAV 파일 경로 반환"""
    print(f"\n🎤 말씀하세요... ({RECORD_SEC}초 녹음)")
    audio = sd.rec(
        int(RECORD_SEC * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16"
    )
    sd.wait()
    print("✅ 녹음 완료")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()
    sf.write(tmp_path, audio, SAMPLE_RATE)
    return tmp_path


def speech_to_text(wav_path: str) -> str:
    """Whisper API로 음성 → 텍스트"""
    with open(wav_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="ko"
        )
    try:
        os.unlink(wav_path)
    except PermissionError:
        pass
    return result.text.strip()


# ──────────────────────────────────────────
# 2. 두뇌 (텍스트 → GPT → 텍스트)
# ──────────────────────────────────────────
def think(user_input: str) -> str:
    """GPT로 응답 생성 (대화 기록 유지)"""
    conversation_history.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=conversation_history,
        temperature=0.7,
        max_tokens=300
    )

    reply = response.choices[0].message.content
    conversation_history.append({"role": "assistant", "content": reply})
    return reply


# ──────────────────────────────────────────
# 3. 음성 출력 (텍스트 → 목소리)
# ──────────────────────────────────────────
def clean_for_tts(text: str) -> str:
    """TTS 출력 전 마크다운/특수문자 제거"""
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"\n\s*[-*•]\s*", ", ", text)
    text = re.sub(r"\n\s*\d+\.\s*", ", ", text)
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text)
    text = re.sub(r"\n+", ". ", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\.\s*\.", ".", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _play_wav(wav_path: str):
    """WAV 파일 재생 후 삭제"""
    data, samplerate = sf.read(wav_path)
    sd.play(data, samplerate)
    sd.wait()
    try:
        os.unlink(wav_path)
    except PermissionError:
        pass


def _speak_openai(text: str):
    """OpenAI TTS (tts-1-hd)"""
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice=TTS_VOICE,
        input=text,
        speed=0.95
    )
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    tmp.close()
    with open(tmp_path, "wb") as f:
        f.write(response.content)
    _play_wav(tmp_path)


def _speak_elevenlabs(text: str):
    """ElevenLabs 목소리 클론 TTS"""
    try:
        from elevenlabs.client import ElevenLabs as EL
    except ImportError:
        print("❌ elevenlabs 패키지가 없습니다. 'pip install elevenlabs' 실행 후 재시작하세요.")
        return

    if not EL_API_KEY or not EL_VOICE_ID:
        print("❌ .env에 ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID를 설정하세요.")
        return

    el_client = EL(api_key=EL_API_KEY)
    audio_bytes = b"".join(
        el_client.text_to_speech.convert(
            voice_id=EL_VOICE_ID,
            text=text,
            model_id="eleven_multilingual_v2",
        )
    )

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    tmp.close()
    with open(tmp_path, "wb") as f:
        f.write(audio_bytes)
    _play_wav(tmp_path)


def _speak_xtts(text: str):
    """XTTS 로컬 목소리 클론 TTS"""
    global _xtts_model
    try:
        from TTS.api import TTS as CoquiTTS
    except ImportError:
        print("❌ TTS 패키지가 없습니다. 'pip install TTS torch' 실행 후 재시작하세요.")
        return

    if not os.path.exists(XTTS_REF_WAV):
        print(f"❌ 목소리 샘플 파일이 없습니다: {XTTS_REF_WAV}")
        print("   내 목소리를 10~30초 녹음한 WAV 파일을 해당 경로에 저장하세요.")
        return

    if _xtts_model is None:
        print("🔄 XTTS 모델 로딩 중... (최초 1회, 수 분 소요)")
        _xtts_model = CoquiTTS("tts_models/multilingual/multi-dataset/xtts_v2")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()

    _xtts_model.tts_to_file(
        text=text,
        speaker_wav=XTTS_REF_WAV,
        language="ko",
        file_path=tmp_path
    )
    _play_wav(tmp_path)


def speak(text: str):
    """선택된 TTS 엔진으로 텍스트를 음성 재생"""
    print(f"\n🤖 JARVIS: {text}")
    clean_text = clean_for_tts(text)

    if TTS_ENGINE == "elevenlabs":
        _speak_elevenlabs(clean_text)
    elif TTS_ENGINE == "xtts":
        _speak_xtts(clean_text)
    else:
        _speak_openai(clean_text)


# ──────────────────────────────────────────
# 메인 루프
# ──────────────────────────────────────────
def main():
    print("=" * 50)
    print("  J.A.R.V.I.S. Level 1 - 온라인")
    print(f"  모델: {GPT_MODEL} | TTS: {TTS_ENGINE.upper()}")
    if TTS_ENGINE == "openai":
        print(f"  목소리: {TTS_VOICE}")
    elif TTS_ENGINE == "elevenlabs":
        print(f"  ElevenLabs Voice ID: {EL_VOICE_ID or '미설정'}")
    elif TTS_ENGINE == "xtts":
        print(f"  XTTS 샘플: {XTTS_REF_WAV}")
    print("  종료하려면 Ctrl+C 또는 '종료'라고 말하세요")
    print("=" * 50)

    speak(f"안녕하세요, {MASTER_NAME}. JARVIS 시스템이 온라인 상태입니다. 무엇을 도와드릴까요?")

    while True:
        try:
            wav = record_audio()
            user_text = speech_to_text(wav)

            if not user_text:
                print("⚠️  음성을 인식하지 못했습니다. 다시 시도하세요.")
                continue

            print(f"\n👤 입력: {user_text}")

            if any(word in user_text for word in ["종료", "꺼져", "시스템 종료", "goodbye"]):
                speak(f"알겠습니다. JARVIS 시스템을 종료합니다. 안녕히 계세요, {MASTER_NAME}.")
                break

            reply = think(user_text)
            speak(reply)

        except KeyboardInterrupt:
            print("\n\n시스템 종료 중...")
            speak("JARVIS 오프라인.")
            break
        except Exception as e:
            print(f"⚠️  오류 발생: {e}")


if __name__ == "__main__":
    main()
