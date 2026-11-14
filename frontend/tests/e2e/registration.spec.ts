import { expect, test, type Page, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const cors = {
  'access-control-allow-origin': '*',
  'access-control-allow-headers': '*',
  'access-control-allow-methods': 'POST',
};

// The preview runs without the API, so the registration endpoint is answered here.
async function mockRegistration(page: Page, respond: (body: Record<string, string>) => object) {
  const requests: Record<string, string>[] = [];
  await page.route('**/api/v1/accounts', async (route: Route) => {
    if (route.request().method() === 'OPTIONS')
      return route.fulfill({ status: 204, headers: cors });
    const body = route.request().postDataJSON() as Record<string, string>;
    requests.push(body);
    const { status, json } = respond(body) as { status: number; json: object };
    return route.fulfill({ status, headers: cors, json });
  });
  return requests;
}

// Registration signs the user in, so the sign-in endpoint is answered too. The refresh
// call that restores a session on every page load always fails: nobody is signed in yet.
async function mockSignIn(page: Page, role: string, succeeds = true) {
  const requests: Record<string, string>[] = [];
  await page.route('**/api/v1/auth/*', async (route: Route) => {
    const origin = (await route.request().headerValue('origin')) ?? '*';
    const headers = {
      'access-control-allow-origin': origin,
      'access-control-allow-credentials': 'true',
      'access-control-allow-headers': 'content-type',
      'access-control-allow-methods': 'POST',
    };
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    if (!route.request().url().endsWith('/sign-in') || !succeeds)
      return route.fulfill({ status: 401, headers, json: { detail: [] } });
    requests.push(route.request().postDataJSON() as Record<string, string>);
    return route.fulfill({
      status: 200,
      headers,
      json: {
        access_token: 'token',
        token_type: 'bearer',
        expires_in: 900,
        account: {
          id: '1',
          display_name: 'Olena Koval',
          email: 'olena@example.com',
          phone: '+380671234567',
          role,
          status: 'active',
          email_verified: false,
          phone_verified: false,
        },
      },
    });
  });
  return requests;
}

async function fillForm(page: Page, role: 'Customer' | 'Provider', phone = '671234567') {
  await page.getByRole('radio', { name: new RegExp(role) }).check();
  await page.getByLabel('Display name').fill('Olena Koval');
  await page.getByLabel('Email address').fill('olena@example.com');
  await page.getByLabel('Phone number').fill(phone);
  await page.getByLabel('Password').fill('secret123');
}

test('formats a local phone number using the Ukrainian template', async ({ page }) => {
  await page.goto('/register');

  const phone = page.getByLabel('Phone number');
  await expect(phone).toHaveValue('+38 (0__)-___-__-__');
  await phone.press('Control+A');
  await phone.press('Backspace');
  await expect(phone).toHaveValue('+38 (0__)-___-__-__');

  await phone.pressSequentially('671234567');

  await expect(phone).toHaveValue('+38 (067)-123-45-67');
});

for (const role of ['Customer', 'Provider'] as const) {
  test(`registers a ${role.toLowerCase()} account and signs it in`, async ({ page }) => {
    const requests = await mockRegistration(page, (body) => ({
      status: 201,
      json: { ...body, id: '1', email_verified: false, phone_verified: false, status: 'active' },
    }));
    const signIns = await mockSignIn(page, role.toLowerCase());
    await page.goto('/');
    await page.getByRole('link', { name: 'Get started' }).click();
    await expect(page).toHaveURL('/register');

    await fillForm(page, role);
    await page.getByRole('button', { name: 'Create account' }).click();

    await expect(page).toHaveURL('/account');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Olena Koval.');
    await expect(page.getByRole('link', { name: 'My account' })).toBeVisible();
    expect(signIns).toEqual([{ email: 'olena@example.com', password: 'secret123' }]);
    expect(requests).toEqual([
      {
        display_name: 'Olena Koval',
        email: 'olena@example.com',
        phone: '+380671234567',
        role: role.toLowerCase(),
        password: 'secret123',
      },
    ]);
  });
}

test('keeps the new account and offers sign-in when the automatic sign-in fails', async ({
  page,
}) => {
  await mockRegistration(page, (body) => ({
    status: 201,
    json: { ...body, id: '1', email_verified: false, phone_verified: false, status: 'active' },
  }));
  await mockSignIn(page, 'customer', false);
  await page.goto('/register');

  await fillForm(page, 'Customer');
  await page.getByRole('button', { name: 'Create account' }).click();

  await expect(page).toHaveURL('/register');
  await expect(page.getByRole('heading', { name: 'Welcome, Olena Koval.' })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Your customer account');
  await expect(page.getByRole('link', { name: 'Sign in' }).last()).toBeVisible();
});

test('explains invalid input before sending it', async ({ page }) => {
  const requests = await mockRegistration(page, () => ({ status: 500, json: {} }));
  await page.goto('/register');

  await page.getByLabel('Phone number').fill('+48123456789');
  await page.getByLabel('Password').fill('password');
  await page.getByRole('button', { name: 'Create account' }).click();

  await expect(page.getByText('Choose exactly one role: customer or provider')).toBeVisible();
  await expect(page.getByLabel('Phone number')).toHaveAccessibleDescription(
    /Enter the remaining 9 digits\./,
  );
  await expect(page.getByLabel('Password')).toHaveAccessibleDescription(
    /Use at least 8 characters, including at least one letter and one digit/,
  );
  await expect(page.getByRole('radio', { name: /Customer/ })).toBeFocused();
  expect(requests).toEqual([]);
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);
});

test('shows when contacts belong to a banned account', async ({ page }) => {
  await mockRegistration(page, () => ({
    status: 403,
    json: {
      detail: [
        {
          loc: ['body', 'email'],
          msg: 'This email address belongs to a banned account.',
          type: 'email_banned',
        },
      ],
    },
  }));
  await page.goto('/register');

  await fillForm(page, 'Provider');
  await page.getByRole('button', { name: 'Create account' }).click();

  await expect(page.getByLabel('Email address')).toHaveAccessibleDescription(
    /This email address belongs to a banned account\./,
  );
  await expect(page.getByLabel('Email address')).toBeFocused();
});
