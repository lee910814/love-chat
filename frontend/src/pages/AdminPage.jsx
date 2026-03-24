/** @jsxImportSource @emotion/react */
import styled from "@emotion/styled";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { adminAPI } from "../api/client";
import { theme } from "../theme";

// ─────────────────────────── 스타일 ───────────────────────────

const Layout = styled.div`
  min-height: 100vh;
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
`;

const HeaderTitle = styled.h1`
  font-size: 1.1rem;
  font-weight: 600;
  color: ${theme.colors.text};
  margin: 0;
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
  &:hover { border-color: ${theme.colors.primary}; color: ${theme.colors.primary}; }
`;

const Content = styled.div`
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px;
`;

const SectionTitle = styled.h2`
  font-size: 1rem;
  font-weight: 600;
  color: ${theme.colors.text};
  margin: 0 0 16px;
`;

const TabBar = styled.div`
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
`;

const Tab = styled.button`
  padding: 8px 20px;
  border-radius: ${theme.radii.full};
  border: 1.5px solid ${(p) => (p.active ? theme.colors.primary : theme.colors.border)};
  background: ${(p) => (p.active ? theme.colors.primary : "transparent")};
  color: ${(p) => (p.active ? "white" : theme.colors.textSecondary)};
  font-size: 0.85rem;
  font-family: ${theme.fonts.base};
  cursor: pointer;
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  background: ${theme.colors.surface};
  border-radius: ${theme.radii.lg};
  overflow: hidden;
  box-shadow: ${theme.shadows.card};
`;

const Th = styled.th`
  padding: 12px 16px;
  text-align: left;
  font-size: 0.8rem;
  font-weight: 600;
  color: ${theme.colors.textMuted};
  background: ${theme.colors.surfaceAlt};
  border-bottom: 1px solid ${theme.colors.border};
`;

const Td = styled.td`
  padding: 12px 16px;
  font-size: 0.85rem;
  color: ${theme.colors.text};
  border-bottom: 1px solid ${theme.colors.border};
`;

const RiskBadge = styled.span`
  padding: 3px 10px;
  border-radius: ${theme.radii.full};
  font-size: 0.75rem;
  font-weight: 600;
  background: ${(p) =>
    p.level === "위험" ? "#ffe0e6" :
    p.level === "주의" ? "#fff3e0" :
    p.level === "보통" ? "#e8f5e9" : "#e3f2fd"};
  color: ${(p) =>
    p.level === "위험" ? "#c62828" :
    p.level === "주의" ? "#e65100" :
    p.level === "보통" ? "#2e7d32" : "#1565c0"};
`;

const ScoreBar = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ScoreFill = styled.div`
  width: 80px;
  height: 8px;
  background: ${theme.colors.border};
  border-radius: 4px;
  overflow: hidden;

  &::after {
    content: "";
    display: block;
    width: ${(p) => p.pct}%;
    height: 100%;
    background: ${(p) =>
      p.pct < 30 ? "#ef5350" :
      p.pct < 50 ? "#ff9800" :
      p.pct < 70 ? "#66bb6a" : "#42a5f5"};
    border-radius: 4px;
  }
`;

const UserRow = styled.tr`
  cursor: pointer;
  &:hover td { background: ${theme.colors.surfaceAlt}; }
`;

const DetailPanel = styled.div`
  margin-top: 24px;
  background: ${theme.colors.surface};
  border-radius: ${theme.radii.lg};
  box-shadow: ${theme.shadows.card};
  padding: 24px;
`;

const DetailHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
`;

const CloseBtn = styled.button`
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  color: ${theme.colors.textMuted};
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 60px 20px;
  color: ${theme.colors.textMuted};
  font-size: 0.9rem;
`;

const LoadingText = styled.div`
  text-align: center;
  padding: 60px 20px;
  color: ${theme.colors.textMuted};
