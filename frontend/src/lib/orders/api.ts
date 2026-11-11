import { PUBLIC_API_BASE_URL } from '$app/env/public';
import { session } from '#lib/accounts/session.svelte.ts';
import type { ListingType, Spec } from '#lib/listings/api.ts';

export type OrderStatus =
  | 'awaiting_payment'
  | 'paid'
  | 'in_progress'
  | 'in_review'
  | 'disputed'
  | 'done'
  | 'canceled'
  | 'rejected';

interface Party {
  id: string;
  display_name: string;
  role: 'customer' | 'provider';
}

export interface Order {
  id: string;
  status: OrderStatus;
  details: string;
  price_uah: string;
  deadline: string | null;
  stages: { title: string; deadline: string | null }[];
  requirements: {
    listing_type: ListingType;
    category: string;
    has_requirements: boolean;
    specs: Spec[];
  };
  listing: { id: string; title: string; type: ListingType };
  chat_id: string | null;
  is_listing_owner: boolean;
  customer: Party;
  provider: Party;
  created_at: string;
  paid_at: string | null;
}

// Mono invoice statuses as the API reports them (FR-038).
export type PaymentStatus =
  'created' | 'processing' | 'hold' | 'success' | 'failure' | 'reversed' | 'expired';

export interface Payment {
  status: PaymentStatus;
  amount_uah: string;
  page_url: string | null;
  failure_reason: string | null;
  created_at: string;
}

export interface StageInput {
  title: string;
  deadline: string;
}

export interface OrderInput {
  details: string;
  price: string;
  deadline: string;
  stages: StageInput[];
}

export type OrderResult<T> = { ok: true; value: T } | { ok: false; message: string };

export const statusLabel: Record<OrderStatus, string> = {
  awaiting_payment: 'Awaiting payment',
  paid: 'Paid',
  in_progress: 'In progress',
  in_review: 'In review',
  disputed: 'Disputed',
  done: 'Done',
  canceled: 'Canceled',
  rejected: 'Rejected',
};

// Deadlines are calendar days, so they are shown without a time-zone shift.
export const formatDay = (day: string) =>
  new Intl.DateTimeFormat('en-US', { day: 'numeric', month: 'long', year: 'numeric' }).format(
    new Date(`${day}T00:00:00`),
  );

async function request<T>(path: string, body?: object): Promise<OrderResult<T>> {
  try {
    const response = await fetch(`${PUBLIC_API_BASE_URL}/api/v1${path}`, {
      method: body ? 'POST' : 'GET',
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (response.ok) return { ok: true, value: (await response.json()) as T };
    const data = (await response.json().catch(() => null)) as {
      detail?: { msg?: string }[];
    } | null;
    const message = data?.detail?.[0]?.msg?.replace(/^Value error, /, '');
    return { ok: false, message: message ?? 'The order could not be saved.' };
  } catch {
    return { ok: false, message: 'Adify is unreachable. Try again in a moment.' };
  }
}

export const fetchChatOrders = (chatId: string) => request<Order[]>(`/chats/${chatId}/orders`);
export const fetchOrder = (id: string) => request<Order>(`/orders/${id}`);

// FR-038: the API answers with Mono's payment page; an open invoice is reused.
export const startPayment = (orderId: string) => request<Payment>(`/orders/${orderId}/payment`, {});
// Reading the payment also syncs it from Mono, so it works where webhooks cannot arrive.
export const fetchPayment = (orderId: string) => request<Payment>(`/orders/${orderId}/payment`);

// FR-033, FR-037: mirrors the API rules so most mistakes are explained before sending.
export function validateOrder(input: OrderInput): string | null {
  const today = new Date().toISOString().slice(0, 10);
  if (!input.details.trim()) return 'Describe what the order includes.';
  const price = Number(input.price);
  if (!input.price.trim() || !Number.isFinite(price) || price <= 0)
    return 'Enter the agreed price in UAH.';
  if (input.deadline && input.deadline < today) return 'The order deadline cannot be in the past.';
  for (const stage of input.stages) {
    if (!stage.title.trim()) return 'Give every stage a name, or remove the empty one.';
    if (stage.deadline && stage.deadline < today)
      return `The deadline of “${stage.title}” cannot be in the past.`;
    if (input.deadline && stage.deadline && stage.deadline > input.deadline)
      return `The deadline of “${stage.title}” is later than the order deadline.`;
  }
  return null;
}

export const createOrder = (chatId: string, input: OrderInput) =>
  request<Order>(`/chats/${chatId}/orders`, {
    details: input.details.trim(),
    price_uah: input.price.trim(),
    deadline: input.deadline || null,
    stages: input.stages.map((stage) => ({
      title: stage.title.trim(),
      deadline: stage.deadline || null,
    })),
  });
