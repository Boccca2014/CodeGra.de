/* SPDX-License-Identifier: AGPL-3.0-only */
import moment from 'moment';

import { keys } from 'ts-transformer-keys';

import { CoursePermission as CPerm, CoursePermissionOptions as CPermOpts } from '@/permissions';

import { Rubric } from '@/models';

import { CoursesStore, store } from '@/store';

import { NONEXISTENT, MANAGE_ASSIGNMENT_PERMISSIONS } from '@/constants';
import * as utils from '@/utils/typed';
import { LTIProvider } from '@/lti_providers';

import * as assignmentState from '@/store/assignment-states';
import { makeCache } from '@/utils/cache';
import { AnyUser, User, GroupServerData } from './user';
import { Course } from './course';

export enum AssignmentKind {
    normal = 'normal',

    exam = 'exam',
}

/* eslint-disable camelcase */
export interface AssignmentServerProps {
    id: number;
    state: assignmentState.AssignmentStates;
    description: string | null;
    name: string;
    is_lti: boolean;
    cgignore: any;
    cgignore_version: string | null;
    whitespace_linter: any;
    done_type: string | null;
    done_email: string | null;
    fixed_max_rubric_points: number | null;
    max_grade: number | null;
    group_set: GroupServerData | null;
    division_parent_id: number | null;
    auto_test_id: number | null;
    files_upload_enabled: boolean;
    webhook_upload_enabled: boolean;
    max_submissions: number | null;
    amount_in_cool_off_period: number;
    lms_name: string | null;
    analytics_workspace_ids: number[];
    peer_feedback_settings: AssignmentPeerFeedbackSettings;
    kind: AssignmentKind;
    send_login_links: boolean;
    course_id: number;

    deadline: string | null;
    created_at: string;
    reminder_time: string | null;
    cool_off_period: string;
    available_at: string | null;
}

export interface AssignmentUpdateableProps {
    fixed_max_rubric_points?: number | null;
    group_set?: GroupServerData;
    division_parent_id?: number | null;
    auto_test_id?: number | null;
    peer_feedback_settings?: AssignmentPeerFeedbackSettings | null;
}

const ALLOWED_UPDATE_PROPS = new Set(keys<AssignmentUpdateableProps>());

const KEYS_TO_COPY = (() => {
    const keysNotToCopy = <const>[
        'created_at',
        'reminder_time',
        'available_at',
        'course_id',
        'cool_off_period',
    ];
    type KeyNotToCopy = typeof keysNotToCopy[number];
    const lookup: Readonly<Set<string>> = new Set(keysNotToCopy);
    return Object.freeze(
        keys<AssignmentServerProps>().filter(key => !lookup.has(key)),
    ) as ReadonlyArray<Exclude<keyof AssignmentServerProps, KeyNotToCopy>>;
})();

export interface AssignmentPeerFeedbackSettings {
    time: number;
    amount: number;
    // eslint-disable-next-line camelcase
    auto_approved: boolean;
}

abstract class AssignmentData {
    constructor(props: AssignmentData) {
        Object.assign(this, props);
    }

    readonly id!: number;

    readonly state!: assignmentState.AssignmentStates;

    readonly description!: string | null;

    readonly name!: string;

    readonly is_lti!: boolean;

    readonly cgignore!: any;

    readonly cgignore_version!: string | null;

    readonly whitespace_linter!: any;

    readonly done_type!: string | null;

    readonly done_email!: string | null;

    readonly fixed_max_rubric_points!: number | null;

    readonly max_grade!: number | null;

    readonly group_set!: GroupServerData | null;

    readonly division_parent_id!: number | null;

    readonly auto_test_id!: number | null;

    readonly files_upload_enabled!: boolean;

    readonly webhook_upload_enabled!: boolean;

    readonly max_submissions!: number | null;

    readonly amount_in_cool_off_period!: number;

    readonly lms_name!: string | null;

    readonly coolOffPeriod!: moment.Duration;

    readonly courseId!: number;

    readonly deadline!: moment.Moment;

    readonly createdAt!: moment.Moment;

    readonly availableAt!: moment.Moment | null;

    readonly reminderTime!: moment.Moment;

    readonly graderIds?: number[] | null;

    readonly analytics_workspace_ids!: number[];

