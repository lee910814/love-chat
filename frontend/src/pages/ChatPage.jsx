/** @jsxImportSource @emotion/react */
import styled from "@emotion/styled";
import { useState, useRef, useEffect, useCallback } from "react";
import { css } from "@emotion/react";
import { useNavigate } from "react-router-dom";
import { streamChat, chatAPI } from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import MessageBubble from "../components/MessageBubble";
import { theme } from "../theme";

const API_BASE = import.meta.env.VITE_API_URL || "";

// ─────────────────────────── 스타일 ───────────────────────────

const Layout = styled.div`
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: ${theme.colors.background};
  font-family: ${theme.fonts.base};
`;

const Header = styled.header`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: ${theme.colors.surface};
  border-bottom: 1.5px solid ${theme.colors.border};
  box-shadow: 0 2px 8px rgba(255, 107, 157, 0.08);
  flex-shrink: 0;
`;

const HeaderLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
`;

const HeaderIcon = styled.span`
  font-size: 1.5rem;
`;

const HeaderTitle = styled.h1`
  font-size: 1.1rem;
  font-weight: 600;
  color: ${theme.colors.text};
  margin: 0;
  cursor: pointer;
  &:hover { color: ${theme.colors.primary}; }
`;

const HeaderSub = styled.p`
  font-size: 0.75rem;
  color: ${theme.colors.textMuted};
  margin: 0;
`;

const HeaderRight = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const Username = styled.span`
  font-size: 0.875rem;
  color: ${theme.colors.textSecondary};
  font-weight: 500;
`;

const HeaderBtn = styled.button`
  padding: 7px 16px;
  background: transparent;
  border: 1.5px solid ${theme.colors.border};
  border-radius: ${theme.radii.full};
  color: ${theme.colors.textSecondary};
  font-size: 0.8rem;
  font-family: ${theme.fonts.base};
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: ${theme.colors.primary};
    color: ${theme.colors.primary};
  }
`;

const GuestBadge = styled.span`
  font-size: 0.75rem;
  color: ${theme.colors.textMuted};
  background: ${theme.colors.surfaceAlt};
  border: 1px solid ${theme.colors.border};
  border-radius: ${theme.radii.full};
  padding: 4px 10px;
`;

const CategoryBar = styled.div`
  display: flex;
  gap: 8px;
  padding: 10px 20px;
  overflow-x: auto;
  background: ${theme.colors.surface};
  border-bottom: 1px solid ${theme.colors.border};
  flex-shrink: 0;

  &::-webkit-scrollbar { display: none; }
`;

const CategoryChip = styled.button`
  padding: 5px 14px;
  border-radius: ${theme.radii.full};
  border: 1.5px solid ${(p) => (p.active ? theme.colors.primary : theme.colors.border)};
  background: ${(p) => (p.active ? theme.colors.primary : "transparent")};
  color: ${(p) => (p.active ? "white" : theme.colors.textSecondary)};
  font-size: 0.8rem;
  font-family: ${theme.fonts.base};
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;

  &:hover {
    border-color: ${theme.colors.primary};
    color: ${(p) => (p.active ? "white" : theme.colors.primary)};
  }
`;

const MessageArea = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
  display: flex;
  flex-direction: column;

  /* 스크롤바 커스텀 */
  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-thumb {
    background: ${theme.colors.primaryLight};
    border-radius: 3px;
  }
`;

const WelcomeBox = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  text-align: center;
  padding: 40px 20px;
`;

const WelcomeEmoji = styled.div`
  font-size: 3.5rem;
  margin-bottom: 16px;
`;

const WelcomeTitle = styled.h2`
  font-size: 1.3rem;
  font-weight: 600;
  color: ${theme.colors.text};
  margin: 0 0 10px;
`;

const WelcomeDesc = styled.p`
  color: ${theme.colors.textMuted};
  font-size: 0.9rem;
  line-height: 1.6;
  max-width: 320px;
`;

const SuggestGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 24px;
  width: 100%;
  max-width: 400px;
`;

const SuggestCard = styled.button`
  padding: 12px 14px;
  background: ${theme.colors.surface};
  border: 1.5px solid ${theme.colors.border};
  border-radius: ${theme.radii.lg};
  font-size: 0.82rem;
  color: ${theme.colors.textSecondary};
  font-family: ${theme.fonts.base};
  cursor: pointer;
  text-align: left;
  line-height: 1.4;
  transition: all 0.2s;

  &:hover {
    border-color: ${theme.colors.primary};
    color: ${theme.colors.primary};
    background: ${theme.colors.surfaceAlt};
  }
`;

const MESSAGE_MAX = 500;

const InputArea = styled.form`
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 12px 20px 16px;
  background: ${theme.colors.surface};
  border-top: 1.5px solid ${theme.colors.border};
  flex-shrink: 0;
  flex-direction: column;
`;

