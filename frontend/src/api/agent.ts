import { checkAndroidStatus } from '../platform/android-config';
import { getApiBaseUrl } from '../platform/web';
import { readAgentEvents } from './agent-stream.mjs';

const STORAGE_KEY = 'livelife.agent.session.v1';

export interface AgentCitation {
  rank: number;
  information_id: string;
  title: string | null;
  source_url: string | null;
  platform: string;
  source_id: string;
  published_at: string | null;
  activity_location: string | null;
  activity_start_at: string | null;
  activity_end_at: string | null;
  registration_deadline_at: string | null;
  snippet: string;
}

export interface AgentMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  status: 'pending' | 'completed' | 'failed' | 'cancelled';
  citations: AgentCitation[];
  created_at: string;
  client_request_id?: string;
  request_id?: string;
}

export interface AgentSession {
  session_id: string;
  session_token: string;
  expires_at: string;
}

const base = () => getApiBaseUrl().replace(/\/+$/, '');
const headers = (token?: string) => ({
  Accept: 'application/json',
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
});

async function request<T>(path: string, token?: string, init: RequestInit = {}): Promise<T> {
  await checkAndroidStatus();
  const response = await fetch(`${base()}${path}`, {
    ...init,
    headers: { ...headers(token), ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...init.headers },
  });
  if (!response.ok) {
    let code = `http_${response.status}`;
    try { code = (await response.json())?.detail?.code || code; } catch { /* retain status */ }
    throw new Error(code);
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}

export async function loadAgentSession(): Promise<{ session: AgentSession; messages: AgentMessage[] }> {
  const saved = sessionStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      const session = JSON.parse(saved) as AgentSession;
      if (session.session_token && Date.parse(session.expires_at) > Date.now()) {
        try {
          const current = await request<{ session_id: string; expires_at: string; messages: AgentMessage[] }>(
            '/agent/sessions/current', session.session_token,
          );
          const renewed = { ...session, session_id: current.session_id, expires_at: current.expires_at };
          sessionStorage.setItem(STORAGE_KEY, JSON.stringify(renewed));
          return { session: renewed, messages: current.messages };
        } catch (error) {
          if (!['invalid_session', 'session_expired', 'http_401', 'http_404'].includes((error as Error).message)) throw error;
        }
      }
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
    }
  }
  sessionStorage.removeItem(STORAGE_KEY);
  const session = await request<AgentSession>('/agent/sessions', undefined, { method: 'POST' });
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  return { session, messages: [] };
}

export async function closeAgentSession(token: string): Promise<void> {
  await request<void>('/agent/sessions/close', token, { method: 'POST' });
  sessionStorage.removeItem(STORAGE_KEY);
}

export async function rateAgentMessage(token: string, messageId: string, rating: 'like' | 'dislike' | null): Promise<void> {
  await request<void>(`/agent/messages/${encodeURIComponent(messageId)}/rating`, token, {
    method: 'POST', body: JSON.stringify({ rating }),
  });
}

export async function sendAgentMessage(
  token: string,
  content: string,
  clientRequestId: string,
  handlers: Record<string, (data: any) => void | Promise<void>>,
  signal: AbortSignal,
): Promise<void> {
  await checkAndroidStatus();
  const response = await fetch(`${base()}/agent/messages/stream`, {
    method: 'POST',
    headers: { ...headers(token), Accept: 'text/event-stream', 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, client_request_id: clientRequestId }),
    signal,
  });
  await readAgentEvents(response, handlers, signal);
}
