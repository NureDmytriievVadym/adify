import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const ORDER_ID = '6c1f1d0e-5c3a-4a53-9f37-1d2f5b8c9a96';
const PAGE_URL = 'https://pay.mbnk.biz/p2_test';

const customer = { id: '1', display_name: 'Olena Koval', role: 'customer' as const };
const provider = { id: '2', display_name: 'Digital Daily', role: 'provider' as const };

interface Options {
  viewer: 'customer' | 'provider';
  status?: 'awaiting_payment' | 'paid';
  payment?: { status: string; failure_reason?: string };
}

// The preview runs without the API; Mono's page is stubbed so the redirect stays local.
async function mockApi(page: Page, { viewer, status = 'awaiting_payment', payment }: Options) {
  const me = viewer === 'customer' ? customer : provider;
  const calls: string[] = [];
  await page.route(PAGE_URL, (route) =>
    route.fulfill({ status: 200, contentType: 'text/html', body: '<h1>Mono payment</h1>' }),
  );
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
    calls.push(`${request.method()} ${path}`);
    if (path.endsWith('/auth/refresh')) {
      return route.fulfill({
        status: 200,
        headers,
        json: {
          access_token: 'token',
          token_type: 'bearer',
          expires_in: 900,
          account: {
            ...me,
            email: 'me@example.com',
            phone: '+380671234567',
            status: 'active',
            email_verified: true,
            phone_verified: true,
          },
        },
      });
    }
    if (path.endsWith(`/orders/${ORDER_ID}/payment`)) {
      if (request.method() === 'POST') {
        return route.fulfill({
          status: 201,
          headers,
          json: {
            status: 'created',
            amount_uah: '3000.00',
            page_url: PAGE_URL,
            failure_reason: null,
            created_at: '2026-11-10T10:05:00Z',
          },
        });
      }
      return route.fulfill({
        status: 200,
        headers,
        json: {
          status: payment?.status ?? 'created',
          amount_uah: '3000.00',
          page_url: null,
          failure_reason: payment?.failure_reason ?? null,
          created_at: '2026-11-10T10:05:00Z',
        },
      });
    }
    if (path.endsWith(`/orders/${ORDER_ID}`)) {
      return route.fulfill({
        status: 200,
        headers,
        json: {
          id: ORDER_ID,
          status,
          details: 'Homepage banner for two weeks.',
          price_uah: '3000.00',
          deadline: null,
          stages: [],
          evidence: [],
          requirements: {
            listing_type: 'offer',
            category: 'website-banners',
            has_requirements: false,
            specs: [],
          },
          listing: { id: 'listing', title: 'Your brand on a design journal', type: 'offer' },
          chat_id: null,
          is_listing_owner: viewer === 'provider',
          customer,
          provider,
          created_at: '2026-11-10T10:00:00Z',
          paid_at: status === 'paid' ? '2026-11-10T10:06:00Z' : null,
        },
      });
    }
    return route.fulfill({ status: 404, headers, json: { detail: [] } });
  });
  return calls;
}

test('the customer pays an order on the Mono page', async ({ page }) => {
  const calls = await mockApi(page, { viewer: 'customer' });
  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.locator('.order-state')).toHaveText('Awaiting payment');
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);
  await page.getByRole('button', { name: 'Pay 3,000 UAH' }).click();

  await expect(page).toHaveURL(PAGE_URL);
  expect(calls).toContain(`POST /api/v1/orders/${ORDER_ID}/payment`);
});

test('the provider waits for the payment', async ({ page }) => {
  await mockApi(page, { viewer: 'provider' });
  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.getByText('Waiting for the customer to pay through Mono.')).toBeVisible();
  await expect(page.getByRole('button', { name: /^Pay/ })).toHaveCount(0);
});

test('returning from Mono after a hold shows the order paid', async ({ page }) => {
  const calls = await mockApi(page, {
    viewer: 'customer',
    status: 'paid',
    payment: { status: 'hold' },
  });
  await page.goto(`/orders/${ORDER_ID}?payment=return`);

  await expect(page.locator('.order-state')).toHaveText('Paid');
  await expect(
    page.getByText(
      'Paid on November 10, 2026. Mono holds the funds until the provider starts work.',
    ),
  ).toBeVisible();
  expect(calls).toContain(`GET /api/v1/orders/${ORDER_ID}/payment`);
});

test('returning from Mono after a failure explains it', async ({ page }) => {
  await mockApi(page, {
    viewer: 'customer',
    payment: { status: 'failure', failure_reason: 'Insufficient funds' },
  });
  await page.goto(`/orders/${ORDER_ID}?payment=return`);

  await expect(page.getByRole('alert')).toHaveText(
    'The payment did not go through (Insufficient funds). You can try again.',
  );
  await expect(page.getByRole('button', { name: 'Pay 3,000 UAH' })).toBeVisible();
});
