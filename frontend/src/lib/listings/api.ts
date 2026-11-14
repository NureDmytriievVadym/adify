import { PUBLIC_API_BASE_URL } from '$app/env/public';
import { session } from '#lib/accounts/session.svelte.ts';

export type ListingType = 'request' | 'offer';
/** FR-018–FR-020: only an active listing appears in the marketplace and takes new orders. */
export type ListingStatus = 'active' | 'paused' | 'expired' | 'soft_deleted';
export type ListingField =
  'category' | 'title' | 'description' | 'price' | 'delivery_days' | 'specs' | 'audience';
export type FieldErrors = Partial<Record<ListingField, string>>;

export interface Spec {
  label: string;
  value: string;
}

export interface AudienceInput {
  ageMin: string;
  ageMax: string;
  country: string;
  socioeconomic: string;
  traits: string;
}

export interface ListingInput {
  category: string;
  title: string;
  description: string;
  price: string;
  delivery_days: string;
  specs: Spec[];
  ageMin: string;
  ageMax: string;
  country: string;
  socioeconomic: string;
  traits: string;
}

export interface Attachment {
  id: string;
  filename: string;
  content_type: string;
  size: number;
  url: string;
}

export interface ApiAudience {
  age_min: number | null;
  age_max: number | null;
  country: string | null;
  socioeconomic: string | null;
  traits: string[];
}

export interface ApiListing {
  id: string;
  type: ListingType;
  category: string;
  title: string;
  description: string;
  price_uah: string;
  delivery_days: number | null;
  specs: Spec[];
  audience: ApiAudience | null;
  owner: { id: string; display_name: string; role: 'customer' | 'provider' };
  attachments: Attachment[];
  status: ListingStatus;
  expires_at: string;
  /** Owner view only (FR-017): fields that cannot change right now, e.g. `category`. */
  locked_fields?: ListingField[];
}

export type CreateResult =
  | { ok: true; listing: ApiListing }
  | { ok: false; fieldErrors: FieldErrors; message?: string; type?: string };
export type SaveResult = CreateResult;

export const MAX_SPECS = 10;
export const MAX_ATTACHMENTS = 5;
export const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
const ATTACHMENT_EXTENSIONS = /\.(jpe?g|png|gif|webp|mp4|pdf)$/i;

export const isListingId = (value: string) =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);

