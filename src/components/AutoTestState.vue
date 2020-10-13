<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';
import { Action, Getter } from 'vuex-class';
import { CreateElement } from 'vue';
import * as tsx from 'vue-tsx-support';

import { CoursePermission as CPerm } from '@/permissions';
import * as models from '@/models';

// @ts-ignore
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/ban';
import 'vue-awesome/icons/check';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/clock-o';
import 'vue-awesome/icons/exclamation-triangle';

import PromiseLoader from './PromiseLoader';

@Component
export default class AutoTestState extends Vue {
    _tsx!: tsx.DeclareProps<Pick<AutoTestState, 'assignment' | 'result' | 'btn' | 'noTimer' | 'showIcon'>>;

    @Prop({ required: true })
    public assignment!: models.Assignment;

    @Prop({ default: null })
    public result!: models.AutoTestResult | { state: string, startedAt: number | null} | null;

    @Prop({ default: false })
    public btn!: boolean;

    @Prop({ default: false })
    public noTimer!: boolean;

    @Prop({ default: false })
    public showIcon!: boolean;

    private restartPromise: Promise<unknown> | null = null;

    @Action('autotest/restartAutoTestResult')
    storeRestartAutoTestResult!: (data: {
        autoTestId: number,
        autoTestRunId: number,
        autoTestResultId: number,
    }) => Promise<unknown>;

    @Action('submissions/loadSubmissions')
    storeLoadSubmissions!: (_: { assignmentId: number, courseId?: number }) => Promise<unknown>;

    @Getter('submissions/getLatestSubmissions')
    storeGetLatestSubmissions!: (assignmentId: number) => ReadonlyArray<models.Submission>;

    get state(): string {
        return this.result?.state ?? 'not_started';
    }

    get latestSubmissions() {
        return this.storeGetLatestSubmissions(this.assignment.id);
    }

    get currentSubmissionIsLatest() {
        const result = this.result as ({ submissionId?: number } | null);
        const submissionId = result?.submissionId;
        if (submissionId == null) {
            return false;
        }
        return !!this.latestSubmissions.find(sub => sub.id === submissionId);
    }

    get canRestart(): boolean {
        if (!(this.result instanceof models.AutoTestResult)) {
            return false;
        }
        if (!this.assignment) {
            return false;
        }
        if (!this.currentSubmissionIsLatest) {
            return false;
        }
        return this.hasRestartPermissions;
    }

    get hasRestartPermissions() {
        return [
            CPerm.canRunAutotest,
            CPerm.canDeleteAutotestRun,
        ].every(perm => this.assignment.hasPermission(perm));
    }

    get showRestartBtn(): boolean {
        return this.hasRestartPermissions && this.btn;
    }

    @Watch('showRestartBtn')
    onShowRestartBtnChanged() {
        if (this.showRestartBtn && this.assignment) {
            // Submissions are probably already loaded by the parent
            // component. But it doesn't hurt make the dependency explicit here
            // too.
            this.storeLoadSubmissions({
                assignmentId: this.assignment.id,
                courseId: this.assignment.courseId,
            });
        }
    }

    get icon() {
        switch (this.state) {
        case 'passed':
        case 'done':
            return 'check';
        case 'partial':
            return 'tilde';
        case 'failed':
            return 'times';
        case 'hidden':
        case 'skipped':
            return 'ban';
        case 'starting':
        case 'not_started':
        case 'waiting_for_runner':
            return 'clock-o';
        case 'timed_out':
        case 'crashed':
            return 'exclamation-triangle';
        default:
            return '';
        }
    }

    get iconClass() {
        switch (this.state) {
        case 'passed':
        case 'done':
            return 'text-success';
        case 'failed':
        case 'timed_out':
        case 'crashed':
            return 'text-danger';
        case 'hidden':
        case 'skipped':
            return 'text-muted';
        default:
            return '';
        }
    }

    get readableState() {
        switch (this.state) {
        case 'hidden':
            return "This step is hidden and will not be executed until the assignment's deadline has passed.";
        case 'not_started':
            return 'Waiting to be started';
        default:
            return this.$utils.capitalize(this.state.replace(/_/g, ' '));
        }
    }

