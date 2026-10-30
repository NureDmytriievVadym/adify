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

async function fillForm(page: Page, role: 'Customer' | 'Provider', phone = '+380 67 123 45 67') {
  await page.getByRole('radio', { name: new RegExp(role) }).check();
  await page.getByLabel('Display name').fill('Olena Koval');
  await page.getByLabel('Email address').fill('olena@example.com');
  await page.getByLabel('Phone number').fill(phone);
  await page.getByLabel('Password').fill('secret123');
}

for (const role of ['Customer', 'Provider'] as const) {
  test(`registers a ${role.toLowerCase()} account`, async ({ page }) => {
    const requests = await mockRegistration(page, (body) => ({
      status: 201,
      json: { ...body, id: '1', email_verified: false, phone_verified: false, status: 'active' },
    }));
    await page.goto('/');
    await page.getByRole('link', { name: 'Get started' }).click();
    await expect(page).toHaveURL('/register');

    await fillForm(page, role);
    await page.getByRole('button', { name: 'Create account' }).click();

    await expect(page.getByRole('heading', { name: 'Welcome, Olena Koval.' })).toBeVisible();
    await expect(page.getByRole('status')).toContainText(`Your ${role.toLowerCase()} account`);
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

test('explains invalid input before sending it', async ({ page }) => {
  const requests = await mockRegistration(page, () => ({ status: 500, json: {} }));
  await page.goto('/register');

  await page.getByLabel('Phone number').fill('+48123456789');
  await page.getByLabel('Password').fill('password');
  await page.getByRole('button', { name: 'Create account' }).click();

  await expect(page.getByText('Choose exactly one role: customer or provider.')).toBeVisible();
  await expect(page.getByLabel('Phone number')).toHaveAccessibleDescription(
    /Enter a Ukrainian phone number in the format \+380XXXXXXXXX\./,
  );
  await expect(page.getByLabel('Password')).toHaveAccessibleDescription(
    /Use at least 8 characters, including at least one letter and one digit\./,
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
