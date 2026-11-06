import { PUBLIC_API_BASE_URL } from '$app/env/public';

export type ResetResult = { ok: true } | { ok: false; message: string };

const UNREACHABLE = 'Adify is unreachable. Try again in a moment.';

const post = (path: string, body: object) =>
  fetch(`${PUBLIC_API_BASE_URL}/api/v1/auth/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

async function apiMessage(response: Response, fallback: string) {
  const body = (await response.json().catch(() => null)) as { detail?: { msg?: string }[] } | null;
  return (Array.isArray(body?.detail) && body.detail[0]?.msg) || fallback;
}

// FR-081: the API answers 202 whether or not the email belongs to an account.
export async function requestPasswordReset(email: string): Promise<ResetResult> {
  try {
    const response = await post('password-reset', { email: email.trim() });
    if (response.ok) return { ok: true };
    if (response.status === 422) return { ok: false, message: 'Enter a valid email address.' };
    return { ok: false, message: await apiMessage(response, UNREACHABLE) };
  } catch {
    return { ok: false, message: UNREACHABLE };
  }
}

export async function resetPassword(token: string, password: string): Promise<ResetResult> {
  try {
    const response = await post('password-reset/confirm', { token, password });
    if (response.ok) return { ok: true };
    return { ok: false, message: await apiMessage(response, 'The password could not be changed.') };
  } catch {
    return { ok: false, message: UNREACHABLE };
  }
}
