import { expect, test, type Page } from '@playwright/test';

const account = {
  id: '1',
  display_name: 'Olena Koval',
  email: 'olena@example.com',
  phone: '+380671234567',
  role: 'provider',
  status: 'active',
  email_verified: false,
  phone_verified: false,
};
const tokens = { access_token: 'token', token_type: 'bearer', expires_in: 900, account };

// The preview runs without the API; credentialed CORS needs the exact origin echoed back.
async function mockAuth(page: Page, signedIn: { value: boolean }) {
  await page.route('**/api/v1/auth/*', async (route) => {
    const origin = (await route.request().headerValue('origin')) ?? '*';
    const headers = {
      'access-control-allow-origin': origin,
      'access-control-allow-credentials': 'true',
      'access-control-allow-headers': 'content-type',
      'access-control-allow-methods': 'POST',
    };
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/sign-in')) {
      const { password } = route.request().postDataJSON() as { password: string };
      if (password !== 'secret123') {
        return route.fulfill({
          status: 401,
          headers,
          json: {
            detail: [
              {
                loc: ['body'],
                msg: 'Incorrect email address or password.',
                type: 'invalid_credentials',
              },
            ],
          },
        });
      }
      signedIn.value = true;
    }
    if (path.endsWith('/sign-out')) {
      signedIn.value = false;
      return route.fulfill({ status: 204, headers });
    }
    if (!signedIn.value) {
      return route.fulfill({ status: 401, headers, json: { detail: [] } });
    }
    return route.fulfill({ status: 200, headers, json: tokens });
  });
}

test('signs in, keeps the session across reloads and signs out', async ({ page }) => {
  const signedIn = { value: false };
  await mockAuth(page, signedIn);
  await page.goto('/');
  await page.getByRole('link', { name: 'Sign in' }).click();
  await expect(page).toHaveURL('/sign-in');

  await page.getByLabel('Email address').fill('olena@example.com');
  await page.getByLabel('Password').fill('secret123');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page).toHaveURL('/account');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Olena Koval.');
  await expect(page.getByText('olena@example.com · Not verified')).toBeVisible();
  await expect(page.getByRole('link', { name: 'My account' })).toBeVisible();

  await page.reload();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Olena Koval.');

  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL('/sign-in');
  await expect(page.getByRole('link', { name: 'Get started' })).toBeVisible();
  expect(signedIn.value).toBe(false);
});

test('shows a clear error for invalid credentials', async ({ page }) => {
  await mockAuth(page, { value: false });
  await page.goto('/sign-in');

  await page.getByLabel('Email address').fill('olena@example.com');
  await page.getByLabel('Password').fill('wrong-password1');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page.getByRole('alert')).toHaveText('Incorrect email address or password.');
  await expect(page.getByRole('alert')).toBeFocused();
  await expect(page).toHaveURL('/sign-in');
});

test('asks for both fields before sending them', async ({ page }) => {
  await mockAuth(page, { value: false });
  await page.goto('/sign-in');

  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page.getByRole('alert')).toHaveText('Enter your email address and password.');
});

test('the account page asks guests to sign in', async ({ page }) => {
  await mockAuth(page, { value: false });
  await page.goto('/account');

  await expect(page.getByText('Sign in to see your account.')).toBeVisible();
  await page.getByRole('main').getByRole('link', { name: 'Sign in' }).click();
  await expect(page).toHaveURL('/sign-in');
});
