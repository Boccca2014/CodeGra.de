import { config } from '@vue/test-utils';
import '@/polyfills';
import Vue from 'vue';
import axios from 'axios';

import * as utils from '@/utils';

Vue.prototype.$utils = utils;
Vue.prototype.$afterRerender = function() {};

config.mocks.$http = axios;

config.mocks.$htmlEscape = jest.fn(a => a);

global.log = console.log;
