<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="student-contact p-relative">
    <div class="text-left" >
        <b-form-group label="Recipients"
                      label-size="lg"
                      label-class="pt-0">
            <b-form-radio-group v-if="!noEverybodyEmailOption"
                                v-model="selectedDefaultReceiver"
                                :options="defaultReceiverOptions"
                                stacked/>

            <component v-if="showRecipientSelector"
                       :is="noEverybodyEmailOption ? 'div' : 'b-form-group'"
                       class="mt-2">
                <label v-if="!noEverybodyEmailOption">
                    Users
                </label>
                <b-input-group>
                    <user-selector
                        :placeholder="userSelectorPlaceholder"
                        v-model="users"
                        :use-selector="canListUsers"
                        :base-url="`/api/v1/courses/${course.id}/users/`"
                        multiple />
                    <b-input-group-append>
                        <b-button variant="warning"
                                  @click="clearUsers"
                                  v-b-popover.top.hover="'Clear all'">
                            <icon name="reply" />
                        </b-button>
                    </b-input-group-append>
                </b-input-group>
            </component>
        </b-form-group>


        <b-form-group label="Subject"
                      label-size="lg">
            <input v-model="subject"
                   class="form-control"
                   ref="subjectInput" />
        </b-form-group>

        <b-form-group label="Body"
                      label-size="lg">
            <snippetable-input
                v-model="body"
                :course="course"
                :force-snippets-above="false"
                :total-amount-lines="1000"
                :feedback-disabled="false"
                :can-use-snippets="canUseSnippets"
                no-auto-focus
                :min-initial-height="300"
                :line="0"
                @ctrlEnter="() => submitButton.onClick()"
                :bounce-time="300" />
        </b-form-group>
    </div>

    <div class="d-flex"
         :class="`justify-content-${noCancel ? 'end' : 'between'}`">
        <cg-submit-button
            v-if="!noCancel"
            variant="outline-danger"
            confirm="Are you sure you want to discard this email?"
            :submit="() => ({})"
            @success="$emit('hide')">
            Cancel
        </cg-submit-button>

        <cg-submit-button
            ref="submitButton"
            :submit="sendEmail"
            confirm="Are you sure you want to send this email?"
            @error="maybeSetDeliveryError"
            @after-success="afterEmail"
            label="Send">
        </cg-submit-button>
    </div>

    <b-alert v-if="deliveryError != null"
             show
             variant="warning"
             dismissible
             @dismissed="deliveryError = null">
        Failed to email some users:

        <ul>
            <li v-for="user in deliveryError.response.data.failed_users">
                <cg-user :user="user"  />
            </li>
        </ul>

        <template v-if="getSuccessfulUsers(deliveryError.response.data).length > 0">
            Please note that emailing these users did succeed:

            <ul>
                <li v-for="user in getSuccessfulUsers(deliveryError.response.data)">
                    <cg-user :user="user" />
                </li>
            </ul>
        </template>
    </b-alert>
</div>
</template>

<script lang="ts">
import { Vue, Component, Prop, Ref } from 'vue-property-decorator';

import * as models from '@/models';

// @ts-ignore
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/reply';

// @ts-ignore
import Toggle from './Toggle';
// @ts-ignore
import UserSelector from './UserSelector';
// @ts-ignore
import SnippetableInput from './SnippetableInput';

enum DefaultReceiver {
    // Everyone in the course
    Everyone,
    // Users selected in the multiselect.
    Selected,
    // All users _not_ selected in the multiselect.
    NotSelected,
}

@Component({
    components: {
        SnippetableInput,
        UserSelector,
        Toggle,
        Icon,
    },
})
export default class StudentContact extends Vue {
    // When the user has no permission to search through the site users this
    // will be a list of objects with only a `username` property. Otherwise
    // it will be User models.
    @Prop({ required: true }) initialUsers!: ({ username: string } | models.User)[];

    @Prop({ required: true }) canUseSnippets!: boolean;

    @Prop({ required: true }) defaultSubject!: string;

    @Prop({ required: true }) course!: models.Course;

