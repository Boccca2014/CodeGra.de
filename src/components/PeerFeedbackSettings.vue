<template>
<div class="peer-feedback-settings">
    <div v-if="!enabled"
         class="d-flex flex-column align-items-center">
        <b-button style="height: 12rem; width: 12rem;"
                  @click="enable"
                  :disabled="hasGroupSet">
            <fa-icon name="comments-o" :scale="6" />
            <p>Enable peer feedback</p>
        </b-button>

        <div v-if="hasGroupSet"
             class="mt-3">
            This is a group assignment, but peer feedback is not yet supported
            for group assignments.
        </div>
    </div>

    <template v-else>
        <b-form-group :id="`peer-feedback-amount-${uniqueId}`"
                      :label-for="`peer-feedback-amount-${uniqueId}-input`"
                      :state="amount.isRight()">
            <template #label>
                Amount of students
            </template>

            <template #description>
                The amount of students that each student must review.
            </template>

            <template #invalid-feedback>
                {{ $utils.getErrorMessage(amount.extract()) }}
            </template>

            <b-input-group>
                <cg-number-input :id="`peer-feedback-amount-${uniqueId}-input`"
                                 v-model="amount"
                                 name="Amount of students"
                                 :required="true"
                                 :min="1"
                                 @keyup.ctrl.enter.native="doSubmit"/>
            </b-input-group>
        </b-form-group>

        <b-form-group :id="`peer-feedback-time-${uniqueId}`"
                      :label-for="`peer-feedback-time-${uniqueId}-days-input`"
                      :state="days.isRight() && hours.isRight()">
            <template #label>
                Time to give peer feedback
            </template>

            <template #description>
                The amount of time students have to give feedback on the
                submissions they were assigned, after the deadline of
                this assignment has passed.
            </template>

            <template #invalid-feedback>
                <div v-if="days.isLeft()">
                    {{ $utils.getErrorMessage(days.extract()) }}
                </div>
                <div v-if="hours.isLeft()">
                    {{ $utils.getErrorMessage(hours.extract()) }}
                </div>
            </template>

            <b-input-group>
                <cg-number-input :id="`peer-feedback-time-${uniqueId}-days-input`"
                                 v-model="days"
                                 name="Days"
                                 :required="true"
                                 :min="0"
                                 @keyup.ctrl.enter.native="doSubmit"/>

                <b-input-group-prepend is-text>
                    Days
                </b-input-group-prepend>

                <cg-number-input :id="`peer-feedback-time-${uniqueId}-hours-input`"
                                 v-model="hours"
                                 name="Hours"
                                 :required="true"
                                 :min="0"
                                 :max="24"
                                 @keyup.ctrl.enter.native="doSubmit"/>

                <b-input-group-prepend is-text>
                    Hours
                </b-input-group-prepend>
            </b-input-group>
        </b-form-group>

        <b-form-group :id="`peer-feedback-auto-approve-${uniqueId}`"
                      :label-for="`peer-feedback-auto-approve-${uniqueId}-input`">
            <template #label>
                Automatically approve comments
            </template>

            <template #description>
                Should new peer feedback comments be automatically approved.

                <cg-description-popover hug-text>
                    Changing this value does not change the approval status of
                    existing comments.
                </cg-description-popover>
            </template>

            <cg-toggle :id="`peer-feedback-auto-approve-${uniqueId}-input`"
                       v-model="autoApproved"
                       class="float-right"
                       style="margin-top: -2rem;"
                       label-on="Yes"
                       label-off="No" />
        </b-form-group>

        <b-button-toolbar class="justify-content-end">
            <cg-submit-button :submit="disable"
                              @after-success="afterDisable"
                              confirm="Are you sure you want to disable peer feedback?"
                              variant="danger"
                              label="Disable"
                              class="mr-2"/>
            <div v-b-popover.top.hover="submitButtonPopover">
                <cg-submit-button :submit="submit"
                                  @after-success="afterSubmit"
                                  :disabled="!!submitButtonPopover"
                                  :confirm="shouldConfirmOnSubmit"
                                  ref="submitButton">
                    <template #confirm>
                        Changing the amount of students will redistribute all
                        students. If some students have already given peer feedback
                        to other students they will not be able to see their own
                        given feedback again, although it is not deleted from the
                        server either. Are you sure you want to change it?
                    </template>
                </cg-submit-button>
            </div>
        </b-button-toolbar>
    </template>
</div>
</template>

<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';

import 'vue-awesome/icons/comments-o';

import * as models from '@/models';
import { AssignmentsStore } from '@/store';
import { Either, Right, Maybe, Nothing } from '@/utils';

