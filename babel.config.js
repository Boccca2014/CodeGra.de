module.exports = {
    "presets": [
        [
            "@vue/babel-preset-jsx",
            {
                "modules": false,
                "targets": {
                    "browsers": [
                        ">0.5%",
                        "not ie >= 11",
                        "not op_mini All",
                        "Firefox ESR"
                    ]
                }
            }
        ]
    ],
    "plugins": [
        [
            "@babel/plugin-proposal-decorators",
            {
                "legacy": true
            }
        ],
        "@babel/plugin-proposal-function-sent",
        "@babel/plugin-proposal-export-namespace-from",
        "@babel/plugin-proposal-numeric-separator",
        "@babel/plugin-proposal-throw-expressions",
        "@babel/plugin-syntax-dynamic-import",
        "@babel/plugin-syntax-import-meta",
        [
            "@babel/plugin-proposal-class-properties",
            {
                "loose": false
            }
        ],
        "@babel/plugin-proposal-json-strings",
        "transform-vue-jsx",
        "babel-plugin-vue-tsx-functional/lib/plugin",
    ],
    "comments": false,
    "env": {
        "test": {
            "passPerPreset": true,
            "presets": [
                {
                    "plugins": [
                        [
                            "@babel/plugin-proposal-decorators",
                            {
                                "legacy": true
                            }
                        ],
                        "@babel/plugin-proposal-function-sent",
                        "@babel/plugin-proposal-export-namespace-from",
                        "@babel/plugin-proposal-numeric-separator",
                        "@babel/plugin-proposal-throw-expressions",
                        "@babel/plugin-syntax-dynamic-import",
                        "@babel/plugin-syntax-import-meta",
                        [
                            "@babel/plugin-proposal-class-properties",
                            {
                                "loose": false
                            }
                        ],
                        "@babel/plugin-proposal-json-strings",
                        "babel-plugin-vue-tsx-functional/lib/plugin"
                    ]
                },
                {
                    "passPerPreset": false,
                    "presets": [
                        "@vue/babel-preset-jsx",
                    ]
                }
            ]
        },
        "integration_testing": {
            "plugins": [
                "istanbul"
            ]
        }
    }
}
