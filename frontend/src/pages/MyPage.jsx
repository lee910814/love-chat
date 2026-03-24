/** @jsxImportSource @emotion/react */
import styled from "@emotion/styled";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { authAPI } from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { theme } from "../theme";

const Page = styled.div`
  min-height: 100vh;
  background: ${theme.colors.background};
  font-family: ${theme.fonts.base};
  padding: 40px 20px;
`;

const Container = styled.div`
  max-width: 480px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
`;

const BackBtn = styled.button`
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: ${theme.colors.textSecondary};
  font-size: 0.9rem;
  font-family: ${theme.fonts.base};
  cursor: pointer;
  padding: 0;
  margin-bottom: 4px;

  &:hover { color: ${theme.colors.primary}; }
`;

const Card = styled.div`
  background: ${theme.colors.surface};
  border-radius: ${theme.radii.xl};
  box-shadow: ${theme.shadows.card};
  padding: 28px;
`;

const CardTitle = styled.h2`
  font-size: 1rem;
  font-weight: 600;
  color: ${theme.colors.text};
  margin: 0 0 20px;
  padding-bottom: 14px;
  border-bottom: 1px solid ${theme.colors.border};
`;

const InfoRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  font-size: 0.9rem;
  color: ${theme.colors.textSecondary};

  span:first-of-type { color: ${theme.colors.textMuted}; font-size: 0.82rem; }
  span:last-of-type { font-weight: 500; color: ${theme.colors.text}; }
`;

const FormGroup = styled.div`
  margin-bottom: 16px;
`;

const Label = styled.label`
  display: block;
  font-size: 0.82rem;
  font-weight: 500;
  color: ${theme.colors.textSecondary};
  margin-bottom: 6px;
`;

const Input = styled.input`
  width: 100%;
  padding: 11px 14px;
  border: 1.5px solid ${theme.colors.border};
  border-radius: ${theme.radii.md};
  font-size: 0.95rem;
  font-family: ${theme.fonts.base};
  color: ${theme.colors.text};
  box-sizing: border-box;
  outline: none;
  transition: border-color 0.2s;

  &:focus { border-color: ${theme.colors.primary}; }
`;

const Btn = styled.button`
  width: 100%;
  padding: 12px;
  border-radius: ${theme.radii.full};
  font-size: 0.95rem;
  font-weight: 600;
  font-family: ${theme.fonts.base};
  cursor: pointer;
  transition: all 0.2s;
  margin-top: 4px;
  border: none;

  background: ${(p) => (p.danger ? "transparent" : theme.colors.primary)};
  color: ${(p) => (p.danger ? theme.colors.error : "white")};
  border: ${(p) => (p.danger ? `1.5px solid ${theme.colors.error}` : "none")};
  box-shadow: ${(p) => (p.danger ? "none" : theme.shadows.button)};

  &:hover:not(:disabled) {
    background: ${(p) => (p.danger ? theme.colors.error : theme.colors.primaryDark)};
    color: white;
  }
  &:disabled { opacity: 0.6; cursor: not-allowed; }
`;

const Msg = styled.p`
  font-size: 0.85rem;
  text-align: center;
  margin: 10px 0 0;
  color: ${(p) => (p.success ? theme.colors.success : theme.colors.error)};
`;

const Modal = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 20px;
`;

const ModalCard = styled.div`
  background: white;
  border-radius: ${theme.radii.xl};
  padding: 32px 28px;
  width: 100%;
  max-width: 360px;
  text-align: center;
`;

const ModalTitle = styled.h3`
  font-size: 1.1rem;
  font-weight: 600;
  color: ${theme.colors.text};
  margin: 0 0 10px;
`;

const ModalDesc = styled.p`
  font-size: 0.88rem;
  color: ${theme.colors.textMuted};
  margin: 0 0 20px;
  line-height: 1.6;
`;

const ModalBtns = styled.div`
  display: flex;
  gap: 10px;
`;

const ModalBtn = styled.button`
  flex: 1;
  padding: 11px;
  border-radius: ${theme.radii.full};
  font-size: 0.9rem;
  font-weight: 600;
  font-family: ${theme.fonts.base};
  cursor: pointer;
  border: 1.5px solid ${(p) => (p.danger ? theme.colors.error : theme.colors.border)};
  background: ${(p) => (p.danger ? theme.colors.error : "transparent")};
  color: ${(p) => (p.danger ? "white" : theme.colors.textSecondary)};
  transition: all 0.2s;

  &:hover { opacity: 0.85; }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
`;

