import axios from "axios";

const api = axios.create({
  baseURL: "/",
  headers: { "Content-Type": "application/json" },
});

// 요청마다 최신 토큰을 주입
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("love_rag_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 응답 시 로그아웃
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("love_rag_token");
      localStorage.removeItem("love_rag_user");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export const authAPI = {
  register: (data) => api.post("/auth/register", data),
  login: (data) => api.post("/auth/login", data),
  me: () => api.get("/auth/me"),
  changePassword: (data) => api.put("/auth/password", data),
  deleteAccount: (data) => api.delete("/auth/me", { data }),
};

export const chatAPI = {
  history: () => api.get("/chat/history"),
  clearHistory: () => api.delete("/chat/history"),
};

export const adminAPI = {
  summary: () => api.get("/admin/emotion-scores/summary"),
  scores: () => api.get("/admin/emotion-scores"),
  userScores: (userId) => api.get(`/admin/emotion-scores/user/${userId}`),
};

/**
 * SSE 스트리밍 채팅
 * @param {string} message
 * @param {string} token
 * @param {(delta: string) => void} onDelta
 * @param {() => void} onDone
 * @param {(err: string) => void} onError
 */
export async function streamChat(message, token, onDelta, onDone, onError, category = null, history = [], onEmotion = null) {
  try {
    const headers = { "Content-Type": "application/json" };
    if (token) headers.Authorization = `Bearer ${token}`;

    const response = await fetch("/chat/stream", {
      method: "POST",
      headers,
      body: JSON.stringify({ message, category, history }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      onError(err.detail || "서버 오류가 발생했습니다");
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // 마지막 불완전 줄 보존

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6).trim();
        if (data === "[DONE]") {
          onDone();
          return;
        }
        try {
          const parsed = JSON.parse(data);
          if (parsed.delta) onDelta(parsed.delta);
          if (parsed.emotion && onEmotion) onEmotion(parsed.emotion);
          if (parsed.error) onError(parsed.error);
        } catch {
          // 파싱 실패 무시
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err.message || "네트워크 오류가 발생했습니다");
  }
}

export default api;
