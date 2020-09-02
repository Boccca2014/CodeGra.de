<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="register">
    <b-form-group label="Username"
                  description="You cannot change your username after the registration.">
        <input type="text"
               placeholder="Enter your wanted username"
               class="form-control"
               v-model="username"
               tabindex="1"/>
    </b-form-group>

    <b-form-group label="Name">
        <input type="text"
               placeholder="Enter your full name"
               class="form-control"
               v-model="name"
               tabindex="2" />
    </b-form-group>

    <b-form-group label="Email address">
        <input type="email"
               placeholder="Enter your email"
               class="form-control"
               v-model="firstEmail"
               tabindex="3" />
    </b-form-group>

    <b-form-group label="Repeat email address">
        <input type="email"
               class="form-control"
               placeholder="Repeat your email"
               v-model="secondEmail"
               tabindex="4" />
    </b-form-group>

    <b-form-group label="Password">
        <input class="form-control"
               placeholder="Enter a unique and secure password"
               v-model="firstPw"
               tabindex="5"
               type="password" />
    </b-form-group>

    <b-form-group label="Repeat password">
        <input class="form-control"
               placeholder="Repeat your password"
               v-model="secondPw"
               tabindex="6"
               type="password" />
    </b-form-group>

    <div class="text-right">
        <submit-button tabindex="7"
                       label="Register"
                       :submit="submit"
                       @after-success="afterSubmit"
                       :confirm="PASSWORD_UNIQUE_MESSAGE">
            <template slot="error"
                      slot-scope="error"
                      v-if="error.error">
                <password-suggestions
                    v-if="$utils.getProps(error.error, null, 'response', 'data', 'feedback')"
                    :error="error.error"/>

                <template v-else>
                    <p class="mb-0">{{ $utils.getErrorMessage(error.error) }}</p>

                    <ul v-if="$utils.getProps(error.error, 0, 'messages', 'length') > 0"
                        class="mb-0 pl-3 text-left">
                        <li v-for="msg in error.error.messages">
                            {{ msg }}
                        </li>
                    </ul>
                </template>
            </template>
        </submit-button>
    </div>
</div>
</template>

<script>
import { mapActions } from 'vuex';

import { PASSWORD_UNIQUE_MESSAGE } from '@/constants';

import SubmitButton from './SubmitButton';
import DescriptionPopover from './DescriptionPopover';
import PasswordSuggestions from './PasswordSuggestions';

export default {
    name: 'register',

    props: {
        registrationUrl: {
            type: String,
            required: true,
        },

        redirectRoute: {
            type: Object,
            default: () => ({
                name: 'home',
                query: {
                    sbloc: 'm',
                },
            }),
        },
    },

    data() {
        return {
            username: '',
            firstEmail: '',
            secondEmail: '',
            name: '',
            firstPw: '',
            secondPw: '',

            fieldLabels: {
                username: 'Username',
                name: 'Name',
                firstEmail: 'Email',
                secondEmail: 'Repeat email',
                firstPw: 'Password',
                secondPw: 'Repeat password',
            },

            PASSWORD_UNIQUE_MESSAGE,
        };
    },

    methods: {
        ...mapActions('user', ['updateAccessToken']),

        submit() {
            const errors = [];

            Object.entries(this.fieldLabels).forEach(([key, label]) => {
                if (this[key].length === 0) {
                    errors.push(`Field "${label}" is empty.`);
                }
            });

            if (this.firstPw !== this.secondPw) {
                errors.push('The passwords do not match.');
            }

            if (this.firstEmail !== this.secondEmail) {
                errors.push('The emails do not match.');
            }

            if (errors.length > 0) {
                const err = new Error();
                err.messages = errors;
                throw err;
            }

            return this.$http.post(this.registrationUrl, {
                username: this.username,
                password: this.firstPw,
                email: this.firstEmail,
                name: this.name,
            });
        },

        afterSubmit(response) {
            const token = response.data.access_token;
            if (token) {
                this.updateAccessToken(token).then(() => {
                    this.$router.push(this.redirectRoute);
                });
            }
        },
    },

    components: {
        SubmitButton,
        DescriptionPopover,
        PasswordSuggestions,
    },
};
</script>
