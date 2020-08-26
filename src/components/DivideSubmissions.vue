<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="divide-submissions mb-3">
    <table class="table table-striped grader-list border-bottom mb-3">
        <thead>
            <tr>
                <th class="name shrink">Grader</th>
                <th class="weight">Weight</th>
                <th class="percentage shrink">Percent</th>
            </tr>
        </thead>

        <tbody :class="{ 'disabled-table': tableDisabled }"
               v-b-popover.top.hover="textDisabledPopover">
            <tr v-for="grader in graders"
                :class="{ 'text-muted': tableDisabled }"
                class="grader">
                <td class="name shrink">
                    <b-form-checkbox @change="graderChanged(grader.userId)"
                                     :disabled="tableDisabled"
                                     :checked="graderWeights[grader.userId] != 0">
                        <user :user="grader.user"/>
                    </b-form-checkbox>
                </td>
                <td class="weight p-0 align-bottom">
                    <input class="form-control"
                           :class="{ 'text-muted': tableDisabled }"
                           :disabled="tableDisabled"
                           type="number"
                           min="0"
                           step="any"
                           ref="inputField"
                           :data-user-id="grader.userId"
                           @keydown.ctrl.enter="$refs.submitButton.onClick"
                           v-model.number="graderWeights[grader.userId]"/>
                </td>
                <td class="percentage shrink">
                    {{ (100 * graderWeights[grader.userId] / totalWeight).toFixed(1) }}%
                </td>
            </tr>
        </tbody>
    </table>

    <b-button-toolbar v-if="graders.length"
                      justify
                      class="button-bar flex-row mx-3">
        <multiselect class="assignment-selector mr-3 flex-grow-1"
                     :disabled="divisionChildren.length > 0"
                     v-model="importAssignment"
                     :options="otherAssignments"
                     :searchable="true"
                     :multiple="false"
                     track-by="id"
                     label="name"
                     placeholder="Connect divisions to"
                     :close-on-select="true"
                     :hide-selected="false"
                     :internal-search="true"
                     :loading="false">
            <template slot="option" slot-scope="prop">
                <span :class="{ 'disabled-option': getDivisionParent(prop.option) }">
                    {{ prop.option.name }}
                </span>
            </template>
            <span slot="noResult">
                No results were found.
            </span>
        </multiselect>

        <div id="division-submit-button-wrapper"
             class="flex-grow-0">
            <submit-button label="Divide"
                           :disabled="divisionChildren.length > 0 || invalidParentSelected"
                           :submit="divideSubmissions"
                           @success="afterDivideSubmissions"
                           ref="submitButton"/>
        </div>

        <b-popover v-if="invalidParentSelected"
                   triggers="click blur hover"
                   placement="top"
                   show
                   target="division-submit-button-wrapper">
            <div class="text-justify">
                The division of the selected assignment is determined by
                {{getDivisionParent(importAssignment).name}}, so you cannot
                connect to this assignment.
            </div>
        </b-popover>
    </b-button-toolbar>
    <span v-else>No graders found for this assignment</span>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';
import Multiselect from 'vue-multiselect';

import Loader from './Loader';
import SubmitButton from './SubmitButton';
import User from './User';

