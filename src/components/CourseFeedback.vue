<template>
<div class="course-feedback d-flex flex-column">
    <div class="overflow-auto h-100">
        <div class="p-3 sticky-top bg-light border-bottom">
            <b-input-group>
                <input :value="filter"
                       v-debounce:300ms="newFilter => { filter = newFilter }"
                       class="filter form-control"
                       placeholder="Filter on comment or author"/>

                <b-input-group-append>
                    <b-button variant="secondary"
                              class="settings-button"
                              @click="settingsCollapsed = !settingsCollapsed"
                              v-b-popover.top.hover.window="`${settingsCollapsed ? 'Show' : 'Hide'} settings`">
                        <fa-icon name="gear"
                                 :class="{ rotate: settingsCollapsed }"/>
                    </b-button>
                </b-input-group-append>
            </b-input-group>

            <collapse :collapsed="settingsCollapsed">
                <hr class="mb-2"/>

                <b-form-group label="Context lines"
                              :id="`course-feedback-context-lines-${id}`"
                              :label-for="`course-feedback-context-lines-${id}-input`"
                              :state="contextLines.isRight()">
                    <template #invalid-feedback>
                        {{ $utils.getErrorMessage(contextLines.extract()) }}
                    </template>

                    <cg-number-input
                        :id="`course-feedback-context-lines-${id}-input`"
                        v-model="contextLines"
                        placeholder="Context lines"/>
                </b-form-group>

                <b-input-group class="mb-0">
                    <b-input-group-prepend is-text>
                        <b-form-checkbox
                            v-model="hideAutoTestRubricCategories"
                            :id="`course-feedback-hide-at-rubric-${id}`"
                            class="mr-n2"/>
                    </b-input-group-prepend>

                    <div class="form-control">
                        <label :for="`course-feedback-hide-at-rubric-${id}`"
                               class="mb-0 d-block cursor-pointer">
                            Hide AutoTest rubric categories
                        </label>
                    </div>
                </b-input-group>
            </collapse>
        </div>

        <b-alert show
                 variant="danger"
                 class="m-3"
                 v-if="error != null">
            {{ error }}
        </b-alert>

        <cg-loader v-else-if="loading"
                   class="p-3" />

        <div v-else-if="assignments.length === 0"
            class="p-3 text-muted font-italic">
            No
            <template v-if="excludeSubmission">
                other
            </template>
            assignments in this course.
        </div>

        <ol v-else
            class="mb-0 pl-0">
            <template v-for="(assig, i) in sortedAssignments">
                <li v-if="submissionsByAssignmentId[assig.id] == null"
                     class="border-top cursor-not-allowed">
                    <h6 class="assignment-name no-submission p-3 mb-0 text-muted">
                        {{ assig.name }}

                        <span class="font-italic">
                            (no submission)
                        </span>
                    </h6>
                </li>

                <li v-else
                    v-for="sub in [submissionsByAssignmentId[assig.id]]"
                    :key="sub.id"
                    class="border-top">
                    <collapse :collapsed="shouldCollapse(sub)">
                        <h6 slot="handle"
                            v-b-toggle="`course-feedback-collapse-${sub.id}`"
                            class="assignment-name p-3 mb-0 cursor-pointer"
                            :class="{
                                'text-muted': !hasFeedbackMatches(sub),
                            }">
                            <div class="caret mr-2 float-left">
                                <fa-icon name="chevron-down" :scale="0.75" />
                            </div>

                            {{ assig.name }}

                            <span v-if="sub.grade != null"
                                class="font-italic">
                                (graded: {{ sub.grade }})
                            </span>

                            <span v-else
                                class="text-muted font-italic">
                                (not yet graded)
                            </span>

                            <span class="float-right">
                                <cg-loader :scale="1" v-if="sub.feedback == null" />

                                <b-badge v-else
                                        :variant="hasFeedbackMatches(sub) ? 'primary' : 'secondary'"
                                        title="Comments on this submission">
                                    <template v-if="filter">
                                        {{ filteredFeedbackCounts[sub.id] }} /
                                    </template>

                                    {{ totalFeedbackCounts[sub.id] }}
                                </b-badge>
                            </span>
                        </h6>

                        <div v-if="filteredRubricResults[sub.id] != null"
                            class="px-3 pb-3">
                            <span v-for="{ result, row, item } in filteredRubricResults[sub.id]"
                                :key="`${sub.id}-${item.id}`">
                                <b-badge
                                    :id="`course-feedback-rubric-item-${id}-${sub.id}-${item.id}`"
                                    pill
                                    class="mr-1"
                                    variant="secondary">
                                    <span class="mr-1">{{ row.header }}</span>
                                    <sup>{{ item.achieved_points }}</sup>&frasl;<sub>{{ row.maxPoints }}</sub>

                                    <template v-if="row.locked === 'auto_test'">
                                        <span class="mx-1">|</span> AT
                                    </template>
                                </b-badge>

                                <b-popover
                                    triggers="hover"
                                    placement="top"
                                    :target="`course-feedback-rubric-item-${id}-${sub.id}-${item.id}`"
                                    custom-class="course-feedback-rubric-row-popover">
                                    <component
                                        :is="`rubric-viewer-${row.type}-row`"
                                        :value="result"
                                        :rubric-row="row"
                                        :assignment="assig"/>
                                </b-popover>
                            </span>
                        </div>

                        <div v-if="!hasFeedbackMatches(sub)"
                            class="p-3 border-top text-muted font-italic">
                            <template v-if="filter">
                                No comments match the filter.
                            </template>

                            <template v-else>
                                No feedback given.
                            </template>
                        </div>

                        <feedback-overview
                            v-else
                            :assignment="assig"
                            :submission="sub"
                            show-inline-feedback
                            :non-editable="true"
                            :context-lines="currentContextLines"
                            :should-render-general="shouldRenderGeneral(sub)"
                            :should-render-thread="shouldRenderThread"
                            :should-fade-reply="shouldFadeReply"
                            :open-files-in-new-tab="!$inLTI">
                            <template v-if="filter" #no-inline-feedback>
                                No inline feedback matching the filter.
                            </template>
                        </feedback-overview>
                    </collapse>
                </li>
            </template>
        </ol>
    </div>
