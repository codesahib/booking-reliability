import { expect, test } from '@playwright/test'

test('original reservation desk accepts a simulated payment', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Upcoming stays' })).toBeVisible()
  await page.getByRole('button', { name: 'Send payment success', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Provider event applied')
  await expect(page.locator('.reservation.selected')).toContainText('paid')
  await page.screenshot({ path: 'evidence/baseline-ui.png', fullPage: true })
})
