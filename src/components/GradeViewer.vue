<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="grade-viewer"
     v-b-popover.top.hover="globalPopover"
     :class="globalPopover ? 'cursor-not-allowed' : undefined">
    <b-collapse id="rubric-collapse"
                v-if="showRubric"
                v-model="rubricOpen">
        <rubric-viewer :assignment="assignment"
                       :submission="submission"
                       :editable="realEditable"
                       :visible="rubricOpen"
                       @load="setRubricResult"
                       @input="rubricGradeChanged"
                       @submit="() => $refs.submitButton.onClick()"
                       class="mb-3" />
    </b-collapse>

    <b-form-fieldset class="mb-0">
        <b-input-group>
            <b-input-group-prepend>
                <submit-button ref="submitButton"
                               class="submit-grade-btn"
                               v-if="realEditable"
                               :submit="putGrade"
                               @success="afterPutGrade">
                    <template slot="error"
                              slot-scope="scope"
                              v-if="scope.error instanceof ValidationError">
                        <p v-if="scope.error.multipliers.length > 0"
                           class="text-justify">
                            The following continuous categories have an invalid
                            score, which must be between 0 and 100:

                            <ul>
                                <li v-for="msg in scope.error.multipliers">
                                    {{ msg }}
                                </li>
                            </ul>
                        </p>
                    </template>
                </submit-button>
                <span class="input-group-text" v-else>Grade</span>
            </b-input-group-prepend>

            <input type="number"
                   class="form-control"
                   :disabled="!!globalPopover"
                   name="grade-input"
                   step="any"
                   min="0"
                   :max="maxAllowedGrade"
                   :readonly="!realEditable"
                   :placeholder="editable ? 'Grade' : 'Not yet available'"
                   @keydown.enter="() => $refs.submitButton.onClick()"
                   @input="rubricOverridden = showRubric"
                   v-model="grade"/>

            <b-input-group-append class="rubric-score d-inline text-center"
                                  :class="{ warning: rubricOverridden, 'help-cursor': rubricOverridden }"
                                  v-if="showRubric"
                                  is-text>
                <span v-b-popover.top.hover="rubricOverridden ? 'Rubric grade was overridden.' : ''">
                    {{ rubricScore }}
                </span>
            </b-input-group-append>

            <b-input-group-append class="delete-button-group"
                                  v-if="realEditable"
                                  v-b-popover.hover.top="showDeleteButton ? deleteButtonText : ''">
                <submit-button class="delete-button"
                               variant="danger"
                               :disabled="!showDeleteButton"
                               :submit="deleteGrade"
                               @success="afterPutGrade"
                               :confirm="deleteConfirmText">
                    <icon :name="rubricOverridden || submission.grade_overridden ? 'reply' : 'times'"/>
                </submit-button>
            </b-input-group-append>

            <b-input-group-append v-if="showRubric">
                <b-button variant="secondary"
                          class="rubric-toggle"
                          v-b-popover.top.hover="'Toggle rubric'"
                          v-b-toggle.rubric-collapse>
                    <loader :scale="1" v-if="rubricResult == null" />
                    <icon name="th" v-else/>
                </b-button>
            </b-input-group-append>

            <b-input-group-append class="rubric-save-warning warning text-right help-cursor"
                                  v-if="isRubricChanged"
                                  is-text
                                  v-b-popover.hover.top="'Press the submit button to submit the changes.'">
                The rubric is not saved yet!
            </b-input-group-append>
        </b-input-group>
    </b-form-fieldset>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/th';
import 'vue-awesome/icons/info';
import 'vue-awesome/icons/refresh';
import 'vue-awesome/icons/reply';
import 'vue-awesome/icons/times';

import { NONEXISTENT } from '@/constants';
import { ValidationError } from '@/models/errors';
import { formatGrade, isDecimalNumber } from '@/utils';
import { User } from '@/models';

import RubricViewer from './RubricViewer';
import SubmitButton from './SubmitButton';
import Loader from './Loader';

const DeleteButtonState = Object.freeze({
    DELETE_GRADE: {},
    CLEAR_RUBRIC: {},
    RUBRIC_CHANGED: {},
    RUBRIC_CHANGED_AND_OVERRIDDEN: {},
});