</div>
</template>

<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';
import { mapActions, mapGetters } from 'vuex';

import 'vue-awesome/icons/chevron-down';
import 'vue-awesome/icons/gear';

import {
    Assignment,
    Submission,
    User,
    Feedback,
    FeedbackLine,
    FeedbackReply,
    Rubric,
    RubricRow,
    RubricResult,
    RubricResultItemServerData,
} from '@/models';
import { Search } from '@/utils/search';
import { defaultdict } from '@/utils/defaultdict';
import { isEmpty, flatMap1, filterMap, Just, Nothing } from '@/utils';
import { NONEXISTENT } from '@/constants';

import { FeedbackOverview } from '@/components';

import { NumberInputValue, numberInputValue } from './NumberInput';
// @ts-ignore
import Collapse from './Collapse';
// @ts-ignore
import RubricViewerNormalRow from './RubricViewerNormalRow';
// @ts-ignore
import RubricViewerContinuousRow from './RubricViewerContinuousRow';

const GeneralFeedbackSearcher = new Search(['general', 'comment', 'author']);

interface GeneralFeedbackRecord {
    general: string;
    comment: string;
    author: string;
    sub: Submission;
}

const InlineFeedbackSearcher = new Search(['inline', 'comment', 'author']);

interface InlineFeedbackRecord {
    inline: string;
    comment: string;
    author: string;
    thread: FeedbackLine,
    reply: FeedbackReply,
}

interface RubricResultItem {
    result: RubricResult;
    item: RubricResultItemServerData;
    row: RubricRow<number>;
}