    readonly peer_feedback_settings!: AssignmentPeerFeedbackSettings;

    readonly kind!: AssignmentKind;

    readonly send_login_links!: boolean;
}
/* eslint-enable camelcase */

// eslint-disable-next-line
export class Assignment extends AssignmentData {
    @utils.nonenumerable
    private _cache = makeCache('canManage');

    private constructor(props: AssignmentData) {
        super(props);
        Object.freeze(this);
    }

    @utils.nonenumerable
    get canManage() {
        return this._cache.get('canManage', () =>
            MANAGE_ASSIGNMENT_PERMISSIONS.some(perm => this.hasPermission(perm)),
        );
    }

    static fromServerData(serverData: AssignmentServerProps): Assignment {
        const props = utils.pickKeys(serverData, KEYS_TO_COPY);

        const courseId = serverData.course_id;

        let deadline;
        if (serverData.deadline == null) {
            deadline = moment.invalid();
        } else {
            deadline = moment.utc(serverData.deadline, moment.ISO_8601);
        }
        const createdAt = moment.utc(serverData.created_at, moment.ISO_8601);

        let availableAt;
        if (serverData.available_at != null) {
            availableAt = moment.utc(serverData.available_at, moment.ISO_8601);
        } else {
            availableAt = null;
        }

        let reminderTime;
        if (serverData.reminder_time == null) {
            reminderTime = moment.invalid();
        } else {
            reminderTime = moment.utc(serverData.reminder_time, moment.ISO_8601);
        }

        const coolOffPeriod = moment.duration(serverData.cool_off_period, 'seconds');

        return new Assignment(
            Object.assign(props, {
                courseId,
                deadline,
                createdAt,
                availableAt,
                reminderTime,
                coolOffPeriod,
            }),
        );
    }

    @utils.nonenumerable
    get course(): Course {
        return CoursesStore.getCourse()(this.courseId).unsafeCoerce();
    }

    @utils.nonenumerable
    get ltiProvider(): utils.Maybe<LTIProvider> {
        if (!this.is_lti) {
            return utils.Nothing;
        }
        return this.course.ltiProvider;
    }

    getReminderTimeOrDefault(): moment.Moment {
        if (this.reminderTime.isValid()) {
            return this.reminderTime.clone();
        }

        const deadline = this.deadline;
        let baseTime = deadline;
        const now = moment();

        if ((deadline.isValid() && deadline.isBefore(now)) || !deadline.isValid()) {
            baseTime = now;
        }

        return baseTime.clone().add(1, 'weeks');
    }

    @utils.nonenumerable
    get hasDeadline(): boolean {
        return this.deadline.isValid();
    }

    @utils.nonenumerable
    // eslint-disable-next-line camelcase
    get created_at(): string {
        return utils.formatDate(this.createdAt);
    }

    getDeadlineAsString(): string | null {
        if (this.hasDeadline) {
            return utils.formatDate(this.deadline);
        }
        return null;
    }

    // eslint-disable-next-line
    getFormattedDeadline(): string | null {
        if (this.hasDeadline) {
            return utils.readableFormatDate(this.deadline);
        }
        return null;
    }

    getFormattedCreatedAt(): string {
        return utils.readableFormatDate(this.createdAt);
    }

    deadlinePassed(now: moment.Moment = moment(), dflt: boolean = false): boolean {
        if (this.deadline == null) {
            return dflt;
        }
        return now.isAfter(this.deadline);
    }

    @utils.nonenumerable
    get peerFeedbackDeadline() {
        if (this.deadline == null || this.peer_feedback_settings == null) {
            return null;
        }
        return this.deadline.clone().add(this.peer_feedback_settings.time, 'seconds');
    }

    peerFeedbackDeadlinePassed(now: moment.Moment = moment(), dflt: boolean = true): boolean {
        const deadline = this.peerFeedbackDeadline;
        if (deadline == null) {
            return dflt;
        }
        return now.isAfter(deadline);
    }

