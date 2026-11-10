import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const LISTING_ID = '0b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a10';
const REQUEST_ID = '1b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a11';
const PNG = Buffer.from('89504e470d0a1a0a0000000000000000', 'hex');

type Role = 'customer' | 'provider';

// Creating listings needs verified contacts (FR-008); verification.spec.ts covers the blocked path.
const accountFor = (role: Role) => ({
  id: '1',
  display_name: 'Olena Koval',
  email: 'olena@example.com',
  phone: '+380671234567',
  role,
  status: 'active',
  email_verified: true,
  phone_verified: true,
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
      const params = new URL(request.url()).searchParams;
      const type = params.get('type');
      const category = params.get('category');
      const term = params.get('q')?.toLowerCase();
      const priceMin = Number(params.get('price_min') ?? 0);
      const priceMax = Number(params.get('price_max') ?? Infinity);
      const deliveryMax = Number(params.get('delivery_max') ?? Infinity);
      const ageMin = Number(params.get('age_min') ?? 0);
      const ageMax = Number(params.get('age_max') ?? Infinity);
      const country = params.get('country')?.toLowerCase();
      const socioeconomic = params.get('socioeconomic')?.toLowerCase();
      const traits = params.getAll('traits').map((trait) => trait.toLowerCase());
      const invalidRange =
        Number(params.get('price_min') ?? 0) > Number(params.get('price_max') ?? Infinity);
      if (invalidRange) {
        return route.fulfill({
          status: 422,
          headers,
          json: {
            detail: [
              {
                loc: ['query', 'price_min'],
                msg: 'The minimum price exceeds the maximum.',
                type: 'invalid_price_range',
              },
            ],
          },
        });
      }
      const items: MockListing[] = [
        listing('offer', {
          id: LISTING_ID,
          title: 'A provider offering',
          description: 'A website banner placement on a design journal.',
          category: 'website-banners',
          price_uah: '1200.00',
          delivery_days: 3,
          audience: {
            age_min: 18,
            age_max: 40,
            country: 'Ukraine',
            socioeconomic: 'Middle income',
            traits: ['gamers'],
          },
        }),
        listing('request', {
          id: REQUEST_ID,
          title: 'A customer request',
          description: 'A sponsored article about a small homeware brand.',
          category: 'sponsored-articles',
          price_uah: '8000.00',
          delivery_days: 20,
          audience: null,
        }),
      ]
        .filter((item) => !type || item.type === type)
        .filter((item) => !category || item.category === category)
        .filter((item) => Number(item.price_uah) >= priceMin && Number(item.price_uah) <= priceMax)
        .filter((item) => (item.delivery_days ?? Infinity) <= deliveryMax)
        .filter(
          (item) =>
            !item.audience ||
            (Number(item.audience.age_max ?? Infinity) >= ageMin &&
              Number(item.audience.age_min ?? 0) <= ageMax),
        )
        .filter(
          (item) =>
            !country ||
            String(item.audience?.country ?? '')
              .toLowerCase()
              .includes(country),
        )
        .filter(
          (item) =>
            !socioeconomic ||
            String(item.audience?.socioeconomic ?? '')
              .toLowerCase()
              .includes(socioeconomic),
        )
        .filter((item) => {
          if (!traits.length) return true;
          const itemTraits = Array.isArray(item.audience?.traits) ? item.audience.traits : [];
          return itemTraits.some((trait) => traits.includes(String(trait).toLowerCase()));
        })
        .filter(
          (item) =>
            !term ||
            `${item.title} ${item.description} ${item.category}`.toLowerCase().includes(term),
        );
      const sort = params.get('sort');
      if (sort === 'price_asc') items.sort((a, b) => Number(a.price_uah) - Number(b.price_uah));
      if (sort === 'price_desc') items.sort((a, b) => Number(b.price_uah) - Number(a.price_uah));
      if (sort === 'oldest') items.reverse();
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

type MockListing = {
  id: string;
  type: 'request' | 'offer';
  category: string;
  title: string;
  description: string;
  price_uah: string;
  delivery_days: number;
  specs: { label: string; value: string }[];
  audience: Record<string, unknown> | null;
  owner: { id: string; display_name: string; role: string };
  status: 'active' | 'paused' | 'expired';
  expires_at: string;
  attachments: {
    id: string;
    filename: string;
    content_type: string;
    size: number;
    url: string;
  }[];
};

const listing = (type: 'request' | 'offer', body: Record<string, unknown>): MockListing => ({
  id: LISTING_ID,
  type,
  category: 'website-banners',
  title: 'Your brand on a design journal',
  description: 'A display banner placement on an independent design journal.',
  price_uah: '3500.50',
  delivery_days: 5,
  specs: [{ label: 'Dimensions', value: '728 × 90 px' }],
  audience: null as null | Record<string, unknown>,
  owner: { id: '1', display_name: 'Olena Koval', role: 'provider' },
  status: 'active',
  expires_at: '2026-12-01T10:00:00Z',
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
  await expect(page.getByRole('link', { name: 'Reveal phone number' })).toHaveAttribute(
    'href',
    `/sign-in?next=${encodeURIComponent(`/listings/${LISTING_ID}`)}`,
  );
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

  await page.getByRole('radio', { name: 'Ad requests' }).check();
  await page.getByRole('button', { name: 'Apply filters' }).click();
  await expect(page.getByRole('link', { name: 'A customer request' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'A provider offering' })).toHaveCount(0);
  await expect(page.getByRole('radio', { name: 'Ad requests' })).toBeChecked();
});

// ADY-011 filter sidebar

test('filters by price and delivery time through the sidebar', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings');

  await expect(page.getByRole('link', { name: 'A provider offering' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'A customer request' })).toBeVisible();

  await page.getByLabel('From', { exact: true }).fill('1000');
  await page.getByLabel('To', { exact: true }).fill('5000');
  await page.getByLabel('Delivery time').selectOption('7');
  await page.getByRole('button', { name: 'Apply filters' }).click();

  await expect(page).toHaveURL(/price_min=1000/);
  await expect(page).toHaveURL(/price_max=5000/);
  await expect(page).toHaveURL(/delivery_max=7/);
  await expect(page.getByRole('link', { name: 'A provider offering' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'A customer request' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '1000–5000 UAH' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Up to 7 days' })).toBeVisible();
});

test('validates an inverted price range before applying', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings');

  await page.getByLabel('From', { exact: true }).fill('5000');
  await page.getByLabel('To', { exact: true }).fill('1000');
  await page.getByRole('button', { name: 'Apply filters' }).click();

  await expect(
    page.getByText('The minimum price cannot be greater than the maximum.'),
  ).toBeVisible();
  await expect(page).not.toHaveURL(/price_min/);
});

test('filters by target audience including traits', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings');

  await page.getByLabel('Age from').fill('20');
  await page.getByLabel('Age to').fill('30');
  await page.getByLabel('Country').fill('Ukraine');
  await page.getByLabel('Socioeconomic background').fill('middle');
  await page.getByLabel('Traits').fill('gamers, students');
  await page.getByRole('button', { name: 'Apply filters' }).click();

  await expect(page).toHaveURL(/age_min=20/);
  await expect(page).toHaveURL(/age_max=30/);
  await expect(page).toHaveURL(/country=Ukraine/);
  await expect(page).toHaveURL(/socioeconomic=middle/);
  await expect(page).toHaveURL(/traits=gamers/);
  await expect(page.getByRole('link', { name: 'A provider offering' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'A customer request' })).toHaveCount(0);
});

test('applies a sort order and survives a reload', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings');

  await page.getByLabel('Sort').selectOption('price_desc');
  await expect(page).toHaveURL(/sort=price_desc/);
  const cards = page.locator('.listing-card h3 a');
  await expect(cards.first()).toHaveText('A customer request');

  await page.reload();
  await expect(page.getByLabel('Sort')).toHaveValue('price_desc');
  await expect(page.locator('.listing-card h3 a').first()).toHaveText('A customer request');
});

test('clears all filters but keeps the search term', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings?q=offering&price_min=1000&price_max=2000&delivery_max=7');

  await expect(page.getByRole('link', { name: 'A provider offering' })).toBeVisible();
  await page.getByRole('button', { name: 'Clear all', exact: true }).first().click();

  await expect(page).toHaveURL('/listings?q=offering');
  await expect(page.getByRole('link', { name: 'A customer request' })).toHaveCount(0);
});

