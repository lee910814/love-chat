/** @jsxImportSource @emotion/react */
import { css } from "@emotion/react";
import styled from "@emotion/styled";
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { authAPI } from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { theme } from "../theme";

const Page = styled.div`
  min-height: 100vh;
  background: ${theme.colors.background};
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: ${theme.fonts.base};
`;

const Card = styled.div`
  background: ${theme.colors.surface};
  border-radius: ${theme.radii.xl};
  box-shadow: ${theme.shadows.card};
  padding: 48px 40px;
  width: 100%;
  max-width: 420px;
`;

const Logo = styled.div`
  text-align: center;
  margin-bottom: 32px;
  font-size: 2.4rem;
`;

const Title = styled.h1`
  text-align: center;
  font-size: 1.5rem;
  font-weight: 600;
  color: ${theme.colors.text};
  margin: 0 0 8px;
`;

const Subtitle = styled.p`
  text-align: center;
  color: ${theme.colors.textMuted};
  font-size: 0.9rem;
  margin: 0 0 32px;
`;

const FormGroup = styled.div`
  margin-bottom: 20px;
`;

const Label = styled.label`
  display: block;
  font-size: 0.85rem;
  font-weight: 500;
  color: ${theme.colors.textSecondary};
  margin-bottom: 8px;
`;

const Input = styled.input`
  width: 100%;
  padding: 12px 16px;
  border: 1.5px solid ${theme.colors.border};
  border-radius: ${theme.radii.md};
  font-size: 1rem;
  font-family: ${theme.fonts.base};
  color: ${theme.colors.text};
  background: ${theme.colors.surface};
  box-sizing: border-box;
  transition: border-color 0.2s;
  outline: none;

  &:focus {
    border-color: ${theme.colors.primary};
  }
  &::placeholder {
    color: ${theme.colors.textMuted};
  }
`;

const Button = styled.button`
  width: 100%;
  padding: 14px;
  background: ${theme.colors.primary};
  color: white;
  border: none;
  border-radius: ${theme.radii.full};
  font-size: 1rem;
  font-weight: 600;
  font-family: ${theme.fonts.base};
  cursor: pointer;
  box-shadow: ${theme.shadows.button};
  transition: background 0.2s, transform 0.1s;
  margin-top: 8px;

  &:hover:not(:disabled) {
    background: ${theme.colors.primaryDark};
  }
  &:active:not(:disabled) {
    transform: scale(0.98);
  }
  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
`;

const ErrorMsg = styled.p`
  color: ${theme.colors.error};
  font-size: 0.85rem;
  text-align: center;
  margin: 12px 0 0;
`;

const FooterText = styled.p`
  text-align: center;
  color: ${theme.colors.textMuted};
  font-size: 0.875rem;
  margin-top: 24px;

  a {
    color: ${theme.colors.primary};
    text-decoration: none;
    font-weight: 500;
    &:hover {
      text-decoration: underline;
    }
  }
`;

const Divider = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 20px 0 0;
  color: ${theme.colors.textMuted};
  font-size: 0.8rem;

  &::before,
  &::after {
    content: "";
    flex: 1;
    height: 1px;
    background: ${theme.colors.border};
  }
`;

const GuestBtn = styled.button`
  width: 100%;
  padding: 12px;
  background: transparent;
  color: ${theme.colors.textSecondary};
  border: 1.5px solid ${theme.colors.border};
  border-radius: ${theme.radii.full};
  font-size: 0.9rem;
  font-family: ${theme.fonts.base};
  cursor: pointer;
  margin-top: 12px;
  transition: all 0.2s;

  &:hover {
    border-color: ${theme.colors.primary};
    color: ${theme.colors.primary};
  }
`;

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
    setError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const { data } = await authAPI.login(form);
      login(data.access_token, { username: data.username });
      navigate("/chat");
    } catch (err) {
      setError(err.response?.data?.detail || "로그인에 실패했습니다");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Page>
      <Card>
        <Logo>💕</Logo>
        <Title>연애 상담 AI</Title>
        <Subtitle>당신의 연애 고민, 함께 풀어봐요</Subtitle>

        <form onSubmit={handleSubmit}>
          <FormGroup>
            <Label htmlFor="email">이메일</Label>
            <Input
              id="email"
              name="email"
              type="email"
              placeholder="이메일을 입력하세요"
              value={form.email}
              onChange={handleChange}
              required
            />
          </FormGroup>
          <FormGroup>
            <Label htmlFor="password">비밀번호</Label>
            <Input
              id="password"
              name="password"
              type="password"
              placeholder="비밀번호를 입력하세요"
              value={form.password}
              onChange={handleChange}
              required
            />
          </FormGroup>

          {error && <ErrorMsg>{error}</ErrorMsg>}

          <Button type="submit" disabled={loading}>
            {loading ? "로그인 중..." : "로그인"}
          </Button>
        </form>

        <Divider>또는</Divider>
        <GuestBtn type="button" onClick={() => navigate("/chat")}>
          비회원으로 시작하기 (대화 내용 자동 삭제)
        </GuestBtn>

        <FooterText>
          아직 계정이 없으신가요? <Link to="/register">회원가입</Link>
        </FooterText>
      </Card>
    </Page>
  );
}