export default {
    name: 'grade-viewer',

    props: {
        editable: {
            type: Boolean,
            default: false,
        },
        rubricStartOpen: {
            type: Boolean,
            default: false,
        },
        assignment: {
            type: Object,
            required: true,
        },
        submission: {
            type: Object,
            required: true,
        },

        notLatest: {
            type: Boolean,
            default: false,
        },

        groupOfUser: {
            type: User,
            default: null,
        },
    },

    data() {
        return {
            grade: this.submission.grade,
            rubricOpen: this.rubricStartOpen && !this.notLatest,
            rubricOverridden: null,
            rubricResult: null,

            ValidationError,
        };
    },

    computed: {
        ...mapGetters('rubrics', {
            storeRubrics: 'rubrics',
            storeRubricResults: 'results',
        }),

        course() {
            return this.$utils.getProps(this.assignment, null, 'course');
        },

        ltiProvider() {
            return this.$utils.getPropMaybe(this.assignment, 'ltiProvider');
        },

        globalPopover() {
            if (this.notLatest) {
                let msg = `This is not the latest submission by ${this.$utils.nameOfUser(
                    this.submission.user,
                )} so you cannot edit the grade.`;
                this.ltiProvider.ifJust(prov => {
                    msg += ` This grade will not be passed back to ${prov.lms}.`;
                });
                return msg;
            } else if (this.groupOfUser) {
                return `This user is member of the group "${
                    this.groupOfUser.group.name
                }", which also created a submission. Therefore, this submission is not the latest of this user.`;
            } else {
                return '';
            }
        },

        realEditable() {
            return this.editable && !this.notLatest;
        },

        storeResult() {
            return this.storeRubricResults[this.submissionId];
        },

        rubric() {
            const rubric = this.storeRubrics[this.assignmentId];
            return rubric === NONEXISTENT ? null : rubric;
        },

        rubricPoints() {
            return this.$utils.getProps(this.rubricResult, null, 'points');
        },

        rubricMaxPoints() {
            return this.$utils.getProps(
                this.rubricResult,
                this.$utils.Nothing,
                'maxPoints',
            ).extractNullable();
        },

        rubricHasSelectedItems() {
            return this.rubricPoints != null;
        },

        rubricGrade() {
            return this.$utils.getProps(this.rubricResult, null, 'grade');
        },

        isRubricChanged() {
            if (!this.showRubric || this.storeResult == null || this.rubricResult == null) {
                return false;
            }

            const diff = this.rubricResult.diffSelected(this.storeResult);
            return diff.size !== 0;
        },

        maxAllowedGrade() {
            return (this.assignment && this.assignment.max_grade) || 10;
        },

        deleteButtonState() {
            if (this.showRubric) {
                if (this.rubricOverridden) {
                    return DeleteButtonState.RUBRIC_OVERRIDDEN;
                } else if (this.submission.grade_overridden) {
                    return DeleteButtonState.RUBRIC_CHANGED_AND_OVERRIDDEN;
                } else {
                    return DeleteButtonState.CLEAR_RUBRIC;
                }
            } else {
                return DeleteButtonState.DELETE_GRADE;
            }
        },

        deleteButtonText() {
            switch (this.deleteButtonState) {
                case DeleteButtonState.DELETE_GRADE:
                    return 'Delete grade';
                case DeleteButtonState.CLEAR_RUBRIC:
                    return 'Clear the rubric';
                case DeleteButtonState.RUBRIC_OVERRIDDEN:
                    return 'Reset to the grade from the rubric';
                case DeleteButtonState.RUBRIC_CHANGED_AND_OVERRIDDEN:
                    return 'Discard changes to the rubric';
                default:
                    return '';
            }
        },

        deleteConfirmText() {
            switch (this.deleteButtonState) {
                case DeleteButtonState.DELETE_GRADE:
                    return 'Are you sure you want to clear the grade?';
                case DeleteButtonState.CLEAR_RUBRIC:
                    return 'Are you sure you want to clear the rubric?';
                case DeleteButtonState.RUBRIC_OVERRIDDEN:
                    return 'Are you sure you want to reset the grade?';
                case DeleteButtonState.RUBRIC_CHANGED_AND_OVERRIDDEN:
                    return 'Are you sure you want to discard changes to the rubric?';
                default:
                    return '';
            }
        },

        showDeleteButton() {
            if (!this.realEditable) {
                return false;
            } else if (this.rubricOverridden) {
                return true;
            } else if (this.showRubric) {
                return this.rubricHasSelectedItems;
            } else {
                return this.grade != null;
            }
        },

        showRubric() {
            return !!(this.rubric && this.rubric.rows.length);
        },

        rubricScore() {
            const toFixed = val => {
                const fval = parseFloat(val);
                return this.$utils.toMaxNDecimals(fval, 2);
            };
            const points = this.rubricPoints;
            const scored = points ? toFixed(points) : 0;
            const max = this.rubricMaxPoints == null ? '…' : toFixed(this.rubricMaxPoints);
            return `${scored} / ${max}`;
        },

        submissionGrade() {
            return this.submission.grade;
        },

        assignmentId() {
            return this.assignment.id;
        },

        submissionId() {
            return this.submission.id;
        },
    },

    watch: {
        assignmentId: {
            immediate: true,
            handler() {
                this.storeLoadRubric({
                    assignmentId: this.assignmentId,
                }).catch(err => {
                    if (this.$utils.getProps(err, 500, 'response', 'status') !== 404) {
                        throw err;
                    }
                });
            },
        },

        submissionId: {
            immediate: true,
            handler() {
                const grade = this.submission.grade;
                if (grade) {
                    this.grade = formatGrade(grade);
                    this.rubricOverridden = this.submission.grade_overridden ? true : null;
                } else {
                    this.grade = null;
                }
                this.storeLoadRubricResult({
                    submissionId: this.submissionId,
                    assignmentId: this.assignmentId,
                });
            },
        },

        submissionGrade: {
            immediate: false,
            handler(newGrade) {
                this.grade = formatGrade(newGrade);
            },
        },
    },

    async mounted() {
        this.$root.$on('open-rubric-category', () => {
            this.rubricOpen = true;
        });
    },

    destroyed() {
        this.$root.$off('open-rubric-category');
    },

    methods: {
        ...mapActions('submissions', {
            storeUpdateSubmission: 'updateSubmission',
        }),

        ...mapActions('rubrics', {
            storeLoadRubric: 'loadRubric',
            storeLoadRubricResult: 'loadResult',
            storeUpdateRubricResult: 'updateRubricResult',
        }),

        setRubricResult(rubricResult) {
            this.rubricResult = rubricResult;
        },

        rubricGradeChanged(rubricResult) {
            this.rubricResult = rubricResult;
            this.grade = this.rubricGrade;
            this.rubricOverridden = false;
        },

        submitRubricItems() {
            return this.storeUpdateRubricResult({
                assignmentId: this.assignmentId,
                submissionId: this.submissionId,
                result: this.rubricResult,
            });
        },

        clearRubricItems() {
            return this.storeUpdateRubricResult({
                assignmentId: this.assignmentId,
                submissionId: this.submissionId,
                result: this.rubricResult.clearSelected(),
            });
        },

        clearSubmissionGrade() {
            return this.$http.patch(`/api/v1/submissions/${this.submissionId}`, { grade: null });
        },

        deleteGrade() {
            switch (this.deleteButtonState) {
                case DeleteButtonState.DELETE_GRADE:
                case DeleteButtonState.RUBRIC_OVERRIDDEN:
                    return this.clearSubmissionGrade();
                case DeleteButtonState.CLEAR_RUBRIC:
                    return this.clearRubricItems().then(res => {
                        this.$root.$emit('cg::rubric-viewer::reset');
                        return res;
                    });
                case DeleteButtonState.RUBRIC_CHANGED_AND_OVERRIDDEN:
                    return {
                        data: {
                            grade: this.submission.grade,
                            grade_overridden: true,
                        },
                    };
                default:
                    throw new TypeError('Invalid deleteButtonState');
            }
        },

        putGrade() {
            let grade = this.grade === '' ? null : this.grade;

            if (grade != null && !isDecimalNumber(grade)) {
                throw new Error('Grade must be a number.');
            }

            grade = parseFloat(grade);
            const overridden = this.rubricOverridden;
            const normalGrade = overridden || !this.showRubric;

            if (
                !(grade >= 0 && grade <= this.maxAllowedGrade) &&
                normalGrade &&
                !Number.isNaN(grade)
            ) {
                throw new Error(`Grade must be between 0 and ${this.maxAllowedGrade}.`);
            }

            let req = Promise.resolve([]);

            // These requests must happen sequentially because the backend must receive
            // the grade after the rubric to set grade_overridden correctly.
            if (this.showRubric) {
                req = req.then(responses =>
                    this.submitRubricItems().then(res => responses.concat(res)),
                );
            }

            if (!this.showRubric || overridden) {
                req = req.then(responses =>
                    this.$http
                        .patch(`/api/v1/submissions/${this.submissionId}`, { grade })
                        .then(res => responses.concat(res)),
                );
            }

            return req;
        },

        afterPutGrade(responses) {
            const res = this.$utils.ensureArray(responses);
            const { data } = res[res.length - 1];
            const grade = formatGrade(data.grade);

            this.grade = grade;
            this.rubricOverridden = data.grade_overridden;
            this.storeUpdateSubmission({
                assignmentId: this.assignmentId,
                submissionId: this.submissionId,
                submissionProps: { grade, grade_overridden: data.grade_overridden },
            });
        },
    },

    components: {
        Icon,
        SubmitButton,
        RubricViewer,
        Loader,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.cursor-not-allowed {
    cursor: not-allowed !important;
}

input:read-only {
    color: black;
    background-color: white;
    .grade-viewer:not(.cursor-not-allowed) & {
        cursor: text;
    }
    pointer-events: all;
    user-select: initial;
}

.help-cursor {
    cursor: help;
}
</style>
