/* SPDX-License-Identifier: AGPL-3.0-only */
import axios from 'axios';
import moment from 'moment';

import { getNoNull, nameOfUser, formatDate } from '@/utils/typed';

// @ts-ignore
import { store } from '@/store';

/* eslint-disable camelcase */
export interface GroupServerData {
    id: number;
    members: UserServerData[];
    name: string;
    group_set_id: number;
    created_at: string;

    virtual_user?: UserServerData;
}

export interface BaseUserServerData {
    id: number;
    name: string;
    username: string;
    is_test_student?: boolean;

    email?: string;
    hidden?: boolean;
}
/* eslint-enable camelcase */

export interface GroupUserServerData extends BaseUserServerData {
    group: GroupServerData;
}

export interface NormalUserServerData extends BaseUserServerData {
    group: null;
}

export type UserServerData = NormalUserServerData | GroupUserServerData;

export abstract class User implements BaseUserServerData {
    readonly id: number;

    readonly name: string;

    readonly username: string;

    // eslint-disable-next-line camelcase
    readonly is_test_student: boolean;

    readonly readableName: string;

    abstract readonly group: Group | null;

    abstract readonly isGroup: boolean;

    constructor(data: BaseUserServerData, oldObject: User | null = null) {
        this.id = data.id;
        this.name = getNoNull('name', data, oldObject);
        this.username = getNoNull('username', data, oldObject);
        this.is_test_student = getNoNull('is_test_student', data, oldObject) ?? false;

        this.readableName = nameOfUser(this);
    }

    abstract getContainedUsers(): NormalUser[];

    abstract getGroupMembers(): AnyUser[];

    get isTestStudent(): boolean {
        return !!this.is_test_student;
    }

    /* eslint-disable lines-between-class-members */
    public isEqualOrMemberOf(): false;
    public isEqualOrMemberOf(other: AnyUser): boolean;
    public isEqualOrMemberOf(other?: AnyUser): boolean {
        if (other == null) {
            return false;
        } else if (other.id === this.id) {
            return true;
        } else if (other.isGroup) {
            return this.isMemberOf(other.group);
        } else if (this.isGroup) {
            return other.isMemberOf(this.group);
        }
        return false;
    }
    /* eslint-enable lines-between-class-members */

    isMemberOf(group: Group | null): boolean {
        if (group == null) {
            return false;
        }

        return group.memberIds.some(memberId => memberId === this.id);
    }

    static findUserById(userId: number | null): AnyUser | null {
        if (userId == null) {
            return null;
        }
        return store.getters['users/getUser'](userId);
    }
}

export class Group implements GroupServerData {
    readonly id: number;

    readonly memberIds: number[];

    readonly name: string;

    readonly groupSetId: number;

    readonly createdAt: moment.Moment;

    constructor(data: GroupServerData) {
        // Make sure id can never be overridden, as this would break all code.
        this.id = data.id;

        data.members.forEach(user => {
            store.dispatch('users/addOrUpdateUser', { user });
        });

        this.memberIds = data.members.map(m => m.id);
        this.name = data.name;
        this.groupSetId = data.group_set_id;
        this.createdAt = moment.utc(data.created_at);
    }

    // eslint-disable-next-line camelcase
    get created_at() {
        return formatDate(this.createdAt);
    }

    // eslint-disable-next-line camelcase
    get group_set_id() {
        return this.groupSetId;
    }

    get members(): NormalUser[] {
        return this.memberIds.map(User.findUserById).filter((x): x is NormalUser => x != null);
    }

    getMemberStates(assignmentId: number): any {
        return axios.get(`/api/v1/assignments/${assignmentId}/groups/${this.id}/member_states/`);
    }
}

export class NormalUser extends User implements NormalUserServerData {
    readonly group: null;

    constructor(data: NormalUserServerData, oldObject: User | null = null) {
        super(data, oldObject);
        this.group = null;
        Object.freeze(this);
    }

    // eslint-disable-next-line class-methods-use-this
    getGroupMembers(): AnyUser[] {
        return [];
    }

    static getCurrentUser(): NormalUser {
        const myId = store.getters['user/id'];
        const res = User.findUserById(myId);
        if (res == null || res.isGroup) {
            throw new Error(`Could not find currently logged in user, found: ${res}`);
        }
        return res;
    }

    readonly isGroup: false = false;

    getContainedUsers(): NormalUser[] {
        return [this];
    }
}

export class GroupUser extends User implements GroupUserServerData {
    readonly group: Group;

    constructor(data: GroupUserServerData, oldObject: User | null = null) {
        super(data, oldObject);
        this.group = Object.freeze(new Group(data.group));
        Object.freeze(this);
    }

    getGroupMembers(): AnyUser[] {
        return this.group.members;
    }

    readonly isGroup: true = true;

    getContainedUsers(): NormalUser[] {
        return this.group.members;
    }
}

export function makeUser(data: UserServerData, oldObject: any = null): AnyUser {
    if (data.group == null) {
        return new NormalUser(data, oldObject);
    }
    return new GroupUser(data, oldObject);
}

export type AnyUser = NormalUser | GroupUser;
