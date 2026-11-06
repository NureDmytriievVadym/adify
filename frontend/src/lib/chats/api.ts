import { PUBLIC_API_BASE_URL } from '$app/env/public';
import { session } from '#lib/accounts/session.svelte.ts';
import type { ListingStatus, ListingType } from '#lib/listings/api.ts';

export interface Chat {
  id: string;
  listing: { id: string; title: string; type: ListingType; status: ListingStatus } | null;
  counterpart: { id: string; display_name: string; role: 'customer' | 'provider' };
  created_at: string;
}

export type ChatResult<T> = { ok: true; value: T } | { ok: false; message: string };

async function get<T>(path: string): Promise<ChatResult<T>> {
  try {
    const response = await fetch(`${PUBLIC_API_BASE_URL}/api/v1${path}`, {
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });
    if (response.ok) return { ok: true, value: (await response.json()) as T };
    const body = (await response.json().catch(() => null)) as {
      detail?: { msg?: string }[];
    } | null;
    return { ok: false, message: body?.detail?.[0]?.msg ?? 'This chat could not be loaded.' };
  } catch {
    return { ok: false, message: 'Adify is unreachable. Try again in a moment.' };
  }
}

export const fetchChats = () => get<Chat[]>('/chats');
export const fetchChat = (id: string) => get<Chat>(`/chats/${id}`);

export const roleName = (role: Chat['counterpart']['role']) =>
  role === 'provider' ? 'Provider' : 'Customer';
