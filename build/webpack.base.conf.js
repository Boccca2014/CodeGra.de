var path = require('path')
var utils = require('./utils')
var webpack = require('webpack')
var config = require('../config')
var vueLoaderConfig = require('./vue-loader.conf')
var userConfig = require('./userConfig')
const { VueLoaderPlugin } = require('vue-loader')
const ForkTsCheckerWebpackPlugin = require('fork-ts-checker-webpack-plugin');
const keysTransformer = require('ts-transformer-keys/transformer').default;
const CreateFileWebpack = require('./createFile')

function resolve (dir) {
  return path.join(__dirname, '..', dir)
}

module.exports = {
  mode: process.env.NODE_ENV === 'development' ? 'development' : 'production',
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
        test: /\.(js|vue|ts)$/,
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
        use: [
          {
            loader: 'babel-loader',
          },
          {
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
          },
        ]
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
    buffer: false,
  },
  plugins: [
    new webpack.IgnorePlugin(/^\.\/locale$/, /moment$/),
    new VueLoaderPlugin(),
    new CreateFileWebpack({
        path: resolve('src'),
        fileName: 'userConfig.ts',
        content: `// eslint-disable-next-line
const userConfig = Object.freeze(<const>${JSON.stringify(userConfig)});
export default userConfig;
`,
    }),
      new webpack.ProvidePlugin({
          'UserConfig': [resolve('src/userConfig.ts'), 'default'],
      }),
  ],
}