@Component({
    computed: {
        ...mapGetters('courses', {
            allAssignments: 'assignments',
        }),
        ...mapGetters('rubrics', {
            allRubrics: 'rubrics',
            allRubricResults: 'results',
        }),
    },
    methods: {
        ...mapActions('submissions', {
            loadUserSubmissions: 'loadLatestByUserInCourse',
        }),
        ...mapActions('feedback', [
            'loadFeedback',
        ]),
        ...mapActions('rubrics', {
            loadRubric: 'loadRubric',
            loadRubricResult: 'loadResult',
        }),
    },
    components: {
        Collapse,
        FeedbackOverview,
        RubricViewerNormalRow,
        RubricViewerContinuousRow,
    },
})
export default class CourseFeedback extends Vue {
    allAssignments!: Readonly<Record<string, Assignment>>;

    allRubrics!: Readonly<Record<number, Rubric<number> | NONEXISTENT>>;

    allRubricResults!: Readonly<Record<number, RubricResult>>;

    loadUserSubmissions!:
        (args: { courseId: number, userId: number }) => Promise<Submission[]>;

    loadFeedback!:
        (args: { assignmentId: number, submissionId: number }) => Promise<Feedback>;

    loadRubric!:
        (args: { assignmentId: number }) => Promise<void>;

    loadRubricResult!:
        (args: { assignmentId: number, submissionId: number }) => Promise<void>;

    @Prop({ required: true })
    course!: { id: number };

    @Prop({ required: true })
    user!: User;

    @Prop({ default: null })
    excludeSubmission!: Submission;

    public id: number = this.$utils.getUniqueId();

    public loading: boolean = true;

    public error: string | null = null;

    public filter: string = '';

    public submissionsByAssignmentId: Readonly<Record<number, Submission | null>> = {};

    public settingsCollapsed: boolean = true;

    public currentContextLines: number = 3;

    public contextLines: NumberInputValue = numberInputValue(this.currentContextLines);

    public hideAutoTestRubricCategories: boolean = true;

    @Watch('contextLines')
    handleContextLines() {
        this.contextLines.orDefault(Nothing).ifJust(contextLines => {
            this.currentContextLines = contextLines;
        });
    }

    get courseId(): number {
        return this.course.id;
    }

    @Watch('courseId', { immediate: true })
    handleCourseId() {
        this.loadCourseFeedback();
    }

    get userId(): number {
        return this.user.id;
    }

    @Watch('userId', { immediate: true })
    handleUserId() {
        this.loadCourseFeedback();
    }

    get assignments(): ReadonlyArray<Assignment> {
        // It can happen that a new assignment was created between the moment
        // the page was loaded and the feedback sidebar was opened. In that
        // case, the assignment does not exist in `this.allAssignments`, which
        // would cause an error. We ignore those newly created assignments for
        // now, because we do not yet have a method in the store to load a
        // single assignment.

        let assigs = filterMap(
            Object.keys(this.submissionsByAssignmentId),
            (id: string) => {
                const assig = this.allAssignments[id];
                return assig == null ? Nothing : Just(assig);
            },
        );

        if (this.excludeSubmission != null) {
            assigs = assigs.filter(a => a.id !== this.excludeSubmission.assignment.id);
        }

        return assigs;
    }

    get sortedAssignments(): ReadonlyArray<Assignment> {
        // The order of the assignment depends on a few factors. If the filter is empty,
        // assignments are sorted on their deadline, latest first, and assignments with no
        // deadline set are sorted last. If the filter is not empty, assignments are sorted
        // on the amount of comments matching the filter. Assignments for which this is equal
        // are then sorted based on their deadline.

        return [...this.assignments].sort((a, b) => {
            const subA = this.submissionsByAssignmentId[a.id];
            const subB = this.submissionsByAssignmentId[b.id];

            if (subB == null) {
                return -1;
            } else if (subA == null) {
                return 1;
            }

            if (this.filter) {
                const hasA = this.hasFeedbackMatches(subA);
                const hasB = this.hasFeedbackMatches(subB);

                if (hasA !== hasB) {
                    return hasA ? -1 : 1;
                }
            }

            if (b.deadline == null) {
                return -1;
            } else if (a.deadline == null) {
                return 1;
            } else {
                return a.deadline.isBefore(b.deadline) ? 1 : -1;
            }
        });
    }

