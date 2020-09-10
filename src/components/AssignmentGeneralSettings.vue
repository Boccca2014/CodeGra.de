<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-card header="General"
        class="assignment-general-settings">
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

    <b-form-group :id="`assignment-kind-${uniqueId}`"
                  :label-for="`assignment-kind-${uniqueId}-select`">
        <template #label>
            Assignment type
        </template>

        <template #description v-if="isLTI">
            Some settings of this assignment are managed through {{ lmsName.extract() }}.
        </template>
        <template #description v-else-if="isExam">
            In exam mode students receive an e-mail with a link to access the exam.

            <cg-description-popover hug-text>
                Students will only be able to see the contents of this course
                while logged in through the link they have received.
            </cg-description-popover>
        </template>

        <b-form-select
            :id="`assignment-kind-${uniqueId}-select`"
            v-model="kind"
            :options="kindOptions"
            :disabled="isLTI"/>
    </b-form-group>

    <b-form-group v-if="isExam"
                  :id="`assignment-login-mail-${uniqueId}`"
                  :label-for="`assignment-login-mail-${uniqueId}-toggle`"
                  :description="loginLinksDescription"
                  :state="!!name">
        <template #label>
            Send login mails
        </template>

        <cg-toggle :id="`assignment-login-mail-${uniqueId}-toggle`"
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
            The available at date

            <template v-if="isExam">
                must be set in exam mode.
            </template>

            <template v-else-if="availableAt != null">
                must be before the deadline.
            </template>
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
                    :id="`assignment-available-at-${uniqueId}-reset`"
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
            <div v-if="examDuration.isLeft()">
                <template v-for="err in examDuration.extract()">
                    {{ $utils.getErrorMessage(err) }}
                </template>
            </div>

            <div v-if="examTooLong">
                With "Send login mails" enabled, exams can take at most
                {{ maxExamDuration }} hours.

                <cg-description-popover hug-text>
                    This is because the login links allow anyone with the link
                    to log in and act on behalf of the connected user. So if
                    a student accidentally leaks their login mail, it can be
                    misused only for a short while.
                </cg-description-popover>
            </div>
        </template>

        <b-input-group>
            <cg-number-input
                :id="`assignment-deadline-hours-${uniqueId}-input`"
                name="Exam duration hours"
                :required="true"
                :min="0"
                :step="1"
                v-model="examDurationHours"
                @input="deadline = examDeadline"
                @keydown.native.ctrl.enter="$refs.submitGeneralSettings.onClick"/>

            <b-input-group-append is-text>
                hours
            </b-input-group-append>

            <cg-number-input
                :id="`assignment-deadline-minutes-${uniqueId}-input`"
                name="Exam duration minutes"
                :required="true"
                :min="0"
                :step="1"
                v-model="examDurationMinutes"
                @input="deadline = examDeadline"
                @keydown.native.ctrl.enter="$refs.submitGeneralSettings.onClick"/>

            <b-input-group-append is-text>
                minutes
            </b-input-group-append>
        </b-input-group>
    </b-form-group>

    <b-form-group
        v-else
        :state="deadlineValid"
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
            <template v-if="deadline == null">
                The deadline has not been set yet!
            </template>
            <template v-else>
                The deadline must be after the available at date.
            </template>
        </template>

        <b-input-group v-b-popover.top.hover="deadlinePopover">
            <datetime-picker
                v-model="deadline"
                @input="recalcExamDuration"
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
                :id="`assignment-max-points-${uniqueId}-input`"
                :min="0"
                :step="1"
                placeholder="10"
                v-model="maxGrade"
                @keydown.native.ctrl.enter="$refs.submitGeneralSettings.onClick"/>

            <b-input-group-append
                v-b-popover.hover.top="maxGradeEmpty ? '' : 'Reset to the default value.'">
                <b-button
                    variant="warning"
                    @click="resetMaxGrade"
                    :disabled="maxGradeEmpty">
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
import moment from 'moment';

import * as models from '@/models';
import { Either, Left, Maybe, Nothing, formatNullableDate } from '@/utils';