const InputRow = styled.div`
  display: flex;
  align-items: flex-end;
  gap: 10px;
  width: 100%;
`;

const InputMeta = styled.div`
  display: flex;
  justify-content: flex-end;
  width: 100%;
`;

const CharCount = styled.span`
  font-size: 0.75rem;
  color: ${(p) => (p.over ? theme.colors.error : theme.colors.textMuted)};
`;

const TextArea = styled.textarea`
  flex: 1;
  padding: 12px 16px;
  border: 1.5px solid ${(p) => (p.over ? theme.colors.error : theme.colors.border)};
  border-radius: ${theme.radii.lg};
  font-size: 0.95rem;
  font-family: ${theme.fonts.base};
  color: ${theme.colors.text};
  resize: none;
  outline: none;
  min-height: 48px;
  max-height: 140px;
  line-height: 1.5;
  transition: border-color 0.2s;
  overflow-y: auto;

  &:focus {
    border-color: ${(p) => (p.over ? theme.colors.error : theme.colors.primary)};
  }
  &::placeholder {
    color: ${theme.colors.textMuted};
  }
`;

const SendBtn = styled.button`
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: ${(p) => (p.disabled ? theme.colors.border : theme.colors.primary)};
  border: none;
  cursor: ${(p) => (p.disabled ? "not-allowed" : "pointer")};
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  flex-shrink: 0;
  transition: background 0.2s, transform 0.1s;
  box-shadow: ${(p) => (p.disabled ? "none" : theme.shadows.button)};

  &:hover:not(:disabled) {
    background: ${theme.colors.primaryDark};
  }
  &:active:not(:disabled) {
    transform: scale(0.93);
  }
`;

const MicBtn = styled.button`
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: ${(p) => (p.recording ? "#ff4757" : theme.colors.surface)};
  border: 1.5px solid ${(p) => (p.recording ? "#ff4757" : theme.colors.border)};
  cursor: ${(p) => (p.disabled ? "not-allowed" : "pointer")};
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  flex-shrink: 0;
  transition: all 0.2s;
  opacity: ${(p) => (p.disabled ? 0.5 : 1)};

  ${(p) =>
    p.recording &&
    css`
      animation: pulse 1s infinite;
      @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(255, 71, 87, 0.4); }
        50% { box-shadow: 0 0 0 8px rgba(255, 71, 87, 0); }
      }
    `}

  &:hover:not(:disabled) {
    border-color: ${theme.colors.primary};
  }
`;

const SUGGESTIONS = [
  "고백해야 할지 모르겠어요",
  "카톡 답장이 늦어요",
  "싸우고 나서 먼저 연락해야 할까요?",
  "썸타는 사람이 다른 이성을 만나요",
];

const CATEGORIES = [
  { label: "전체", value: null },
  { label: "썸", value: "썸" },
  { label: "고백", value: "고백" },
  { label: "이별", value: "이별" },
  { label: "권태기", value: "권태기" },
  { label: "재회", value: "재회" },
  { label: "연락", value: "연락" },
  { label: "질투/바람", value: "질투/바람" },
  { label: "결혼", value: "결혼" },
  { label: "기타", value: "기타" },
];

// ─────────────────────────── 컴포넌트 ───────────────────────────

