import react from '@vitejs/plugin-react'
import { configDefaults, defineConfig } from 'vitest/config'

export default defineConfig(({ command }) => ({
  plugins: [react()],
  publicDir: command === 'serve' ? 'public-dev' : false,
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    exclude: [...configDefaults.exclude, 'tests/e2e/**', 'tests/production/**'],
  },
}))
