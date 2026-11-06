import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const CHAT_ID = '9c1f1d0e-5c3a-4a53-9f37-1d2f5b8c9a99';
const OTHER_CHAT = '8c1f1d0e-5c3a-4a53-9f37-1d2f5b8c9a98';
const FORBIDDEN_CHAT = '7c1f1d0e-5c3a-4a53-9f37-1d2f5b8c9a97';

const chats = [
  {
    id: CHAT_ID,
    listing: {
      id: '0b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a10',
      title: 'Your brand on a design journal',
      type: 'offer',
      status: 'active',
    },
    counterpart: { id: '2', display_name: 'Digital Daily', role: 'provider' },
    created_at: '2026-11-06T10:00:00Z',
  },
  {
    id: OTHER_CHAT,
    listing: null,
    counterpart: { id: '3', display_name: 'Pocket Studio', role: 'provider' },
    created_at: '2026-11-05T10:00:00Z',
  },
];

// The preview runs without the API; credentialed CORS needs the exact origin echoed back.
async function mockApi(page: Page, signedIn = true) {
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
    if (path.endsWith('/auth/refresh')) {
      if (!signedIn) return route.fulfill({ status: 401, headers, json: { detail: [] } });
      return route.fulfill({
        status: 200,
        headers,
        json: {
          access_token: 'token',
          token_type: 'bearer',
          expires_in: 900,
          account: {
            id: '1',
            display_name: 'Olena Koval',
            email: 'olena@example.com',
            phone: '+380671234567',
            role: 'customer',
            status: 'active',
            email_verified: true,
            phone_verified: true,
          },
        },
      });
    }
    if (path.endsWith('/api/v1/chats')) return route.fulfill({ status: 200, headers, json: chats });
    if (path.endsWith(`/chats/${FORBIDDEN_CHAT}`)) {
      return route.fulfill({
        status: 403,
        headers,
        json: {
          detail: [
            {
              loc: ['path'],
              msg: 'Only the two participants can open this chat.',
              type: 'not_chat_participant',
            },
          ],
        },
      });
    }
    const match = chats.find((chat) => path.endsWith(`/chats/${chat.id}`));
    if (match) return route.fulfill({ status: 200, headers, json: match });
    return route.fulfill({ status: 404, headers, json: { detail: [] } });
  });
}

test('the chat list shows each conversation and opens it', async ({ page }) => {
  await mockApi(page);
  await page.goto('/');
  await page.getByRole('link', { name: 'Chats', exact: true }).click();

  await expect(page).toHaveURL('/chats');
  await expect(page.getByRole('link', { name: /Digital Daily/ })).toContainText(
    'Provider · Your brand on a design journal',
  );
  await expect(page.getByRole('link', { name: /Pocket Studio/ })).toContainText('Deleted listing');
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);

  await page.getByRole('link', { name: /Digital Daily/ }).click();

  await expect(page).toHaveURL(`/chats/${CHAT_ID}`);
  await expect(page.getByRole('heading', { name: 'Chat with Digital Daily' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Your brand on a design journal' })).toHaveAttribute(
    'href',
    '/listings/0b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a10',
  );
  await expect(page.getByText('No messages yet.')).toBeVisible();
});

test('a chat of a deleted listing still opens', async ({ page }) => {
  await mockApi(page);
  await page.goto(`/chats/${OTHER_CHAT}`);

  await expect(page.getByRole('heading', { name: 'Chat with Pocket Studio' })).toBeVisible();
  await expect(page.getByText('The listing was deleted')).toBeVisible();
});

test('only participants can open a chat', async ({ page }) => {
  await mockApi(page);
  await page.goto(`/chats/${FORBIDDEN_CHAT}`);

  await expect(page.getByRole('alert')).toHaveText('Only the two participants can open this chat.');
});

test('guests are asked to sign in to see chats', async ({ page }) => {
  await mockApi(page, false);
  await page.goto('/chats');

  await expect(page.getByText('Sign in to see your chats.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Chats', exact: true })).toHaveCount(0);
});
