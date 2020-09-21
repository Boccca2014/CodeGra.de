<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="assignment-state" v-if="editable">
    <b-button-group>
        <template v-if="canManageOpenState">
            <b-button-group v-b-popover.window.top.hover="labels[states.HIDDEN]">
                <submit-button class="state-button state-hidden"
                            :variant="hiddenVariant"
                            :duration="0"
                            confirm="true"
                            :submit="() => updateState(states.HIDDEN)">
                    <icon :name="icons[states.HIDDEN]"/>

                    <template #confirm>
                        Students will not be able to view the assignment. Are you
                        sure?
                    </template>
                </submit-button>
            </b-button-group>

            <b-button-group v-b-popover.window.top.hover="labels[states.OPEN]">
                <submit-button class="state-button state-open"
                            :variant="openVariant"
                            :duration="0"
                            confirm="true"
                            :submit="() => updateState(states.OPEN)">
                    <icon :name="icons[states.OPEN]"/>

                    <template #confirm>
                        Students will be able to see the assignment and submit work
                        if the deadline has not passed yet, but they will not be
                        able to see their grade. Are you sure?
                    </template>
                </submit-button>
            </b-button-group>
        </template>

        <b-button-group v-else
                        v-b-popover.window.top.hover="openOrClosePopover">
            <submit-button class="state-button larger state-hidden state-open"
                           :variant="ltiHiddenOpenVariant"
                           :duration="0"
                           confirm="true"
                           :submit="() => updateState(states.OPEN)">
                <icon :name="icons[states.HIDDEN]"/>
                <icon :name="icons[states.OPEN]"/>

                <template #confirm v-if="assignment.availableAt">
                    Students will not be able to see their grade.
                    <template v-if="assignment.availableAt.isBefore($root.$now)">
                        They will be able to see the assignment.
                    </template>
                    <template v-else>
                        They will be able to see the assignment in
                        <cg-relative-time :date="assignment.availableAt"
                                          :now="$root.$now" />.
                    </template>
                </template>
                <template #confirm v-else>
                    Students will not be able to see their grade. Whether they
                    can see the assignment at all is determined by the
                    assignment's state in {{ lmsName }}.
                </template>
            </submit-button>
        </b-button-group>


        <b-button-group v-b-popover.window.top.hover="labels[states.DONE]">
            <submit-button class="state-button state-done"
                           :variant="doneVariant"
                           :duration="0"
                           confirm="true"
                           :submit="() => updateState(states.DONE)">
                <icon :name="icons[states.DONE]"/>

                <template #confirm>
                    Students will be able to see their grade. Are you sure?
                </template>
            </submit-button>
        </b-button-group>
    </b-button-group>
</div>
<icon :name="icons[assignment.state]"
      class="assignment-state state-icon"
      :class="`assignment-state-${labels[assignment.state]}`"
      v-b-popover.window.top.hover="currentStatePopover"
      v-else/>
</template>

<script>
import { mapActions } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/eye-slash';
import 'vue-awesome/icons/clock-o';
import 'vue-awesome/icons/pencil';
import 'vue-awesome/icons/check';

import * as states from '../store/assignment-states';

import Loader from './Loader';
import SubmitButton from './SubmitButton';

export default {
    name: 'assignment-state',

    props: {
        assignment: {
            type: Object,
            default: null,
        },

        editable: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            states,
            labels: {
                [states.HIDDEN]: 'Hidden',
                [states.SUBMITTING]: 'Submitting',
                [states.GRADING]: 'Grading',
                [states.OPEN]: 'Open',
                [states.DONE]: 'Done',
            },
            icons: {
                [states.HIDDEN]: 'eye-slash',
                [states.SUBMITTING]: 'clock-o',
                [states.GRADING]: 'pencil',
                [states.OPEN]: 'clock-o',
                [states.DONE]: 'check',
            },
        };
    },

    computed: {
        ltiHiddenOpenVariant() {
            const st = this.assignment.state;
            return st !== states.DONE ? 'primary' : 'outline-primary';
        },

        hiddenVariant() {
            const st = this.assignment.state;
            return st === states.HIDDEN ? 'danger' : 'outline-danger';
        },

        openVariant() {
            const st = this.assignment.state;
            return st === states.SUBMITTING || st === states.GRADING || st === states.OPEN
                ? 'warning'
                : 'outline-warning';
        },

        doneVariant() {
            const st = this.assignment.state;
            return st === states.DONE ? 'success' : 'outline-success';
        },

        ltiProvider() {
            return this.$utils.getPropMaybe(this.assignment, 'ltiProvider');
        },

        canManageOpenState() {
            if (this.assignment.availableAt) {
                return false;
            }
            return this.ltiProvider.mapOrDefault(prov => !prov.supportsStateManagement, true);
        },

        lmsName() {
            return this.ltiProvider.mapOrDefault(prov => prov.lms, null);
        },

        openOrClosePopover() {
            const availableAt = this.$utils.getProps(this.assignment, null, 'availableAt');
            if (availableAt != null) {
                let base = '';
                const readable = availableAt.clone().local().calendar(this.$root.$now);

                switch (this.assignment.state) {
                case states.GRADING:
                case states.SUBMITTING:
                case states.OPEN:
                    base = `Openend ${readable}`;
                    break;
                case states.HIDDEN:
                    base = `Hidden until ${readable}`;
                    break;
                case states.DONE:
                    if (availableAt.isBefore(this.$root.$now)) {
                        base = `Opened ${readable}`;
                    } else {
                        base = `Hidden until ${readable}`;
                    }
                    break;
                default:
                    base = 'Unknown state';
                    break;
                }

                let managedBy = '';
                if (this.lmsName != null) {
                    managedBy = `, managed by ${this.lmsName}`;
                }
                return `${base}${managedBy}.`;
            }

            let curState = '';
            switch (this.assignment.state) {
            case states.SUBMITTING:
            case states.OPEN:
                curState = ', currently open';
                break;
            case states.HIDDEN:
                curState = ', currently hidden';
                break;
            default:
                break;
            }
            return `Hidden or open, managed by ${this.lmsName}${curState}.`;
        },

        currentStatePopover() {
            if (this.assignment.state === states.HIDDEN && this.assignment.availableAt) {
                const time = this.assignment.availableAt.clone().local().calendar(this.$root.$now);
                return `Hidden until ${time}`;
            }
            return this.labels[this.assignment.state];
        },
    },

    methods: {
        ...mapActions('assignments', ['patchAssignment']),

        updateState(pendingState) {
            return this.patchAssignment({
                assignmentId: this.assignment.id,
                assignmentProps: {
                    state: pendingState,
                },
            });
        },
    },

    components: {
        Icon,
        Loader,
        SubmitButton,
    },
};
</script>

<style lang="less" scoped>
.state-button.larger .fa-icon {
    margin-left: 0;
}
</style>
