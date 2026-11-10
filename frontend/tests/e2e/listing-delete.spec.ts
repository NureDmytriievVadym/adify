import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// FR-020: the owner deletes a listing; one with order history is soft-deleted and kept.

const LISTING_ID = '0b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a10';

interface MockOptions {
  owner?: boolean;
  status?: 'active' | 'soft_deleted';
  /** What the API answers to the delete: depends on the listing's order history. */
  result?: 'removed' | 'soft_deleted';
}

async function mockApi(page: Page, options: MockOptions = {}) {
  const { owner = true, status = 'active', result = 'removed' } = options;
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
    status,
    expires_at: '2026-12-01T10:00:00Z',
  };
  const calls: string[] = [];

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

    if (path.endsWith('/auth/refresh')) {
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
            role: owner ? 'provider' : 'customer',
            status: 'active',
            email_verified: true,
            phone_verified: true,
          },
        },
      });
    }
    if (path.endsWith('/listings/mine')) {
      return route.fulfill({ status: 200, headers, json: { items: [], total: 0 } });
    }
    if (path.endsWith(`/listings/${LISTING_ID}`) && method === 'DELETE') {
      calls.push('delete');
      return route.fulfill({ status: 200, headers, json: { result } });
    }
    if (path.endsWith(`/listings/${LISTING_ID}`)) {
      return route.fulfill({ status: 200, headers, json: stored });
    }
    return route.fulfill({ status: 404, headers, json: { detail: [] } });
  });
  return calls;
}

const listingPage = `/listings/${LISTING_ID}`;

test('the owner confirms before a listing is deleted', async ({ page }) => {
  const calls = await mockApi(page);
  await page.goto(listingPage);

  await page.getByRole('button', { name: 'Delete listing' }).click();
  await expect(page.getByText('Delete this listing?')).toBeVisible();
  await page.getByRole('button', { name: 'Keep it' }).click();

  await expect(page.getByText('Delete this listing?')).toHaveCount(0);
  expect(calls).toEqual([]);
});

test('a listing without orders is removed', async ({ page }) => {
  const calls = await mockApi(page);
  await page.goto(listingPage);

  await page.getByRole('button', { name: 'Delete listing' }).click();
  await page.getByRole('button', { name: 'Delete listing' }).click();

  await expect(page).toHaveURL('/listings/mine');
  await expect(page.getByRole('status').filter({ hasText: 'deleted' })).toHaveText(
    'Your listing was deleted.',
  );
  expect(calls).toEqual(['delete']);
});

test('a listing with order history is kept for its orders', async ({ page }) => {
  await mockApi(page, { result: 'soft_deleted' });
  await page.goto(listingPage);

  await page.getByRole('button', { name: 'Delete listing' }).click();
  await page.getByRole('button', { name: 'Delete listing' }).click();

  await expect(page).toHaveURL('/listings/mine');
  await expect(
    page.getByText('Its orders still show it, but it is gone from the marketplace.', {
      exact: false,
    }),
  ).toBeVisible();
});

test('the owner sees a soft-deleted listing as a record only', async ({ page }) => {
  await mockApi(page, { status: 'soft_deleted' });
  await page.goto(listingPage);

  await expect(page.locator('.detail-title .listing-state')).toHaveText('Deleted');
  await expect(page.getByText('You deleted this listing.', { exact: false })).toBeVisible();
  for (const name of ['Edit listing', 'Pause listing', 'Delete listing']) {
    await expect(page.getByRole('button', { name })).toHaveCount(0);
  }
  await expect(page.getByRole('link', { name: 'Edit listing' })).toHaveCount(0);
});

test('others can still chat about a soft-deleted listing (FR-026)', async ({ page }) => {
  await mockApi(page, { owner: false, status: 'soft_deleted' });
  await page.goto(listingPage);

  await expect(
    page.getByText('The owner deleted this listing, so it is not accepting new orders.', {
      exact: false,
    }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start chat' })).toBeEnabled();
});

test('the delete confirmation has no accessibility violations', async ({ page }) => {
  await mockApi(page);
  await page.goto(listingPage);
  await page.getByRole('button', { name: 'Delete listing' }).click();
  await expect(page.getByText('Delete this listing?')).toBeVisible();

  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(results.violations).toEqual([]);
});
