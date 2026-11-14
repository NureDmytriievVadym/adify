import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const LISTING_ID = '0b6f1d0e-5c3a-4a53-9f37-1d2f5b8c9a10';
const EMAIL_CODE = '742419';
const SMS_CODE = '552194';

const offer = {
  id: LISTING_ID,
  type: 'offer',
  category: 'website-banners',
  title: 'A provider offering',
  description: 'A website banner placement on a design journal.',
  price_uah: '1200.00',
  delivery_days: 3,
  specs: [],
  audience: null,
  owner: { id: '2', display_name: 'Digital Daily', role: 'provider' },
  attachments: [],
  created_at: '2026-10-30T12:00:00Z',
  status: 'active',
  expiry_date: '2026-11-29',
  expires_at: '2026-11-29T21:59:00Z',
};

const chat = {
  id: '9c1f1d0e-5c3a-4a53-9f37-1d2f5b8c9a99',
  listing: {
    id: LISTING_ID,
    title: 'Your brand on a design journal',
    type: 'offer',
    status: 'active',
  },
  counterpart: { id: '2', display_name: 'Digital Daily', role: 'provider' },
  created_at: '2026-11-06T10:00:00Z',
};

// The preview runs without the API; this mock keeps the account's verification state.
async function mockApi(page: Page) {
  const account = {
    id: '1',
    display_name: 'Olena Koval',
    email: 'olena@example.com',
    phone: '+380671234567',
    role: 'customer',
    status: 'active',
    email_verified: false,
    phone_verified: false,
  };
  const sent: string[] = [];
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
    const error = (status: number, type: string, msg: string) =>
      route.fulfill({ status, headers, json: { detail: [{ loc: ['body'], msg, type }] } });
    const verified = account.email_verified && account.phone_verified;

    if (path.endsWith('/auth/refresh')) {
      return route.fulfill({
        status: 200,
        headers,
        json: { access_token: 'token', token_type: 'bearer', expires_in: 900, account },
      });
    }
    if (path.endsWith('/accounts/me/verification')) {
      const channel = (name: 'email' | 'phone') => ({
        verified: account[`${name}_verified`],
        destination: name === 'email' ? account.email : account.phone,
        // The registration email is already out; no SMS until one is requested.
        code_sent: name === 'email' ? !account.email_verified : sent.includes('phone'),
        resend_in: 0,
      });
      return route.fulfill({
        status: 200,
        headers,
        json: { email: channel('email'), phone: channel('phone') },
      });
    }
    const verification = path.match(/verification\/(email|phone)\/(code|confirm)$/);
    if (verification) {
      const [, channel, action] = verification;
      if (action === 'code') {
        sent.push(channel);
        const destination = channel === 'email' ? account.email : account.phone;
        return route.fulfill({
          status: 202,
          headers,
          json: { channel, destination, expires_in: 900, resend_in: 60 },
        });
      }
      const { code } = request.postDataJSON() as { code: string };
      if (code !== (channel === 'email' ? EMAIL_CODE : SMS_CODE)) {
        return error(400, 'code_incorrect', 'This code is incorrect. 4 attempts left.');
      }
      if (channel === 'email') account.email_verified = true;
      else account.phone_verified = true;
      return route.fulfill({ status: 200, headers, json: account });
    }
    if (path.endsWith(`/listings/${LISTING_ID}`)) {
      return route.fulfill({ status: 200, headers, json: offer });
    }
    if (path.endsWith(`/chats/${chat.id}`)) {
      return route.fulfill({ status: 200, headers, json: chat });
    }
    if (path.endsWith('/phone-reveal') || path.endsWith('/chats')) {
      if (!verified) {
        return error(
          403,
          'verification_required',
          'Verify your email address and phone number to continue.',
        );
      }
      if (path.endsWith('/chats')) {
        return route.fulfill({ status: 201, headers, json: chat });
      }
      return route.fulfill({ status: 200, headers, json: { phone: '+380501110101' } });
    }
    return route.fulfill({ status: 404, headers, json: { detail: [] } });
  });
  return { account, sent };
}

async function verifyBoth(page: Page) {
  await page.goto('/account#verification');
  await page.getByLabel('Enter the six-digit code we emailed to you').fill(EMAIL_CODE);
  await page.getByRole('button', { name: 'Verify email address' }).click();
  await expect(page.getByText('Your email address is verified.')).toBeVisible();
  await page.getByRole('button', { name: 'Text me a code' }).click();
  await expect(page.getByText('We texted a code to +380671234567.')).toBeVisible();
  await page.getByLabel('Enter the six-digit code we texted to you').fill(SMS_CODE);
  await page.getByRole('button', { name: 'Verify phone number' }).click();
  await expect(page.getByText('Your phone number is verified.')).toBeVisible();
}

test('blocks contact actions and listing creation until both contacts are verified', async ({
  page,
}) => {
  await mockApi(page);
  await page.goto(`/listings/${LISTING_ID}`);

  await page.getByRole('button', { name: 'Reveal phone number' }).click();
  await expect(page.getByRole('alert')).toContainText(
    'Verify your email address and phone number to continue.',
  );
  await page.getByRole('button', { name: 'Start chat' }).click();
  await expect(page.getByRole('alert')).toContainText('Verify your email address and phone number');
  await expect(page.getByRole('link', { name: 'Verify now' })).toHaveAttribute(
    'href',
    '/account#verification',
  );

  await page.goto('/listings/new');
  await expect(page.getByRole('heading', { name: 'Verify your account first' })).toBeVisible();
  await expect(page.getByLabel('Title')).toHaveCount(0);
});

test('a wrong code shows an error and the right codes verify both contacts', async ({ page }) => {
  const { sent } = await mockApi(page);
  await page.goto('/account#verification');
  // Only a channel with a code already sent offers a code field.
  await expect(page.getByLabel('Enter the six-digit code we texted to you')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Text me a code' })).toBeVisible();

  await page.getByLabel('Enter the six-digit code we emailed to you').fill('111111');
  await page.getByRole('button', { name: 'Verify email address' }).click();
  await expect(page.getByRole('alert')).toHaveText('This code is incorrect. 4 attempts left.');

  await page.getByLabel('Enter the six-digit code we emailed to you').fill('12');
  await page.getByRole('button', { name: 'Verify email address' }).click();
  await expect(page.getByRole('alert')).toHaveText('Enter the six-digit code.');

  await verifyBoth(page);
  expect(sent).toEqual(['phone']);
  await expect(page.getByText('Verified', { exact: true })).toHaveCount(2);
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);
});

test('the link in the verification email fills in the code', async ({ page }) => {
  await mockApi(page);
  await page.goto(`/account?email_code=${EMAIL_CODE}#verification`);

  await expect(page.getByLabel('Enter the six-digit code we emailed to you')).toHaveValue(
    EMAIL_CODE,
  );
});

test('after verification the same actions are allowed', async ({ page }) => {
  await mockApi(page);
  await verifyBoth(page);

  await page.goto(`/listings/${LISTING_ID}`);
  await page.getByRole('button', { name: 'Reveal phone number' }).click();
  await expect(page.getByRole('link', { name: '+380501110101' })).toBeVisible();
  await page.getByRole('button', { name: 'Start chat' }).click();
  await expect(page).toHaveURL(`/chats/${chat.id}`);
  await expect(page.getByRole('heading', { name: 'Chat with Digital Daily' })).toBeVisible();

  await page.goto('/listings/new');
  await expect(page.getByLabel('Title')).toBeVisible();
});
