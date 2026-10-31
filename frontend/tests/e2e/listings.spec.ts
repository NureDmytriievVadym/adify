import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const LISTING_ID = '0b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a10';
const PNG = Buffer.from('89504e470d0a1a0a0000000000000000', 'hex');

type Role = 'customer' | 'provider';

const accountFor = (role: Role) => ({
  id: '1',
  display_name: 'Olena Koval',
  email: 'olena@example.com',
  phone: '+380671234567',
  role,
  status: 'active',
  email_verified: false,
  phone_verified: false,
});

// The preview runs without the API; credentialed CORS needs the exact origin echoed back.
async function mockApi(page: Page, role: Role | null) {
  const created: { path: string; body: Record<string, unknown> }[] = [];
  const uploads: string[] = [];
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
      if (!role) return route.fulfill({ status: 401, headers, json: { detail: [] } });
      return route.fulfill({
        status: 200,
        headers,
        json: {
          access_token: 'token',
          token_type: 'bearer',
          expires_in: 900,
          account: accountFor(role),
        },
      });
    }
    if (path.endsWith('/attachments')) {
      uploads.push(new URL(request.url()).searchParams.get('filename') ?? '');
      return route.fulfill({ status: 201, headers, json: {} });
    }
    if (/\/listings\/(requests|offers)$/.test(path)) {
      const body = request.postDataJSON() as Record<string, unknown>;
      created.push({ path, body });
      return route.fulfill({
        status: 201,
        headers,
        json: listing(path.endsWith('requests') ? 'request' : 'offer', body),
      });
    }
    if (path.endsWith('/listings/mine')) {
      if (!role) return route.fulfill({ status: 401, headers, json: { detail: [] } });
      return route.fulfill({
        status: 200,
        headers,
        json: { items: [listing('request', { title: 'My own request' })], total: 1 },
      });
    }
    if (path.endsWith('/listings')) {
      const type = new URL(request.url()).searchParams.get('type');
      const items = [
        listing('offer', { title: 'A provider offering' }),
        listing('request', { id: 'x', title: 'A customer request' }),
      ].filter((item) => !type || item.type === type);
      return route.fulfill({ status: 200, headers, json: { items, total: items.length } });
    }
    if (path.endsWith(`/listings/${LISTING_ID}`)) {
      return route.fulfill({ status: 200, headers, json: listing('offer', {}) });
    }
    if (path.includes('/listings/')) {
      return route.fulfill({
        status: 404,
        headers,
        json: { detail: [{ loc: ['body'], msg: 'This listing could not be found.', type: 'x' }] },
      });
    }
    return route.fulfill({ status: 404, headers, json: { detail: [] } });
  });
  await page.route('**/attachments/*', (route) =>
    route.fulfill({ status: 200, contentType: 'image/png', body: PNG }),
  );
  return { created, uploads };
}

const listing = (type: 'request' | 'offer', body: Record<string, unknown>) => ({
  id: LISTING_ID,
  type,
  category: 'website-banners',
  title: 'Your brand on a design journal',
  description: 'A display banner placement on an independent design journal.',
  price_uah: '3500.50',
  delivery_days: 5,
  specs: [{ label: 'Dimensions', value: '728 × 90 px' }],
  owner: { id: '1', display_name: 'Olena Koval', role: 'provider' },
  attachments: [
    {
      id: 'a1',
      filename: 'banner.png',
      content_type: 'image/png',
      size: 2048,
      url: `/api/v1/listings/${LISTING_ID}/attachments/a1`,
    },
  ],
  ...body,
});

test('a customer publishes an ad request with a budget', async ({ page }) => {
  const api = await mockApi(page, 'customer');
  await page.goto('/listings/new');

  await expect(page.getByRole('heading', { level: 1 })).toContainText('what you need.');
  await page.getByLabel('Category').selectOption('sponsored-articles');
  await page.getByLabel('Title').fill('Looking for a home for our story');
  await page.getByLabel('Description').fill('We want a website to publish a sponsored article.');
  await page.getByLabel('Budget (UAH)').fill('4500');
  await page.getByLabel('Specification 1 name').fill('Length');
  await page.getByLabel('Specification 1 value').fill('1,000 words');
  await page.getByLabel(/Attachments/).setInputFiles({
    name: 'brief.png',
    mimeType: 'image/png',
    buffer: PNG,
  });
  await page.getByRole('button', { name: 'Publish request' }).click();

  await expect(page).toHaveURL(`/listings/${LISTING_ID}`);
  expect(api.created).toHaveLength(1);
  expect(api.created[0].path).toMatch(/\/listings\/requests$/);
  expect(api.created[0].body).toMatchObject({
    category: 'sponsored-articles',
    budget_uah: '4500',
    specs: [{ label: 'Length', value: '1,000 words' }],
  });
  expect(api.created[0].body).not.toHaveProperty('delivery_days');
  expect(api.uploads).toEqual(['brief.png']);
});

