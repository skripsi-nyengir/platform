import { expect, expectVisibleFocus, scenarioUrl, test } from './helpers'

test('an unauthenticated visitor is sent to the login form', async ({ page, httpErrorGuard }) => {
  httpErrorGuard.allow(401)

  await page.goto(scenarioUrl('/', 'unauthenticated'))

  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Anomaly Detection Platform',
  )
  await expect(page.getByLabel(/nama pengguna/i)).toBeVisible()
  // The protected shell must not be rendered behind the form.
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toHaveCount(0)
})

test('signing in lands on the route that was originally requested', async ({ page, httpErrorGuard }) => {
  httpErrorGuard.allow(401)

  await page.goto(scenarioUrl('/system-health', 'unauthenticated'))

  await page.getByLabel(/nama pengguna/i).fill('operator')
  await page.getByLabel(/kata sandi/i).fill('operator-password')
  await page.getByRole('button', { name: 'Masuk' }).click()

  await expect(page.getByRole('heading', { name: 'System Health' })).toBeVisible()
})

test('the form is operable from the keyboard alone', async ({ page, httpErrorGuard }) => {
  httpErrorGuard.allow(401)

  await page.goto(scenarioUrl('/', 'unauthenticated'))

  const username = page.getByLabel(/nama pengguna/i)
  await expect(username).toBeFocused()
  await expectVisibleFocus(username)

  await page.keyboard.type('operator')
  await page.keyboard.press('Tab')
  await page.keyboard.type('operator-password')
  await page.keyboard.press('Enter')

  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
})

test('a rejected credential is explained without leaving the form', async ({ page, httpErrorGuard }) => {
  httpErrorGuard.allow(401)

  await page.goto(scenarioUrl('/', 'login-invalid'))

  await page.getByLabel(/nama pengguna/i).fill('operator')
  await page.getByLabel(/kata sandi/i).fill('wrong-password')
  await page.getByRole('button', { name: 'Masuk' }).click()

  await expect(page.getByRole('alert')).toContainText(/username or password is incorrect/i)
  await expect(page.getByLabel(/nama pengguna/i)).toBeVisible()
})

test('a locked account is reported distinctly from a rejected password', async ({ page, httpErrorGuard }) => {
  httpErrorGuard.allow(401)
  httpErrorGuard.allow(429)

  await page.goto(scenarioUrl('/', 'login-locked'))

  await page.getByLabel(/nama pengguna/i).fill('operator')
  await page.getByLabel(/kata sandi/i).fill('operator-password')
  await page.getByRole('button', { name: 'Masuk' }).click()

  await expect(page.getByRole('alert')).toContainText(/too many failed sign-in attempts/i)
})

test('signing out returns to the form', async ({ page, httpErrorGuard }) => {
  httpErrorGuard.allow(401)

  await page.goto(scenarioUrl('/', 'normal'))
  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()

  await page.getByRole('button', { name: 'Sign out' }).click()

  await expect(page.getByLabel(/nama pengguna/i)).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)
})

test('the form stays contained at 390px', async ({ page, httpErrorGuard }) => {
  httpErrorGuard.allow(401)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(scenarioUrl('/', 'unauthenticated'))

  await expect(page.getByLabel(/nama pengguna/i)).toBeVisible()
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(0)
})
