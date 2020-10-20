/* SPDX-License-Identifier: AGPL-3.0-only */
import { AssignmentsStore, store } from '@/store';
import { formatGrade, snakeToCamelCase, readableFormatDate } from '@/utils';
import moment from 'moment';
import * as mutationTypes from '@/store/mutation-types';

const SUBMISSION_SERVER_PROPS = ['id', 'origin', 'extra_info', 'grade_overridden', 'comment'];

const USER_PROPERTIES = Object.freeze(['user', 'assignee', 'comment_author']);
const USER_PROPERTIES_CAMELCASE_LOOKUP = Object.freeze(
    USER_PROPERTIES.reduce((acc, cur) => {
        acc[cur] = `${snakeToCamelCase(cur)}Id`;
        return acc;
    }, {}),
);

export class Submission {
    constructor(props) {
        Object.assign(this, props);
        this.grade = formatGrade(this.fullGrade);
        this.formattedCreatedAt = readableFormatDate(this.createdAt);
        Object.freeze(this);
    }

    static fromServerData(serverData, assignmentId) {
        const props = {};
        SUBMISSION_SERVER_PROPS.forEach(prop => {
            props[prop] = serverData[prop];
        });

        props.assignmentId = assignmentId;
        props.createdAt = moment.utc(serverData.created_at, moment.ISO_8601);
        props.fullGrade = serverData.grade;

        USER_PROPERTIES.forEach(serverProp => {
            const user = serverData[serverProp];
            const idProp = USER_PROPERTIES_CAMELCASE_LOOKUP[serverProp];

            if (user != null) {
                props[idProp] = user.id;
                store.commit(`users/${mutationTypes.ADD_OR_UPDATE_USER}`, user);
            } else {
                props[idProp] = null;
            }
        });

        return new Submission(props);
    }

    get fileTree() {
        return store.getters['fileTrees/getFileTree'](this.assignmentId, this.id);
    }

    get feedback() {
        return store.getters['feedback/getFeedback'](this.assignmentId, this.id);
    }

    update(newProps) {
        return new Submission(
            Object.assign(
                {},
                this,
                Object.entries(newProps).reduce((acc, [key, val]) => {
                    if (key === 'id') {
                        throw TypeError(`Cannot set submission property: ${key}`);
                    } else if (key === 'grade') {
                        acc.fullGrade = val;
                    } else if (USER_PROPERTIES_CAMELCASE_LOOKUP[key] != null) {
                        const prop = USER_PROPERTIES_CAMELCASE_LOOKUP[key];

                        if (val) {
                            store.dispatch('users/addOrUpdateUser', { user: val });
                            acc[prop] = val.id;
                        } else {
                            acc[prop] = null;
                        }
                    } else {
                        acc[key] = val;
                    }

                    return acc;
                }, {}),
            ),
        );
    }

    get assignment() {
        return AssignmentsStore.getAssignment()(this.assignmentId).extract();
    }

    isLate() {
        if (this.assignment == null) {
            return false;
        }
        return this.createdAt.isAfter(this.assignment.deadline);
    }
}

USER_PROPERTIES.forEach(wantedProp => {
    const idProp = USER_PROPERTIES_CAMELCASE_LOOKUP[wantedProp];

    Object.defineProperty(Submission.prototype, wantedProp, {
        get() {
            return store.getters['users/getUser'](this[idProp]) || { id: null };
        },
        enumerable: false,
    });
});
