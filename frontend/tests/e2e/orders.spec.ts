import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const CHAT_ID = '9c1f1d0e-5c3a-4a53-9f37-1d2f5b8c9a99';
const ORDER_ID = '6c1f1d0e-5c3a-4a53-9f37-1d2f5b8c9a96';
const LISTING_ID = '0b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a10';

const day = (offset: number) => {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
};

const customer = { id: '1', display_name: 'Olena Koval', role: 'customer' as const };
const provider = { id: '2', display_name: 'Digital Daily', role: 'provider' as const };

interface Options {
  viewer: 'customer' | 'provider';
  listingType?: 'offer' | 'request';
  status?: 'active' | 'paused';
}

// The preview runs without the API; this mock keeps the orders created during a test.
async function mockApi(page: Page, { viewer, listingType = 'offer', status = 'active' }: Options) {
  const me = viewer === 'customer' ? customer : provider;
  const owner = listingType === 'offer' ? provider : customer;
  const other = viewer === 'customer' ? provider : customer;
  const orders: object[] = [];
  const created: Record<string, unknown>[] = [];
  const specs = listingType === 'offer' ? [{ label: 'Dimensions', value: '728 x 90 px' }] : [];

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
    if (path.endsWith(`/chats/${CHAT_ID}/orders`)) {
      if (request.method() === 'POST') {
        const body = request.postDataJSON() as Record<string, unknown>;
        created.push(body);
        const order = {
          id: ORDER_ID,
          status: 'awaiting_payment',
          details: body.details,
          price_uah: `${Number(body.price_uah).toFixed(2)}`,
          deadline: body.deadline,
          stages: (body.stages as { title: string; deadline: string }[]).map((stage, index) => ({
            ...stage,
            id: `stage-${index}`,
            completed_at: null,
            completed_by: null,
          })),
          evidence: [],
          requirements: {
            listing_type: listingType,
            category: 'website-banners',
            has_requirements: specs.length > 0,
            specs,
          },
          listing: { id: LISTING_ID, title: 'Your brand on a design journal', type: listingType },
          chat_id: CHAT_ID,
          is_listing_owner: me.id === owner.id,
          customer,
          provider,
          created_at: '2026-11-10T10:00:00Z',
        };
        orders.push(order);
        return route.fulfill({ status: 201, headers, json: order });
      }
      return route.fulfill({ status: 200, headers, json: orders });
    }
    if (path.endsWith(`/chats/${CHAT_ID}`)) {
      return route.fulfill({
        status: 200,
        headers,
        json: {
          id: CHAT_ID,
          listing: {
            id: LISTING_ID,
            owner_id: owner.id,
            title: 'Your brand on a design journal',
            type: listingType,
            status,
          },
          counterpart: other,
          created_at: '2026-11-10T09:00:00Z',
        },
      });
    }
    if (path.endsWith(`/orders/${ORDER_ID}`)) {
      const order = orders[0] ?? {
        id: ORDER_ID,
        status: 'awaiting_payment',
        details: 'A sponsored article about our brand.',
        price_uah: '3000.00',
        deadline: null,
        stages: [],
        evidence: [],
        requirements: {
          listing_type: listingType,
          category: 'sponsored-articles',
          has_requirements: specs.length > 0,
          specs,
        },
        listing: { id: LISTING_ID, title: 'Looking for a home for our story', type: listingType },
        chat_id: CHAT_ID,
        is_listing_owner: me.id === owner.id,
        customer,
        provider,
        created_at: '2026-11-10T10:00:00Z',
      };
      return route.fulfill({ status: 200, headers, json: order });
    }
    return route.fulfill({ status: 404, headers, json: { detail: [] } });
  });
  return created;
}

test('the listing owner creates an order with two stages', async ({ page }) => {
  const created = await mockApi(page, { viewer: 'provider' });
  await page.goto(`/chats/${CHAT_ID}`);

  await page.getByRole('button', { name: 'Create order' }).click();
  await page.getByLabel('Order details').fill('Homepage banner for two weeks.');
  await page.getByLabel('Agreed price, UAH').fill('3000');
  await page.getByLabel('Order deadline (optional)').fill(day(20));
  await page.getByRole('button', { name: 'Add a stage' }).click();
  await page.getByLabel('Stage 1', { exact: true }).fill('Banner goes live');
  await page.getByLabel('Stage 1 deadline').fill(day(5));
  await page.getByRole('button', { name: 'Add a stage' }).click();
  await page.getByLabel('Stage 2', { exact: true }).fill('Placement report');
  await page.getByLabel('Stage 2 deadline').fill(day(19));
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);
  await page.getByRole('button', { name: 'Create order', exact: true }).last().click();

  await expect(page).toHaveURL(`/orders/${ORDER_ID}`);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('3,000 UAH');
  await expect(page.locator('.order-state')).toHaveText('Awaiting payment');
  await expect(page.getByText('Banner goes live')).toBeVisible();
  await expect(page.getByText('Placement report')).toBeVisible();
  await expect(page.getByText('728 x 90 px')).toBeVisible();
  expect(created).toEqual([
    {
      details: 'Homepage banner for two weeks.',
      price_uah: '3000',
      deadline: day(20),
      stages: [
        { title: 'Banner goes live', deadline: day(5) },
        { title: 'Placement report', deadline: day(19) },
      ],
    },
  ]);
});

test('the form explains missing details before sending', async ({ page }) => {
  const created = await mockApi(page, { viewer: 'provider' });
  await page.goto(`/chats/${CHAT_ID}`);

  await page.getByRole('button', { name: 'Create order' }).click();
  await page.getByRole('button', { name: 'Create order', exact: true }).last().click();

  await expect(page.getByRole('alert')).toHaveText('Describe what the order includes.');
  expect(created).toEqual([]);
});

test('the other party sees no Create order button', async ({ page }) => {
  await mockApi(page, { viewer: 'customer' });
  await page.goto(`/chats/${CHAT_ID}`);

  await expect(page.getByRole('heading', { name: 'Orders' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create order' })).toHaveCount(0);
  await expect(
    page.getByText('The listing owner creates the order once you agree on the details.'),
  ).toBeVisible();
});

test('a paused listing explains why no order can be created', async ({ page }) => {
  await mockApi(page, { viewer: 'provider', status: 'paused' });
  await page.goto(`/chats/${CHAT_ID}`);

  await expect(
    page.getByText('This listing is paused and is not accepting new orders.'),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create order' })).toHaveCount(0);
});

test('an order of an ad request without requirements says so', async ({ page }) => {
  await mockApi(page, { viewer: 'provider', listingType: 'request' });
  await page.goto(`/orders/${ORDER_ID}`);

  await expect(
    page.getByText('No technical requirements: the customer did not set any for this ad request.'),
  ).toBeVisible();
  await expect(page.getByRole('link', { name: 'Back to the chat' })).toHaveAttribute(
    'href',
    `/chats/${CHAT_ID}`,
  );
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);
});
