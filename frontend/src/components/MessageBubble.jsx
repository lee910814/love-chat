/** @jsxImportSource @emotion/react */
import styled from "@emotion/styled";
import { theme } from "../theme";

const Wrapper = styled.div`
  display: flex;
  flex-direction: column;
  align-items: ${(p) => (p.$isUser ? "flex-end" : "flex-start")};
  margin-bottom: 16px;
`;

const SenderLabel = styled.span`
  font-size: 0.75rem;
  color: ${theme.colors.textMuted};
  margin-bottom: 4px;
  padding: 0 4px;
`;

const Bubble = styled.div`
  max-width: 72%;
  padding: 14px 18px;
  border-radius: ${(p) => (p.$isUser ? "20px 20px 4px 20px" : "20px 20px 20px 4px")};
  background: ${(p) => (p.$isUser ? theme.colors.userBubble : theme.colors.aiBubble)};
  color: ${(p) => (p.$isUser ? "#fff" : theme.colors.text)};
  box-shadow: ${theme.shadows.bubble};
  font-size: 0.95rem;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  border: ${(p) => (p.$isUser ? "none" : `1.5px solid ${theme.colors.border}`)};
`;

const EmotionBadge = styled.span`
  font-size: 0.75rem;
  color: ${theme.colors.textMuted};
  margin-top: 4px;
  padding: 2px 8px;
  background: ${theme.colors.surface};
  border: 1px solid ${theme.colors.border};
  border-radius: ${theme.radii.full};
  align-self: flex-end;
`;

const Cursor = styled.span`
  display: inline-block;
  width: 2px;
  height: 1em;
  background: ${theme.colors.primary};
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 0.7s step-end infinite;

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }
`;

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <Wrapper $isUser={isUser}>
      {isUser && <SenderLabel>나</SenderLabel>}
      <Bubble $isUser={isUser}>
        {message.content}
        {message.streaming && <Cursor />}
      </Bubble>
      {isUser && message.emotion && (
        <EmotionBadge>{message.emotion.emoji} {message.emotion.label}</EmotionBadge>
      )}
    </Wrapper>
  );
}
