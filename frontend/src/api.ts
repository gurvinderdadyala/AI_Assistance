export type ChatRole = 'user' | 'assistant';

export type ChatHistoryItem = {
  role: ChatRole;
  content: string;
};

export type Source = {
  title: string;
  path: string;
};

export type ChatResponse = {
  answer: string;
  sources: Source[];
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function sendChatMessage(
  message: string,
  history: ChatHistoryItem[]
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ message, history })
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const detail = errorBody?.detail ?? 'The IT assistant service is unavailable.';
    throw new Error(detail);
  }

  return response.json();
}

