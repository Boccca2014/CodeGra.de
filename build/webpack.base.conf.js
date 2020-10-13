const path = require('path')
const utils = require('./utils')
const webpack = require('webpack')
const config = require('../config')
const vueLoaderConfig = require('./vue-loader.conf')
const { VueLoaderPlugin } = require('vue-loader')
const ForkTsCheckerWebpackPlugin = require('fork-ts-checker-webpack-plugin');
const keysTransformer = require('ts-transformer-keys/transformer').default;
const CreateFileWebpack = require('./createFile')
const execFileSync = require('child_process').execFileSync;
const gitCommitLong = require('./git_commit');

function resolve (dir) {
  return path.join(__dirname, '..', dir)
}

const IS_PRODUCTION = process.env.NODE_ENV !== 'development';
globalConstants = {
    IS_PRODUCTION: JSON.stringify(IS_PRODUCTION),
    COMMIT_HASH: JSON.stringify(gitCommitLong),
    SENTRY_DSN: JSON.stringify(process.env['SENTRY_DSN'] || ''),
};
utils.assert(typeof JSON.parse(globalConstants.IS_PRODUCTION) === 'boolean', 'IS_PRODUCTION wrong type');
utils.assert(typeof JSON.parse(globalConstants.COMMIT_HASH) === 'string', 'COMMIT_HASH wrong type');
utils.assert(typeof JSON.parse(globalConstants.SENTRY_DSN) === 'string', 'SENTRY_DSN wrong type');

function makeTsLoaders() {
    const loaders = [{
        loader: 'babel-loader',
    }];

    if (!IS_PRODUCTION) {
        loaders.push({
            loader: 'vue-jsx-hot-loader',
        });
    }

    loaders.push({
        loader: "ts-loader",
        options: {
            appendTsSuffixTo: [/\.vue$/],
            transpileOnly: false,
            experimentalWatchApi: false,
            getCustomTransformers: program => ({
                before: [
                    keysTransformer(program),
                ],
            }),
        },
    });
    return loaders;
}

module.exports = {
  mode: IS_PRODUCTION ? 'production' : 'development',
  entry: {
    app: './src/main.js'
  },
  output: {
    path: config.build.assetsRoot,
    chunkFilename: '[name].bundle.[chunkhash].js',
    publicPath: process.env.NODE_ENV === 'production'
      ? config.build.assetsPublicPath
      : config.dev.assetsPublicPath
  },
  resolve: {
    extensions: ['.js', '.vue', '.json', '.ts', '.tsx'],
    alias: {
      'vue$': 'vue/dist/vue.esm.js',
      '@': resolve('src'),
      'mixins': path.resolve(__dirname, '../src/mixins.less'),
      'mixins.less': path.resolve(__dirname, '../src/mixins.less')
    },
  },
  module: {
    rules: [
      {
        test: /\.(js|vue|tsx?)$/,
        loader: 'eslint-loader',
        enforce: 'pre',
          include: [
              resolve('src'),
              resolve('test'),
          ],
        options: {
          formatter: require('eslint-friendly-formatter')
        }
      },
      {
        test: /\.vue$/,
        loader: 'vue-loader',
        options: vueLoaderConfig
      },
      {
        test: /\.d\.ts$/,
        loader: 'ignore-loader',
      },
      {
        test: /\.tsx?$/,
        exclude: /node_modules|\.d\.ts$/,
        use: makeTsLoaders(),
      },
      {
        test: /\.js$/,
        loader: 'babel-loader',
          include: [
              resolve('src'),
              resolve('test'),
          ],
      },
      {
        test: /\.(png|jpe?g|gif|svg)(\?.*)?$/,
        loader: 'url-loader',
        options: {
          limit: 10000,
          name: utils.assetsPath('img/[name].[hash:7].[ext]')
        }
      },
      {
        test: /\.(woff2?|eot|ttf|otf)(\?.*)?$/,
        loader: 'url-loader',
        options: {
          limit: 10000,
          name: utils.assetsPath('fonts/[name].[hash:7].[ext]')
        }
      }
    ]
  },
  node: {
    fs: 'empty',
    Buffer: false,
    process: false,
  },
  plugins: [
    new webpack.IgnorePlugin(/^\.\/locale$/, /moment$/),
    new VueLoaderPlugin(),
    new webpack.DefinePlugin(globalConstants),
  ],
}
