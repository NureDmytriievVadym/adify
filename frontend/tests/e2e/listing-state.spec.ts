import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// FR-018/FR-019: the owner pauses and resumes a listing; an expired one cannot be resumed.

const LISTING_ID = '0b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a10';
const CHAT_ID = '9c1f1d0e-5c3a-4a53-9f37-1d2f5b8c9a99';

type Status = 'active' | 'paused' | 'expired';

interface MockOptions {
  role?: 'customer' | 'provider' | null;
  owner?: boolean;
  status?: Status;
  /** The listing expires while the page is open, so the API refuses to resume it. */
  expiresOnResume?: boolean;
}

async function mockApi(page: Page, options: MockOptions = {}) {
  const { role = 'provider', owner = true, status = 'active', expiresOnResume = false } = options;
  const stored = {
    id: LISTING_ID,
    type: 'offer',
    category: 'website-banners',
    title: 'Your brand on a design journal',
    description: 'A display banner placement on an independent design journal.',
    price_uah: '3500.00',
    delivery_days: 5,
    specs: [],
    audience: null,
    owner: { id: owner ? '1' : '2', display_name: 'Digital Daily', role: 'provider' },
    attachments: [],
    created_at: '2026-11-01T10:00:00Z',
    status: status as Status,
    expires_at: status === 'expired' ? '2026-10-20T10:00:00Z' : '2026-12-01T10:00:00Z',
  };
  const calls: string[] = [];
  const chatStore: object[] = [];

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const origin = (await request.headerValue('origin')) ?? '*';
    const headers = {
      'access-control-allow-origin': origin,
      'access-control-allow-credentials': 'true',
      'access-control-allow-headers': '*',
      'access-control-allow-methods': '*',
    };
    const method = request.method();
    if (method === 'OPTIONS') return route.fulfill({ status: 204, headers });
    const path = new URL(request.url()).pathname;
    const expired = () =>
      route.fulfill({
        status: 409,
        headers,
        json: {
          detail: [
            {
              loc: ['body'],
              msg: 'An expired listing cannot be resumed.',
              type: 'listing_expired',
            },
          ],
        },
      });

    if (path.endsWith('/auth/refresh')) {
      if (!role) return route.fulfill({ status: 401, headers, json: { detail: [] } });
      return route.fulfill({
        status: 200,
        headers,
        json: {
          access_token: 'token',
          token_type: 'bearer',
          expires_in: 900,
          account: {
            id: '1',
            display_name: 'Digital Daily',
            email: 'digital@example.com',
            phone: '+380671234567',
            role,
            status: 'active',
            email_verified: true,
            phone_verified: true,
          },
        },
      });
    }
    if (path.endsWith('/pause') && method === 'POST') {
      calls.push('pause');
      if (stored.status === 'expired') return expired();
      stored.status = 'paused';
      return route.fulfill({ status: 200, headers, json: { ...stored, locked_fields: [] } });
    }
    if (path.endsWith('/resume') && method === 'POST') {
      calls.push('resume');
      if (expiresOnResume) stored.status = 'expired';
      if (stored.status === 'expired') return expired();
      stored.status = 'active';
      return route.fulfill({ status: 200, headers, json: { ...stored, locked_fields: [] } });
    }
    if (path.endsWith('/chats') && method === 'POST') {
      calls.push('chat');
      const chat = {
        id: CHAT_ID,
        listing: { id: LISTING_ID, title: stored.title, type: 'offer', status: stored.status },
        counterpart: { id: '2', display_name: 'Digital Daily', role: 'provider' },
        created_at: '2026-11-06T10:00:00Z',
      };
      chatStore.push(chat);
      return route.fulfill({ status: 201, headers, json: chat });
    }
    if (path.endsWith(`/chats/${CHAT_ID}`)) {
      return route.fulfill({ status: 200, headers, json: chatStore[0] });
    }
    if (path.endsWith('/listings/mine')) {
      const other = (state: Status, id: string, title: string) => ({
        ...stored,
        id,
        title,
        status: state,
      });
      return route.fulfill({
        status: 200,
        headers,
        json: {
          items: [
            stored,
            other('paused', '2b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a12', 'A paused banner slot'),
            other('expired', '3b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a13', 'An expired newsletter'),
          ],
          total: 3,
        },
      });
    }
    if (path.endsWith(`/listings/${LISTING_ID}`)) {
      return route.fulfill({ status: 200, headers, json: stored });
    }
    return route.fulfill({ status: 404, headers, json: { detail: [] } });
  });
  return calls;
}

