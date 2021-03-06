// http://eslint.org/docs/user-guide/configuring

module.exports = {
    root: true,
    parser: '@typescript-eslint/parser',
    parserOptions: {
        ecmaVersion: 2018,
        sourceType: 'module',
        project: './tsconfig.json',
        tsconfigRootDir: __dirname,
        ecmaFeatures: {
            jsx: true,
        },
        extraFileExtensions: ['.vue'],
    },
    env: {
        browser: true,
    },
    extends: [
        'plugin:prettier-vue/recommended',
        'airbnb-base',
    ],

    // required to lint *.vue files
    plugins: [
        '@typescript-eslint',
        'html',
    ],
    // check if imports actually resolve
    'settings': {
        'import/resolver': {
            'webpack': {
                'config': 'build/webpack.base.conf.js'
            }
        },

        'prettier-vue': {
            // Settings for how to process Vue SFC Blocks
            SFCBlocks: {
                /**
                 * Use prettier to process `<template>` blocks or not
                 *
                 * If set to `false`, remember not to `extends: ['prettier/vue']`, as you need the rules from `eslint-plugin-vue` to lint `<template>` blocks
                 */
                template: false,
            },
        },
    },
    // add your custom rules here
    'rules': {
        // don't require .vue extension when importing
        'import/extensions': ['error', 'always', {
            'js': 'never',
            'vue': 'never'
        }],
        // allow optionalDependencies
        'import/no-extraneous-dependencies': ['error', {
            'optionalDependencies': ['test/unit/index.js']
        }],
        // allow debugger during development
        'no-debugger': process.env.NODE_ENV === 'production' ? 2 : 0,
        'indent': 'off',
        'no-else-return': 'off',
        'no-plusplus': 'off',
        'function-paren-newline': 'off',
        'no-bitwise': 'off',
        'no-mixed-operators': 'off',
        'arrow-parens': ['error', 'as-needed'],
        'prefer-destructuring': 'off',
        'import/prefer-default-export': 'off',
        'operator-linebreak': 'off',
        'import/no-cycle': 'off',
        'import/extensions': 'off',
        'object-curly-newline': 'off',
        'implicit-arrow-linebreak': 'off',
        'comma-style': 'off',

        'no-unused-vars': 'off',
        '@typescript-eslint/no-unused-vars': ['error', {
            'vars': 'all',
            'args': 'after-used',
            'ignoreRestSiblings': false,
            'argsIgnorePattern': '^_+$',
        }],

        "no-use-before-define": 'off',
        "@typescript-eslint/no-use-before-define": ["error", { "functions": true, "classes": true }],

        "no-useless-constructor": "off",
        "@typescript-eslint/no-useless-constructor": ["error"],

        "no-empty-function": "off",
        "@typescript-eslint/no-empty-function": ["error", {
            'allow': ['arrowFunctions'],
        }],

        // allow vuex
        'no-param-reassign': ["error", { 'props': false }],

        'no-underscore-dangle': ['error', { 'allowAfterThis': true, 'allowAfterSuper': true }],
        "no-inner-declarations": "off",

        'no-dupe-class-members': 'off',
        '@typescript-eslint/no-dupe-class-members': ['error'],
        // https://github.com/typescript-eslint/typescript-eslint/pull/1684
        // 'lines-between-class-members': 'off',
        // '@typescript-eslint/lines-between-class-members': ['error', 'always'],

        'no-continue': 'off',

        '@typescript-eslint/strict-boolean-expressions': ['error', {
            allowString: true,
            allowNumber: false,
            allowNullableObject: false,
            allowNullableBoolean: false,
            allowNullableString: false,
            allowNullableNumber: false,
            allowAny: false,
        }],
        'no-redeclare': 'off',
        '@typescript-eslint/no-redeclare': ['error'],

        "no-shadow": "off",
        "@typescript-eslint/no-shadow": ["error"],

        "@typescript-eslint/await-thenable": "error",
        "@typescript-eslint/no-misused-promises": [
            "error",
            {
                "checksConditionals": false
            }
        ],

        // This rule would be really nice, however it simply doesn't work with
        // the vue style of passing callbacks.
        '@typescript-eslint/unbound-method': 'off',

        '@typescript-eslint/prefer-reduce-type-parameter': 'error',

        '@typescript-eslint/no-unnecessary-type-arguments': 'error',

        '@typescript-eslint/prefer-includes': 'error',

        '@typescript-eslint/restrict-template-expressions': [
            'error',
            {
                allowNumber: true,
                allowBoolean: true,
                allowAny: true,
            },
        ],

        '@typescript-eslint/adjacent-overload-signatures': 'error',

        'prettier-vue/prettier': ['error', {
            'singleQuote': true,
            'parser': 'typescript',
            'useTabs': false,
            'tabWidth': 4,
            'trailingComma': 'all',
            'printWidth': 100,
            'allowParans': 'avoid',
            'endOfLine': 'auto',
        }],
        "no-restricted-syntax": [
            "warn",
            {
                "selector": "CallExpression[callee.name='trace']",
                "message": "Trace calls should be removed."
            }
        ],
    },
    globals: {
        'AutoTestBaseSystems': true,
        'IS_PRODUCTION': true,
        'SENTRY_DSN': true,
        'COMMIT_HASH': true,
    },
    overrides: [
        {
            files: ['*.tsx'],
            rules: {
                '@typescript-eslint/no-unused-vars': ['error', {
                    'argsIgnorePattern': '^h$',
                }],
            },
        },
        {
            files: ['*.js', '*.vue'],
            rules: {
                '@typescript-eslint/strict-boolean-expressions': 'off',
                '@typescript-eslint/restrict-template-expressions': 'off',
            },
        },
    ]
}
