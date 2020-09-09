/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
import Icon from 'vue-awesome/components/Icon';
import icons from '@/icons.json';

Vue.component('fa-icon', Icon);

Icon.register(icons);
