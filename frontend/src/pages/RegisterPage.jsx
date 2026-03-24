/** @jsxImportSource @emotion/react */
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
  margin-bottom: 24px;
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
  margin: 0 0 28px;
`;

const FormGroup = styled.div`
  margin-bottom: 18px;
`;

const Label = styled.label`
  display: block;
  font-size: 0.85rem;
  font-weight: 500;
  color: ${theme.colors.textSecondary};
  margin-bottom: 7px;
`;

const Select = styled.select`
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
  cursor: pointer;

  &:focus {
    border-color: ${theme.colors.primary};
  }
`;

const Input = styled.input`
  width: 100%;
  padding: 12px 16px;
  border: 1.5px solid ${(p) => (p.$error ? theme.colors.error : theme.colors.border)};
  border-radius: ${theme.radii.md};
  font-size: 1rem;
  font-family: ${theme.fonts.base};
  color: ${theme.colors.text};
  background: ${theme.colors.surface};
  box-sizing: border-box;
  transition: border-color 0.2s;
  outline: none;

  &:focus {
    border-color: ${(p) => (p.$error ? theme.colors.error : theme.colors.primary)};
  }
  &::placeholder {
    color: ${theme.colors.textMuted};
  }
`;

const FieldError = styled.span`
  color: ${theme.colors.error};
  font-size: 0.78rem;
  margin-top: 4px;
  display: block;
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

const ServerError = styled.p`
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

function validate(form) {
  const errors = {};
  if (!form.username || form.username.length < 2) errors.username = "2자 이상 입력해주세요";
  if (!form.email || !/\S+@\S+\.\S+/.test(form.email)) errors.email = "올바른 이메일을 입력해주세요";
  if (!form.password || form.password.length < 6) errors.password = "6자 이상 입력해주세요";
  if (form.password !== form.confirm) errors.confirm = "비밀번호가 일치하지 않습니다";
  return errors;
}

export default function RegisterPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", email: "", password: "", confirm: "", mbti: "" });
  const [fieldErrors, setFieldErrors] = useState({});
  const [serverError, setServerError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
    setFieldErrors((fe) => ({ ...fe, [e.target.name]: "" }));
    setServerError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errors = validate(form);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setLoading(true);
    try {
      const { data } = await authAPI.register({
        username: form.username,
        email: form.email,
        password: form.password,
        mbti: form.mbti || null,
      });
      login(data.access_token, { username: data.username });
      navigate("/chat");
    } catch (err) {
      setServerError(err.response?.data?.detail || "회원가입에 실패했습니다");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Page>
      <Card>
        <Logo>💌</Logo>
        <Title>회원가입</Title>
        <Subtitle>연애 상담 AI와 함께하세요</Subtitle>

        <form onSubmit={handleSubmit}>
          <FormGroup>
            <Label htmlFor="username">닉네임</Label>
            <Input
              id="username"
              name="username"
              placeholder="닉네임 (2~30자)"
              value={form.username}
              onChange={handleChange}
              $error={!!fieldErrors.username}
            />
            {fieldErrors.username && <FieldError>{fieldErrors.username}</FieldError>}
          </FormGroup>

          <FormGroup>
            <Label htmlFor="email">이메일</Label>
            <Input
              id="email"
              name="email"
              type="email"
              placeholder="이메일"
              value={form.email}
              onChange={handleChange}
              $error={!!fieldErrors.email}
            />
            {fieldErrors.email && <FieldError>{fieldErrors.email}</FieldError>}
          </FormGroup>

          <FormGroup>
            <Label htmlFor="password">비밀번호</Label>
            <Input
              id="password"
              name="password"
              type="password"
              placeholder="비밀번호 (6자 이상)"
              value={form.password}
              onChange={handleChange}
              $error={!!fieldErrors.password}
            />
            {fieldErrors.password && <FieldError>{fieldErrors.password}</FieldError>}
          </FormGroup>

          <FormGroup>
            <Label htmlFor="confirm">비밀번호 확인</Label>
            <Input
              id="confirm"
              name="confirm"
              type="password"
              placeholder="비밀번호 재입력"
              value={form.confirm}
              onChange={handleChange}
              $error={!!fieldErrors.confirm}
            />
            {fieldErrors.confirm && <FieldError>{fieldErrors.confirm}</FieldError>}
          </FormGroup>

          <FormGroup>
            <Label htmlFor="mbti">MBTI <span style={{ color: theme.colors.textMuted, fontWeight: 400 }}>(선택)</span></Label>
            <Select id="mbti" name="mbti" value={form.mbti} onChange={handleChange}>
              <option value="">MBTI를 선택해주세요</option>
              {["INTJ","INTP","ENTJ","ENTP","INFJ","INFP","ENFJ","ENFP",
                "ISTJ","ISFJ","ESTJ","ESFJ","ISTP","ISFP","ESTP","ESFP"].map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </Select>
          </FormGroup>

          {serverError && <ServerError>{serverError}</ServerError>}

          <Button type="submit" disabled={loading}>
            {loading ? "가입 중..." : "회원가입"}
          </Button>
        </form>

        <FooterText>
          이미 계정이 있으신가요? <Link to="/login">로그인</Link>
        </FooterText>
      </Card>
    </Page>
  );
}
