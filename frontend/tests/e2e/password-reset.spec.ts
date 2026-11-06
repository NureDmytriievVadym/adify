import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const INVALID_LINK = 'This link has expired or has already been used. Request a new one.';

// The preview runs without the API; one link works once, like the real endpoint.
async function mockReset(page: Page) {
  const calls: { path: string; body: Record<string, string> }[] = [];
  const used = new Set<string>();
  await page.route('**/api/v1/auth/password-reset**', async (route) => {
    const origin = (await route.request().headerValue('origin')) ?? '*';
    const headers = {
      'access-control-allow-origin': origin,
      'access-control-allow-headers': 'content-type',
      'access-control-allow-methods': 'POST',
    };
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    const path = new URL(route.request().url()).pathname;
    const body = route.request().postDataJSON() as Record<string, string>;
    calls.push({ path, body });
    if (path.endsWith('/password-reset')) return route.fulfill({ status: 202, headers });
    if (body.token !== 'good-token' || used.has(body.token)) {
      return route.fulfill({
        status: 400,
        headers,
        json: { detail: [{ loc: ['body'], msg: INVALID_LINK, type: 'reset_link_invalid' }] },
      });
    }
    used.add(body.token);
    return route.fulfill({ status: 204, headers });
  });
  return calls;
}

test('requests a reset link from the sign-in page', async ({ page }) => {
  const calls = await mockReset(page);
  await page.goto('/sign-in');
  await page.getByRole('link', { name: 'Forgot password?' }).click();
  await expect(page).toHaveURL('/forgot-password');

  await page.getByLabel('Email address').fill('olena@example.com');
  await page.getByRole('button', { name: 'Send reset link' }).click();

  await expect(page.getByRole('heading', { name: 'Check your email.' })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('olena@example.com');
  expect(calls).toEqual([
    { path: '/api/v1/auth/password-reset', body: { email: 'olena@example.com' } },
  ]);
});

test('rejects an invalid email before calling the API', async ({ page }) => {
  const calls = await mockReset(page);
  await page.goto('/forgot-password');
  await page.getByLabel('Email address').fill('not-an-email');
  await page.getByRole('button', { name: 'Send reset link' }).click();

  await expect(page.getByRole('alert')).toHaveText('Enter a valid email address.');
  expect(calls).toEqual([]);
});

test('sets a new password once; the same link then fails', async ({ page }) => {
  await mockReset(page);
  await page.goto('/reset-password?token=good-token');

  await page.getByLabel('New password').fill('short');
  await page.getByRole('button', { name: 'Set new password' }).click();
  await expect(page.getByText('Use at least 8 characters, including')).toBeVisible();
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);

  await page.getByLabel('New password').fill('fresh456pass');
  await page.getByRole('button', { name: 'Set new password' }).click();
  await expect(page.getByRole('heading', { name: 'Password changed.' })).toBeVisible();

  await page.goto('/reset-password?token=good-token');
  await page.getByLabel('New password').fill('fresh456pass');
  await page.getByRole('button', { name: 'Set new password' }).click();
  await expect(page.getByRole('alert')).toContainText(INVALID_LINK);
  await expect(page.getByRole('link', { name: 'Request a new link' })).toBeVisible();
});

test('explains a link without a token', async ({ page }) => {
  await page.goto('/reset-password');
  await expect(page.getByRole('heading', { name: 'This link is incomplete.' })).toBeVisible();
});
