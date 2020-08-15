<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="forgot-password">
    <b-form-group label="Username">
        <input type="text"
               class="form-control"
               name="username"
               placeholder="Enter your username"
               v-model="username"
               ref="username"
               @keyup.enter="$refs.btn.onClick"/>
    </b-form-group>

    <p>
        A link to reset your password will be sent to your e-mail shortly. This
        link can be used for a limited period of time. Please check your spam
        folder if you did not receive the e-mail shortly after requesting it.
    </p>

    <div class="d-flex justify-content-between align-items-center">
        <!-- This happens when a logged in user wants to reset its password -->
        <router-link :to="{ name: 'login' }" v-show="!loggedIn">
            Login
        </router-link>

        <submit-button label="Request email"
                       ref="btn"
                       :submit="submit"/>
    </div>
</div>
</template>

<script>
import { mapGetters } from 'vuex';

import SubmitButton from './SubmitButton';

export default {
    name: 'login',

    data() {
        return {
            username: '',
        };
    },

    components: {
        SubmitButton,
    },

    computed: {
        ...mapGetters('user', ['loggedIn']),
    },

    async mounted() {
        const userInput = await this.$waitForRef('username');
        if (userInput != null) {
            userInput.focus();
        }
    },

    methods: {
        submit() {
            if (!this.username) {
                throw new Error('Please enter a username.');
            }

            return this.$http.patch('/api/v1/login?type=reset_email', { username: this.username });
        },
    },
};
</script>

<style lang="less" scoped>
@link-margin: 2em;

a.login {
    text-decoration: underline !important;
}
</style>