export default function ChatPage() {
  const { user, token, logout } = useAuth();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  // 로그인 유저 → 대화 기록 불러오기
  useEffect(() => {
    if (!token) return;
    setHistoryLoading(true);
    chatAPI.history()
      .then((res) => {
        const loaded = res.data.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
        }));
        setMessages(loaded);
      })
      .catch(() => {})
      .finally(() => setHistoryLoading(false));
  }, [token]);

  // 새 메시지마다 스크롤 하단 이동
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const isGuest = !token;

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed || streaming) return;

      // 현재까지의 대화를 history로 구성 (스트리밍 중인 메시지 제외)
      const history = messages
        .filter((m) => !m.streaming && m.content)
        .map((m) => ({ role: m.role, content: m.content }));

      const userMsg = { id: Date.now(), role: "user", content: trimmed };
      const aiMsg = { id: Date.now() + 1, role: "assistant", content: "", streaming: true };

      setMessages((prev) => [...prev, userMsg, aiMsg]);
      setInput("");
      setStreaming(true);

      await streamChat(
        trimmed,
        token ?? null,
        (delta) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === aiMsg.id ? { ...m, content: m.content + delta } : m))
          );
        },
        () => {
          setMessages((prev) =>
            prev.map((m) => (m.id === aiMsg.id ? { ...m, streaming: false } : m))
          );
          setStreaming(false);
        },
        (errMsg) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsg.id
                ? { ...m, content: `오류가 발생했습니다: ${errMsg}`, streaming: false }
                : m
            )
          );
          setStreaming(false);
        },
        selectedCategory,
        history,
        (emotion) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === userMsg.id ? { ...m, emotion } : m))
          );
        }
      );
    },
    [token, streaming, messages, selectedCategory]
  );

  const handleMic = useCallback(async () => {
    if (recording) {
      mediaRecorderRef.current?.stop();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        },
      });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setRecording(false);
        setTranscribing(true);

        try {
          const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
          const formData = new FormData();
          formData.append("file", blob, "audio.webm");

          const headers = {};
          if (token) headers.Authorization = `Bearer ${token}`;

          const res = await fetch(`${API_BASE}/chat/transcribe`, { method: "POST", headers, body: formData });
          if (!res.ok) throw new Error("변환 실패");
          const { text } = await res.json();
          if (text.trim()) {
            sendMessage(text.trim());
          }
        } catch (err) {
          console.error("STT 오류:", err);
        } finally {
          setTranscribing(false);
        }
      };

      mediaRecorder.start();
      setRecording(true);
    } catch {
      alert("마이크 권한이 필요합니다.");
    }
  }, [recording, token, sendMessage]);

  // 스페이스바 PTT (Push-to-Talk)
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.code !== "Space") return;
      if (e.repeat) return;
      // textarea에 포커스가 있으면 일반 타이핑으로 처리
      if (document.activeElement === textareaRef.current) return;
      e.preventDefault();
      if (!recording && !streaming && !transcribing) {
        handleMic();
      }
    };

    const onKeyUp = (e) => {
      if (e.code !== "Space") return;
      if (document.activeElement === textareaRef.current) return;
      if (recording) {
        mediaRecorderRef.current?.stop();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [recording, streaming, transcribing, handleMic]);

  const handleClearHistory = async () => {
    if (!window.confirm("대화 기록을 모두 삭제할까요?")) return;
    await chatAPI.clearHistory();
    setMessages([]);
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  // textarea 높이 자동 조절
  const handleInput = (e) => {
    setInput(e.target.value);
    const el = textareaRef.current;
    if (el) {
      el.style.height = "48px";
      el.style.height = Math.min(el.scrollHeight, 140) + "px";
    }
  };

  return (
    <Layout>
      <Header>
        <HeaderLeft>
          <div>
            <HeaderTitle onClick={() => setMessages([])}>연애 상담 AI</HeaderTitle>
            <HeaderSub>유튜브 상담 전문가 기반 RAG</HeaderSub>
          </div>
        </HeaderLeft>
        <HeaderRight>
          {isGuest ? (
            <>
              <GuestBadge>비회원</GuestBadge>
            </>
          ) : (
            <>
              {user && <Username>{user.username}님</Username>}
              <HeaderBtn onClick={handleClearHistory} disabled={streaming}>대화 초기화</HeaderBtn>
              <HeaderBtn onClick={() => navigate("/mypage")}>마이페이지</HeaderBtn>
              <HeaderBtn onClick={handleLogout}>로그아웃</HeaderBtn>
            </>
          )}
        </HeaderRight>
      </Header>

      <MessageArea>
        {historyLoading ? (
          <WelcomeBox>
            <WelcomeEmoji>💕</WelcomeEmoji>
            <WelcomeTitle>대화 기록 불러오는 중...</WelcomeTitle>
          </WelcomeBox>
        ) : messages.length === 0 ? (
          <WelcomeBox>
            <WelcomeTitle>연애 고민이 있으신가요?</WelcomeTitle>
            <SuggestGrid>
              {SUGGESTIONS.map((s) => (
                <SuggestCard key={s} onClick={() => sendMessage(s)} disabled={streaming}>
                  {s}
                </SuggestCard>
              ))}
            </SuggestGrid>
          </WelcomeBox>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}
        <div ref={bottomRef} />
      </MessageArea>

      <InputArea onSubmit={handleSubmit}>
        <InputRow>
          <TextArea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={transcribing ? "음성 변환 중..." : recording ? "말씀하세요... (스페이스바를 떼면 전송)" : "연애 고민을 입력하세요... (Enter 전송 / 스페이스바 음성입력)"}
            disabled={streaming || transcribing}
            rows={1}
            over={input.length > MESSAGE_MAX}
          />
          <MicBtn
            type="button"
            recording={recording}
            disabled={streaming || transcribing}
            onClick={handleMic}
            title={recording ? "스페이스바를 떼면 전송" : "스페이스바를 누르고 있으면 녹음"}
          >
            {transcribing ? "⏳" : recording ? "⏹" : "🎤"}
          </MicBtn>
          <SendBtn type="submit" disabled={!input.trim() || streaming || input.length > MESSAGE_MAX}>
            {streaming ? "⏳" : "➤"}
          </SendBtn>
        </InputRow>
        <InputMeta>
          <CharCount over={input.length > MESSAGE_MAX}>
            {input.length} / {MESSAGE_MAX}
          </CharCount>
        </InputMeta>
      </InputArea>
    </Layout>
  );
}
