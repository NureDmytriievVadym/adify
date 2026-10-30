import { PUBLIC_API_BASE_URL } from '$app/env/public';

export type AccountRole = 'customer' | 'provider';
export type RegistrationField = 'display_name' | 'email' | 'phone' | 'role' | 'password';
export type RegistrationInput = Record<RegistrationField, string>;
export type FieldErrors = Partial<Record<RegistrationField, string>>;

export interface Account {
  id: string;
  display_name: string;
  email: string;
  phone: string;
  role: AccountRole;
  email_verified: boolean;
  phone_verified: boolean;
}

export type RegistrationResult =
  { ok: true; account: Account } | { ok: false; fieldErrors: FieldErrors; message?: string };

interface ApiFieldError {
  loc: (string | number)[];
  msg: string;
}

const fields: RegistrationField[] = ['display_name', 'email', 'phone', 'role', 'password'];

export const normalizePhone = (phone: string) => phone.replace(/[\s()-]/g, '');

// Mirrors the API rules (FR-078, FR-080) so most mistakes are caught before a request.
export function validateRegistration(input: RegistrationInput): FieldErrors {
  const errors: FieldErrors = {};
  if (!input.display_name.trim()) errors.display_name = 'Enter a display name.';
  else if (input.display_name.trim().length > 100)
    errors.display_name = 'Use at most 100 characters.';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.email.trim()))
    errors.email = 'Enter a valid email address.';
  if (!/^\+380\d{9}$/.test(normalizePhone(input.phone)))
    errors.phone = 'Enter a Ukrainian phone number in the format +380XXXXXXXXX.';
  if (input.role !== 'customer' && input.role !== 'provider')
    errors.role = 'Choose exactly one role: customer or provider.';
  if (input.password.length < 8 || !/\p{L}/u.test(input.password) || !/\d/.test(input.password))
    errors.password = 'Use at least 8 characters, including at least one letter and one digit.';
  return errors;
}

export async function registerAccount(
  input: RegistrationInput,
  fetcher: typeof fetch = fetch,
): Promise<RegistrationResult> {
  let response: Response;
  try {
    response = await fetcher(`${PUBLIC_API_BASE_URL}/api/v1/accounts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...input,
        display_name: input.display_name.trim(),
        email: input.email.trim(),
        phone: normalizePhone(input.phone),
      }),
    });
  } catch {
    return { ok: false, fieldErrors: {}, message: 'Adify is unreachable. Try again in a moment.' };
  }
  if (response.ok) return { ok: true, account: (await response.json()) as Account };

  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const fieldErrors: FieldErrors = {};
  let message: string | undefined;
  if (Array.isArray(body?.detail)) {
    for (const error of body.detail as ApiFieldError[]) {
      const field = error.loc.at(-1);
      if (fields.includes(field as RegistrationField)) {
        fieldErrors[field as RegistrationField] ??= error.msg;
      } else {
        message ??= error.msg;
      }
    }
  }
  if (!message && Object.keys(fieldErrors).length === 0) {
    message = 'Registration failed. Try again in a moment.';
  }
  return { ok: false, fieldErrors, message };
}
