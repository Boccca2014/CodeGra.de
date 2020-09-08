/* SPDX-License-Identifier: AGPL-3.0-only */
import { LTIProviderServerData } from '@/api/v1/lti';
import { CoursePermission as CPerm, CoursePermissionOptions as CPermOpts } from '@/permissions';
import { AssignmentServerProps } from '@/models';
import moment from 'moment';
import { LTIProvider, makeProvider as makeLTIProvider } from '@/lti_providers';
import { CourseSnippet } from '@/interfaces';
import { Maybe, nonenumerable, filterMap, formatDate } from '@/utils';
import { AssignmentsStore, CoursesStore } from '@/store';
import { makeCache } from '@/utils/cache';
import { MANAGE_GENERAL_COURSE_PERMISSIONS } from '@/constants';

export enum CourseState {
    visible = 'visible',
    archived = 'archived',
    deleted = 'deleted',
}

/* eslint-disable camelcase */
interface CourseServerData {
    id: number;
    name: string;
    created_at: string;
    is_lti: boolean;
    virtual: boolean;
    lti_provider: null | LTIProviderServerData;
    state: CourseState;
}

interface GroupSetServerData {
    id: number;
    minimum_size: number;
    maximum_size: number;
    assignment_ids: ReadonlyArray<number>;
}

export interface CourseExtendedServerData extends CourseServerData {
    assignments: AssignmentServerProps[];
    group_sets: GroupSetServerData[];
    snippets: CourseSnippet[];
    role: string;
}
/* eslint-enable camelcase */

export interface CourseUpdatableProps {
    name: string;
    state: CourseState;
    groupSets: ReadonlyArray<GroupSetServerData>;
    snippets: ReadonlyArray<CourseSnippet>;
}

export class Course {
    @nonenumerable
    private _cache = makeCache('canManage', 'isStudent');

    constructor(
        public readonly id: number,
        public readonly name: string,
        public readonly createdAt: moment.Moment,
        public readonly virtual: boolean,
        public readonly state: CourseState,
        public readonly ltiProvider: Maybe<LTIProvider>,
        public readonly assignmentIds: ReadonlyArray<number>,
        public readonly groupSets: ReadonlyArray<GroupSetServerData>,
        public readonly snippets: ReadonlyArray<CourseSnippet>,
    ) {
        Object.freeze(this.assignmentIds);
        Object.freeze(this.groupSets);
        Object.freeze(this.snippets);
        Object.freeze(this);
    }

    get isLTI() {
        return this.ltiProvider.isJust();
    }

    get assignments() {
        return filterMap(this.assignmentIds, id => AssignmentsStore.getAssignment()(id));
    }

    get permissions() {
        return CoursesStore.getPermissionsForCourse()(this.id);
    }

    get canManage() {
        return this._cache.get('canManage', () => {
            const perms = this.permissions;
            return MANAGE_GENERAL_COURSE_PERMISSIONS.some(x => perms[x]);
        });
    }

    get canCreateAssignments(): boolean {
        return !!this.permissions.can_create_assignment;
    }

    static fromServerData(data: CourseExtendedServerData): Course {
        return new Course(
            data.id,
            data.name,
            moment.utc(data.created_at, moment.ISO_8601),
            data.virtual,
            data.state,
            Maybe.fromNullable(data.lti_provider).map(prov => makeLTIProvider(prov)),
            data.assignments.map(a => a.id),
            data.group_sets,
            data.snippets,
        );
    }

    get isStudent() {
        return this._cache.get(
            'isStudent',
            () =>
                !(
                    this.canManage ||
                    this.canCreateAssignments ||
                    this.assignments.some(a => a.canManage)
                ),
        );
    }

    // eslint-disable-next-line camelcase
    get created_at() {
        return formatDate(this.createdAt, true);
    }

    hasPermission(permission: CPerm | CPermOpts): boolean {
        let res;
        const allPerms = this.permissions;
        if (typeof permission === 'string') {
            res = allPerms[permission];
        } else {
            res = allPerms[permission.value];
        }
        return !!res;
    }

    update(props: CourseUpdatableProps): Course {
        return new Course(
            this.id,
            props.name ?? this.name,
            this.createdAt,
            this.virtual,
            this.state,
            this.ltiProvider,
            this.assignmentIds,
            props.groupSets ?? this.groupSets,
            props.snippets ?? this.snippets,
        );
    }

    get isArchived(): boolean {
        return this.state === CourseState.archived;
    }
}
