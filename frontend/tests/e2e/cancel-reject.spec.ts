import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const ORDER_ID = '9f4a4a31-8f6d-4d86-8c6a-4a5e8ebe2d39';

const customer = { id: '1', display_name: 'Olena Koval', role: 'customer' as const };
const provider = { id: '2', display_name: 'Digital Daily', role: 'provider' as const };

type Status = 'awaiting_payment' | 'paid' | 'in_progress' | 'rejected';

// The preview runs without the API; this mock applies cancel and reject (ADY-025, ADY-026).
async function mockApi(page: Page, viewer: 'customer' | 'provider', status: Status) {
  const me = viewer === 'customer' ? customer : provider;
  const calls: string[] = [];
  const paidAt = status === 'awaiting_payment' ? null : '2026-11-10T10:06:00Z';
  const order = {
    id: ORDER_ID,
    status: status as string,
    details: 'Homepage banner for two weeks.',
    price_uah: '3000.00',
    deadline: null,
    stages: [],
    requirements: {
      listing_type: 'offer',
      category: 'website-banners',
      has_requirements: false,
      specs: [],
      requires_creatives: false,
    },
    listing: { id: 'listing', title: 'Your brand on a design journal', type: 'offer' },
    chat_id: null,
    is_listing_owner: viewer === 'provider',
    customer,
    provider,
    created_at: '2026-11-10T10:00:00Z',
    paid_at: paidAt,
    start_deadline: status === 'paid' ? '2026-11-17T10:06:00Z' : null,
    work_started_at: status === 'in_progress' ? '2026-11-11T09:00:00Z' : null,
    work_start_blocker: null,
    canceled_at: status === 'rejected' ? '2026-11-12T08:00:00Z' : (null as string | null),
    cancel_reason: status === 'rejected' ? 'provider_rejected' : (null as string | null),
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
    const base = `/api/v1/orders/${ORDER_ID}`;
    if (path === `${base}/cancel` || path === `${base}/reject`) {
      const rejected = path.endsWith('/reject');
      Object.assign(order, {
        status: rejected ? 'rejected' : 'canceled',
        canceled_at: '2026-11-14T12:00:00Z',
        cancel_reason: rejected ? 'provider_rejected' : 'customer_canceled',
        start_deadline: null,
      });
    } else if (path !== base) {
      return route.fulfill({ status: 404, headers, json: { detail: [] } });
    }
    return route.fulfill({ status: 200, headers, json: order });
  });
  return calls;
}

test('the customer cancels a paid order and the hold is released', async ({ page }) => {
  const calls = await mockApi(page, 'customer', 'paid');
  await page.goto(`/orders/${ORDER_ID}`);

  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);
  await expect(page.getByRole('button', { name: 'Reject order' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Cancel order' }).click();
  const dialog = page.getByRole('dialog', { name: 'Cancel this order?' });
  await expect(dialog).toContainText('Mono will release the held 3,000 UAH back to your card.');
  await expect(dialog.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused();
  await dialog.getByRole('button', { name: 'Cancel order' }).click();

  await expect(page.locator('.order-state')).toHaveText('Canceled');
  await expect(page.getByRole('status')).toContainText(
    'Canceled by the customer on November 14, 2026',
  );
  await expect(page.getByRole('status')).toContainText('Mono released the held funds');
  expect(calls).toContain(`POST /api/v1/orders/${ORDER_ID}/cancel`);
});

test('the customer cancels an order awaiting payment', async ({ page }) => {
  await mockApi(page, 'customer', 'awaiting_payment');
  await page.goto(`/orders/${ORDER_ID}`);

  await page.getByRole('button', { name: 'Cancel order' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('nothing will be charged');
  await dialog.getByRole('button', { name: 'Cancel order' }).click();

  await expect(page.locator('.order-state')).toHaveText('Canceled');
  await expect(page.getByRole('status')).not.toContainText('Mono released');
});

test('the provider rejects a paid order and the funds are released', async ({ page }) => {
  await mockApi(page, 'provider', 'paid');
  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.getByRole('button', { name: 'Cancel order' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Reject order' }).click();
  const dialog = page.getByRole('dialog', { name: 'Reject this order?' });
  await expect(dialog).toContainText('release the held 3,000 UAH back to the customer');
  await dialog.getByRole('button', { name: 'Reject order' }).click();

  await expect(page.locator('.order-state')).toHaveText('Rejected');
  await expect(page.getByRole('status')).toContainText('Funds released');
});

test('the customer sees that a rejected order released the funds', async ({ page }) => {
  await mockApi(page, 'customer', 'rejected');
  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.getByRole('status')).toContainText(
    'Rejected by the provider on November 12, 2026',
  );
  await expect(page.getByRole('status')).toContainText(
    'Funds released: Mono released the held funds to the customer.',
  );
});

test('after work starts there is no cancel, and a dispute is suggested', async ({ page }) => {
  await mockApi(page, 'customer', 'in_progress');
  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.getByRole('button', { name: 'Cancel order' })).toHaveCount(0);
  await expect(page.getByText(/can no longer be canceled/)).toContainText('open a dispute');
});

test('after work starts the provider cannot reject', async ({ page }) => {
  await mockApi(page, 'provider', 'in_progress');
  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.getByRole('button', { name: 'Submit for review' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Reject order' })).toHaveCount(0);
});

test('closing the confirmation keeps the order', async ({ page }) => {
  const calls = await mockApi(page, 'provider', 'awaiting_payment');
  await page.goto(`/orders/${ORDER_ID}`);

  await page.getByRole('button', { name: 'Reject order' }).click();
  await page.keyboard.press('Escape');

  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(page.locator('.order-state')).toHaveText('Awaiting payment');
  expect(calls).not.toContain(`POST /api/v1/orders/${ORDER_ID}/reject`);
});
