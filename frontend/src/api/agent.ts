import { authState, readAuthToken, clearSession, onAuthSessionChange } from './auth';
import { checkAndroidStatus } from '../platform/android-config';
import { getApiBaseUrl } from '../platform/web';
import { usableCurrentLocation } from '../platform/location-tracker';
import { readAgentEvents } from './agent-stream.mjs';

const STORAGE_KEY = 'livelife.agent.session.v3';

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
  rating?: 'like' | 'dislike' | null;
}

export interface AgentSession {
  is_pinned?: boolean;
  session_id: string;
  expires_at: string | null;
  title: string;
  created_at: string;
  updated_at: string;
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
    signal: init.signal ? AbortSignal.any([init.signal, AbortSignal.timeout(10000)]) : AbortSignal.timeout(10000),
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

export interface AgentHistoryPage {
  session_id: string; title: string; expires_at: string | null; created_at: string; updated_at: string;
  is_pinned?: boolean;
  messages: AgentMessage[]; next_before: number | null;
}
export interface AgentSessionList { items: AgentSession[]; next_offset: number | null }

export function selectAgentDraft() {
  identity();
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({owner:authState.user?.id, base:base(), draft:true}));
}
export async function pinAgentSession(id: string, is_pinned: boolean): Promise<AgentSession> {
  return request(`/agent/sessions/${encodeURIComponent(id)}`, undefined, {method:"PATCH", body:JSON.stringify({is_pinned})});
}
export function selectAgentSession(session: AgentSession) {
  const captured = identity();
  assertIdentity(captured);
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ owner: authState.user?.id, base: base(), session_id: session.session_id }));
}
export async function listAgentSessions(query = '', offset = 0): Promise<AgentSessionList> {
  return request(`/agent/sessions?${new URLSearchParams({query, offset: String(offset), limit:'20'})}`);
}
export async function createAgentSession(): Promise<AgentSession> {
  const captured = identity();
  const created = await request<AgentSession>('/agent/sessions', undefined, {method:'POST'});
  const session = {session_id:created.session_id, title:created.title, is_pinned:created.is_pinned, created_at:created.created_at, updated_at:created.updated_at, expires_at:created.expires_at};
  assertIdentity(captured); return session;
}
export async function loadAgentMessages(id: string, before?: number): Promise<AgentHistoryPage> {
  return request(`/agent/sessions/${encodeURIComponent(id)}?limit=50${before ? `&before=${before}` : ''}`);
}
export async function loadAgentSession(id?: string): Promise<{ session: AgentSession | null; messages: AgentMessage[]; next_before: number | null }> {
  const captured = identity();
  if (!id) {
    try { const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
      if (saved?.owner === authState.user?.id && saved.base === base()) {
        if (saved.draft) return {session:null, messages:[], next_before:null};
        id = saved.session_id;
      }
    } catch { /* malformed hint is discarded; history remains server-owned */ }
  }
  if (!id) id = (await listAgentSessions()).items[0]?.session_id;
  if (id) {
    try {
      const page = await loadAgentMessages(id);
      const session = {session_id:page.session_id, title:page.title, is_pinned:page.is_pinned, created_at:page.created_at, updated_at:page.updated_at, expires_at:page.expires_at};
      assertIdentity(captured);
      return {session, messages:page.messages, next_before:page.next_before};
    } catch (error) {
      if ((error as Error).message !== 'session_not_found') throw error;
    }
  }
  return {session:null, messages:[], next_before:null};
}
export async function closeAgentSession(id: string): Promise<void> {
  await request<void>(`/agent/sessions/${encodeURIComponent(id)}`, undefined, {method:'DELETE'});
}
export async function rateAgentMessage(id: string, messageId: string, rating: 'like' | 'dislike' | null): Promise<void> {
  await request<void>(`/agent/sessions/${encodeURIComponent(id)}/messages/${encodeURIComponent(messageId)}/rating`, undefined, {
    method:'POST', body: JSON.stringify({rating}),
  });
}

export async function sendAgentMessage(
  sessionId: string,
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
    const point = usableCurrentLocation();
    const location = point
      ? {latitude:point.latitude, longitude:point.longitude, accuracy:point.accuracy, timestamp:point.timestamp} : undefined;
    const response = await fetch(`${base()}/agent/sessions/${encodeURIComponent(sessionId)}/messages/stream`, {
      method: 'POST',
      headers: { ...headers(captured.token), Accept: 'text/event-stream', 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, client_request_id: clientRequestId, location }),
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
