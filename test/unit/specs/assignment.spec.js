/* SPDX-License-Identifier: AGPL-3.0-only */
import moment from 'moment';
import { store } from '@/store';

import * as mutationTypes from '@/store/mutation-types';

import * as assignmentState from '@/store/assignment-states';
import { formatDate } from '@/utils';
import { CoursesStore, AssignmentsStore } from '@/store';

jest.useFakeTimers();

describe('assignment model', () => {
    const makeAssig = (() => {
        let courseId = 0;
        let assigId = 0;

        return (assigServerData = {}) => {
            const cId = assigServerData.courseId || ++courseId;
            const aId = assigServerData.a || ++assigId;
            const hadCourse = CoursesStore.getCourse()(cId).isJust();

            Object.assign(assigServerData, {
                id: aId,
                course_id: cId,
                name: `Assignment ${aId}`,
            });
            CoursesStore.addCourse({
                course: {
                    id: cId,
                    name: `Course ${cId}`,
                    assignments: [assigServerData]
                },
            });
            if (!hadCourse) {
                CoursesStore.commitPermissions({ permissions: { [cId]: { } } });
            }
            return AssignmentsStore.getAssignment()(assigServerData.id).unsafeCoerce();
        };
    })();

    function updatePerms(assig, perms) {
        Object.entries(perms).forEach(([perm, value]) => {
            CoursesStore.commitPermission({
                courseId: assig.courseId,
                perm,
                value,
            });
        });
    }

    describe('canSeeGrade', () => {
        it.each([
            assignmentState.HIDDEN,
            assignmentState.SUBMITTING,
            assignmentState.GRADING,
            assignmentState.OPEN,
        ])('should return false when the assignment state is %s and you don\'t have permission can_see_grade_before_open', (state) => {
            const assig = makeAssig({ state });
            CoursesStore.commitPermission({
                courseId: assig.courseId,
                perm: 'can_see_grade_before_open',
                value: false,
            });

            expect(assig.canSeeGrade()).toBe(false);
        });

        it('should return true when the assignment state is done', () => {
            const assig = makeAssig({ state: assignmentState.DONE });
            CoursesStore.commitPermission({
                courseId: assig.courseId,
                perm: 'can_see_grade_before_open',
                value: false,
            });

            expect(assig.canSeeGrade()).toBe(true);
        });

        it.each([
            assignmentState.HIDDEN,
            assignmentState.SUBMITTING,
            assignmentState.GRADING,
            assignmentState.OPEN,
        ])('should return true when you have the permission can_see_grade_before_open for every state', (state) => {
            const assig = makeAssig({ state });
            CoursesStore.commitPermission({
                courseId: assig.courseId,
                perm: 'can_see_grade_before_open',
                value: true,
            });

            expect(assig.canSeeGrade()).toBe(true);
        });
    });

    describe('canSubmitWork', () => {
        it('should return false when you cannot submit work', () => {
            const assig = makeAssig();
            updatePerms(
                assig,
                { can_submit_own_work: false, can_submit_others_work: false },
            )
            expect(assig.canSubmitWork(moment())).toBe(false);
        });

        it.each([
            [false],
            [true],
        ])('should return true when the assignment is hidden', (submitOwn) => {
            const now = moment();
            let assig = makeAssig({
                state: assignmentState.HIDDEN,
                deadline: formatDate(moment().add(1, 'days')),
            });
            updatePerms(
                assig,
                { can_submit_own_work: true, can_submit_others_work: false },
            );
            expect(assig.canSubmitWork(now)).toBe(true);

            updatePerms(
                assig,
                {
                    can_submit_own_work: false,
                    can_submit_others_work: true,
                },
            );
            expect(assig.canSubmitWork(now)).toBe(true);

            CoursesStore.commitPermission({
                courseId: assig.courseId,
                perm: 'can_submit_own_work',
                value: true,
            });
            expect(assig.canSubmitWork(now)).toBe(true);
        });

        it('should return false when the deadline has passed and you do not have permission to submit after the deadline', () => {
            const now = moment();
            const assigData = {
                id: 1000,
                courseId: 1000,
                state: assignmentState.OPEN,
                deadline: formatDate(moment(now).add(-1, 'days')),
            };
            let assig = makeAssig(assigData);
            updatePerms(assig, {
                can_submit_own_work: true,
                can_submit_others_work: false,
                can_upload_after_deadline: false,
            });

            expect(assig.canSubmitWork(now)).toBe(false);

            updatePerms(assig, {
                can_submit_own_work: false,
                can_submit_others_work: true,
            });
            expect(assig.canSubmitWork(now)).toBe(false);

            updatePerms(assig, { can_submit_own_work: true });
            expect(assig.canSubmitWork(now)).toBe(false);

            assigData.state = assignmentState.DONE;
            updatePerms(assig, { can_submit_others_work: false });
            assig = makeAssig(assigData);
            expect(assig.canSubmitWork(now)).toBe(false);

            updatePerms(assig, {
                can_submit_own_work: false,
                can_submit_others_work: true,
            });
            expect(assig.canSubmitWork(now)).toBe(false);

            updatePerms(assig, { can_submit_own_work: true });
            expect(assig.canSubmitWork(now)).toBe(false);

        });

        it('should return true when you can submit work, the assignment is not hidden, and the deadline has not passed', () => {
            const now = moment();
            const assigData = {
                state: assignmentState.OPEN,
                deadline: moment(now).add(1, 'days'),
            };
            let assig = makeAssig(assigData);
            updatePerms(assig, {
                can_submit_own_work: true,
                can_submit_others_work: false,
            })

            expect(assig.canSubmitWork(now)).toBe(true);

            assig = makeAssig({
                ...assig,
                state: assignmentState.DONE,
            });
            expect(assig.canSubmitWork(now)).toBe(true);
        });
    });

    describe('deadlinePassed', () => {
        it.each([
            [-1, 'minutes'],
            [-1, 'hours'],
            [-1, 'days'],
            [-1, 'months'],
            [-1, 'years'],
            [1, 'minutes'],
            [1, 'hours'],
            [1, 'days'],
            [1, 'months'],
            [1, 'years'],
        ])('should return true (false) when the deadline has (not) passed', (delta, type) => {
            const now = moment.utc();
            const givenDeadline = now.clone().add(delta, type).toISOString();
            const assig = makeAssig({
                deadline: givenDeadline,
            });

            expect(assig.deadlinePassed(now)).toBe(delta < 0 ? true : false);
        });
    });

    describe('maxGrade', () => {
        it('should return the value if it is set', () => {
            const assig = makeAssig({
                max_grade: 15,
                course: {},
            });

            expect(assig.maxGrade).toBe(15);
        });

        it('should default to 10', () => {
            const assig = makeAssig({
                max_grade: null,
                course: {},
            });

            expect(assig.maxGrade).toBe(10);
        });
    });

    describe('getFormattedDeadline', () => {
        it('should return the value if it is set', () => {
            const assig = makeAssig({
                deadline: moment().toISOString(),
                course: {},
            });

            expect(assig.getFormattedDeadline()).toMatch(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}/);
        });

        it('should default to null', () => {
            const assig = makeAssig({
                deadline: null,
                course: {},
            });

            expect(assig.getFormattedDeadline()).toBe(null);
        });
    });

    describe('getFormattedCreatedAt', () => {
        it('should return always return a value', () => {
            const assig = makeAssig({
                created_at: moment().toISOString(),
                course: {},
            });

            expect(assig.getFormattedCreatedAt()).toMatch(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}/);
        });
    });
});