`;

// ─────────────────────────── 컴포넌트 ───────────────────────────

export default function AdminPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState("summary");
  const [summary, setSummary] = useState([]);
  const [scores, setScores] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userDetail, setUserDetail] = useState([]);
  const [loading, setLoading] = useState(false);

  // 관리자 권한 체크
  useEffect(() => {
    if (!user?.is_admin) {
      navigate("/chat", { replace: true });
    }
  }, [user, navigate]);

  useEffect(() => {
    if (!user?.is_admin) return;
    setLoading(true);
    if (tab === "summary") {
      adminAPI.summary()
        .then((r) => setSummary(r.data))
        .catch(() => {})
        .finally(() => setLoading(false));
    } else {
      adminAPI.scores()
        .then((r) => setScores(r.data))
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [tab, user]);

  const handleUserClick = async (userId, username) => {
    if (selectedUser?.id === userId) {
      setSelectedUser(null);
      setUserDetail([]);
      return;
    }
    setSelectedUser({ id: userId, username });
    const { data } = await adminAPI.userScores(userId);
    setUserDetail(data);
  };

  const formatDate = (iso) => {
    const d = new Date(iso);
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  };

  const daysUntil = (iso) => {
    const diff = new Date(iso) - new Date();
    return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
  };

  if (!user?.is_admin) return null;

  return (
    <Layout>
      <Header>
        <HeaderTitle>관리자 대시보드 — 감정 점수</HeaderTitle>
        <HeaderBtn onClick={() => navigate("/chat")}>채팅으로 돌아가기</HeaderBtn>
      </Header>

      <Content>
        <TabBar>
          <Tab active={tab === "summary"} onClick={() => { setTab("summary"); setSelectedUser(null); }}>
            유저별 요약
          </Tab>
          <Tab active={tab === "all"} onClick={() => { setTab("all"); setSelectedUser(null); }}>
            전체 기록
          </Tab>
        </TabBar>

        {loading ? (
          <LoadingText>불러오는 중...</LoadingText>
        ) : tab === "summary" ? (
          <>
            <SectionTitle>유저별 감정 점수 요약 (낮은 점수 먼저)</SectionTitle>
            {summary.length === 0 ? (
              <EmptyState>데이터가 없습니다</EmptyState>
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>유저</Th>
                    <Th>MBTI</Th>
                    <Th>평균 점수</Th>
                    <Th>최저 / 최고</Th>
                    <Th>상담 횟수</Th>
                    <Th>위험도</Th>
                    <Th>마지막 상담</Th>
                  </tr>
                </thead>
                <tbody>
                  {summary.map((u) => (
                    <UserRow key={u.user_id} onClick={() => handleUserClick(u.user_id, u.username)}>
                      <Td><strong>{u.username}</strong></Td>
                      <Td>{u.mbti || "—"}</Td>
                      <Td>
                        <ScoreBar>
                          <ScoreFill pct={u.avg_score * 10} />
                          <span>{u.avg_score} / 10</span>
                        </ScoreBar>
                      </Td>
                      <Td>{u.min_score} / {u.max_score}</Td>
                      <Td>{u.count}회</Td>
                      <Td><RiskBadge level={u.risk_level}>{u.risk_level}</RiskBadge></Td>
                      <Td>{formatDate(u.last_at)}</Td>
                    </UserRow>
                  ))}
                </tbody>
              </Table>
            )}

            {selectedUser && (
              <DetailPanel>
                <DetailHeader>
                  <SectionTitle style={{ margin: 0 }}>{selectedUser.username}님 감정 이력</SectionTitle>
                  <CloseBtn onClick={() => { setSelectedUser(null); setUserDetail([]); }}>✕</CloseBtn>
                </DetailHeader>
                {userDetail.length === 0 ? (
                  <EmptyState>기록이 없습니다</EmptyState>
                ) : (
                  <Table>
                    <thead>
                      <tr>
                        <Th>시각</Th>
                        <Th>감정</Th>
                        <Th>점수</Th>
                        <Th>메시지 일부</Th>
                        <Th>만료까지</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {userDetail.map((s) => (
                        <tr key={s.id}>
                          <Td>{formatDate(s.created_at)}</Td>
                          <Td>{s.emotion_emoji} {s.emotion_label}</Td>
                          <Td>
                            <ScoreBar>
                              <ScoreFill pct={s.score * 10} />
                              <span>{s.score}</span>
                            </ScoreBar>
                          </Td>
                          <Td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {s.message_snippet}
                          </Td>
                          <Td>{daysUntil(s.expires_at)}일 후 삭제</Td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                )}
              </DetailPanel>
            )}
          </>
        ) : (
          <>
            <SectionTitle>전체 감정 점수 기록 (최근 500건)</SectionTitle>
            {scores.length === 0 ? (
              <EmptyState>데이터가 없습니다</EmptyState>
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>시각</Th>
                    <Th>유저</Th>
                    <Th>MBTI</Th>
                    <Th>감정</Th>
                    <Th>점수</Th>
                    <Th>메시지 일부</Th>
                    <Th>만료까지</Th>
                  </tr>
                </thead>
                <tbody>
                  {scores.map((s) => (
                    <tr key={s.id}>
                      <Td>{formatDate(s.created_at)}</Td>
                      <Td><strong>{s.username}</strong></Td>
                      <Td>{s.mbti || "—"}</Td>
                      <Td>{s.emotion_emoji} {s.emotion_label}</Td>
                      <Td>
                        <ScoreBar>
                          <ScoreFill pct={s.score * 10} />
                          <span>{s.score}</span>
                        </ScoreBar>
                      </Td>
                      <Td style={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {s.message_snippet}
                      </Td>
                      <Td>{daysUntil(s.expires_at)}일 후 삭제</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </>
        )}
      </Content>
    </Layout>
  );
}