export default {
    name: 'divide-submissions',

    props: {
        assignment: {
            type: Object,
            default: null,
        },

        graders: {
            type: Array,
            default: null,
        },
    },

    data() {
        return {
            importAssignment: null,
            graderWeights: {},
        };
    },

    watch: {
        graders: {
            immediate: true,
            handler() {
                this.graderWeights = this.resetGraderWeights();
            },
        },

        currentDivisionParent(newVal) {
            if (newVal != null && this.importAssignment != null) {
                this.importAssignment = {
                    id: newVal.id,
                    name: newVal.name,
                };
            }
        },
    },

    mounted() {
        if (this.currentDivisionParent) {
            const a = this.currentDivisionParent;
            this.importAssignment = { id: a.id, name: a.name };
        }
    },

    computed: {
        ...mapGetters('courses', ['courses', 'assignments']),

        currentDivisionParent() {
            return this.assignments[this.assignment.division_parent_id];
        },

        textDisabledPopover() {
            if (this.divisionChildren.length > 0) {
                const other = this.divisionChildren.map(a => a.name).join(', ');
                return `The graders of ${other} are connected to this assignment. This means you cannot change the division of this assignment.`;
            } else if (
                this.importAssignment &&
                this.currentDivisionParent &&
                this.currentDivisionParent.id === this.importAssignment.id
            ) {
                return `These values are determined by ${this.importAssignment.name}.`;
            } else if (this.importAssignment) {
                return `These values will be determined by ${
                    this.importAssignment.name
                } when you connect to it.`;
            } else {
                return '';
            }
        },

        invalidParentSelected() {
            return this.importAssignment && !!this.getDivisionParent(this.importAssignment);
        },

        divisionChildren() {
            return this.courses[this.assignment.course.id].assignments
                .filter(a => a.division_parent_id === this.assignment.id)
                .map(a => ({ id: a.id, name: a.name }));
        },

        tableDisabled() {
            return this.divisionChildren.length > 0 || !!this.importAssignment;
        },

        totalWeight() {
            const graderWeight = Object.values(this.graderWeights).reduce(
                (acc, w) => acc + (w || 0),
                0,
            );
            return graderWeight === 0 ? 1 : graderWeight;
        },

        otherAssignments() {
            return this.courses[this.assignment.course.id].assignments
                .filter(
                    a => a.id !== this.assignment.id,
                    // This map is needed as a recursion error occurs otherwise
                )
                .map(a => ({
                    id: a.id,
                    name: a.name,
                }));
        },
    },

    methods: {
        ...mapActions('courses', ['updateAssignment']),
        ...mapActions('submissions', ['forceLoadSubmissions']),

        getDivisionParent(assig) {
            return this.assignments[this.assignments[assig.id].division_parent_id];
        },

        graderChanged(userId) {
            this.graderWeights[userId] = this.graderWeights[userId] ? 0 : 1;
            const field = this.$refs.inputField.find(f =>
                f.getAttribute('data-user-id') === `${userId}`,
            );
            if (field != null) {
                field.focus();
            }
        },

        resetGraderWeights() {
            return this.$utils.mapToObject(
                this.graders,
                grader => [grader.userId, grader.weight],
            );
        },

        divideSubmissions() {
            if (this.importAssignment) {
                return this.$http.patch(
                    `/api/v1/assignments/${this.assignment.id}/division_parent`,
                    {
                        parent_id: this.importAssignment.id,
                    },
                );
            } else {
                const negativeWeights = Object.values(this.graders)
                    .filter(x => this.graderWeights[x.userId] < 0);

                if (negativeWeights.length) {
                    const names = negativeWeights.map(x => x.name).join(', ');
                    const multi = negativeWeights.length > 1;
                    throw new Error(
                        `Negative weights are not allowed, but the
                        weight${multi ? 's' : ''} for ${names}
                        ${multi ? 'are' : 'is'} negative.`,
                    );
                }

                let req = Promise.resolve();
                if (this.currentDivisionParent != null) {
                    req = req.then(() =>
                        this.$http.patch(
                            `/api/v1/assignments/${this.assignment.id}/division_parent`,
                            {
                                parent_id: null,
                            },
                        ),
                    );
                }

                return req.then(() =>
                    this.$http.patch(`/api/v1/assignments/${this.assignment.id}/divide`, {
                        graders: Object.values(this.graders)
                            .filter(x => this.graderWeights[x.userId] !== 0)
                            .reduce((res, g) => {
                                res[`${g.userId}`] = this.graderWeights[g.userId];
                                return res;
                            }, {}),
                    }),
                );
            }
        },

        afterDivideSubmissions() {
            this.updateAssignment({
                assignmentId: this.assignment.id,
                assignmentProps: {
                    division_parent_id: this.importAssignment && this.importAssignment.id,
                },
            });
            this.forceLoadSubmissions(this.assignment.id);
            this.$emit('divided');
        },
    },

    components: {
        Loader,
        SubmitButton,
        User,
        Multiselect,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.table {
    th {
        border-top: 0;
    }

    .weight,
    .percentage {
        text-align: right;
    }

    .weight input {
        min-width: 3rem;
        padding: 0.75rem;
        height: auto;
        border: none;
        border-bottom: 1px solid transparent !important;
        border-radius: 0;
        background: transparent !important;
        margin-bottom: -1px;
        position: relative;
        z-index: 1;

        &:not(:disabled):hover {
            border-color: @color-primary !important;

            @{dark-mode} {
                border-color: @color-primary-darkest !important;
            }
        }
    }
}

.disabled-table {
    cursor: not-allowed;
}

.button-bar {
    flex-wrap: nowrap;
}
</style>

<style lang="less">
.divide-submissions {
    .custom-checkbox label {
        display: block;
    }

    .disabled-option {
        font-style: italic !important;
    }

    .multiselect__option:not(.multiselect__option--highlight) {
        .disabled-option {
            color: rgb(206, 206, 206);
        }
    }
}
</style>
