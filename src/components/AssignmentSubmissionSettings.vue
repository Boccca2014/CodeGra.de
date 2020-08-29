<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-card header="Submission settings"
        class="assignment-submission-settings">
    <b-form-group :state="submitTypesValid">
        <template #label>
            Allowed upload types
        </template>

        <template #description>
            Select how you want your student to hand in their submissions.
        </template>

        <template #invalid-feedback>
            Enable at least one way of uploading.
        </template>

        <assignment-submit-types
            :assignment-id="assignmentId"
            v-model="submitTypes" />
    </b-form-group>

    <submission-limits
        v-model="submissionLimits"
        @keydown.ctrl.enter.native="$refs.submitSubmissionSettings.onClick()" />

    <div class="float-right"
         v-b-popover.top.hover="submitButtonPopover">
        <cg-submit-button
            ref="submitSubmissionSettings"
            :disabled="!!submitButtonPopover"
            :submit="submitSubmissionSettings" />
    </div>
</b-card>
</template>

<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';

import * as models from '@/models';
import { Right } from '@/utils';
import { AssignmentsStore } from '@/store/modules/assignments';

// @ts-ignore
import AssignmentSubmitTypes, { AssignmentSubmitTypesValue } from './AssignmentSubmitTypes';
// @ts-ignore
import SubmissionLimits, { SubmissionLimitValue } from './SubmissionLimits';

@Component({
    components: {
        AssignmentSubmitTypes,
        SubmissionLimits,
    },
})
export default class AssignmentSubmissionSettings extends Vue {
    @Prop({ required: true })
    assignment!: models.Assignment

    submitTypes: AssignmentSubmitTypesValue = Right(this.assigSubmitTypes);

    submissionLimits: SubmissionLimitValue = Right(this.assigSubmissionLimits);

    readonly uniqueId: number = this.$utils.getUniqueId();

    get assignmentId() {
        return this.assignment.id;
    }

    @Watch('assignmentId', { immediate: true })
    onAssignmentChanged() {
        this.submitTypes = Right(this.assigSubmitTypes);
        this.submissionLimits = Right(this.assigSubmissionLimits);
    }

    get assigSubmitTypes() {
        return {
            files: this.assignment.files_upload_enabled,
            webhook: this.assignment.webhook_upload_enabled,
        };
    }

    get assigSubmissionLimits() {
        return {
            maxSubmissions: this.assignment.max_submissions,
            coolOff: {
                period: this.assignment.coolOffPeriod.asMinutes(),
                amount: this.assignment.amount_in_cool_off_period,
            },
        };
    }

    get permissions() {
        return new models.AssignmentCapabilities(this.assignment);
    }

    get submitTypesChanged() {
        return this.submitTypes.either(
            () => false,
            types => !this.$utils.deepEquals(types, this.assigSubmitTypes),
        );
    }

    get submissionLimitsChanged() {
        return this.submissionLimits.either(
            () => false,
            limits => !this.$utils.deepEquals(limits, this.assigSubmissionLimits),
        );
    }

    get nothingChanged() {
        return !this.submitTypesChanged && !this.submissionLimitsChanged;
    }

    get submitTypesValid() {
        return this.submitTypes.isRight();
    }

    get submissionLimitsValid() {
        return this.submissionLimits.isRight();
    }

    get allDataValid() {
        return this.submitTypesValid && this.submissionLimitsValid;
    }

    get submitButtonPopover() {
        if (this.nothingChanged) {
            return 'Nothing has changed.';
        } else if (!this.allDataValid) {
            return 'Some data is invalid.';
        } else {
            return '';
        }
    }

    submitSubmissionSettings() {
        if (!this.allDataValid) {
            return Promise.reject();
        }

        const types = this.submitTypes.unsafeCoerce();
        const limits = this.submissionLimits.unsafeCoerce();

        return AssignmentsStore.patchAssignment({
            assignmentId: this.assignment.id,
            assignmentProps: {
                files_upload_enabled: types.files,
                webhook_upload_enabled: types.webhook,
                max_submissions: limits.maxSubmissions,
                cool_off_period: limits.coolOff.period ? 60 * limits.coolOff.period : 0,
                amount_in_cool_off_period: limits.coolOff.amount ?? undefined,
            },
        });
    }
}
</script>
