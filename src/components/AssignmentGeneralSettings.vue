<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-card header="General"
        class="assignment-general-settings">
    <b-form-group :id="`assignment-type-${uniqueId}`"
                  :label-for="`assignment-type-${uniqueId}-toggle`">
        <template #label>
            Assignment type
        </template>

        <template #description v-if="isLTI">
            Some settings of this assignment are managed through {{ lmsName.extract() }}.
        </template>
        <template #description v-else>
            In exam mode students receive an e-mail with a link to register for
            and access the exam.
        </template>

        <b-form-select
            :id="`assignment-type-${uniqueId}-toggle`"
            v-model="kind"
            :options="kindOptions"
            :disabled="isLTI"/>
    </b-form-group>

    <b-form-group :id="`assignment-name-${uniqueId}`"
                  :label-for="`assignment-name-${uniqueId}-input`"
                  :state="!!name">
        <template #label>
            Assignment name
        </template>

        <template #invalid-feedback>
            The assignment name may not be empty.
        </template>

        <div v-b-popover.top.hover="permissions.canEditName ? '' : 'You cannot change the name of an LTI assignment'">
            <input :id="`assignment-name-${uniqueId}-input`"
                   type="text"
                   class="form-control"
                   v-model="name"
                   :disabled="!permissions.canEditName"
                   @keydown.ctrl.enter="$refs.submitGeneralSettings.onClick"/>
        </div>
    </b-form-group>

    <b-form-group v-if="isExam"
                  :id="`assignment-login-mail-${uniqueId}`"
                  :label-for="`assignment-login-mail-${uniqueId}-input`"
                  :description="loginLinksDescription"
                  :state="!!name">
        <template #label>
            Send login mails
        </template>

        <cg-toggle :id="`assignment-login-mail-${uniqueId}-input`"
                   v-model="sendLoginLinks"
                   class="float-right"
                   style="margin-top: -2rem" />
    </b-form-group>

    <b-form-group :id="`assignment-available-at-${uniqueId}`"
                  :label-for="`assignment-available-at-${uniqueId}-input`"
                  :state="availableAtValid">
        <template #label>
            {{ isExam ? 'Starts' : 'Available' }} at
        </template>

        <template #description>
            The time the assignment should switch from the hidden state to the
            open state.<cg-description-popover hug-text>
                With the default permissions this means that students will be
                able to see the assignment at this moment.
            </cg-description-popover>
        </template>

        <template #invalid-feedback>
            The "Available at" date must be set in exam mode.
        </template>

        <b-input-group v-b-popover.top.hover="availableAtPopover">
            <datetime-picker v-model="availableAt"
                             :disabled="!permissions.canEditAvailableAt"
                             :id="`assignment-available-at-${uniqueId}-input`"
                             placeholder="Manual"/>

            <b-input-group-append
                v-if="permissions.canEditAvailableAt && !isExam"
                v-b-popover.top.hover="availableAt == null ? '' : 'Revert to manual mode.'">

                <b-button
                    @click="availableAt = null"
                    :disabled="!permissions.canEditAvailableAt || availableAt == null"
                    variant="warning">
                    <fa-icon name="reply"/>
                </b-button>
            </b-input-group-append>
        </b-input-group>
    </b-form-group>

    <b-form-group
        v-if="isExam"
        :id="`assignment-deadline-${uniqueId}`"
        :label-for="`assignment-deadline-${uniqueId}-input`"
        :state="examDurationValid">
        <template #label>
            Duration
        </template>

        <template #description>
            Students can submit this long after the exam has become available.
        </template>

        <template #invalid-feedback>
            <div v-if="examDuration == null">
                The exam duration must be set in exam mode.
            </div>

            <div v-else-if="sendLoginLinks && examDuration > maxExamDuration">
                With "Send login mails" enabled, exams can take at most {{
                maxExamDuration }} hours.

                <cg-description-popover hug-text>
                    This is because the login links allow anyone with the link
                    to log in and act on behalf of the connected user. So if
                    a student accidentally leaks their login mail, it can be
                    misused only for a short while.
                </cg-description-popover>
            </div>
        </template>

        <b-input-group append="hours">
            <cg-number-input
                :id="`assignment-deadline-${uniqueId}-input`"
                :min="0"
                :step="1"
                v-model="examDuration"
                @input="deadline = examDeadline" />
        </b-input-group>
    </b-form-group>

    <b-form-group
        v-else
        :state="assignment.hasDeadline"
        :id="`assignment-deadline-${uniqueId}`"
        :label-for="`assignment-deadline-${uniqueId}-input`">
        <template #label>
            Deadline
        </template>

        <template #description>
            Students will not be able to submit work unless a deadline has
            been set.

            <cg-description-popover hug-text v-if="assignment.ltiProvider.isJust()">
                {{ lmsName.extract() }} did not pass this assignment&apos;s
                deadline on to CodeGrade.
            </cg-description-popover>
        </template>

        <template #invalid-feedback>
            The deadline has not been set yet!
        </template>

        <b-input-group v-b-popover.top.hover="deadlinePopover">
            <datetime-picker
                v-model="deadline"
                @input="examDuration = calcExamDuration()"
                :id="`assignment-deadline-${uniqueId}-input`"
                class="assignment-deadline"
                placeholder="None set"
                :disabled="!permissions.canEditDeadline"/>
        </b-input-group>
    </b-form-group>

    <b-form-group v-if="permissions.canEditMaxGrade"
                  :id="`assignment-max-points-${uniqueId}`"
                  :label-for="`assignment-max-points-${uniqueId}-input`">
        <template #label>
            Max points
        </template>

        <template #description>
            The maximum grade it is possible to achieve for this assignment.

            <cg-description-popover hug-text>
                Setting this value enables you to give 'bonus' points for an
                assignment, as a 10 will still be seen as a perfect score.  So
                if this value is 12 a user can score 2 additional bonus points.
                The default value is 10. Existing grades will not be changed by
                changing this value!
            </cg-description-popover>
        </template>

        <b-input-group class="maximum-grade">
            <cg-number-input
                :min="0"
                :step="1"
                :id="`assignment-max-points-${uniqueId}-input`"
                placeholder="10"
                v-model="maxGrade" />

            <b-input-group-append
                v-b-popover.hover.top="maxGrade == null ? '' : 'Reset to the default value.'">
                <b-button
                    variant="warning"
                    @click="maxGrade = null"
                    :disabled="maxGrade == null">
                    <fa-icon name="reply"/>
                </b-button>
            </b-input-group-append>
        </b-input-group>
    </b-form-group>

    <div class="float-right"
         v-b-popover.top.hover="submitGeneralSettingsPopover">
        <cg-submit-button
            ref="submitGeneralSettings"
            :disabled="!!submitGeneralSettingsPopover"
            :confirm="submitGeneralSettingsConfirm"
            :submit="submitGeneralSettings" />
    </div>
