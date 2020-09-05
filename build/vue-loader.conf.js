var config = require('../config')

module.exports = {
    cacheBusting: config.dev.cacheBusting,
    transformToRequire: {
        transformAssetUrls: {
            video: ['src', 'poster'],
            source: 'src',
            img: 'src',
            image: 'xlink:href'
        }
    },
    // loaders: {
    //     "ts": "ts-loader",
    //     "tsx": "babel-loader!ts-loader",
    // },
}
