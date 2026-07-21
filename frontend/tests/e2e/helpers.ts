import {
  expect,
  test as base,
  type Locator,
  type Page,
} from '@playwright/test'
import type { MockScenario } from '../../src/mocks/scenario'

export const fixedNow = '2026-07-19T10:30:00Z'

type DateArguments =
  | []
  | [value: string | number | Date]
  | [
      year: number,
      monthIndex: number,
      date?: number,
      hours?: number,
      minutes?: number,
      seconds?: number,
      milliseconds?: number,
    ]

function setFixedDate(timestamp: number): void {
  const NativeDate = Date

  class FixedDate extends NativeDate {
    constructor(...args: DateArguments) {
      if (args.length === 0) {
        super(timestamp)
        return
      }
      if (args.length === 1) {
        super(args[0])
        return
      }

      const [year, monthIndex, date = 1, hours = 0, minutes = 0, seconds = 0, milliseconds = 0] = args
      super(year, monthIndex, date, hours, minutes, seconds, milliseconds)
    }

    static override now(): number {
      return timestamp
    }
  }

  Object.defineProperty(globalThis, 'Date', {
    configurable: true,
    value: FixedDate,
    writable: true,
  })
}

interface Task13Fixtures {
  appErrorGuard: void
}

export const test = base.extend<Task13Fixtures>({
  appErrorGuard: [async ({ page }, use) => {
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
    page.on('console', (message) => {
      if (message.type() !== 'error') return
      const text = message.text()
      if (text === 'Failed to load resource: the server responded with a status of 409 (Conflict)') return
      errors.push(`console: ${text}`)
    })
    await page.addInitScript(setFixedDate, Date.parse(fixedNow))

    await use(undefined)

    expect(errors, 'app console and page errors').toEqual([])
  }, { auto: true }],
})

export { expect }

export function scenarioUrl(route: string, scenario: MockScenario): string {
  const url = new URL(route, 'http://127.0.0.1:5173')
  url.searchParams.set('__scenario', scenario)
  return `${url.pathname}?${url.searchParams}`
}

export async function gotoScenario(
  page: Page,
  route: string,
  scenario: MockScenario,
): Promise<void> {
  await page.goto(scenarioUrl(route, scenario))
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
}

export async function setBrowserTime(page: Page, isoTimestamp: string): Promise<void> {
  await page.evaluate(setFixedDate, Date.parse(isoTimestamp))
}

export async function failNextAppFetch(page: Page, pathname: string): Promise<void> {
  await page.evaluate((targetPath) => {
    const originalFetch = window.fetch
    window.fetch = async (...args: Parameters<typeof window.fetch>) => {
      const input = args[0]
      const href = typeof input === 'string'
        ? input
        : input instanceof URL
          ? input.href
          : input.url

      if (new URL(href, window.location.href).pathname === targetPath) {
        window.fetch = originalFetch
        throw new TypeError(`Deterministic browser failure for ${targetPath}`)
      }
      return originalFetch(...args)
    }
  }, pathname)
}

export async function refetchAppQuery(page: Page, queryKey: readonly string[]): Promise<void> {
  const serializedKey = JSON.stringify(queryKey)
  await page.evaluate(
    `import('/src/app/queryClient.ts').then(({ queryClient }) => queryClient.refetchQueries({ queryKey: ${serializedKey} }))`,
  )
}

export async function disableAppQueryRetries(page: Page): Promise<void> {
  await page.evaluate(`import('/src/app/queryClient.ts').then(({ queryClient }) => {
    queryClient.setDefaultOptions({ queries: { retry: false } })
    for (const query of queryClient.getQueryCache().getAll()) {
      query.setOptions({ ...query.options, retry: false })
    }
  })`)
}

export async function tabTo(page: Page, target: Locator, maximumTabs = 80): Promise<void> {
  for (let index = 0; index < maximumTabs; index += 1) {
    await page.keyboard.press('Tab')
    if (await target.evaluate((element) => element === document.activeElement)) return
  }
  throw new Error(`Tab focus did not reach ${await target.getAttribute('aria-label') ?? await target.textContent()}`)
}

export async function expectVisibleFocus(target: Locator): Promise<void> {
  await expect(target).toBeFocused()
  const hasVisibleIndicator = await target.evaluate((element) => {
    const style = getComputedStyle(element)
    const focusContainer = element.closest(
      '.Mui-focused, .MuiDataGrid-cell--withFocus, .MuiDataGrid-columnHeader--withFocus',
    )
    const outlined = style.outlineStyle !== 'none' && Number.parseFloat(style.outlineWidth) > 0
    return element.matches(':focus-visible') && (outlined || focusContainer !== null)
  })
  expect(hasVisibleIndicator).toBe(true)
}