export const formatSize = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MB`;

export const formatDate = (iso: string) =>
  new Intl.DateTimeFormat('en-US', { day: 'numeric', month: 'long', year: 'numeric' }).format(
    new Date(iso),
  );

export const formatDelivery = (days: number | null) =>
  days === null ? 'To be agreed' : `${days} ${days === 1 ? 'day' : 'days'}`;

// Mirrors the API rules so most mistakes are caught before a request.
export function validateListing(input: ListingInput, type: ListingType): FieldErrors {
  const errors: FieldErrors = {};
  if (!input.category) errors.category = 'Choose a category.';
  const title = input.title.trim();
  if (title.length < 5 || title.length > 120) errors.title = 'Use 5 to 120 characters.';
  const description = input.description.trim();
  if (description.length < 20 || description.length > 5000)
    errors.description = 'Use 20 to 5,000 characters.';

  const price = input.price.trim();
  const noun = type === 'request' ? 'budget' : 'price';
  if (!/^\d+([.,]\d{1,2})?$/.test(price) || Number(price.replace(',', '.')) <= 0)
    errors.price = `Enter a ${noun} in UAH, for example 2500 or 2500.50.`;
  else if (Number(price.replace(',', '.')) > 99999999.99)
    errors.price = `The ${noun} is too large.`;

  const days = input.delivery_days.trim();
  if (days === '' && type === 'offer') errors.delivery_days = 'Enter the delivery time in days.';
  else if (days !== '' && (!/^\d+$/.test(days) || Number(days) < 1 || Number(days) > 365))
    errors.delivery_days = 'Enter a whole number of days from 1 to 365.';

  const ageMin = input.ageMin.trim();
  const ageMax = input.ageMax.trim();
  for (const [value, label] of [
    [ageMin, 'minimum'],
    [ageMax, 'maximum'],
  ] as const) {
    if (value && (!/^\d{1,3}$/.test(value) || Number(value) > 120))
      errors.audience = `Enter a ${label} age from 0 to 120.`;
  }
  if (!errors.audience && ageMin && ageMax && Number(ageMin) > Number(ageMax))
    errors.audience = 'The minimum age cannot be greater than the maximum.';

  for (const spec of input.specs) {
    const label = spec.label.trim();
    const value = spec.value.trim();
    if (!label && !value) continue;
    if (!label || !value || label.length > 60 || value.length > 300) {
      errors.specs =
        'Give every specification a name (up to 60 characters) and a value (up to 300).';
      break;
    }
  }
  return errors;
}

export function validateFiles(files: File[]): string | undefined {
  if (files.length > MAX_ATTACHMENTS) return `Attach at most ${MAX_ATTACHMENTS} files.`;
  for (const file of files) {
    if (!ATTACHMENT_EXTENSIONS.test(file.name))
      return `${file.name}: attach a JPG, PNG, GIF, WebP, MP4, or PDF file.`;
    if (file.size === 0) return `${file.name} is empty.`;
    if (file.size > MAX_ATTACHMENT_BYTES)
      return `${file.name} is larger than ${formatSize(MAX_ATTACHMENT_BYTES)}.`;
  }
}

const authorization = () => ({ Authorization: `Bearer ${session.accessToken}` });

interface ApiError {
  loc: (string | number)[];
  msg: string;
  type?: string;
}

async function errorsOf(response: Response): Promise<ApiError[]> {
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  return Array.isArray(body?.detail) ? (body.detail as ApiError[]) : [];
}

const apiField: Record<string, ListingField> = {
  category: 'category',
  title: 'title',
  description: 'description',
  budget_uah: 'price',
  price_uah: 'price',
  delivery_days: 'delivery_days',
  specs: 'specs',
  audience: 'audience',
};

const audienceOf = (input: ListingInput): ApiAudience | undefined => {
  const traits = input.traits
    .split(',')
    .map((trait) => trait.trim())
    .filter(Boolean);
  const audience: ApiAudience = {
    age_min: input.ageMin.trim() ? Number(input.ageMin) : null,
    age_max: input.ageMax.trim() ? Number(input.ageMax) : null,
    country: input.country.trim() || null,
    socioeconomic: input.socioeconomic.trim() || null,
    traits,
  };
  return audience.age_min === null &&
    audience.age_max === null &&
    !audience.country &&
    !audience.socioeconomic &&
    !traits.length
    ? undefined
    : audience;
};

/**
 * The request body for a listing. A new listing omits empty optional fields; an edit
 * sends them as `null` so the API clears a removed delivery time or audience (FR-017).
 */
function listingBody(type: ListingType, input: ListingInput, mode: 'create' | 'update') {
  const days = input.delivery_days.trim();
  const audience = audienceOf(input);
  const clear = mode === 'update' ? null : undefined;
  const body: Record<string, unknown> = {
    category: input.category,
    title: input.title.trim(),
    description: input.description.trim(),
    [type === 'request' ? 'budget_uah' : 'price_uah']: input.price.trim().replace(',', '.'),
    delivery_days: days ? Number(days) : clear,
    specs: input.specs
      .map((spec) => ({ label: spec.label.trim(), value: spec.value.trim() }))
      .filter((spec) => spec.label || spec.value),
    audience: audience ?? clear,
  };
  for (const key of Object.keys(body)) if (body[key] === undefined) delete body[key];
  return body;
}

async function sendListing(
  url: string,
  method: 'POST' | 'PATCH',
  body: Record<string, unknown>,
  fallback: string,
): Promise<SaveResult> {
  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json', ...authorization() },
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, fieldErrors: {}, message: 'Adify is unreachable. Try again in a moment.' };
  }
  if (response.ok) return { ok: true, listing: (await response.json()) as ApiListing };

  const fieldErrors: FieldErrors = {};
  let message: string | undefined;
  let type: string | undefined;
  for (const error of await errorsOf(response)) {
    type ??= error.type;
    const field = apiField[String(error.loc[1])];
    if (field) fieldErrors[field] ??= error.msg;
    else message ??= error.msg;
  }
  if (!message && Object.keys(fieldErrors).length === 0) message = fallback;
  return { ok: false, fieldErrors, message, type };
}

export const createListing = (type: ListingType, input: ListingInput): Promise<CreateResult> =>
  sendListing(
    `${PUBLIC_API_BASE_URL}/api/v1/listings/${type}s`,
    'POST',
    listingBody(type, input, 'create'),
    'The listing could not be created. Try again in a moment.',
  );

/** FR-017: the owner saves every field; an unchanged locked category is not a change. */
export const updateListing = (
  id: string,
  type: ListingType,
  input: ListingInput,
): Promise<SaveResult> =>
  sendListing(
    `${PUBLIC_API_BASE_URL}/api/v1/listings/${id}`,
    'PATCH',
    listingBody(type, input, 'update'),
    'Your changes could not be saved. Try again in a moment.',
  );

/** The edit form starts from the stored listing. */
export function inputFromListing(listing: ApiListing): ListingInput {
  const audience = listing.audience;
  return {
    category: listing.category,
    title: listing.title,
    description: listing.description,
    price: listing.price_uah.replace(/\.00$/, ''),
    delivery_days: listing.delivery_days === null ? '' : String(listing.delivery_days),
    specs: listing.specs.length
      ? listing.specs.map((spec) => ({ ...spec }))
      : [{ label: '', value: '' }],
    ageMin: audience?.age_min == null ? '' : String(audience.age_min),
    ageMax: audience?.age_max == null ? '' : String(audience.age_max),
    country: audience?.country ?? '',
    socioeconomic: audience?.socioeconomic ?? '',
    traits: audience?.traits.join(', ') ?? '',
  };
}

export async function deleteAttachment(
  listingId: string,
  attachment: Attachment,
): Promise<{ ok: true } | { ok: false; message: string }> {
  try {
    const response = await fetch(
      `${PUBLIC_API_BASE_URL}/api/v1/listings/${listingId}/attachments/${attachment.id}`,
      { method: 'DELETE', headers: authorization() },
    );
    if (response.ok || response.status === 404) return { ok: true };
    const [error] = await errorsOf(response);
    return {
      ok: false,
      message: `${attachment.filename}: ${error?.msg ?? 'the file could not be removed.'}`,
    };
  } catch {
    return { ok: false, message: `${attachment.filename}: Adify is unreachable.` };
  }
}

export async function uploadAttachment(
  listingId: string,
  file: File,
): Promise<{ ok: true } | { ok: false; message: string }> {
  try {
    const response = await fetch(
      `${PUBLIC_API_BASE_URL}/api/v1/listings/${listingId}/attachments?filename=${encodeURIComponent(file.name)}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/octet-stream', ...authorization() },
        body: file,
      },
    );
    if (response.ok) return { ok: true };
    const [error] = await errorsOf(response);
    return { ok: false, message: `${file.name}: ${error?.msg ?? 'the upload failed.'}` };
  } catch {
    return { ok: false, message: `${file.name}: Adify is unreachable.` };
  }
}

