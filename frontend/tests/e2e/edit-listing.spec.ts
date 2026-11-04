import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// FR-017: the owner edits a listing; an active order locks only its category.

const LISTING_ID = '0b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a10';
const PNG = Buffer.from('89504e470d0a1a0a0000000000000000', 'hex');

type Role = 'customer' | 'provider';

interface MockOptions {
  role?: Role | null;
  /** `locked_fields` reported by the owner view when the form opens. */
  locked?: string[];
  /** An order becomes active after the form opens, so a category change gets a 409. */
  lockOnSave?: boolean;
  owner?: boolean;
}

const account = (role: Role) => ({
  id: '1',
  display_name: 'Digital Daily',
  email: 'digital@example.com',
  phone: '+380671234567',
  role,
  status: 'active',
  email_verified: true,
  phone_verified: true,
});

async function mockApi(page: Page, options: MockOptions = {}) {
  const { role = 'provider', locked = [], lockOnSave = false, owner = true } = options;
  const stored: Record<string, unknown> = {
    id: LISTING_ID,
    type: 'offer',
    category: 'website-banners',
    title: 'Your brand on a design journal',
    description: 'A display banner placement on an independent design journal.',
    price_uah: '3500.00',
    delivery_days: 5,
    specs: [{ label: 'Dimensions', value: '728 × 90 px' }],
    audience: null,
    owner: { id: owner ? '1' : '2', display_name: 'Digital Daily', role: 'provider' },
    attachments: [
      {
        id: 'a1',
        filename: 'banner.png',
        content_type: 'image/png',
        size: 2048,
        url: `/api/v1/listings/${LISTING_ID}/attachments/a1`,
      },
    ],
    created_at: '2026-11-01T10:00:00Z',
    status: 'active',
    expires_at: '2026-12-01T10:00:00Z',
  };
  const api = {
    patches: [] as Record<string, unknown>[],
    deleted: [] as string[],
    uploads: [] as string[],
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
    const method = request.method();
    if (method === 'OPTIONS') return route.fulfill({ status: 204, headers });
    const path = new URL(request.url()).pathname;
    const error = (status: number, type: string, msg: string, loc = ['body']) =>
      route.fulfill({ status, headers, json: { detail: [{ loc, msg, type }] } });

    if (path.endsWith('/auth/refresh')) {
      if (!role) return route.fulfill({ status: 401, headers, json: { detail: [] } });
      return route.fulfill({
        status: 200,
        headers,
        json: {
          access_token: 'token',
          token_type: 'bearer',
          expires_in: 900,
          account: account(role),
        },
      });
    }
    if (path.includes('/attachments/') && method === 'GET') {
      return route.fulfill({ status: 200, headers, contentType: 'image/png', body: PNG });
    }
    if (path.includes('/attachments/') && method === 'DELETE') {
      api.deleted.push(path.split('/').pop() ?? '');
      return route.fulfill({ status: 204, headers });
    }
    if (path.endsWith('/attachments') && method === 'POST') {
      api.uploads.push(new URL(request.url()).searchParams.get('filename') ?? '');
      return route.fulfill({ status: 201, headers, json: {} });
    }
    if (path.endsWith(`/listings/mine/${LISTING_ID}`)) {
      if (!owner) return error(403, 'not_listing_owner', 'Only the owner can change this listing.');
      return route.fulfill({ status: 200, headers, json: { ...stored, locked_fields: locked } });
    }
    if (path.endsWith('/listings/mine')) {
      return route.fulfill({ status: 200, headers, json: { items: [stored], total: 1 } });
    }
    if (path.endsWith(`/listings/${LISTING_ID}`) && method === 'PATCH') {
      const body = request.postDataJSON() as Record<string, unknown>;
      api.patches.push(body);
      const locks = lockOnSave || locked.includes('category');
      if (locks && body.category && body.category !== stored.category) {
        return error(
          409,
          'category_locked',
          'The category cannot be changed while this listing has an active order.',
          ['body', 'category'],
        );
      }
      const { price_uah: price, ...rest } = body;
      Object.assign(stored, rest, price ? { price_uah: Number(price).toFixed(2) } : {});
      return route.fulfill({
        status: 200,
        headers,
        json: { ...stored, locked_fields: locks ? ['category'] : [] },
      });
    }
    if (path.endsWith(`/listings/${LISTING_ID}`)) {
      return route.fulfill({ status: 200, headers, json: stored });
    }
    return route.fulfill({ status: 404, headers, json: { detail: [] } });
  });
  return api;
}

const editPage = `/listings/${LISTING_ID}/edit`;

test('the owner edits the title and price and sees them on the listing page', async ({ page }) => {
  const api = await mockApi(page);
  await page.goto(editPage);

  await expect(page.getByLabel('Title')).toHaveValue('Your brand on a design journal');
  await expect(page.getByLabel('Price (UAH)')).toHaveValue('3500');
  await expect(page.getByLabel('Category')).toBeEnabled();
  await page.getByLabel('Title').fill('Your brand, front and center');
  await page.getByLabel('Price (UAH)').fill('4200');
  await page.getByRole('button', { name: 'Save changes' }).click();

  await expect(page).toHaveURL(`/listings/${LISTING_ID}`);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Your brand, front and center');
  await expect(page.getByText('4,200 UAH')).toBeVisible();
  await expect(page.getByText('Your changes are saved.')).toBeVisible();
  expect(api.patches).toHaveLength(1);
  expect(api.patches[0]).toMatchObject({
    category: 'website-banners',
    title: 'Your brand, front and center',
    price_uah: '4200',
    delivery_days: 5,
    audience: null,
  });
  expect(api.patches[0]).not.toHaveProperty('budget_uah');
});

