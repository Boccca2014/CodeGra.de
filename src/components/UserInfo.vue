<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="userinfo">
    <loader class="col-md-12 text-center" v-if="loading" :scale="1"/>
    <b-form @keyup.enter="$refs.submitButton.onClick" v-else>
        <b-form-fieldset>
            <b-input-group prepend="Username">
                <div v-b-popover.top.hover="'You cannot change your username'"
                     style="flex: 1;">
                    <input type="text"
                           v-model="username"
                           disabled
                           style="border-top-left-radius: 0; border-bottom-left-radius: 0; width: 100%"
                           class="form-control"/>
                </div>
            </b-input-group>
        </b-form-fieldset>

        <b-form-fieldset>
            <b-input-group prepend="Full name">
                <input :disabled="!canEditInfo"
                       class="form-control"
                       name="full-name"
                       type="text"
                       v-model="name"/>
            </b-input-group>
        </b-form-fieldset>

        <b-form-fieldset>
            <b-input-group prepend="Email">
                <input :disabled="!canEditInfo"
                       type="text"
                       name="email"
                       class="form-control"
                       v-model="email"/>
            </b-input-group>
        </b-form-fieldset>

        <b-form-fieldset v-if="canEditPw || canEditInfo">
            <b-input-group>
                <b-input-group-prepend is-text>
                    Current Password
                    <description-popover hug-text
                                         placement="right"
                                         title="What is my current password?">
                        <p slot="description"
                           class="text-left mb-1">
                            If your account was created by using an
                            <span title="Learning Management System, e.g. Canvas or Blackboard"
                                  class="cursor-help"
                                  style="border-bottom: 1px dotted currentColor;">
                                LMS</span>
                            it can happen that you don't know this password. In
                            this case you should use the
                            <router-link :to="{ name: 'forgot' }" target="_blank">
                                reset password</router-link>
                            page.<br><br>

                            However this does require that your email is correct.
                            If this is not the case you can force CodeGrade to copy
                            the email that your LMS gives us the next time you use
                            CodeGrade within your LMS. To do this please
                            press <submit-button
                                      label="here"
                                      id="resetOnLtiButton-fixPopover"
                                      size="sm"
                                      :submit="resetEmailOnLti"
                                      style="display: inline;"/>
                            <!-- The id for the submit button is needed as vue
                            reuses elements and if that is done here the
                            popover will not show correctly. -->
                        </p>
                    </description-popover>
                </b-input-group-prepend>

                <input name="old-password"
                       class="form-control"
                       v-model="oldPw"
                       type="password" />
            </b-input-group>
        </b-form-fieldset>

        <b-form-fieldset v-if="canEditPw">
            <b-input-group prepend="New password">
                <input class="form-control"
                       v-model="newPw"
                       name="new-password"
                       type="password" />
            </b-input-group>
        </b-form-fieldset>

        <b-form-fieldset v-if="canEditPw">
            <b-input-group prepend="Confirm password">
                <input class="form-control"
                       v-model="confirmPw"
                       name="confirm-password"
                       type="password" />
            </b-input-group>
        </b-form-fieldset>

        <b-button-toolbar justify v-if="canEditInfo || canEditPw">
            <b-button variant="danger" @click="reset">Reset</b-button>

            <submit-button ref="submitButton"
                           name="submit-user-info"
                           :submit="submit"
                           @success="afterSubmit"
                           :confirm="confirmMessage">
                <template slot="error" slot-scope="error" v-if="error.error">
                    <password-suggestions :error="error.error"/>
                </template>
            </submit-button>
        </b-button-toolbar>
    </b-form>
</div>
</template>

<script>
import validator from 'email-validator';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/check';
import 'vue-awesome/icons/eye';
import 'vue-awesome/icons/info';
import 'vue-awesome/icons/eye-slash';
import 'vue-awesome/icons/times';

import { PASSWORD_UNIQUE_MESSAGE } from '@/constants';

import Loader from './Loader';
import DescriptionPopover from './DescriptionPopover';
import SubmitButton from './SubmitButton';
import PasswordSuggestions from './PasswordSuggestions';

export default {
    name: 'user-info',

    data() {
        return {
            name: '',
            username: '',
            email: '',
            oldPw: '',
            newPw: '',
            confirmPw: '',
            loading: false,
            canEditInfo: false,
            canEditPw: false,
            validator,
        };
    },

    computed: {
        confirmMessage() {
            if (this.newPw) {
                return PASSWORD_UNIQUE_MESSAGE;
            } else {
                return '';
            }
        },
    },

    mounted() {
        this.loading = true;
        Promise.all([
            this.$http.get('/api/v1/login?extended'),
            this.$hasPermission(['can_edit_own_info', 'can_edit_own_password']),
        ]).then(([{ data }, [canEditInfo, canEditPw]]) => {
            this.canEditInfo = canEditInfo;
            this.canEditPw = canEditPw;

            this.name = data.name;
            this.username = data.username;
            this.email = data.email;
            this.loading = false;
        });
    },

    methods: {
        resetEmailOnLti() {
            return this.$http.patch('/api/v1/login', {}, { params: { type: 'reset_on_lti' } });
        },

        reset() {
            this.name = this.$store.state.user.name;
            this.email = this.$store.state.user.email;
            this.oldPw = '';
            this.newPw = '';
            this.confirmPw = '';
        },

        submit() {
            if (this.newPw !== this.confirmPw) {
                throw new Error('New password does not match confirm password.');
            }

            if (!validator.validate(this.email)) {
                throw new Error('The given email is not valid.');
            }

            return this.$store.dispatch('user/updateUserInfo', {
                name: this.name,
                email: this.email,
                oldPw: this.oldPw,
                newPw: this.newPw,
            });
        },

        afterSubmit() {
            this.reset();
        },
    },

    components: {
        Icon,
        Loader,
        DescriptionPopover,
        SubmitButton,
        PasswordSuggestions,
    },
};
</script>

<style lang="less" scoped>
.userinfo form fieldset:last-child {
    margin-bottom: 0;
}
</style>
