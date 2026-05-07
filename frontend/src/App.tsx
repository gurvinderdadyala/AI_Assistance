import { FormEvent, useMemo, useRef, useState } from 'react';
import { Bot, CircleAlert, Send, Sparkles, UserRound } from 'lucide-react';
import { ChatHistoryItem, Source, sendChatMessage } from './api';

type ChatMessage = ChatHistoryItem & {
  id: string;
  sources?: Source[];
  error?: boolean;
};

const suggestions = [
  'How do I reset my password?',
  'How do I connect to VPN?',
  'Why am I not receiving MFA prompts?',
  'How do I set up my new laptop?'
];

export function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: 'Hi, I can answer questions from the sample IT knowledge base. What can I help with today?'
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const history = useMemo<ChatHistoryItem[]>(
    () =>
      messages
        .filter((message) => !message.error)
        .map(({ role, content }) => ({ role, content })),
    [messages]
  );

  async function submitMessage(messageText: string) {
    const trimmed = messageText.trim();
    if (!trimmed || isLoading) {
      return;
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed
    };

    setMessages((current) => [...current, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await sendChatMessage(trimmed, history);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response.answer,
          sources: response.sources
        }
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: error instanceof Error ? error.message : 'Something went wrong while contacting the assistant.',
          error: true
        }
      ]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitMessage(input);
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-icon">
              <Sparkles size={20} aria-hidden="true" />
            </div>
            <div>
              <h1>IT AI Assistance</h1>
              <p>Knowledge bot</p>
            </div>
          </div>

          <div className="suggestions">
            <h2>Suggested Questions</h2>
            {suggestions.map((suggestion) => (
              <button
                className="suggestion-button"
                key={suggestion}
                type="button"
                onClick={() => void submitMessage(suggestion)}
                disabled={isLoading}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </aside>

        <section className="chat-panel" aria-label="IT assistant chat">
          <div className="chat-header">
            <div>
              <h2>Helpdesk Knowledge Chat</h2>
              <p>Answers are grounded in local sample IT documents.</p>
            </div>
            <span className="status">Local RAG</span>
          </div>

          <div className="messages" aria-live="polite">
            {messages.map((message) => (
              <article className={`message ${message.role} ${message.error ? 'error' : ''}`} key={message.id}>
                <div className="avatar" aria-hidden="true">
                  {message.role === 'assistant' ? <Bot size={18} /> : <UserRound size={18} />}
                </div>
                <div className="message-body">
                  {message.error && (
                    <div className="error-label">
                      <CircleAlert size={16} aria-hidden="true" />
                      Service message
                    </div>
                  )}
                  <p>{message.content}</p>
                  {message.sources && message.sources.length > 0 && (
                    <div className="sources">
                      <span>Sources</span>
                      {message.sources.map((source) => (
                        <code key={source.path}>{source.title}</code>
                      ))}
                    </div>
                  )}
                </div>
              </article>
            ))}
            {isLoading && (
              <article className="message assistant">
                <div className="avatar" aria-hidden="true">
                  <Bot size={18} />
                </div>
                <div className="message-body loading">Searching the IT knowledge base...</div>
              </article>
            )}
          </div>

          <form className="composer" onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              aria-label="Ask an IT support question"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask about VPN, passwords, MFA, printers, or onboarding"
              disabled={isLoading}
            />
            <button type="submit" disabled={isLoading || !input.trim()} title="Send message">
              <Send size={18} aria-hidden="true" />
              <span>Send</span>
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}

