import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const ORDER_ID = '8e3f3f20-7e5c-4c75-9b59-3f4d7dae1c28';
const REQUEST_ID = 'c1a2b3c4-d5e6-4f70-8a9b-0c1d2e3f4a5b';

const customer = { id: '1', display_name: 'Olena Koval', role: 'customer' as const };
const provider = { id: '2', display_name: 'Digital Daily', role: 'provider' as const };

interface ChangeRequest {
  id: string;
  message: string;
  status: 'pending' | 'agreed' | 'declined' | 'withdrawn';
  created_at: string;
  answered_at: string | null;
}

interface Options {
  viewer: 'customer' | 'provider';
  status: 'in_progress' | 'in_review';
  pendingRequest?: boolean;
}

// The preview runs without the API; this mock applies the review transitions of ADY-023.
async function mockApi(page: Page, { viewer, status, pendingRequest }: Options) {
  const me = viewer === 'customer' ? customer : provider;
  const calls: string[] = [];
  const changeRequests: ChangeRequest[] = pendingRequest
    ? [
        {
          id: REQUEST_ID,
          message: 'Please use the new logo.',
          status: 'pending',
          created_at: '2026-11-13T09:00:00Z',
          answered_at: null,
        },
      ]
    : [];
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
    paid_at: '2026-11-10T10:06:00Z',
    start_deadline: null,
    work_started_at: '2026-11-11T09:00:00Z',
    work_start_blocker: null,
    canceled_at: null,
    cancel_reason: null,
    review_started_at: status === 'in_review' ? '2026-11-12T15:00:00Z' : (null as string | null),
    completed_at: null as string | null,
    change_requests: changeRequests,
  };
  const now = '2026-11-14T12:00:00Z';
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
    if (path === `${base}/review`) {
      Object.assign(order, { status: 'in_review', review_started_at: now });
    } else if (path === `${base}/accept`) {
      Object.assign(order, { status: 'done', completed_at: now });
    } else if (path === `${base}/change-requests`) {
      const { message } = request.postDataJSON() as { message: string };
      changeRequests.push({
        id: REQUEST_ID,
        message,
        status: 'pending',
        created_at: now,
        answered_at: null,
      });
      return route.fulfill({ status: 201, headers, json: order });
    } else if (path.startsWith(`${base}/change-requests/`)) {
      const agree = path.endsWith('/agree');
      Object.assign(changeRequests[0], {
        status: agree ? 'agreed' : 'declined',
        answered_at: now,
      });
      if (agree) Object.assign(order, { status: 'in_progress', review_started_at: null });
    } else if (path !== base) {
      return route.fulfill({ status: 404, headers, json: { detail: [] } });
    }
    return route.fulfill({ status: 200, headers, json: order });
  });
  return calls;
}

// Every review step opens a confirmation in the middle of the screen first.
async function confirm(page: Page, title: string, label: string) {
  const dialog = page.getByRole('dialog', { name: title });
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await dialog.getByRole('button', { name: label }).click();
  await expect(dialog).toBeHidden();
}

test('the provider submits work for review', async ({ page }) => {
  const calls = await mockApi(page, { viewer: 'provider', status: 'in_progress' });
  await page.goto(`/orders/${ORDER_ID}`);

  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);
  await page.getByRole('button', { name: 'Submit for review' }).click();
  await confirm(page, 'Submit the work for review?', 'Submit for review');

  await expect(page.locator('.order-state')).toHaveText('In review');
  await expect(
    page.getByText('Waiting for the customer to accept the work or ask for changes.'),
  ).toBeVisible();
  expect(calls).toContain(`POST /api/v1/orders/${ORDER_ID}/review`);
});

test('the customer requests changes', async ({ page }) => {
  await mockApi(page, { viewer: 'customer', status: 'in_review' });
  await page.goto(`/orders/${ORDER_ID}`);

  await page.getByRole('button', { name: 'Request changes' }).click();
  await page.getByRole('button', { name: 'Send request' }).click();
  await expect(page.getByRole('alert')).toHaveText('Describe what the provider should change.');
  await page.getByLabel('What should the provider change?').fill('Make the logo bigger.');
  await page.getByRole('button', { name: 'Send request' }).click();
  await confirm(page, 'Send this change request?', 'Send request');

  await expect(page.getByRole('status')).toContainText('You asked for changes.');
  await expect(page.getByText('Make the logo bigger.')).toBeVisible();
  await expect(page.getByText(/Waiting for the provider’s answer/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Request changes' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Accept work' })).toBeVisible();
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);
});

test('the provider agrees to make changes', async ({ page }) => {
  await mockApi(page, { viewer: 'provider', status: 'in_review', pendingRequest: true });
  await page.goto(`/orders/${ORDER_ID}`);

  await expect(page.locator('blockquote')).toHaveText('Please use the new logo.');
  await page.getByRole('button', { name: 'Agree to make changes' }).click();
  await confirm(page, 'Agree to make the changes?', 'Agree to make changes');

  await expect(page.locator('.order-state')).toHaveText('In progress');
  await expect(page.getByText(/The provider agreed to make the changes/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Submit for review' })).toBeVisible();
});

test('the provider declines the changes', async ({ page }) => {
  await mockApi(page, { viewer: 'provider', status: 'in_review', pendingRequest: true });
  await page.goto(`/orders/${ORDER_ID}`);

  await page.getByRole('button', { name: 'Decline' }).click();
  await confirm(page, 'Decline the change request?', 'Decline request');

  await expect(page.locator('.order-state')).toHaveText('In review');
  await expect(page.getByText(/The provider declined/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Agree to make changes' })).toHaveCount(0);
});

test('the customer accepts the work and the order is done', async ({ page }) => {
  const calls = await mockApi(page, { viewer: 'customer', status: 'in_review' });
  await page.goto(`/orders/${ORDER_ID}`);

  await page.getByRole('button', { name: 'Accept work' }).click();
  await confirm(page, 'Accept the work?', 'Accept work');

  await expect(page.locator('.order-state')).toHaveText('Done');
  await expect(page.getByRole('status')).toContainText('the customer accepted the work.');
  expect(calls).toContain(`POST /api/v1/orders/${ORDER_ID}/accept`);
});

test('a step canceled in its confirmation is not applied', async ({ page }) => {
  const calls = await mockApi(page, { viewer: 'customer', status: 'in_review' });
  await page.goto(`/orders/${ORDER_ID}`);

  await page.getByRole('button', { name: 'Accept work' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click();

  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(page.locator('.order-state')).toHaveText('In review');
  expect(calls).not.toContain(`POST /api/v1/orders/${ORDER_ID}/accept`);
});