import { AssignmentsStore } from '@/store';

// @ts-ignore
import DatetimePicker from './DatetimePicker';
import { NumberInputValue, numberInputValue } from './NumberInput';

function optionalText(cond: boolean, text: string) {
    return cond ? text : '';
}

@Component({
    components: {
        DatetimePicker,
    },
})
export default class AssignmentGeneralSettings extends Vue {
    @Prop({ required: true })
    assignment!: models.Assignment

    name: string | null = null;

    kind: models.AssignmentKind = this.assignment.kind;

    availableAt: string | null = null;

    deadline: string | null = null;

    examDurationHours: NumberInputValue = numberInputValue(null);

    examDurationMinutes: NumberInputValue = numberInputValue(null);

    maxGrade: NumberInputValue = numberInputValue(null);

    sendLoginLinks: boolean = true;

    readonly uniqueId: number = this.$utils.getUniqueId();

    @Watch('availableAt')
    onAvailableAtChanged() {
        if (this.isExam) {
            this.deadline = this.examDeadline;
        } else {
            this.recalcExamDuration();
        }
    }

    get isExam() {
        return this.kind === models.AssignmentKind.exam;
    }

    get examDuration(): Either<Error[], Maybe<number>> {
        const errors = Either.lefts([
            this.examDurationHours,
            this.examDurationMinutes,
        ]);

        if (errors.length > 0) {
            return Left(errors);
        }

        const hours = this.examDurationHours.orDefault(Nothing).orDefault(0);
        const minutes = this.examDurationMinutes.orDefault(Nothing).orDefault(0);

        if (hours === 0 && minutes === 0) {
            return Left([
                new Error('The exam must take longer than 0 minutes!'),
            ]);
        }

        return numberInputValue(hours + minutes / 60);
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
        this.recalcExamDuration();
        this.maxGrade = numberInputValue(this.assignment.max_grade);
        this.sendLoginLinks = this.assignment.send_login_links;
    }

    get permissions() {
        return new models.AssignmentCapabilities(this.assignment);
    }

    get kindChanged() {
        return this.kind !== this.assignment.kind;
    }

    get nameChanged() {
        return this.name !== this.assignment.name;
    }

    get sendLoginLinksChanged() {
        return this.sendLoginLinks !== this.assignment.send_login_links;
    }

    get availableAtChanged() {
        if (this.assignment.availableAt == null) {
            return this.availableAt != null;
        } else {
            return !this.assignment.availableAt.isSame(this.availableAt);
        }
    }

    get deadlineChanged() {
        if (this.isExam) {
            return !this.assignment.deadline.isSame(this.examDeadline);
        } else if (this.assignment.deadline.isValid()) {
            return !this.assignment.deadline.isSame(this.deadline);
        } else {
            return this.deadline != null;
        }
    }

    get maxGradeChanged() {
        return this.maxGrade.either(
            () => false,
            maybeMaxGrade => maybeMaxGrade.extractNullable() !== this.assignment.max_grade,
        );
    }

    get examTooLong() {
        if (!this.sendLoginLinks) {
            return false;
        }

        return this.examDuration.orDefault(Nothing).mapOrDefault(
            duration => duration > this.maxExamDuration,
            false,
        );
    }

    get nothingChanged() {
        return !(
            this.kindChanged ||
            this.nameChanged ||
            this.sendLoginLinksChanged ||
            this.availableAtChanged ||
            this.deadlineChanged ||
            this.maxGradeChanged
        );
    }

    get dataValidForSubmission() {
        if (this.name == null || this.name === '') {
            return false;
        }

        if (!this.availableAtValid) {
            return false;
        }

        if (this.deadline != null && !this.deadlineValid) {
            return false;
        }

        if (!this.examDurationValid) {
            return false;
        }

        return true;
    }

    get availableAtValid() {
        const availableAt = this.$utils.toMomentNullable(this.availableAt);

        if (this.isExam) {
            if (availableAt == null) {
                return false;
            }
        } else {
            if (availableAt == null || this.deadline == null) {
                return true;
            }

            if (availableAt.isAfter(this.deadline)) {
                return false;
            }
        }

        return true;
    }

