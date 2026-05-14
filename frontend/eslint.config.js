import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // API client boundary code intentionally uses `any` until the
      // backend OpenAPI schema is consumed end-to-end. Track separately.
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
  {
    // shadcn/ui components co-export the component and its `cva` variants
    // helper from the same file. That is the canonical shadcn pattern; the
    // fast-refresh rule fires false-positives. HMR cost is dev-only.
    files: ['src/components/ui/**/*.{ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    // React contexts canonically export both the Provider component and a
    // `useXxx` hook from one file. Same false-positive class as shadcn.
    files: ['src/contexts/**/*.{ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
])
