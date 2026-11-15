import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const ORDER_ID = '8e3f3f20-7e5c-4c75-9b59-3f4d7dae1c28';
const STAGE_ID = 'b7c4f1a2-3d5e-4f60-8a1b-2c3d4e5f6a7b';
const EVIDENCE_ID = 'd8e9f0a1-2b3c-4d5e-8f90-1a2b3c4d5e6f';
const FILE_ID = 'f1a2b3c4-5d6e-4f70-8a9b-0c1d2e3f4a5b';

const customer = { id: '1', display_name: 'Olena Koval', role: 'customer' as const };
const provider = { id: '2', display_name: 'Digital Daily', role: 'provider' as const };

type Stage = {
  id: string;
  title: string;
  deadline: string | null;
  completed_at: string | null;
  completed_by: typeof customer | typeof provider | null;
};

// The preview runs without the API; this mock applies the ADY-022 stage and evidence rules.
async function mockApi(page: Page, viewer: 'customer' | 'provider') {
  const me = viewer === 'customer' ? customer : provider;
  let stages: Stage[] = [];
  const evidence: object[] = [];

  const order = () => ({
    id: ORDER_ID,
    status: 'in_progress',
    details: 'Homepage banner for two weeks.',
    price_uah: '3000.00',
    deadline: null,
    stages,
    evidence,
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
    work_started_at: '2026-11-10T10:07:00Z',
    work_start_blocker: null,
    canceled_at: null,
    cancel_reason: null,
    review_started_at: null,
    completed_at: null,
    change_requests: [],
  });

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
    if (path.endsWith(`/orders/${ORDER_ID}/stages`)) {
      const body = request.postDataJSON() as { title: string; deadline: string | null };
      stages = [
        ...stages,
        {
          id: STAGE_ID,
          title: body.title,
          deadline: body.deadline,
          completed_at: null,
          completed_by: null,
        },
      ];
      return route.fulfill({ status: 201, headers, json: order() });
    }
    if (path.endsWith(`/orders/${ORDER_ID}/stages/${STAGE_ID}/complete`)) {
      stages = stages.map((stage) =>
        stage.id === STAGE_ID
          ? { ...stage, completed_at: '2026-11-14T12:00:00Z', completed_by: me }
          : stage,
      );
      return route.fulfill({ status: 200, headers, json: order() });
    }
    if (path.endsWith(`/orders/${ORDER_ID}/stages/${STAGE_ID}/reopen`)) {
      stages = stages.map((stage) =>
        stage.id === STAGE_ID ? { ...stage, completed_at: null, completed_by: null } : stage,
      );
      return route.fulfill({ status: 200, headers, json: order() });
    }
    if (path.endsWith(`/orders/${ORDER_ID}/evidence`)) {
      const body = `${request.postData() ?? ''} ${
        request.postDataBuffer()?.toString('latin1') ?? ''
      }`.toLowerCase();
      if (body.includes('eicar')) {
        return route.fulfill({
          status: 422,
          headers,
          json: {
            detail: [
              {
                loc: ['body'],
                msg: 'eicar.txt: rejected by the malware scan (Eicar-Test-Signature).',
                type: 'malware_detected',
              },
            ],
          },
        });
      }
      evidence.push({
        id: EVIDENCE_ID,
        author: me,
        note: 'Screenshot of the live banner.',
        files: [
          {
            id: FILE_ID,
            filename: 'banner.png',
            content_type: 'image/png',
            size: 2048,
            url: `/api/v1/orders/${ORDER_ID}/evidence/${EVIDENCE_ID}/files/${FILE_ID}`,
            created_at: '2026-11-14T12:00:00Z',
          },
        ],
        created_at: '2026-11-14T12:00:00Z',
      });
      return route.fulfill({ status: 201, headers, json: order() });
    }
    if (path.endsWith(`/orders/${ORDER_ID}`)) {
      return route.fulfill({ status: 200, headers, json: order() });
    }
    return route.fulfill({ status: 404, headers, json: { detail: [] } });
  });
}

test('a participant adds a stage with a deadline and completes it', async ({ page }) => {
  await mockApi(page, 'provider');
  await page.goto(`/orders/${ORDER_ID}`);

  await page.getByLabel('Stage name').fill('Banner goes live');
  await page.getByLabel('Stage deadline (optional)').fill('2026-12-01');
  await page.getByRole('button', { name: /Add stage/ }).click();

  await expect(page.getByText('Banner goes live')).toBeVisible();
  await expect(page.getByText('Due December 1, 2026.')).toBeVisible();
  await page.getByRole('button', { name: 'Mark complete' }).click();

  await expect(page.getByText(/Complete on .* by Digital Daily\./)).toBeVisible();
  await page.getByRole('button', { name: 'Reopen stage' }).click();
  await expect(page.getByText('Due December 1, 2026.')).toBeVisible();
});

test('a participant submits a note and a screenshot as evidence', async ({ page }) => {
  await mockApi(page, 'customer');
  await page.goto(`/orders/${ORDER_ID}`);

  await page
    .getByLabel('What does this evidence show? (optional)')
    .fill('Screenshot of the live banner.');
  await page.getByLabel('Evidence files (optional)').setInputFiles({
    name: 'banner.png',
    mimeType: 'image/png',
    buffer: Buffer.from('89504e470d0a1a0a0000000000000000', 'hex'),
  });
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);
  await page.getByRole('button', { name: /Add evidence/ }).click();

  await expect(page.getByText('Screenshot of the live banner.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'banner.png' })).toBeVisible();
});

test('a file rejected by the malware scan is shown as an error', async ({ page }) => {
  await mockApi(page, 'provider');
  await page.goto(`/orders/${ORDER_ID}`);

  await page.getByLabel('What does this evidence show? (optional)').fill('A suspicious file.');
  await page.getByLabel('Evidence files (optional)').setInputFiles({
    name: 'eicar.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'),
  });
  await page.getByRole('button', { name: /Add evidence/ }).click();

  await expect(page.getByText(/rejected by the malware scan/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'banner.png' })).toHaveCount(0);
});