test('the filter sidebar is collapsible on mobile and has no accessibility violations', async ({
  page,
}) => {
  await mockApi(page, null);
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto('/listings');

  const toggle = page.getByRole('button', { name: /^Filters/ });
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('heading', { name: /^Filters/ })).toBeHidden();
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(page.getByRole('heading', { name: /^Filters/ })).toBeVisible();

  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(results.violations).toEqual([]);

  await page.getByRole('button', { name: 'Close filters' }).click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
});

test('my listings shows what the signed-in user published', async ({ page }) => {
  await mockApi(page, 'customer');
  await page.goto('/listings/mine');

  await expect(page.getByRole('link', { name: 'My own request', exact: true })).toBeVisible();
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(results.violations).toEqual([]);
});

test('guests are asked to sign in to see their listings', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings/mine');

  await expect(page.getByText('Sign in to see your listings.')).toBeVisible();
});

// ADY-007 search and browsing

test('a guest searches public listings from the marketplace URL', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings?q=banner');

  await expect(page.getByRole('link', { name: 'A provider offering' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'A customer request' })).toHaveCount(0);
  await expect(page.getByText('1 listing for “banner”')).toBeVisible();

  const search = page.getByLabel('Search listings');
  await search.fill('article');
  await expect(page).toHaveURL('/listings?q=article');
  await expect(page.getByRole('link', { name: 'A customer request' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'A provider offering' })).toHaveCount(0);

  await page.getByRole('button', { name: 'Clear search field' }).click();
  await expect(page).toHaveURL('/listings');
  await expect(page.getByRole('link', { name: 'A provider offering' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'A customer request' })).toBeVisible();
});