</b-card>
</template>

<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';
import { mapActions } from 'vuex';
import { AxiosResponse } from 'axios';
import moment from 'moment';

import * as models from '@/models';

// @ts-ignore
import DatetimePicker from './DatetimePicker';

function optionalText(cond: boolean, text: string) {
    return cond ? text : '';
}

@Component({
    components: {
        DatetimePicker,
    },
    methods: {
        ...mapActions('courses', [
            'patchAssignment',
        ]),
    },
})
export default class AssignmentGeneralSettings extends Vue {
    @Prop({ required: true })
    assignment!: models.Assignment

    name: string | null = null;

    kind: models.AssignmentKind = this.assignment.kind;

    availableAt: string | null = null;

    deadline: string | null = null;

    examDuration: number | null = null;

    maxGrade: number | null = null;

    sendLoginLinks: boolean = true;

    readonly uniqueId: number = this.$utils.getUniqueId();

    patchAssignment!:
        (args: any) => Promise<AxiosResponse<void>>;

    get isNormal() {
        return this.kind === models.AssignmentKind.normal;
    }

    get isExam() {
        return this.kind === models.AssignmentKind.exam;
    }

    get kindOptions() {
        if (this.isLTI) {
            return [{ text: 'LTI', value: this.kind }];
        }

        return [
            { text: 'Normal', value: models.AssignmentKind.normal },
            { text: 'Exam', value: models.AssignmentKind.exam },
        ];
    }

    get loginLinksBeforeTime() {
        return this.$userConfig.loginTokenBeforeTime.map((time: number) => {
            const asMsecs = 1000 * time;
            return moment.duration(asMsecs).humanize();
        });
    }

    get assignmentId() {
        return this.assignment.id;
    }

    @Watch('assignmentId', { immediate: true })
    onAssignmentChanged() {
        this.name = this.assignment.name;
        this.kind = this.assignment.kind;
        this.availableAt = this.$utils.formatNullableDate(
            this.assignment.availableAt,
            true,
        );
        this.deadline = this.$utils.formatNullableDate(
            this.assignment.deadline,
            true,
        );
        this.examDuration = this.calcExamDuration();
        this.maxGrade = this.assignment.max_grade;
        this.sendLoginLinks = this.assignment.send_login_links;
    }

