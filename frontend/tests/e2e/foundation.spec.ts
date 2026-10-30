import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const routes = [
  '/',
  '/listings',
  '/listings/digital-daily',
  '/orders',
  '/orders/demo',
  '/how-it-works',
  '/register',
];

for (const route of routes) {
  test(`${route} has an accessible English responsive layout`, async ({ page }) => {
    for (const width of [320, 360, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(route);
      await expect(page.locator('html')).toHaveAttribute('lang', 'en');
      await expect(page.locator('h1')).toHaveCount(1);
      await expect(page.getByRole('main')).toBeVisible();
      const dimensions = await page.evaluate(() => ({
        content: document.documentElement.scrollWidth,
        viewport: window.innerWidth,
      }));
      expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
      const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
      expect(audit.violations).toEqual([]);
    }
  });
}

test('mobile navigation opens, closes on Escape and follows links', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto('/');
  const menu = page.getByRole('button', { name: 'Open navigation' });
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeHidden();
  await menu.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: 'Close navigation' })).toHaveAttribute(
    'aria-expanded',
    'true',
  );
  const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag21a']).analyze();
  expect(audit.violations).toEqual([]);
  await page.keyboard.press('Escape');
  await expect(menu).toHaveAttribute('aria-expanded', 'false');
  await menu.click();
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Marketplace', exact: true })
    .click();
  await expect(page).toHaveURL('/listings');
  await expect(menu).toHaveAttribute('aria-expanded', 'false');
});

test('360px listings use a single column and link to details', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto('/listings');
  const cards = page.locator('.listing-card');
  await expect(cards).toHaveCount(6);
  const first = await cards.nth(0).boundingBox();
  const second = await cards.nth(1).boundingBox();
  expect(first?.x).toBe(second?.x);
  expect(second!.y).toBeGreaterThan(first!.y + first!.height);
  await cards.nth(1).getByRole('link').click();
  await expect(page).toHaveURL('/listings/digital-daily');
  await expect(page.getByRole('heading', { name: 'Placement specification' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Reveal phone number' })).toBeDisabled();
});

test('keyboard skip link reaches content and invalid listings return a useful 404', async ({
  page,
}) => {
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
  const response = await page.goto('/listings/not-a-real-listing');
  expect(response?.status()).toBe(404);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('A little off the path.');
});
