<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="login">
    <div class="login-wrapper">
        <cg-logo :inverted="!darkMode"
                 class="standalone-logo" />
        <login class="login"
               @login="onLogin"
               @saml-login="doSamlLogin"/>
    </div>
</div>
</template>

<script>
import { mapGetters } from 'vuex';

import { Login, CgLogo } from '@/components';

import { setPageTitle } from './title';

export default {
    name: 'login-page',

    computed: {
        ...mapGetters('pref', ['darkMode']),
    },

    mounted() {
        setPageTitle('Login');
    },

    methods: {
        doSamlLogin(provider) {
            const next = this.$router.getRestoreRoute();
            const query = {};
            if (next) {
                query.next = next.fullPath;
            }
            window.location.replace(this.$utils.buildUrl(
                provider.loginUrl,
                { query },
            ));
        },

        onLogin() {
            this.$router.replace({ name: 'home' });
        },
    },

    components: {
        Login,
        CgLogo,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.login-wrapper {
    margin: 2em auto;

    .login {
        max-width: 25rem;
        margin: 0 auto;
    }
}
</style>
