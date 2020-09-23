<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="login">
    <b-form @submit="() => $refs.submit.onClick()">
        <b-form-group label="Username">
            <input type="text"
                   class="form-control"
                   placeholder="Enter your username"
                   v-model="username"
                   ref="username"
                   name="username"
                   @keydown.enter="$refs.submit.onClick"/>
        </b-form-group>

        <b-form-group label="Password">
            <input class="form-control"
                   type="password"
                   v-model="password"
                   placeholder="Enter your password"
                   name="password"
                   @keydown.enter="$refs.submit.onClick" />
        </b-form-group>

        <div class="d-flex align-items-center"
             :class="{
                 'justify-content-between': !hideForget,
                 'justify-content-end': hideForget,
             }">
            <router-link :to="{ name: 'forgot' }"
                         v-show="!hideForget"
                         class="forget-link">
                Forgot password
            </router-link>

            <submit-button :label="loginLabel"
                           ref="submit"
                           :submit="submit"
                           @success="success"
                           :wait-at-least="0">
                <template slot="warning" slot-scope="scope">
                    {{ scope.warning.messages.map(x => x.text).join(' ') }}<br>
                    Close this message to continue.
                </template>
            </submit-button>
        </div>
    </b-form>

    <sso-providers @saml-login="$emit('saml-login', $event)"
                   allow-login>
        <hr />
        <h5>Or login using</h5>
    </sso-providers>
</div>
</template>

<script>
import { mapActions } from 'vuex';

import SubmitButton from './SubmitButton';
import SsoProviders from './SsoProviders';

export default {
    name: 'login',

    props: {
        hideForget: {
            type: Boolean,
            default: false,
        },

        loginLabel: {
            type: String,
            default: 'Login',
        },
    },

    data() {
        return {
            username: '',
            password: '',
        };
    },

    components: {
        SubmitButton,
        SsoProviders,
    },

    mounted() {
        this.$waitForRef('username').then(userInput => {
            if (userInput != null) {
                this.$refs.username.focus();
            }
        });
    },

    methods: {
        ...mapActions('user', ['login']),

        submit() {
            if (!this.password || !this.username) {
                return Promise.reject(new Error('Please enter a username and password.'));
            }

            return this.$http.post('/api/v1/login?with_permissions', {
                username: this.username,
                password: this.password,
            });
        },

        success(response) {
            this.login(response).then(() => {
                this.$emit('login');
            });
        },
    },
};
</script>

<style lang="less" scoped>
a.forget-link {
    text-decoration: underline !important;
}
</style>