import { NumberInputValue, numberInputValue } from './NumberInput';
// @ts-ignore
import Toggle from './Toggle';

function hoursToSeconds(hours: number): number {
    return hours * 60 * 60;
}

function daysToSeconds(days: number): number {
    return hoursToSeconds(days * 24);
}

function secondsToDays(secs?: number | null): NumberInputValue {
    return Right(Maybe.fromNullable(secs).map(x => Math.floor(x / daysToSeconds(1))));
}

function secondsToHours(secs?: number | null): NumberInputValue {
    return Right(Maybe.fromNullable(secs).map(x => Math.floor((x % daysToSeconds(1)) / 60 / 60)));
}

@Component({
    components: {
        Toggle,
    },
})
export default class PeerFeedbackSettings extends Vue {
    @Prop({ required: true }) assignment!: models.Assignment;

    get peerFeedbackSettings(): null | models.AssignmentPeerFeedbackSettings {
        return this.assignment.peer_feedback_settings;
    }

    enabled: boolean = false;

    amount: NumberInputValue = numberInputValue(this.peerFeedbackSettings?.amount ?? 0);

    days: NumberInputValue = secondsToDays(this.peerFeedbackSettings?.time);

    hours: NumberInputValue = secondsToHours(this.peerFeedbackSettings?.time);

    readonly uniqueId: number = this.$utils.getUniqueId();

    // eslint-disable-next-line camelcase
    autoApproved: boolean = this.peerFeedbackSettings?.auto_approved ?? false;

    @Watch('assignmentId', { immediate: true })
    onAssignmentIdChanged() {
        this.enabled = this.peerFeedbackSettings != null;
    }

    get totalTime() {
        const days = this.days.orDefault(Nothing).map(daysToSeconds);
        const hours = this.hours.orDefault(Nothing).map(hoursToSeconds);
        return days.chain(x => hours.map(y => x + y));
    }

    updatePeerFeedbackSettings(settings: models.AssignmentPeerFeedbackSettings | null): void {
        AssignmentsStore.updateAssignment({
            assignmentId: this.assignment.id,
            assignmentProps: { peer_feedback_settings: settings },
        });
    }

    get url() {
        return `/api/v1/assignments/${this.assignment.id}/peer_feedback_settings`;
    }

    enable() {
        this.enabled = true;
        this.days = numberInputValue(7);
        this.hours = numberInputValue(0);
        this.amount = numberInputValue(1);
        this.autoApproved = false;
    }

    submit() {
        this.validateSettings();
        return this.$http.put(this.url, {
            time: this.totalTime.extractNullable(),
            amount: this.amount.orDefault(Nothing).extractNullable(),
            auto_approved: this.autoApproved,
        });
    }

    afterSubmit(res: any) {
        this.updatePeerFeedbackSettings(res.data);
    }

    disable() {
        return this.$http.delete(this.url);
    }

    afterDisable() {
        this.enabled = false;
        this.updatePeerFeedbackSettings(null);
    }

    async doSubmit() {
        const btn = await this.$waitForRef('submitButton');
        if (btn != null) {
            (btn as any).onClick();
        }
    }

    get hasGroupSet() {
        // eslint-disable-next-line camelcase
        return this.assignment?.group_set != null;
    }

    get nothingChanged() {
        // eslint-disable-next-line camelcase
        if (this.autoApproved !== this.peerFeedbackSettings?.auto_approved) {
            return false;
        }

        const amountChanged = this.amount.orDefault(Nothing).mapOrDefault(
            amount => amount !== this.peerFeedbackSettings?.amount,
            true,
        );

        const timeChanged = this.totalTime.mapOrDefault(
            time => time !== this.peerFeedbackSettings?.time,
            true,
        );

        return !(amountChanged || timeChanged);
    }

    get submitButtonPopover() {
        if (this.nothingChanged) {
            return 'Nothing has changed.';
        } else if (this.errorMessages.length > 0) {
            return 'Some data is invalid.';
        } else {
            return '';
        }
    }

    get shouldConfirmOnSubmit() {
        return this.amount.orDefault(Nothing).mapOrDefault(
            amount => (this.peerFeedbackSettings?.amount !== amount ? 'true' : ''),
            '',
        );
    }

    get errorMessages() {
        return Either.lefts([
            this.amount,
            this.days,
            this.hours,
        ]).map(err => this.$utils.getErrorMessage(err));
    }

    validateSettings(): void {
        if (this.errorMessages.length > 0) {
            const msgs = this.$utils.readableJoin(this.errorMessages);
            throw new Error(`The peer feedback settings are not valid because: ${msgs}.`);
        }
    }
}
</script>