    get otherSubmissions(): ReadonlyArray<Submission> {
        return filterMap(this.assignments, assig => {
            const sub = this.submissionsByAssignmentId[assig.id];
            return sub == null ? Nothing : Just(sub);
        });
    }

    get searchableGeneralFeedback(): ReadonlyArray<GeneralFeedbackRecord> {
        return filterMap(this.otherSubmissions, sub => {
            if (sub.feedback == null) {
                return Nothing;
            }
            return Just({
                general: sub.feedback.general,
                comment: sub.feedback.general,
                author: sub.comment_author?.readableName ?? '',
                sub,
            });
        });
    }

    get filteredGeneralFeedback(): Readonly<Set<number>> {
        let fb = this.searchableGeneralFeedback;
        if (this.filter != null && this.filter !== '') {
            fb = GeneralFeedbackSearcher.search(this.filter, fb);
        }
        return new Set(fb.map(({ sub }) => sub.id));
    }

    get searchableUserFeedback(): ReadonlyArray<InlineFeedbackRecord> {
        function getThreadFb(thread: FeedbackLine): InlineFeedbackRecord[] {
            return thread.replies.map(reply => ({
                inline: reply.message,
                comment: reply.message,
                author: reply.author?.readableName ?? '',
                thread,
                reply,
            }));
        }

        function getFileFeedback(fileFb: Record<number, FeedbackLine>): InlineFeedbackRecord[] {
            return flatMap1(Object.values(fileFb), getThreadFb);
        }

        function getSubmissionFeedback(sub: Submission): InlineFeedbackRecord[] {
            if (sub.feedback == null) {
                return [];
            }

            return flatMap1(Object.values(sub.feedback.user), getFileFeedback);
        }

        return flatMap1(this.otherSubmissions, getSubmissionFeedback);
    }

    get filteredUserFeedback(): Readonly<Record<number, Set<number>>> {
        let filteredFb = this.searchableUserFeedback;

        if (this.filter != null && this.filter !== '') {
            filteredFb = InlineFeedbackSearcher.search(this.filter, filteredFb);
        }

        return filteredFb.reduce((acc: Record<number, Set<number>>, { thread, reply }) => {
            if (reply.id != null) {
                acc[thread.id].add(reply.id);
            }
            return acc;
        }, defaultdict(() => new Set()));
    }

    get filteredFeedbackCounts(): Readonly<Record<number, number>> {
        return this.otherSubmissions.reduce((acc: Record<number, number>, sub) => {
            const fb = sub.feedback;
            if (fb == null) {
                return acc;
            }

            const general = this.shouldRenderGeneral(sub) ? 1 : 0;
            const threads = this.$utils.flatMap1(
                Object.values(fb.user),
                fileFb => Object.values(fileFb),
            ).filter(thread =>
                this.shouldRenderThread(thread),
            );
            acc[sub.id] = general + threads.length;
            return acc;
        }, {});
    }

    get totalFeedbackCounts(): Readonly<Record<number, number>> {
        return this.otherSubmissions.reduce((acc: Record<number, number>, sub) => {
            const fb = sub.feedback;
            if (fb != null) {
                acc[sub.id] = fb.countEntries();
            }
            return acc;
        }, {});
    }

    get rubricResultsBySub(): Readonly<Record<number, RubricResult>> {
        return this.otherSubmissions.reduce((acc: Record<number, RubricResult>, sub) => {
            if (this.allRubrics[sub.assignmentId] === NONEXISTENT) {
                return acc;
            }
            const result = this.$utils.getProps(this.allRubricResults, null, sub.id);
            if (!isEmpty(result.selected)) {
                acc[sub.id] = result;
            }
            return acc;
        }, {});
    }

