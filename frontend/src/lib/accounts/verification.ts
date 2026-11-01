import { PUBLIC_API_BASE_URL } from '$app/env/public';
import { session } from './session.svelte.ts';
import type { Account } from './registration.ts';

export type Channel = 'email' | 'phone';
export type VerificationResult = { ok: boolean; message: string };

export interface ChannelStatus {
  verified: boolean;
  destination: string;
  code_sent: boolean;
  resend_in: number;
}

export type VerificationStatus = Record<Channel, ChannelStatus>;

const unreachable = 'Adify is unreachable. Try again in a moment.';

export const isVerified = (account: Account) => account.email_verified && account.phone_verified;

export async function fetchStatus(): Promise<VerificationStatus | null> {
  try {
    const response = await fetch(`${PUBLIC_API_BASE_URL}/api/v1/accounts/me/verification`, {
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });
    return response.ok ? ((await response.json()) as VerificationStatus) : null;
  } catch {
    return null;
  }
}

async function call(channel: Channel, action: 'code' | 'confirm', body?: object) {
  try {
    return await fetch(
      `${PUBLIC_API_BASE_URL}/api/v1/accounts/me/verification/${channel}/${action}`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
          ...(body ? { 'Content-Type': 'application/json' } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
      },
    );
  } catch {
    return null;
  }
}

async function messageOf(response: Response, fallback: string) {
  const body = (await response.json().catch(() => null)) as { detail?: { msg?: string }[] } | null;
  return (Array.isArray(body?.detail) && body.detail[0]?.msg) || fallback;
}

export async function sendCode(
  channel: Channel,
): Promise<VerificationResult & { resendIn?: number }> {
  const response = await call(channel, 'code');
  if (!response) return { ok: false, message: unreachable };
  if (!response.ok) {
    return { ok: false, message: await messageOf(response, 'The code could not be sent.') };
  }
  const { destination, resend_in } = (await response.json()) as {
    destination: string;
    resend_in: number;
  };
  return {
    ok: true,
    message:
      channel === 'email'
        ? `We emailed a code to ${destination}.`
        : `We texted a code to ${destination}.`,
    resendIn: resend_in,
  };
}

export async function confirmCode(channel: Channel, code: string): Promise<VerificationResult> {
  if (!/^\d{6}$/.test(code.trim())) return { ok: false, message: 'Enter the six-digit code.' };
  const response = await call(channel, 'confirm', { code: code.trim() });
  if (!response) return { ok: false, message: unreachable };
  if (!response.ok) {
    return { ok: false, message: await messageOf(response, 'The code could not be checked.') };
  }
  session.account = (await response.json()) as Account;
  return {
    ok: true,
    message:
      channel === 'email' ? 'Your email address is verified.' : 'Your phone number is verified.',
  };
}