const listingPage = `/listings/${LISTING_ID}`;

test('the owner pauses a listing and resumes it', async ({ page }) => {
  const calls = await mockApi(page);
  await page.goto(listingPage);

  await expect(page.getByText(/^Active until December 1, 2026\./)).toBeVisible();
  await expect(page.locator('.detail-title .listing-state')).toHaveCount(0);
  await page.getByRole('button', { name: 'Pause listing' }).click();

  await expect(page.locator('.detail-title .listing-state')).toHaveText('Paused');
  await expect(
    page.getByText('Paused: hidden from the marketplace and not accepting new orders.', {
      exact: false,
    }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Resume listing' }).click();

  await expect(page.getByRole('button', { name: 'Pause listing' })).toBeVisible();
  await expect(page.locator('.detail-title .listing-state')).toHaveCount(0);
  await expect(page.getByText(/^Active until December 1, 2026\./)).toBeVisible();
  expect(calls).toEqual(['pause', 'resume']);
});

test('a paused listing takes no new orders but still opens a chat (FR-026)', async ({ page }) => {
  const calls = await mockApi(page, { role: 'customer', owner: false, status: 'paused' });
  await page.goto(listingPage);

  await expect(page.locator('.detail-title .listing-state')).toHaveText('Paused');
  await expect(
    page.getByText(
      'This listing is paused and is not accepting new orders. You can still chat with the owner.',
    ),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Reveal phone number' })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Pause listing' })).toHaveCount(0);

  await page.getByRole('button', { name: /Start chat/ }).click();

  await expect(page).toHaveURL(`/chats/${CHAT_ID}`);
  await expect(page.locator('.listing-state')).toHaveText('Paused');
  expect(calls).toEqual(['chat']);
});

test('guests are sent to sign in before chatting on a paused listing', async ({ page }) => {
  await mockApi(page, { role: null, owner: false, status: 'paused' });
  await page.goto(listingPage);

  await expect(page.getByRole('link', { name: /Start chat/ })).toHaveAttribute('href', '/sign-in');
});

test('an active listing lets other users start a chat', async ({ page }) => {
  const calls = await mockApi(page, { role: 'customer', owner: false });
  await page.goto(listingPage);

  await page.getByRole('button', { name: /Start chat/ }).click();

  await expect(page).toHaveURL(`/chats/${CHAT_ID}`);
  expect(calls).toEqual(['chat']);
});

test('an expired listing cannot be resumed', async ({ page }) => {
  const calls = await mockApi(page, { status: 'expired' });
  await page.goto(listingPage);

  await expect(page.locator('.detail-title .listing-state')).toHaveText('Expired');
  await expect(page.getByRole('button', { name: 'Resume listing' })).toBeDisabled();
  await expect(
    page.getByText('Expired on October 20, 2026. An expired listing cannot be resumed.'),
  ).toBeVisible();
  await expect(page.getByRole('link', { name: 'Edit listing' })).toBeVisible();
  expect(calls).toEqual([]);
});

test('a listing that expired while the page was open is not resumed', async ({ page }) => {
  await mockApi(page, { status: 'paused', expiresOnResume: true });
  await page.goto(listingPage);

  await page.getByRole('button', { name: 'Resume listing' }).click();

  await expect(page.getByRole('alert')).toHaveText('An expired listing cannot be resumed.');
  await expect(page.locator('.detail-title .listing-state')).toHaveText('Expired');
  await expect(page.getByRole('button', { name: 'Resume listing' })).toBeDisabled();
});

test('my listings marks paused and expired listings', async ({ page }) => {
  await mockApi(page);
  await page.goto('/listings/mine');

  const card = (title: string) => page.locator('.listing-card', { hasText: title });
  await expect(card('Your brand on a design journal').locator('.listing-state')).toHaveCount(0);
  await expect(card('A paused banner slot').locator('.listing-state')).toHaveText('Paused');
  await expect(card('An expired newsletter').locator('.listing-state')).toHaveText('Expired');
});

test('paused and expired listing pages have no accessibility violations', async ({ page }) => {
  await mockApi(page, { owner: false, role: 'customer', status: 'paused' });
  await page.setViewportSize({ width: 360, height: 900 });
  await page.goto(listingPage);
  await expect(page.getByRole('button', { name: /Start chat/ })).toBeEnabled();

  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(results.violations).toEqual([]);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
});