    get filteredRubricResults(): Readonly<Record<number, ReadonlyArray<RubricResultItem>>> {
        return this.otherSubmissions.reduce((acc: Record<number, RubricResultItem[]>, sub) => {
            const rubric = this.allRubrics[sub.assignmentId];
            const result = this.rubricResultsBySub[sub.id];

            if (rubric == null || rubric === NONEXISTENT || result == null) {
                return acc;
            }

            // Loop over the rubric rows to ensure the same order as the rubric viewer.
            const items = filterMap(rubric.rows, row => {
                const item = result.selected[row.id];
                if (item == null) {
                    return Nothing;
                }
                if (this.hideAutoTestRubricCategories && row.locked === 'auto_test') {
                    return Nothing;
                }
                return Just({ result, row, item });
            });

            if (items.length > 0) {
                acc[sub.id] = items;
            }
            return acc;
        }, {});
    }

    loadCourseFeedback() {
        this.loading = true;
        this.error = null;
        this.submissionsByAssignmentId = [];

        this.loadUserSubmissions({
            courseId: this.course.id,
            userId: this.user.id,
        }).then(subs => {
            this.submissionsByAssignmentId = subs;
            return Promise.all(
                filterMap(Object.values(subs), sub => {
                    if (sub == null) {
                        return Nothing;
                    }
                    return Just(Promise.all([
                        this.loadFeedback({
                            assignmentId: sub.assignmentId,
                            submissionId: sub.id,
                        }),
                        this.loadRubric({
                            assignmentId: sub.assignmentId,
                        }).catch(this.$utils.makeHttpErrorHandler<void>({
                            // Assignment may not have a rubric.
                            404: () => {},
                        })),
                        this.loadRubricResult({
                            assignmentId: sub.assignmentId,
                            submissionId: sub.id,
                        }),
                    ]));
                }),
            );
        }).catch(err => {
            this.error = this.$utils.getErrorMessage(err);
        }).then(() => {
            this.loading = false;
        });
    }

    shouldRenderGeneral(sub: Submission) {
        return this.filteredGeneralFeedback.has(sub.id);
    }

    shouldRenderThread(thread: FeedbackLine) {
        return this.$utils.getProps(
            this.filteredUserFeedback,
            0,
            thread.id,
            'size',
        ) !== 0;
    }

    shouldFadeReply(thread: FeedbackLine, reply: FeedbackReply) {
        if (reply.id == null) {
            return false;
        }
        return !this.filteredUserFeedback[thread.id].has(reply.id);
    }

    shouldCollapse(sub: Submission) {
        if (this.filter) {
            return this.filteredFeedbackCounts[sub.id] === 0;
        } else {
            return true;
        }
    }

    hasFeedbackMatches(sub: Submission) {
        if (this.filter) {
            return this.filteredFeedbackCounts[sub.id] > 0;
        } else {
            return this.totalFeedbackCounts[sub.id] > 0;
        }
    }

    mounted() {
        this.$root.$on('cg::submissions-page::reload', this.loadCourseFeedback);
    }

    destroyed() {
        this.$root.$off('cg::submissions-page::reload', this.loadCourseFeedback);
    }
}
</script>

<style lang="less" scoped>
@import '~mixins.less';

ol {
    list-style-type: none;

    li:first-child {
        border-top: 0 !important;
    }
}

.caret {
    transform: rotate(0);
    transition: transform @transition-duration;
}

.x-collapsed .caret,
.x-collapsing .caret {
    transform: rotate(-90deg);
}

.settings-button {
    .fa-icon {
        transform: translateY(-1px) rotate(0);
        transition: transform (2 * @transition-duration);

        &.rotate {
            transform: translateY(-1px) rotate(-90deg);
        }
    }
}

.card {
    border-left: none !important;
    border-right: none !important;
    border-bottom: none !important;
    border-radius: 0 !important;
}

.assignment-name.no-submission {
    padding-left: 2.5rem !important;
}
</style>

<style lang="less">
.course-feedback .feedback-overview {
    border-left: none !important;
    border-right: none !important;
    border-bottom: none !important;
    border-radius: 0 !important;

    .scroller > .card {
        border-radius: 0 !important;
    }
}

.course-feedback-rubric-row-popover {
    max-width: 35rem;

    .popover-body {
        text-align: left;
        padding: 0 !important;
    }

    .row-description p {
        margin-bottom: 0.5rem !important;
    }

    .rubric-item .description {
        max-height: 10rem;
    }
}
</style>