export default function MyPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // 비밀번호 변경
  const [pwForm, setPwForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [pwMsg, setPwMsg] = useState(null);
  const [pwLoading, setPwLoading] = useState(false);

  // 회원탈퇴 모달
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteMsg, setDeleteMsg] = useState(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (pwForm.new_password !== pwForm.confirm) {
      setPwMsg({ ok: false, text: "새 비밀번호가 일치하지 않습니다" });
      return;
    }
    setPwLoading(true);
    setPwMsg(null);
    try {
      await authAPI.changePassword({
        current_password: pwForm.current_password,
        new_password: pwForm.new_password,
      });
      setPwMsg({ ok: true, text: "비밀번호가 변경되었습니다" });
      setPwForm({ current_password: "", new_password: "", confirm: "" });
    } catch (err) {
      setPwMsg({ ok: false, text: err.response?.data?.detail || "변경에 실패했습니다" });
    } finally {
      setPwLoading(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!deletePassword) {
      setDeleteMsg("비밀번호를 입력해주세요");
      return;
    }
    setDeleteLoading(true);
    setDeleteMsg(null);
    try {
      await authAPI.deleteAccount({ password: deletePassword });
      logout();
      navigate("/login");
    } catch (err) {
      setDeleteMsg(err.response?.data?.detail || "탈퇴에 실패했습니다");
      setDeleteLoading(false);
    }
  };

  return (
    <Page>
      <Container>
        <BackBtn onClick={() => navigate("/chat")}>← 채팅으로 돌아가기</BackBtn>

        {/* 내 정보 */}
        <Card>
          <CardTitle>내 정보</CardTitle>
          <InfoRow>
            <span>닉네임</span>
            <span>{user?.username}</span>
          </InfoRow>
          <Btn style={{ marginTop: 16 }} onClick={handleLogout}>로그아웃</Btn>
        </Card>

        {/* 비밀번호 변경 */}
        <Card>
          <CardTitle>비밀번호 변경</CardTitle>
          <form onSubmit={handleChangePassword}>
            <FormGroup>
              <Label>현재 비밀번호</Label>
              <Input
                type="password"
                value={pwForm.current_password}
                onChange={(e) => setPwForm((f) => ({ ...f, current_password: e.target.value }))}
                placeholder="현재 비밀번호"
                required
              />
            </FormGroup>
            <FormGroup>
              <Label>새 비밀번호</Label>
              <Input
                type="password"
                value={pwForm.new_password}
                onChange={(e) => setPwForm((f) => ({ ...f, new_password: e.target.value }))}
                placeholder="새 비밀번호 (6자 이상)"
                required
              />
            </FormGroup>
            <FormGroup>
              <Label>새 비밀번호 확인</Label>
              <Input
                type="password"
                value={pwForm.confirm}
                onChange={(e) => setPwForm((f) => ({ ...f, confirm: e.target.value }))}
                placeholder="새 비밀번호 재입력"
                required
              />
            </FormGroup>
            {pwMsg && <Msg success={pwMsg.ok}>{pwMsg.text}</Msg>}
            <Btn type="submit" disabled={pwLoading} style={{ marginTop: 8 }}>
              {pwLoading ? "변경 중..." : "비밀번호 변경"}
            </Btn>
          </form>
        </Card>

        {/* 회원탈퇴 */}
        <Card>
          <CardTitle>회원탈퇴</CardTitle>
          <p style={{ fontSize: "0.85rem", color: theme.colors.textMuted, margin: "0 0 16px", lineHeight: 1.6 }}>
            탈퇴 시 모든 계정 정보가 삭제되며 복구할 수 없습니다.
          </p>
          <Btn danger onClick={() => setShowDeleteModal(true)}>회원탈퇴</Btn>
        </Card>
      </Container>

      {/* 탈퇴 확인 모달 */}
      {showDeleteModal && (
        <Modal onClick={() => setShowDeleteModal(false)}>
          <ModalCard onClick={(e) => e.stopPropagation()}>
            <ModalTitle>정말 탈퇴하시겠어요?</ModalTitle>
            <ModalDesc>
              탈퇴하면 모든 정보가 삭제되고<br />되돌릴 수 없습니다.<br /><br />
              확인을 위해 비밀번호를 입력해주세요.
            </ModalDesc>
            <Input
              type="password"
              value={deletePassword}
              onChange={(e) => setDeletePassword(e.target.value)}
              placeholder="비밀번호 입력"
              style={{ marginBottom: 8 }}
            />
            {deleteMsg && <Msg style={{ marginBottom: 12 }}>{deleteMsg}</Msg>}
            <ModalBtns>
              <ModalBtn onClick={() => { setShowDeleteModal(false); setDeletePassword(""); setDeleteMsg(null); }}>
                취소
              </ModalBtn>
              <ModalBtn danger onClick={handleDeleteAccount} disabled={deleteLoading}>
                {deleteLoading ? "처리 중..." : "탈퇴하기"}
              </ModalBtn>
            </ModalBtns>
          </ModalCard>
        </Modal>
      )}
    </Page>
  );
}
