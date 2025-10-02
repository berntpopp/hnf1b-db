import js from '@eslint/js';
import pluginVue from 'eslint-plugin-vue';
import globals from 'globals';

export default [
  js.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.es2021,
      },
    },
    rules: {
      'no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
      }],
      'vue/multi-word-component-names': 'off',
      'vue/require-default-prop': 'error',
      'vue/require-prop-types': 'error',
      'vue/no-v-html': 'warn',
      'vue/component-tags-order': ['error', {
        order: ['template', 'script', 'style'],
      }],
      'vue/no-unused-components': 'error',
      'vue/no-unused-vars': 'error',
      'vue/padding-line-between-blocks': 'error',
      'vue/valid-v-slot': ['error', {
        allowModifiers: true,
      }],
      'no-console': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
      'no-debugger': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
    },
  },
  {
    ignores: ['node_modules/**', 'dist/**', 'build/**', 'coverage/**', '.vscode/**', '.idea/**'],
  },
];