import { PUBLIC_API_BASE_URL } from '$app/env/public';
import type { Account } from './registration.ts';

interface TokenResponse {
  access_token: string;
  expires_in: number;
  account: Account;
}

interface SessionState {
  account: Account | null;
  accessToken: string | null;
  restored: boolean;
}

export type SignInResult = { ok: true } | { ok: false; message: string };

export const session: SessionState = $state({ account: null, accessToken: null, restored: false });

let refreshTimer: ReturnType<typeof setTimeout> | undefined;

// The refresh token lives in an HttpOnly cookie scoped to /api/v1/auth, so every call sends credentials.
const auth = (path: string, body?: object) =>
  fetch(`${PUBLIC_API_BASE_URL}/api/v1/auth/${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

function start(tokens: TokenResponse) {
  session.account = tokens.account;
  session.accessToken = tokens.access_token;
  clearTimeout(refreshTimer);
  // Renew a minute early so requests never carry an expired access token.
  refreshTimer = setTimeout(refresh, Math.max(tokens.expires_in - 60, 30) * 1000);
}

function clear() {
  clearTimeout(refreshTimer);
  session.account = null;
  session.accessToken = null;
}

async function refresh() {
  try {
    const response = await auth('refresh');
    if (response.ok) start((await response.json()) as TokenResponse);
    else clear();
  } catch {
    clear();
  }
}

export async function restoreSession() {
  await refresh();
  session.restored = true;
}

export async function signIn(email: string, password: string): Promise<SignInResult> {
  let response: Response;
  try {
    response = await auth('sign-in', { email: email.trim(), password });
  } catch {
    return { ok: false, message: 'Adify is unreachable. Try again in a moment.' };
  }
  if (response.ok) {
    start((await response.json()) as TokenResponse);
    return { ok: true };
  }
  const body = (await response.json().catch(() => null)) as {
    detail?: { msg?: string }[] | string;
  } | null;
  const message =
    response.status === 422
      ? 'Enter a valid email address.'
      : Array.isArray(body?.detail)
        ? body.detail[0]?.msg
        : undefined;
  return { ok: false, message: message ?? 'Sign-in failed. Try again in a moment.' };
}

export async function signOut() {
  try {
    await auth('sign-out');
  } finally {
    clear();
  }
}
