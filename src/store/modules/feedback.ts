/* SPDX-License-Identifier: AGPL-3.0-only */
import { getStoreBuilder } from 'vuex-typex';
import * as utils from '@/utils';
import * as api from '@/api/v1';

import * as models from '@/models';
import { RootState } from '@/store/state';
import * as types from '../mutation-types';

const storeBuilder = getStoreBuilder<RootState>();

export interface FeedbackState {
    feedbacks: {
        [assignmentId: number]: {
            [submissionId: number]: models.Feedback;
        };
    };
    // Mapping from assignment id to mapping of user ids to a mapping of the
    // number of comments that user gave per submission.
    inlineFeedbackByUser: {
        [assignmentId: number]: { [userId: number]: { [submissionId: number]: number } };
    };
}

const moduleBuilder = storeBuilder.module<FeedbackState>('feedback', {
    feedbacks: {},
    inlineFeedbackByUser: {},
});

export namespace FeedbackStore {
    const loaders = {
        feedback: <Record<number, Promise<unknown>>>{},
        inlineFeedbackByUser: <Record<number, Record<number, Promise<unknown>>>>{},
    };

    // eslint-disable-next-line
    function _getFeedback(state: FeedbackState) {
        return (assignmentId: number, submissionId: number): models.Feedback | null =>
            state.feedbacks?.[assignmentId]?.[submissionId];
    }

    export const getFeedback = moduleBuilder.read(_getFeedback, 'getFeedback');

    // eslint-disable-next-line
    function _getSubmissionWithFeedbackByUser(state: FeedbackState) {
        return (assignmentId: number, userId: number) =>
            utils.getProps(state.inlineFeedbackByUser, null, assignmentId, userId);
    }

    export const getSubmissionWithFeedbackByUser = moduleBuilder.read(
        _getSubmissionWithFeedbackByUser,
        'getSubmissionWithFeedbackByUser',
    );

    export const commitSetFeedback = moduleBuilder.commit(
        (
            state,
            payload: { assignmentId: number; submissionId: number; feedback: models.Feedback },
        ) => {
            const trees = state.feedbacks[payload.assignmentId] ?? {};
            utils.vueSet(trees, payload.submissionId, payload.feedback);
            utils.vueSet(state.feedbacks, payload.assignmentId, trees);
        },
        'commitSetFeedback',
    );

    export const commitUpdateFeedback = moduleBuilder.commit(
        (
            state,
            payload: { assignmentId: number; submissionId: number; line: models.FeedbackLine },
        ) => {
            const { line, assignmentId, submissionId } = payload;
            const feedback = state.feedbacks[assignmentId][submissionId];
            let newFeedback;

            if (line.isEmpty) {
                newFeedback = feedback.removeFeedbackBase(line);
            } else {
                newFeedback = feedback.addFeedbackBase(line);
            }

            utils.vueSet(state.feedbacks[assignmentId], submissionId, newFeedback);
        },
        'commitUpdateFeedback',
    );

    export const commitDeleteFeedback = moduleBuilder.commit(
        (state, payload: { assignmentId: number }) => {
            utils.vueDelete(state.feedbacks, payload.assignmentId);
        },
        'commitDeleteFeedback',
    );

    export const commitDeleteAllFeedback = moduleBuilder.commit(state => {
        loaders.feedback = {};
        state.feedbacks = {};
    }, 'commitDeleteAllFeedback');

    export const commitUpdateGeneralFeedback = moduleBuilder.commit(
        (state, payload: { assignmentId: number; submissionId: number; comment: string }) => {
            const { assignmentId, submissionId, comment } = payload;
            const fb = state.feedbacks[assignmentId][submissionId];
            const newFb = fb.updateGeneralFeedback(comment);
            utils.vueSet(state.feedbacks[assignmentId], submissionId, newFb);
        },
        'commitUpdateGeneralFeedback',
    );