export type ListResult =
  { ok: true; items: ApiListing[]; total: number } | { ok: false; message: string };

export interface ListQuery {
  mine?: boolean;
  type?: ListingType;
  category?: string;
  /** FR-016 search term; the API matches title, description, and category. */
  search?: string;
  priceMin?: string;
  priceMax?: string;
  deliveryMax?: string;
  ageMin?: string;
  ageMax?: string;
  country?: string;
  socioeconomic?: string;
  traits?: string[];
  /** FR-085: minimum completed and maximum currently disputed orders per owner. */
  ownerCompletedMin?: string;
  ownerDisputedMax?: string;
  sort?: string;
  limit?: number;
  offset?: number;
}

// `mine` lists the signed-in account's own listings; otherwise all public ones.
export async function fetchListings(options: ListQuery = {}): Promise<ListResult> {
  const query = new URLSearchParams({ limit: String(options.limit ?? 50) });
  if (options.type) query.set('type', options.type);
  if (options.category) query.set('category', options.category);
  if (options.search?.trim()) query.set('q', options.search.trim());
  if (options.priceMin) query.set('price_min', options.priceMin);
  if (options.priceMax) query.set('price_max', options.priceMax);
  if (options.deliveryMax) query.set('delivery_max', options.deliveryMax);
  if (options.ageMin) query.set('age_min', options.ageMin);
  if (options.ageMax) query.set('age_max', options.ageMax);
  if (options.country?.trim()) query.set('country', options.country.trim());
  if (options.socioeconomic?.trim()) query.set('socioeconomic', options.socioeconomic.trim());
  for (const trait of options.traits ?? []) {
    if (trait.trim()) query.append('traits', trait.trim());
  }
  if (options.ownerCompletedMin !== undefined && options.ownerCompletedMin !== '') {
    query.set('owner_completed_min', String(options.ownerCompletedMin));
  }
  if (options.ownerDisputedMax !== undefined && options.ownerDisputedMax !== '') {
    query.set('owner_disputed_max', String(options.ownerDisputedMax));
  }
  if (options.sort && options.sort !== 'newest') query.set('sort', options.sort);
  if (options.offset) query.set('offset', String(options.offset));
  const path = options.mine ? 'listings/mine' : 'listings';
  try {
    const response = await fetch(`${PUBLIC_API_BASE_URL}/api/v1/${path}?${query}`, {
      headers: options.mine ? authorization() : undefined,
    });
    if (response.ok) {
      const body = (await response.json()) as { items: ApiListing[]; total: number };
      return { ok: true, items: body.items, total: body.total };
    }
  } catch {
    // Falls through to the generic message below.
  }
  return { ok: false, message: 'The listings could not be loaded. Try again in a moment.' };
}

