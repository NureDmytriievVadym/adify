import { expect, test, type Page } from '@playwright/test';

const LISTING_ID = '0b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a10';
const OWNER_PHONE = '+380501110101';
// The page shows the number grouped the way Ukrainian numbers are usually written.
const SHOWN_PHONE = '+380 50 111 01 01';
const OWNER_EMAIL = 'owner@example.com';

const listing = {
  id: LISTING_ID,
  type: 'offer',
  category: 'website-banners',
  title: 'Your brand on a design journal',
  description: 'A display banner placement on an independent design journal.',
  price_uah: '1200.00',
  delivery_days: 3,
  specs: [],
  audience: null,
  owner: { id: '2', display_name: 'Digital Daily', role: 'provider' },
  attachments: [],
  created_at: '2026-11-01T10:00:00Z',
  status: 'active',
  expires_at: '2026-12-01T10:00:00Z',
};

// The preview runs without the API; the mock signs the user in when the form is sent.
async function mockApi(page: Page, { signedIn = false, verified = true } = {}) {
  const state = { signedIn, reveals: 0 };
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const origin = (await request.headerValue('origin')) ?? '*';
    const headers = {
      'access-control-allow-origin': origin,
      'access-control-allow-credentials': 'true',
      'access-control-allow-headers': '*',
      'access-control-allow-methods': '*',
    };
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    const path = new URL(request.url()).pathname;
    const account = {
      id: '1',
      display_name: 'Olena Koval',
      email: 'olena@example.com',
      phone: '+380671234567',
      role: 'customer',
      status: 'active',
      email_verified: verified,
      phone_verified: verified,
    };
    const tokens = { access_token: 'token', token_type: 'bearer', expires_in: 900, account };
    if (path.endsWith('/auth/sign-in')) {
      state.signedIn = true;
      return route.fulfill({ status: 200, headers, json: tokens });
    }
    if (path.endsWith('/auth/refresh')) {
      return state.signedIn
        ? route.fulfill({ status: 200, headers, json: tokens })
        : route.fulfill({ status: 401, headers, json: { detail: [] } });
    }
    if (path.endsWith('/phone-reveal')) {
      state.reveals += 1;
      if (!verified) {
        return route.fulfill({
          status: 403,
          headers,
          json: {
            detail: [
              {
                loc: ['header', 'Authorization'],
                msg: 'Verify your email address and phone number to continue.',
                type: 'verification_required',
              },
            ],
          },
        });
      }
      return route.fulfill({ status: 200, headers, json: { phone: OWNER_PHONE } });
    }
    if (path.endsWith(`/listings/${LISTING_ID}`)) {
      return route.fulfill({ status: 200, headers, json: listing });
    }
    return route.fulfill({ status: 404, headers, json: { detail: [] } });
  });
  return state;
}

test('a guest is asked to sign in and comes back to the listing', async ({ page }) => {
  const state = await mockApi(page);
  await page.goto(`/listings/${LISTING_ID}`);

  await page.getByRole('link', { name: 'Reveal phone number' }).click();

  await expect(page).toHaveURL(`/sign-in?next=${encodeURIComponent(`/listings/${LISTING_ID}`)}`);
  expect(state.reveals).toBe(0);
  await page.getByLabel('Email address').fill('olena@example.com');
  await page.getByLabel('Password').fill('secret123');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page).toHaveURL(`/listings/${LISTING_ID}`);
  await page.getByRole('button', { name: 'Reveal phone number' }).click();
  await expect(page.getByText(SHOWN_PHONE)).toBeVisible();
});

test('an unverified user is blocked with a way to verify', async ({ page }) => {
  await mockApi(page, { signedIn: true, verified: false });
  await page.goto(`/listings/${LISTING_ID}`);

  await page.getByRole('button', { name: 'Reveal phone number' }).click();

  await expect(page.getByRole('alert')).toContainText(
    'Verify your email address and phone number to continue.',
  );
  await expect(page.getByRole('link', { name: 'Verify now' })).toBeVisible();
  await expect(page.getByText(SHOWN_PHONE)).toHaveCount(0);
});

test('a verified user sees the phone number only after asking, never an email', async ({
  page,
}) => {
  const state = await mockApi(page, { signedIn: true });
  await page.goto(`/listings/${LISTING_ID}`);

  await expect(page.getByText(SHOWN_PHONE)).toHaveCount(0);
  expect(state.reveals).toBe(0);
  await page.getByRole('button', { name: 'Reveal phone number' }).click();

  await expect(page.getByText(SHOWN_PHONE)).toBeVisible();
  expect(state.reveals).toBe(1);
  expect(await page.locator('body').innerText()).not.toContain(OWNER_EMAIL);
  expect(await page.content()).not.toContain(OWNER_EMAIL);
});

test('sign-in ignores a next address on another site', async ({ page }) => {
  await mockApi(page);
  await page.goto('/sign-in?next=//evil.example/steal');

  await page.getByLabel('Email address').fill('olena@example.com');
  await page.getByLabel('Password').fill('secret123');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page).toHaveURL('/account');
});

test('the revealed number can be copied; Call is only offered on touch devices', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const copied: string[] = [];
    (window as unknown as { copied: string[] }).copied = copied;
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: async (text: string) => void copied.push(text) },
    });
  });
  await mockApi(page, { signedIn: true });
  await page.goto(`/listings/${LISTING_ID}`);
  await page.getByRole('button', { name: 'Reveal phone number' }).click();

  await page.getByRole('button', { name: 'Copy' }).click();

  await expect(page.getByRole('button', { name: 'Copied' })).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { copied: string[] }).copied)).toEqual([
    OWNER_PHONE,
  ]);
  // Desktop pointers get no tel: link, so the browser never asks to open a dialer.
  await expect(page.getByRole('link', { name: 'Call' })).toBeHidden();
  await expect(page.locator('.phone-call')).toHaveAttribute('href', `tel:${OWNER_PHONE}`);
});