test('a provider publishes an ad offering with a price and delivery time', async ({ page }) => {
  const api = await mockApi(page, 'provider');
  await page.goto('/listings/new');

  await expect(page.getByRole('heading', { level: 1 })).toContainText('what you offer.');
  await page.getByLabel('Category').selectOption('website-banners');
  await page.getByLabel('Title').fill('Your brand on a design journal');
  await page.getByLabel('Description').fill('A display banner placement on a design journal.');
  await page.getByLabel('Price (UAH)').fill('3500,50');
  await page.getByLabel('Delivery time in days').fill('5');
  await page.getByRole('button', { name: 'Publish offering' }).click();

  await expect(page).toHaveURL(`/listings/${LISTING_ID}`);
  expect(api.created[0].path).toMatch(/\/listings\/offers$/);
  expect(api.created[0].body).toMatchObject({ price_uah: '3500.50', delivery_days: 5, specs: [] });
});

test('validates the form before sending it', async ({ page }) => {
  const api = await mockApi(page, 'provider');
  await page.goto('/listings/new');

  await page.getByRole('button', { name: 'Publish offering' }).click();

  await expect(page.getByText('Choose a category.')).toBeVisible();
  await expect(page.getByText('Use 5 to 120 characters.')).toBeVisible();
  await expect(page.getByText('Use 20 to 5,000 characters.')).toBeVisible();
  await expect(page.getByText('Enter a price in UAH, for example 2500 or 2500.50.')).toBeVisible();
  await expect(page.getByText('Enter the delivery time in days.')).toBeVisible();
  await expect(page.getByLabel('Category')).toBeFocused();
  expect(api.created).toHaveLength(0);
});

test('rejects attachments that are not allowed', async ({ page }) => {
  await mockApi(page, 'customer');
  await page.goto('/listings/new');

  await page.getByLabel(/Attachments/).setInputFiles({
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('hello'),
  });

  await expect(
    page.getByText('notes.txt: attach a JPG, PNG, GIF, WebP, MP4, or PDF file.'),
  ).toBeVisible();
});

test('guests are asked to sign in before creating a listing', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings/new');

  await expect(page.getByText('Sign in to create a listing.')).toBeVisible();
});

test('shows a published listing with its specification and attachments', async ({ page }) => {
  await mockApi(page, null);
  await page.goto(`/listings/${LISTING_ID}`);

  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Your brand on a design journal',
  );
  await expect(page.getByText('3,500.50 UAH')).toBeVisible();
  await expect(page.getByText('Estimated delivery: 5 days')).toBeVisible();
  await expect(page.getByText('728 × 90 px')).toBeVisible();
  await expect(page.getByRole('link', { name: /banner\.png/ })).toBeVisible();
  await expect(page.getByText('olena@example.com')).toHaveCount(0);
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(results.violations).toEqual([]);
});

test('an unknown listing shows a clear message', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings/11111111-1111-4111-8111-111111111111');

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Listing not found.');
});

test('the listing form has no accessibility violations', async ({ page }) => {
  await mockApi(page, 'provider');
  await page.goto('/listings/new');
  await expect(page.getByLabel('Category')).toBeVisible();

  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(results.violations).toEqual([]);
});

test('the marketplace shows published listings and filters them by type', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings');

  await expect(page.getByRole('link', { name: 'A provider offering' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'A customer request' })).toBeVisible();

  await page.getByRole('button', { name: 'Ad requests' }).click();
  await expect(page.getByRole('link', { name: 'A customer request' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'A provider offering' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Ad requests' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
});

test('my listings shows what the signed-in user published', async ({ page }) => {
  await mockApi(page, 'customer');
  await page.goto('/listings/mine');

  await expect(page.getByRole('link', { name: 'My own request' })).toBeVisible();
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(results.violations).toEqual([]);
});

test('guests are asked to sign in to see their listings', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings/mine');

  await expect(page.getByText('Sign in to see your listings.')).toBeVisible();
});