    get passedSinceStart() {
        return Math.max(0, this.$root.$epoch.diff(this.result?.startedAt ?? 0, 'seconds'));
    }

    get minutes() {
        return this.$utils.formatTimePart(Math.floor(this.passedSinceStart / 60));
    }

    get seconds() {
        return this.$utils.formatTimePart(Math.floor(this.passedSinceStart % 60));
    }

    restartAutoTestResult(): void {
        this.$utils.AssertionError.assert(this.result instanceof models.AutoTestResult);
        // @ts-ignore
        this.restartPromise = this.storeRestartAutoTestResult({
            autoTestId: this.result.autoTest.id,
            autoTestRunId: this.result.autoTest.runs?.[0]?.id,
            autoTestResultId: this.result.id,
        });
    }

    // eslint-disable-next-line
    renderRestartOption(h: CreateElement) {
        const directives = [];
        const props: { disabled?: boolean } = {};
        let classes;

        if (!this.canRestart) {
            props.disabled = true;
            classes = { 'cursor-not-allowed': true };
            directives.push({
                name: 'b-popover',
                value: 'You can only restart AutoTest for the latest submission.',
                modifiers: {
                    top: true,
                    hover: true,
                    window: true,
                },
            });
        }

        return h('b-dropdown-item', {
            props,
            directives,
            on: {
                click: (e: Event) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.restartAutoTestResult();
                },
            },
            class: classes,
        }, [
            'Restart this result',
        ]);
    }

    render(h: CreateElement) {
        if (this.restartPromise) {
            return h(this.btn ? 'b-btn' : 'div', {
                class: 'auto-test-state',
            }, [
                h(PromiseLoader, {
                    props: {
                        promise: this.restartPromise,
                    },
                    on: {
                        'after-success': () => {
                            this.restartPromise = null;
                            this.$emit('restarted');
                        },
                        'after-error': () => { this.restartPromise = null; },
                    },
                    class: 'mr-2',
                }),
                'Restarting result',
            ]);
        }

        const innerChildren = [];
        if (this.state === 'running' && !this.noTimer) {
            innerChildren.push(
                h('span', { class: 'running timer' }, [`${this.minutes}:${this.seconds}`]),
            );
        }
        if (this.state !== 'running' && this.showIcon && this.icon) {
            innerChildren.push(
                h(Icon, { class: this.iconClass, props: { name: this.icon } }),
            );
        }

        const directives = [];
        if (this.btn) {
            innerChildren.push(h('span', { class: 'readable-state' }, this.readableState));
        } else {
            directives.push({
                name: 'b-popover',
                value: this.readableState,
                expression: 'readableState',
                modifiers: {
                    top: true,
                    hover: true,
                },
            });
        }
        if (this.$slots.extra) {
            innerChildren.push(this.$slots.extra);
        }

        const inner = [
            h('span', { directives }, innerChildren),
        ];

        if (this.showRestartBtn) {
            return h(
                'b-dropdown',
                {
                    class: 'auto-test-state',
                    props: {
                        split: true,
                        right: true,
                    },
                    scopedSlots: {
                        'button-content': () => inner,
                        default: () => this.renderRestartOption(h),
                    },
                },
            );
        }

        return h(
            this.btn ? 'b-btn' : 'span',
            {
                class: 'auto-test-state',
                props: {
                    variant: 'secondary',
                },
            },
            inner,
        );
    }
}
</script>

<style lang="less" scoped>
.auto-test-state.btn {
    pointer-events: none;
}

.running.timer ~ .readable-state {
    padding-left: 0.25rem;
}

.fa-icon {
    transform: translateY(-2px);
}
</style>

<style lang="less">
@import '~mixins.less';

@{dark-mode} .auto-test-state.b-dropdown > .dropdown-menu {
    background-color: @color-primary-darker;
    &:hover .dropdown-item {
        background-color: @color-primary-darkest;
    }
}

.auto-test-state.b-dropdown > .btn:not(.dropdown-toggle) {
    cursor: inherit;

    &:hover {
        background-color: white !important;
    }
    &:focus {
        box-shadow: none !important;
    }
    @{dark-mode} {
        background-color: @color-primary !important;
    }

}
</style>
