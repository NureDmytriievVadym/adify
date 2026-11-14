import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const ORDER_ID = '7d2e2e1f-6d4b-4b64-8a48-2e3c6c9d0b17';

const customer = { id: '1', display_name: 'Olena Koval', role: 'customer' as const };
const provider = { id: '2', display_name: 'Digital Daily', role: 'provider' as const };

interface Options {
  viewer: 'customer' | 'provider';
  status?: 'paid' | 'canceled';
  blocker?: string;
  startFails?: boolean;
}

// The preview runs without the API, so the order and Start work are answered here.
async function mockApi(page: Page, { viewer, status = 'paid', blocker, startFails }: Options) {
  const me = viewer === 'customer' ? customer : provider;
  const calls: string[] = [];
  const order = {
    id: ORDER_ID,
    status,
    details: 'Homepage banner for two weeks.',
    price_uah: '3000.00',
    deadline: null,
    stages: [],
    requirements: {
      listing_type: 'offer',
      category: 'website-banners',
      has_requirements: false,
      specs: [],
      requires_creatives: Boolean(blocker),
    },
    listing: { id: 'listing', title: 'Your brand on a design journal', type: 'offer' },
    chat_id: null,
    is_listing_owner: viewer === 'provider',
    customer,
    provider,
    created_at: '2026-11-10T10:00:00Z',
    paid_at: '2026-11-10T10:06:00Z',
    start_deadline: status === 'paid' ? '2026-11-17T10:06:00Z' : null,
    work_started_at: null as string | null,
    work_start_blocker: blocker ?? null,
    canceled_at: status === 'canceled' ? '2026-11-17T10:10:00Z' : null,
    cancel_reason: status === 'canceled' ? 'start_timeout' : null,
    review_started_at: null,
    completed_at: null,
    change_requests: [],
  };
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
    if (path.endsWith(`/orders/${ORDER_ID}/start`)) {
      if (startFails) {
        return route.fulfill({
          status: 502,
          headers,
          json: {
            detail: [
              {
                loc: ['body'],
                msg: 'Mono could not charge the payment. Try again.',
                type: 'payment_provider_error',
              },
            ],
          },
        });
      }
      Object.assign(order, {
        status: 'in_progress',
        start_deadline: null,
        work_started_at: '2026-11-12T09:30:00Z',
      });
      return route.fulfill({ status: 200, headers, json: order });
    }
    if (path.endsWith(`/orders/${ORDER_ID}`)) {
      return route.fulfill({ status: 200, headers, json: order });
    }
    return route.fulfill({ status: 404, headers, json: { detail: [] } });
  });
  return calls;
}

test('the provider starts work on a paid order', async ({ page }) => {
  const calls = await mockApi(page, { viewer: 'provider' });
  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.locator('.order-state')).toHaveText('Paid');
  await expect(page.getByText(/^Start by November 17, 2026/)).toBeVisible();
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);
  await page.getByRole('button', { name: 'Start work' }).click();
  const dialog = page.getByRole('dialog', { name: 'Start work on this order?' });
  await expect(dialog).toContainText('Mono will charge the held 3,000 UAH.');
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await dialog.getByRole('button', { name: 'Start work' }).click();

  await expect(page.locator('.order-state')).toHaveText('In progress');
  await expect(page.getByText(/^Work started on November 12, 2026/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start work' })).toHaveCount(0);
  expect(calls).toContain(`POST /api/v1/orders/${ORDER_ID}/start`);
});

test('the customer cannot start work and sees the start deadline', async ({ page }) => {
  await mockApi(page, { viewer: 'customer' });
  await page.goto(`/orders/${ORDER_ID}`);

  await expect(
    page.getByText(/^Waiting for the provider to start work by November 17/),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start work' })).toHaveCount(0);
});

test('a missing validated creative keeps Start work disabled', async ({ page }) => {
  await mockApi(page, { viewer: 'provider', blocker: 'No validated creative' });
  await page.goto(`/orders/${ORDER_ID}`);

  const start = page.getByRole('button', { name: 'Start work' });
  await expect(start).toBeDisabled();
  await expect(start).toHaveAccessibleDescription(/^No validated creative\./);
});

test('a Mono failure on Start work is explained', async ({ page }) => {
  await mockApi(page, { viewer: 'provider', startFails: true });
  await page.goto(`/orders/${ORDER_ID}`);

  await page.getByRole('button', { name: 'Start work' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Start work' }).click();

  await expect(page.getByRole('alert')).toHaveText('Mono could not charge the payment. Try again.');
  await expect(page.locator('.order-state')).toHaveText('Paid');
});

test('canceling the confirmation changes nothing', async ({ page }) => {
  const calls = await mockApi(page, { viewer: 'provider' });
  await page.goto(`/orders/${ORDER_ID}`);

  await page.getByRole('button', { name: 'Start work' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await page.getByRole('button', { name: 'Start work' }).click();
  await page.keyboard.press('Escape');

  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(page.locator('.order-state')).toHaveText('Paid');
  expect(calls).not.toContain(`POST /api/v1/orders/${ORDER_ID}/start`);
});

test('an order canceled by the start timeout says why', async ({ page }) => {
  await mockApi(page, { viewer: 'customer', status: 'canceled' });
  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.locator('.order-state')).toHaveText('Canceled');
  await expect(page.getByRole('status')).toContainText(
    'the provider did not start work in time. Mono released the held funds to the customer.',
  );
});
