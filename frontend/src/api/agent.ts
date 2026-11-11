import { authState, readAuthToken, clearSession, onAuthSessionChange } from './auth';
import { checkAndroidStatus } from '../platform/android-config';
import { getApiBaseUrl } from '../platform/web';
import { readAgentEvents } from './agent-stream.mjs';

const STORAGE_KEY = 'livelife.agent.session.v2';

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
const controllers = new Set<AbortController>();
onAuthSessionChange(() => {
  for (const controller of controllers) controller.abort();
  controllers.clear();
});

function identity() {
  const token = readAuthToken();
  if (!token) throw new Error('authentication_required');
  return { token, revision: authState.revision };
}
function assertIdentity(captured: ReturnType<typeof identity>) {
  if (captured.token !== readAuthToken() || captured.revision !== authState.revision) {
    throw new Error('authentication_required');
  }
}
function headers(account: string, session?: string) {
  return {
    Accept: 'application/json', Authorization: `Bearer ${account}`,
    ...(session ? { 'X-Agent-Session': session } : {}),
  };
}
function expireIdentity(captured: ReturnType<typeof identity>) {
  if (captured.token === readAuthToken() && captured.revision === authState.revision) clearSession();
}
async function request<T>(path: string, token?: string, init: RequestInit = {}): Promise<T> {
  const captured = identity();
  await checkAndroidStatus();
  assertIdentity(captured);
  const response = await fetch(`${base()}${path}`, {
    ...init,
    headers: { ...headers(captured.token, token), ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...init.headers },
  });
  assertIdentity(captured);
  if (!response.ok) {
    let code = `http_${response.status}`;
    try { code = (await response.json())?.detail?.code || code; } catch { /* retain status */ }
    if (response.status === 401 && !['invalid_session', 'session_token_required'].includes(code)) {
      expireIdentity(captured);
      throw new Error('authentication_required');
    }
    throw new Error(code);
  }
  const data = response.status === 204 ? undefined as T : await response.json() as T;
  assertIdentity(captured);
  return data;
}

export async function loadAgentSession(): Promise<{ session: AgentSession; messages: AgentMessage[] }> {
  const captured = identity();
  const owner = authState.user?.id;
  const saved = sessionStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      const stored = JSON.parse(saved);
      const session = stored.session as AgentSession;
      if (stored.owner === owner && stored.base === base() && session?.session_token && Date.parse(session.expires_at) > Date.now()) {
        try {
          const current = await request<{ session_id: string; expires_at: string; messages: AgentMessage[] }>(
            '/agent/sessions/current', session.session_token,
          );
          const renewed = { ...session, session_id: current.session_id, expires_at: current.expires_at };
          assertIdentity(captured);
          sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ owner, base: base(), session: renewed }));
          return { session: renewed, messages: current.messages };
        } catch (error) {
          if (!['invalid_session', 'session_expired', 'http_404'].includes((error as Error).message)) throw error;
        }
      }
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
    }
  }
  sessionStorage.removeItem(STORAGE_KEY);
  const session = await request<AgentSession>('/agent/sessions', undefined, { method: 'POST' });
  assertIdentity(captured);
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ owner, base: base(), session }));
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
  const captured = identity();
  const controller = new AbortController();
  controllers.add(controller);
  const combined = AbortSignal.any([signal, controller.signal]);
  try {
    await checkAndroidStatus();
    assertIdentity(captured);
    const response = await fetch(`${base()}/agent/messages/stream`, {
      method: 'POST',
      headers: { ...headers(captured.token, token), Accept: 'text/event-stream', 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, client_request_id: clientRequestId }),
      signal: combined,
    });
    assertIdentity(captured);
    if (response.status === 401) {
      const data = await response.clone().json().catch(() => null);
      if (!['invalid_session', 'session_token_required'].includes(data?.detail?.code)) {
        expireIdentity(captured);
        throw new Error('authentication_required');
      }
    }
    const guarded = Object.fromEntries(Object.entries(handlers).map(([event, handle]) => [
      event, async (data: any) => {
        assertIdentity(captured);
        if (event === 'error' && data.code === 'authentication_required') {
          expireIdentity(captured);
          throw new Error('authentication_required');
        }
        await handle(data);
      },
    ]));
    await readAgentEvents(response, guarded, combined);
    assertIdentity(captured);
  } finally {
    controllers.delete(controller);
  }
}