    @Prop({ default: false }) noCancel!: boolean;

    @Prop({ default: false }) resetOnEmail!: boolean;

    @Prop({ default: false }) noEverybodyEmailOption!: boolean;

    @Prop({ default: false }) initiallyEverybodyByDefault!: boolean;

    public users: ({ username: string } | models.User)[] = this.initialUsers;

    public subject: string = this.defaultSubject;

    public body: string = '';

    public selectedDefaultReceiver: DefaultReceiver = this.initiallyEverybodyByDefault ?
        DefaultReceiver.NotSelected :
        DefaultReceiver.Selected;

    public onDestroyHook = () => { };

    public deliveryError: Error | null = null;

    get userSelectorPlaceholder() {
        switch (this.selectedDefaultReceiver) {
            case DefaultReceiver.NotSelected:
                return 'Student not to send an email';
            case DefaultReceiver.Selected:
                return 'Students to send an email';
            default:
                return '';
        }
    }

    destroyed() {
        this.onDestroyHook();
    }

    @Ref() submitButton!: any;

    @Ref() subjectInput!: any;

    async mounted() {
        await this.$afterRerender();
        if (this.subjectInput) {
            this.subjectInput.focus();
        }
    }

    public sendEmail(): Promise<unknown> {
        if (!this.subject || !this.body) {
            throw new Error('Both the body and the subject should not be empty');
        }
        let destroyed = false;
        this.onDestroyHook = () => {
            destroyed = true;
        };

        return this.$http.post(`/api/v1/courses/${this.course.id}/email`, {
            subject: this.subject,
            body: this.body,
            email_all_users: !this.noEverybodyEmailOption && this.shouldEmailAll,
            usernames: this.recipientUsernames,
        }).then(response => {
            if (destroyed) {
                return Promise.resolve();
            }
            const taskResult = new models.TaskResult(response.data.id);
            const { promise, stop } = taskResult.poll();

            this.onDestroyHook = stop;
            return promise;
        });
    }

    get shouldEmailAll() {
        return this.selectedDefaultReceiver !== DefaultReceiver.Selected;
    }

    get recipientUsernames(): string[] {
        if (this.selectedDefaultReceiver === DefaultReceiver.Everyone) {
            return [];
        } else {
            return this.users.map(u => u.username);
        }
    }

    get showRecipientSelector() {
        return this.selectedDefaultReceiver !== DefaultReceiver.Everyone;
    }

    // eslint-disable-next-line class-methods-use-this
    get defaultReceiverOptions(): { text: string, value: DefaultReceiver }[] {
        return [
            {
                text: 'All users in the course',
                value: DefaultReceiver.Everyone,
            },
            {
                text: 'All users selected below',
                value: DefaultReceiver.Selected,
            },
            {
                text: 'All users in the course except those selcted below',
                value: DefaultReceiver.NotSelected,
            },
        ];
    }

    // eslint-disable-next-line class-methods-use-this
    getSuccessfulUsers(data: {
        // eslint-disable-next-line camelcase
        all_users: models.UserServerData[], failed_users: models.UserServerData[]
    }): models.User[] {
        const failed = new Set(data.failed_users.map(x => x.id));
        return data.all_users.filter(u => !failed.has(u.id)).map(u => models.makeUser(u));
    }

    get canListUsers() {
        // eslint-disable-next-line camelcase
        return !!(this.course?.permissions.can_list_course_users);
    }

    afterEmail(): void {
        this.$emit('emailed');
        if (this.resetOnEmail) {
            this.users = this.initialUsers;
        }
    }

    maybeSetDeliveryError(e: Error & { response?: { data?: { code?: string } } }) {
        if (this.$utils.getProps(e, null, 'response', 'data', 'code') === 'MAILING_FAILED') {
            this.deliveryError = e;
        }
    }

    clearUsers() {
        this.users = [];
    }
}
</script>

<style lang="less" scoped>
ul {
    padding-left: 1rem;
}
</style>

<style lang="less">
.student-contact .user-selector .multiselect__tags {
    max-height: 10rem;
    overflow: auto;
}
</style>