    export const commitSetFeedbackByUser = moduleBuilder.commit(
        (
            state,
            payload: {
                assignmentId: number;
                userId: number;
                comments: readonly models.FeedbackLine[];
            },
        ) => {
            if (state.inlineFeedbackByUser[payload.assignmentId] == null) {
                utils.vueSet(state.inlineFeedbackByUser, payload.assignmentId, {});
            }
            const submissionIds = payload.comments.reduce<{ [submissionId: number]: number }>(
                (acc, comment) => {
                    if (!utils.hasAttr(acc, comment.workId)) {
                        acc[comment.workId] = 0;
                    }
                    acc[comment.workId]++;
                    return acc;
                },
                {},
            );
            utils.vueSet(
                state.inlineFeedbackByUser[payload.assignmentId],
                payload.userId,
                submissionIds,
            );
        },
        'commitSetFeedbackByUser',
    );

    export const loadFeedback = moduleBuilder.dispatch(
        async (
            context,
            {
                assignmentId,
                submissionId,
                force = false,
            }: { assignmentId: number; submissionId: number; force?: boolean },
        ) => {
            if (!force && _getFeedback(context.state)(assignmentId, submissionId) != null) {
                return null;
            }

            if (force || loaders.feedback[submissionId] == null) {
                const loader = Promise.all([
                    (context as any).dispatch(
                        'submissions/loadSingleSubmission',
                        { assignmentId, submissionId },
                        {
                            root: true,
                        },
                    ),
                    api.submissions.getFeedbacks(submissionId).catch(err => {
                        delete loaders.feedback[submissionId];
                        return utils.handleHttpError(
                            {
                                403: () => ({ data: undefined }),
                            },
                            err,
                        );
                    }),
                ]).then(([, { data }]) => {
                    delete loaders.feedback[submissionId];
                    if (data != null) {
                        FeedbackStore.commitSetFeedback({
                            assignmentId,
                            submissionId,
                            feedback: models.Feedback.fromServerData(data),
                        });
                    }
                });

                loaders.feedback[submissionId] = loader;
            }

            return loaders.feedback[submissionId];
        },
        'loadFeedback',
    );

    export const addFeedbackLine = moduleBuilder.dispatch(
        async (
            _,
            payload: { assignmentId: number; submissionId: number; line: models.FeedbackLine },
        ) => {
            await FeedbackStore.loadFeedback(payload);

            FeedbackStore.commitUpdateFeedback(payload);
        },
        'addFeedbackLine',
    );

    export const deleteFeedback = moduleBuilder.dispatch((_, payload: { assignmentId: number }) => {
        FeedbackStore.commitDeleteFeedback(payload);
    }, 'deleteFeedback');

    export const updateGeneralFeedback = moduleBuilder.dispatch(
        async (
            context,
            payload: { assignmentId: number; submissionId: number; feedback: string | null },
        ) => {
            const { assignmentId, submissionId, feedback } = payload;
            FeedbackStore.loadFeedback(payload);

            return api.submissions.update(submissionId, { feedback: feedback ?? '' }).then(res => {
                // eslint-disable-next-line camelcase
                const { comment, comment_author } = res.data;
                FeedbackStore.commitUpdateGeneralFeedback({ assignmentId, submissionId, comment });
                (context as any).commit(
                    `submissions/${types.UPDATE_SUBMISSION}`,
                    {
                        submissionId,
                        submissionProps: {
                            comment,
                            comment_author,
                        },
                    },
                    { root: true },
                );
                return res;
            });
        },
        'updateGeneralFeedback',
    );

    export const loadInlineFeedbackByUser = moduleBuilder.dispatch(
        (context, payload: { assignmentId: number; userId: number; force?: boolean }) => {
            const { assignmentId, userId, force = false } = payload;
            if (
                !force &&
                _getSubmissionWithFeedbackByUser(context.state)(assignmentId, userId) != null
            ) {
                return null;
            }

            if (force || loaders.inlineFeedbackByUser?.[assignmentId]?.[userId] == null) {
                const loader = api.assignments
                    .getCommentsByUser(assignmentId, userId)
                    .then(({ data }) => {
                        utils.vueDelete(loaders.inlineFeedbackByUser[assignmentId], userId);
                        FeedbackStore.commitSetFeedbackByUser({
                            assignmentId,
                            userId,
                            comments: data.map(d => models.FeedbackLine.fromServerData(d)),
                        });
                    });
                utils.setProps(loaders.inlineFeedbackByUser, loader, assignmentId, userId);
            }

            return loaders.inlineFeedbackByUser[assignmentId][userId];
        },
        'loadInlineFeedbackByUser',
    );
}