    get permissions() {
        return new models.AssignmentCapabilities(this.assignment);
    }

    get nothingChanged() {
        if (this.kind !== this.assignment.kind) {
            return false;
        }

        if (this.name !== this.assignment.name) {
            return false;
        }

        if (this.sendLoginLinks !== this.assignment.send_login_links) {
            return false;
        }

        if (this.assignment.availableAt == null) {
            if (this.availableAt != null) {
                return false;
            }
        } else if (!this.assignment.availableAt.isSame(this.availableAt)) {
            return false;
        }

        if (this.isExam) {
            if (this.examDuration !== this.calcExamDuration()) {
                return false;
            }
        } else if (this.assignment.deadline == null) {
            if (this.deadline != null) {
                return false;
            }
        } else if (!this.assignment.deadline.isSame(this.deadline)) {
            return false;
        }

        if (this.maxGrade !== this.assignment.max_grade) {
            return false;
        }

        return true;
    }

    get allDataValid() {
        if (this.name == null || this.name === '') {
            return false;
        }

        if (!this.availableAtValid) {
            return false;
        }

        if (this.isExam && !this.examDurationValid) {
            return false;
        }

        return true;
    }

    get availableAtValid() {
        if (!this.isExam) {
            return true;
        }

        if (this.availableAt == null) {
            return false;
        }

        return true;
    }

    get examDurationValid() {
        if (this.examDuration == null) {
            return false;
        }

        if (!this.sendLoginLinks) {
            return true;
        }

        if (this.examDuration > this.maxExamDuration) {
            return false;
        }

        return true;
    }

    get maxExamDuration() {
        return this.$userConfig.examLoginMaxLength / 60 / 60;
    }

    get isLTI() {
        return this.assignment.is_lti;
    }

    get lmsName() {
        return this.assignment.ltiProvider.map(prov => prov.lms);
    }

    get availableAtPopover() {
        return optionalText(
            !(this.permissions.canEditAvailableAt || this.lmsName.isNothing()),
            `The "available at" date is managed by ${this.lmsName.extract()}`,
        );
    }

    deadlinePopover() {
        return optionalText(
            !(this.permissions.canEditDeadline || this.lmsName.isNothing()),
            `The deadline is managed by ${this.lmsName.extract()}`,
        );
    }

    get examDeadline() {
        const { availableAt, examDuration } = this;

        if (availableAt == null || examDuration == null) {
            return null;
        } else {
            return this.$utils.formatDate(
                this.$utils.toMoment(availableAt).add(examDuration, 'hour'),
                true,
            );
        }
    }


    get loginLinksDescription() {
        const prefix = 'Send a mail to access the exam at the following times: ';
        const extra = this.loginLinksBeforeTime.map((time: string) => `${time} before the exam`);
        return `${prefix}${this.$utils.readableJoin(extra)}`;
    }

    calcExamDuration() {
        const { assignment, availableAt } = this;

        if (assignment.deadline == null || availableAt == null) {
            return null;
        } else {
            const d = assignment.deadline.diff(availableAt);
            return moment.duration(d).asHours();
        }
    }

    get submitGeneralSettingsPopover() {
        if (this.nothingChanged) {
            return 'Nothing has changed.';
        } else if (!this.allDataValid) {
            return 'Cannot submit while some data is invalid.';
        } else {
            return '';
        }
    }

    get submitGeneralSettingsConfirm() {
        const { availableAt, isExam, sendLoginLinks } = this;

        if (
            !isExam ||
            !sendLoginLinks ||
            availableAt == null ||
            this.$utils.toMoment(availableAt).isSame(this.assignment.availableAt)
        ) {
            return '';
        }

        return optionalText(
            this.$utils.toMoment(availableAt).isBefore(this.$root.$now),
            `You have set the assignment to become available in the past.
            While this is fine, students will only be notified of the exam via
            email once, right now.`,
        );
    }

    submitGeneralSettings() {
        let deadline = this.deadline;
        if (this.isExam) {
            deadline = this.examDeadline;
        }

        return this.patchAssignment({
            assignmentId: this.assignment.id,
            assignmentProps: {
                name: this.name,
                kind: this.kind,
                available_at: this.$utils.formatNullableDate(this.availableAt, true),
                deadline: this.$utils.formatNullableDate(deadline, true) || undefined,
                maximumGrade: this.maxGrade,
                send_login_links: this.isExam && this.sendLoginLinks,
            },
        });
    }
}
</script>