test('an active order locks the category while other details stay editable', async ({ page }) => {
  const api = await mockApi(page, { locked: ['category'] });
  await page.goto(editPage);

  const category = page.getByLabel('Category');
  await expect(category).toBeDisabled();
  await expect(category).toHaveValue('website-banners');
  await expect(page.getByText(/has an active order, so it stays in Website banners/)).toBeVisible();
  const description = 'A banner placement on a design journal, now with a newsletter mention.';
  await page.getByLabel('Description').fill(description);
  await page.getByRole('button', { name: 'Save changes' }).click();

  await expect(page).toHaveURL(`/listings/${LISTING_ID}`);
  await expect(page.getByText(description)).toBeVisible();
  expect(api.patches[0]).toMatchObject({ category: 'website-banners', description });
});

test('a category locked after the form opened is blocked with a message', async ({ page }) => {
  const api = await mockApi(page, { lockOnSave: true });
  await page.goto(editPage);

  await page.getByLabel('Category').selectOption('social-media-posts');
  await page.getByLabel('Title').fill('A title that stays in the form');
  await page.getByRole('button', { name: 'Save changes' }).click();

  const alert = page.locator('.form-alert');
  await expect(alert).toHaveText(
    'The category cannot be changed while this listing has an active order.',
  );
  await expect(alert).toBeFocused();
  await expect(page.getByLabel('Category')).toBeDisabled();
  await expect(page.getByLabel('Category')).toHaveValue('website-banners');
  await expect(page.getByLabel('Title')).toHaveValue('A title that stays in the form');
  await expect(page).toHaveURL(editPage);

  // The stored category is sent back unchanged, so the rest of the edit now saves.
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page).toHaveURL(`/listings/${LISTING_ID}`);
  expect(api.patches).toHaveLength(2);
  expect(api.patches[1]).toMatchObject({ category: 'website-banners' });
});

test('validates edits before saving them', async ({ page }) => {
  const api = await mockApi(page);
  await page.goto(editPage);

  await page.getByLabel('Title').fill('Hi');
  await page.getByLabel('Delivery time in days').fill('');
  await page.getByRole('button', { name: 'Save changes' }).click();

  await expect(page.getByText('Use 5 to 120 characters.')).toBeVisible();
  await expect(page.getByText('Enter the delivery time in days.')).toBeVisible();
  await expect(page.getByLabel('Title')).toBeFocused();
  expect(api.patches).toHaveLength(0);
});

test('attachments can be removed and added while editing', async ({ page }) => {
  const api = await mockApi(page);
  await page.goto(editPage);

  await page.getByRole('button', { name: 'Remove banner.png' }).click();
  await expect(page.getByText('banner.png · 2 KB · will be removed')).toBeVisible();
  await page.getByLabel('Add files').setInputFiles({
    name: 'brief.png',
    mimeType: 'image/png',
    buffer: PNG,
  });
  await page.getByRole('button', { name: 'Save changes' }).click();

  await expect(page).toHaveURL(`/listings/${LISTING_ID}`);
  expect(api.deleted).toEqual(['a1']);
  expect(api.uploads).toEqual(['brief.png']);
});

test('the owner finds the edit action on the listing and in my listings', async ({ page }) => {
  await mockApi(page);
  await page.goto(`/listings/${LISTING_ID}`);

  await expect(page.getByRole('link', { name: 'Edit listing' })).toHaveAttribute('href', editPage);
  await expect(page.getByRole('link', { name: 'Reveal phone number' })).toHaveCount(0);

  await page.goto('/listings/mine');
  await expect(
    page.getByRole('link', { name: 'Edit Your brand on a design journal' }),
  ).toHaveAttribute('href', editPage);
});

test('other users cannot edit the listing', async ({ page }) => {
  await mockApi(page, { owner: false });
  await page.goto(`/listings/${LISTING_ID}`);
  await expect(page.getByRole('link', { name: 'Edit listing' })).toHaveCount(0);

  await page.goto(editPage);
  await expect(page.getByRole('heading', { name: 'This is not your listing' })).toBeVisible();
  await expect(page.getByLabel('Title')).toHaveCount(0);
});

test('guests are asked to sign in to edit a listing', async ({ page }) => {
  await mockApi(page, { role: null });
  await page.goto(editPage);

  await expect(page.getByText('Sign in to edit your listing.')).toBeVisible();
});

test('sample listings cannot be edited', async ({ page }) => {
  await mockApi(page);
  const response = await page.goto('/listings/digital-daily/edit');

  expect(response?.status()).toBe(404);
});

test('the edit form has no accessibility violations', async ({ page }) => {
  await mockApi(page, { locked: ['category'] });
  for (const width of [360, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(editPage);
    await expect(page.getByLabel('Category')).toBeDisabled();

    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
    expect(results.violations).toEqual([]);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(overflow).toBe(false);
  }
});
