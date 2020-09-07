<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="register">
    <div class="register-wrapper">
        <cg-logo :inverted="!darkMode"
                 class="standalone-logo" />
        <h4>
            Register
            <span v-if="$route.query.register_for">
                for {{ $route.query.register_for }}
            </span>
        </h4>
        <register class="register"
                  :registration-url="registrationUrl" />
    </div>
</div>
</template>

<script>
import { mapGetters } from 'vuex';

import { CgLogo, Register } from '@/components';

import { setPageTitle } from './title';

export default {
    name: 'register-page',

    computed: {
        ...mapGetters('pref', ['darkMode']),

        registrationUrl() {
            return '/api/v1/user';
        },
    },

    mounted() {
        const courseId = this.$route.query.course_id;
        const linkId = this.$route.query.course_register_link_id;

        if (courseId && linkId) {
            this.$router.replace({
                name: 'course_enroll',
                params: { courseId, linkId },
            });
        }
        setPageTitle('Register');
    },

    components: {
        CgLogo,
        Register,
    },
};
</script>

<style lang="less" scoped>
h4 {
    margin-bottom: 1rem;
    font-weight: normal;
    text-align: center;
}

.page.register .register-wrapper {
    margin: 0 auto;
    max-width: 25rem;
}
</style>