export type FetchResult =
  { ok: true; listing: ApiListing } | { ok: false; notFound: boolean; message: string };

export async function fetchListing(id: string): Promise<FetchResult> {
  try {
    const response = await fetch(`${PUBLIC_API_BASE_URL}/api/v1/listings/${id}`);
    if (response.ok) return { ok: true, listing: (await response.json()) as ApiListing };
    if (response.status === 404)
      return { ok: false, notFound: true, message: 'This listing could not be found.' };
  } catch {
    // Falls through to the generic message below.
  }
  return { ok: false, notFound: false, message: 'The listing could not be loaded. Try again.' };
}

export type OwnListingResult =
  | { ok: true; listing: ApiListing }
  | { ok: false; reason: 'not_found' | 'not_owner' | 'error'; message: string };

/** The owner's view of a listing with its locked fields (FR-017). */
export async function fetchOwnListing(id: string): Promise<OwnListingResult> {
  try {
    const response = await fetch(`${PUBLIC_API_BASE_URL}/api/v1/listings/mine/${id}`, {
      headers: authorization(),
    });
    if (response.ok) return { ok: true, listing: (await response.json()) as ApiListing };
    if (response.status === 404)
      return { ok: false, reason: 'not_found', message: 'This listing could not be found.' };
    if (response.status === 403)
      return {
        ok: false,
        reason: 'not_owner',
        message: 'Only the owner of this listing can edit it.',
      };
  } catch {
    // Falls through to the generic message below.
  }
  return { ok: false, reason: 'error', message: 'The listing could not be loaded. Try again.' };
}

export type StateResult =
  { ok: true; listing: ApiListing } | { ok: false; type: string; message: string };

// FR-018: the owner pauses or resumes a listing; the API refuses to resume an expired one.
async function changeState(id: string, action: 'pause' | 'resume'): Promise<StateResult> {
  let response: Response;
  try {
    response = await fetch(`${PUBLIC_API_BASE_URL}/api/v1/listings/${id}/${action}`, {
      method: 'POST',
      headers: authorization(),
    });
  } catch {
    return {
      ok: false,
      type: 'unreachable',
      message: 'Adify is unreachable. Try again in a moment.',
    };
  }
  if (response.ok) return { ok: true, listing: (await response.json()) as ApiListing };
  const [error] = await errorsOf(response);
  return {
    ok: false,
    type: error?.type ?? 'unknown',
    message: error?.msg ?? `The listing could not be ${action}d. Try again in a moment.`,
  };
}

export const pauseListing = (id: string) => changeState(id, 'pause');
export const resumeListing = (id: string) => changeState(id, 'resume');

export type DeleteResult =
  { ok: true; result: 'removed' | 'soft_deleted' } | { ok: false; type: string; message: string };

// FR-020: the API decides between a soft delete (order history) and a permanent removal.
export async function deleteListing(id: string): Promise<DeleteResult> {
  let response: Response;
  try {
    response = await fetch(`${PUBLIC_API_BASE_URL}/api/v1/listings/${id}`, {
      method: 'DELETE',
      headers: authorization(),
    });
  } catch {
    return {
      ok: false,
      type: 'unreachable',
      message: 'Adify is unreachable. Try again in a moment.',
    };
  }
  if (response.ok) return { ok: true, ...((await response.json()) as { result: 'removed' }) };
  const [error] = await errorsOf(response);
  return {
    ok: false,
    type: error?.type ?? 'unknown',
    message: error?.msg ?? 'The listing could not be deleted. Try again in a moment.',
  };
}

export type ContactResult =
  { ok: true; phone?: string; chatId?: string } | { ok: false; type: string; message: string };

// FR-024–FR-026: the API checks verification and chat rules; the page only shows the outcome.
async function contact(id: string, action: 'phone-reveal' | 'chats'): Promise<ContactResult> {
  let response: Response;
  try {
    response = await fetch(`${PUBLIC_API_BASE_URL}/api/v1/listings/${id}/${action}`, {
      method: 'POST',
      headers: authorization(),
    });
  } catch {
    return {
      ok: false,
      type: 'unreachable',
      message: 'Adify is unreachable. Try again in a moment.',
    };
  }
  if (response.ok) {
    return action === 'phone-reveal'
      ? { ok: true, phone: ((await response.json()) as { phone: string }).phone }
      : { ok: true, chatId: ((await response.json()) as { id: string }).id };
  }
  const [error] = await errorsOf(response);
  const type = error?.type ?? 'unknown';
  return { ok: false, type, message: error?.msg ?? 'This action is not available.' };
}

export const revealPhone = (id: string) => contact(id, 'phone-reveal');
export const startChat = (id: string) => contact(id, 'chats');