    getSubmitDisabledReasons({ now = moment() }: { now?: moment.Moment } = {}): string[] {
        const res = [];

        if (
            !(
                this.hasPermission(CPerm.canSubmitOwnWork) ||
                this.hasPermission(CPerm.canSubmitOthersWork)
            )
        ) {
            res.push('you cannot submit work for this course');
        }

        if (!this.hasDeadline && !this.hasPermission(CPerm.canSubmitOthersWork)) {
            res.push("the assignment's deadline has not yet been set");
        }

        if (!this.hasPermission(CPerm.canUploadAfterDeadline) && this.deadlinePassed(now)) {
            res.push("the assignment's deadline has already passed");
        }

        return res;
    }

    canSubmitWork(now: moment.Moment = moment()): boolean {
        return this.getSubmitDisabledReasons({ now }).length === 0;
    }

    @utils.nonenumerable
    get maxGrade() {
        return this.max_grade == null ? 10 : this.max_grade;
    }

    @utils.nonenumerable
    get graders(): AnyUser[] | null {
        if (this.graderIds == null) {
            return null;
        }
        return utils.filterMap(this.graderIds, id => {
            const user = User.findUserById(id);
            return utils.Maybe.fromNullable(user);
        });
    }

    hasPermission(permission: CPerm | CPermOpts): boolean {
        return this.course.hasPermission(permission);
    }

    _canSeeFeedbackType(typ: 'grade' | 'linter' | 'user'): boolean {
        if (this.state === assignmentState.DONE) {
            return true;
        }
        const perm = {
            grade: CPerm.canSeeGradeBeforeOpen,
            linter: CPerm.canSeeLinterFeedbackBeforeDone,
            user: CPerm.canSeeUserFeedbackBeforeDone,
        }[typ];

        if (perm == null) {
            throw new Error(`Requested feedback type "${typ}" is not known.`);
        }

        return this.hasPermission(perm);
    }

    canSeeGrade() {
        return this._canSeeFeedbackType('grade');
    }

    canSeeUserFeedback() {
        return this._canSeeFeedbackType('user');
    }

    canSeeLinterFeedback() {
        return this._canSeeFeedbackType('linter');
    }

    @utils.nonenumerable
    get rubric(): Rubric<number> | NONEXISTENT | undefined {
        return store.getters['rubrics/rubrics'][this.id];
    }

    update(newProps: AssignmentUpdateableProps) {
        const propKeys = Object.keys(newProps);
        if (!propKeys.every(key => ALLOWED_UPDATE_PROPS.has(key as any))) {
            const disallowedPairs = propKeys
                .filter(key => !ALLOWED_UPDATE_PROPS.has(key as any))
                .map(key => `${key}: ${(newProps as Record<string, any>)[key]}`)
                .join(', ');
            throw TypeError(`Cannot set assignment property: ${disallowedPairs}`);
        }

        return new Assignment(Object.assign({}, this, newProps));
    }
}

export class AssignmentCapabilities {
    constructor(private readonly assignment: Assignment) {}

    get canEditState() {
        return this.canEditInfo;
    }

    get canEditInfo() {
        return this.assignment.hasPermission(CPerm.canEditAssignmentInfo);
    }

    get canEditName() {
        return this.canEditInfo && !this.assignment.is_lti;
    }

    get canEditDeadline() {
        return (
            this.canEditInfo &&
            this.assignment.ltiProvider.mapOrDefault(prov => !prov.supportsDeadline, true)
        );
    }

    get canEditAvailableAt() {
        return (
            this.canEditInfo &&
            this.assignment.ltiProvider.mapOrDefault(prov => !prov.supportsStateManagement, true)
        );
    }

    get canEditMaxGrade() {
        return (
            this.assignment.hasPermission(CPerm.canEditMaximumGrade) &&
            this.assignment.ltiProvider.mapOrDefault(prov => prov.supportsBonusPoints, true)
        );
    }

    get canEditSomeGeneralSettings() {
        return (
            this.canEditName ||
            this.canEditDeadline ||
            this.canEditAvailableAt ||
            this.canEditMaxGrade
        );
    }

    get canEditSubmissionSettings() {
        return this.canEditInfo;
    }

    get canUpdateGraderStatus() {
        return this.assignment.hasPermission(CPerm.canGradeWork) || this.canUpdateOtherGraderStatus;
    }

    get canUpdateOtherGraderStatus() {
        return this.assignment.hasPermission(CPerm.canUpdateGraderStatus);
    }
}