test('an empty search has a clear recovery action', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings?q=nothing-matches');

  await expect(
    page.getByRole('heading', { name: 'No listings match these filters.' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Clear search field' }).click();
  await expect(page).toHaveURL('/listings');
  await expect(page.getByRole('link', { name: 'A provider offering' })).toBeVisible();
});

test('category navigation filters the public feed and can be cleared', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/listings?category=website-banners');

  await expect(page.getByRole('button', { name: 'Website banners' })).toBeVisible();
  await expect(page.getByLabel('Category')).toHaveValue('website-banners');
  await expect(page.getByRole('link', { name: 'A provider offering' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'A customer request' })).toHaveCount(0);

  await page.getByRole('button', { name: 'Website banners' }).click();
  await expect(page).toHaveURL('/listings');
  await expect(page.getByRole('link', { name: 'A customer request' })).toBeVisible();
});

test('360px live listings use one column and open details', async ({ page }) => {
  await mockApi(page, null);
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto('/listings');

  const cards = page.locator('.listing-card');
  await expect(cards).toHaveCount(2);
  const first = await cards.nth(0).boundingBox();
  const second = await cards.nth(1).boundingBox();
  expect(first?.x).toBe(second?.x);
  expect(second!.y).toBeGreaterThan(first!.y + first!.height);

  await cards.nth(0).getByRole('link').first().click();
  await expect(page).toHaveURL(`/listings/${LISTING_ID}`);
  await expect(page.getByRole('heading', { name: 'Placement specification' })).toBeVisible();
});

test('the home page highlights the latest public listings', async ({ page }) => {
  await mockApi(page, null);
  await page.goto('/');

  await expect(page.getByRole('link', { name: 'A provider offering' })).toBeVisible();
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(results.violations).toEqual([]);
});