    get deadlineValid() {
        const deadline = this.$utils.toMomentNullable(this.deadline);

        if (deadline == null) {
            return false;
        }

        if (this.availableAt == null) {
            return true;
        }

        if (deadline.isBefore(this.availableAt)) {
            return false;
        }

        return true;
    }

    get examDurationValid() {
        if (!this.isExam) {
            return true;
        }

        return this.examDuration.orDefault(Nothing).mapOrDefault(
            duration => (this.sendLoginLinks ? duration <= this.maxExamDuration : true),
            false,
        );
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

    get deadlinePopover() {
        return optionalText(
            !(this.permissions.canEditDeadline || this.lmsName.isNothing()),
            `The deadline is managed by ${this.lmsName.extract()}`,
        );
    }

    get examDeadline() {
        const { availableAt, examDuration } = this;

        if (availableAt == null) {
            return null;
        }

        return examDuration.orDefault(Nothing).mapOrDefault(
            duration => this.$utils.formatDate(
                this.$utils.toMoment(availableAt).add(duration, 'hour'),
                true,
            ),
            null,
        );
    }


    get loginLinksDescription() {
        const prefix = 'Send a mail to access the exam at the following times: ';
        const extra = this.loginLinksBeforeTime.map((time: string) => `${time} before the exam`);
        return `${prefix}${this.$utils.readableJoin(extra)}`;
    }

    get maxGradeEmpty() {
        return this.maxGrade.either(
            () => false,
            maybeMaxGrade => maybeMaxGrade.isNothing(),
        );
    }

    resetMaxGrade() {
        this.maxGrade = numberInputValue(null);
    }

    recalcExamDuration() {
        const { deadline, availableAt } = this;

        if (deadline == null || availableAt == null) {
            this.examDurationHours = numberInputValue(null);
            this.examDurationMinutes = numberInputValue(null);
        } else {
            const d = this.$utils.toMoment(deadline).diff(availableAt);
            const hours = moment.duration(d).asHours();

            this.examDurationHours = numberInputValue(Math.floor(hours));
            this.examDurationMinutes = numberInputValue(Math.round(60 * (hours % 1)));
        }
    }

    get submitGeneralSettingsPopover() {
        if (this.nothingChanged) {
            return 'Nothing has changed.';
        } else if (!this.dataValidForSubmission) {
            return 'Some data is invalid.';
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
        let setDeadline = this.deadline;
        if (this.isExam) {
            setDeadline = this.examDeadline;
        }
        function formatDate<T>(date: string | null, dflt: T) {
            return formatNullableDate(date, true) ?? dflt;
        }

        const { name, availableAt, deadline, maxGrade }: {
            name: string | undefined;
            availableAt: string | undefined | null;
            deadline: string | undefined;
            maxGrade: number | null | undefined,
        } = this.assignment.ltiProvider.mapOrDefault(
            prov => {
                let avail;
                if (!prov.supportsStateManagement) {
                    avail = formatDate(this.availableAt, null);
                }
                let maxGrade;
                if (supportsBonusPoints) {
                    maxGrade = this.maxGrade.orDefault(Nothing).extractNullable();
                }

                return {
                    name: undefined as string | undefined,
                    deadline: (prov.supportsDeadline ?
                        undefined :
                        formatDate(setDeadline, undefined)),
                    availableAt: avail,
                    maxGrade,
                };
            },
            {
                name: this.name ?? undefined,
                availableAt: formatDate(this.availableAt, null),
                deadline: formatDate(setDeadline, undefined),
                max_grade: this.maxGrade.orDefault(Nothing).extractNullable(),
            },
        );

        return AssignmentsStore.patchAssignment({
            assignmentId: this.assignment.id,
            assignmentProps: {
                name,
                available_at: availableAt,
                deadline,
                kind: this.kind,
                max_grade: maxGrade,
                send_login_links: this.isExam && this.sendLoginLinks,
            },
        });
    }
}
</script>
