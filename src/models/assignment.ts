/* SPDX-License-Identifier: AGPL-3.0-only */
import moment from 'moment';

import { keys } from 'ts-transformer-keys';

import { CoursePermission as CPerm, CoursePermissionOptions as CPermOpts } from '@/permissions';

import { Rubric } from '@/models';

// @ts-ignore
import { store } from '@/store';
import { NONEXISTENT } from '@/constants';
import * as utils from '@/utils/typed';

import * as assignmentState from '@/store/assignment-states';
import { NormalUserServerData, AnyUser, User } from './user';

const noop = (_: object): void => undefined as void;

/* eslint-disable camelcase */
interface AssignmentServerProps {
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
    group_set: any;
    division_parent_id: number | null;
    auto_test_id: number | null;
    files_upload_enabled: boolean;
    webhook_upload_enabled: boolean;
    max_submissions: number | null;
    amount_in_cool_off_period: number;
    lms_name: string | null;
    analytics_workspace_ids: number[];
    peer_feedback_settings: AssignmentPeerFeedbackSettings;

    deadline: string;
    created_at: string;
    reminder_time: string | null;
    cool_off_period: string;
}

export interface AssignmentUpdateableProps {
    state?: assignmentState.AssignmentStates;
    description?: string | null;
    name?: string | null;
    is_lti?: string | null;
    cgignore?: any;
    cgignore_version?: string | null;
    whitespace_linter?: any;
    done_type?: string | null;
    done_email?: string | null;
    fixed_max_rubric_points?: number | null;
    max_grade?: number | null;
    group_set?: any;
    division_parent_id?: number | null;
    auto_test_id?: number | null;
    files_upload_enabled?: boolean;
    webhook_upload_enabled?: boolean;
    max_submissions?: number | null;
    amount_in_cool_off_period?: number;

    // Special properties that also may be set.
    reminderTime?: moment.Moment;
    deadline?: moment.Moment;
    graders?: NormalUserServerData[] | null;
    cool_off_period?: number;
    peer_feedback_settings?: AssignmentPeerFeedbackSettings | null;
}

const ALLOWED_UPDATE_PROPS = new Set(keys<AssignmentUpdateableProps>());

export interface AssignmentPeerFeedbackSettings {
    time: number;
    amount: number;
}

type Mutable<T extends { [x: string]: any }, K extends string> = { [P in K]: T[P] };

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

    readonly group_set!: any;

    readonly division_parent_id!: number | null;

    readonly auto_test_id!: number | null;

    readonly files_upload_enabled!: boolean;

    readonly webhook_upload_enabled!: boolean;

    readonly max_submissions!: number | null;

    readonly amount_in_cool_off_period!: number;

    readonly lms_name!: string | null;

    readonly coolOffPeriod!: moment.Duration;

    readonly courseId!: number;

    readonly canManage!: boolean;

    readonly deadline!: moment.Moment;

    readonly createdAt!: moment.Moment;

    readonly reminderTime!: moment.Moment;

    readonly graderIds?: number[] | null;

    readonly analytics_workspace_ids!: number[];

    readonly peer_feedback_settings!: AssignmentPeerFeedbackSettings;
}
/* eslint-enable camelcase */

// eslint-disable-next-line
export class Assignment extends AssignmentData {
    private constructor(props: AssignmentData) {
        super(props);
        Object.freeze(this);
    }

    static fromServerData(serverData: AssignmentServerProps, courseId: number, canManage: boolean) {
        const props = keys<AssignmentServerProps>().reduce((acc, prop) => {
            switch (prop) {
                case 'deadline':
                case 'created_at':
                case 'reminder_time':
                case 'cool_off_period': {
                    break;
                }
                default: {
                    const value = serverData[prop];
                    // Just to make sure this property is found in acc.
                    noop(acc[prop]);
                    // @ts-ignore
                    acc[prop] = value;
                }
            }
            return acc;
        }, {} as Mutable<AssignmentData, keyof AssignmentData>);

        props.courseId = courseId;
        props.canManage = canManage;

        props.deadline = moment.utc(serverData.deadline, moment.ISO_8601);
        props.createdAt = moment.utc(serverData.created_at, moment.ISO_8601);

        props.reminderTime = moment.utc(serverData.reminder_time as string, moment.ISO_8601);

        props.coolOffPeriod = moment.duration(serverData.cool_off_period, 'seconds');

        return new Assignment(props);
    }

    get course(): Record<string, any> {
        return store.getters['courses/courses'][this.courseId];
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

    get hasDeadline(): boolean {
        return this.deadline.isValid();
    }

    // eslint-disable-next-line
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

    getSubmitDisabledReasons(now: moment.Moment = moment()): string[] {
        const res = [];

        if (
            !(
                this.hasPermission(CPerm.canSubmitOwnWork) ||
                this.hasPermission(CPerm.canSubmitOthersWork)
            )
        ) {
            res.push('you cannot submit work for this course');
        }

        if (!this.hasDeadline) {
            res.push("the assignment's deadline has not yet been set");
        }

        if (!this.hasPermission(CPerm.canUploadAfterDeadline) && this.deadlinePassed(now)) {
            res.push("the assignment's deadline has passed");
        }

        return res;
    }

    canSubmitWork(now: moment.Moment = moment()): boolean {
        return this.getSubmitDisabledReasons(now).length === 0;
    }

    get maxGrade() {
        return this.max_grade == null ? 10 : this.max_grade;
    }

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
        let permName;
        if (typeof permission === 'string') {
            permName = permission;
        } else {
            permName = permission.value;
        }
        return !!(this.course?.permissions ?? {})[permName];
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

    get rubric(): Rubric<number> | NONEXISTENT | undefined {
        return store.getters['rubrics/rubrics'][this.id];
    }

    update(newProps: AssignmentUpdateableProps) {
        return new Assignment(
            Object.assign(
                {},
                this,
                Object.keys(newProps).reduce((acc, key) => {
                    // @ts-ignore
                    if (!ALLOWED_UPDATE_PROPS.has(key)) {
                        // @ts-ignore
                        const value: object = newProps[key];
                        throw TypeError(`Cannot set assignment property: ${key} to ${value}`);
                    }

                    if (key === 'graders') {
                        const value = newProps[key];
                        if (value == null) {
                            acc.graderIds = null;
                        } else {
                            value.forEach(grader =>
                                store.dispatch(
                                    'users/addOrUpdateUser',
                                    {
                                        user: grader,
                                    },
                                    { root: true },
                                ),
                            );
                            acc.graderIds = value.map(g => g.id);
                        }
                    } else if (key === 'deadline' || key === 'reminderTime') {
                        const value = newProps[key];
                        if (!moment.isMoment(value)) {
                            throw new Error(`${key} can only be set as moment`);
                        }
                        acc[key] = value;
                    } else if (key === 'cool_off_period') {
                        const value = newProps[key];
                        acc.coolOffPeriod = moment.duration(value, 'seconds');
                    } else {
                        // @ts-ignore
                        const value: any = newProps[key];
                        // @ts-ignore
                        acc[key] = value;
                    }

                    return acc;
                }, {} as Mutable<AssignmentData, keyof AssignmentData>),
            ),
        );
    }
}
