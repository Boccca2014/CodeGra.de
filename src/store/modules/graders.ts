/* SPDX-License-Identifier: AGPL-3.0-only */
import { getStoreBuilder } from 'vuex-typex';
import * as utils from '@/utils';
import * as api from '@/api/v1';

import * as models from '@/models';
import { store } from '@/store';
import { RootState } from '@/store/state';

const storeBuilder = getStoreBuilder<RootState>();

export interface GradersState {
    graders: {
        [assignmentId: number]: models.Graders | null;
    };
}

const moduleBuilder = storeBuilder.module<GradersState>('graders', {
    graders: {},
});

export namespace GradersStore {
    const loaders = {
        graders: <Record<number, Promise<unknown>>>{},
    };

    // eslint-disable-next-line
    function _getGraders(state: GradersState) {
        return (assignmentId: number): models.Graders | null => {
            const graders = state.graders[assignmentId];
            if (graders == null) {
                return null;
            } else {
                return graders;
            }
        };
    }

    export const getGraders = moduleBuilder.read(_getGraders, 'getGraders');

    export const commitGraders = moduleBuilder.commit(
        (state, payload: { assignmentId: number; graders: models.Graders | null }) => {
            const { assignmentId, graders } = payload;
            utils.vueSet(state.graders, assignmentId, graders);
        },
        'commitGraders',
    );

    export const updateGraderState = moduleBuilder.commit(
        (state, payload: { assignmentId: number; status: { [userId: number]: boolean } }) => {
            const { assignmentId, status } = payload;
            const graders = state.graders[assignmentId];
            if (graders != null) {
                state.graders[assignmentId] = graders.map(grader =>
                    grader.setStatus(status[grader.userId]),
                );
            }
        },
        'updateGraderState',
    );

    export const loadGraders = moduleBuilder.dispatch(
        (context, payload: { assignmentId: number; force?: boolean }) => {
            const { assignmentId, force = false } = payload;
            if (!force && _getGraders(context.state)(assignmentId) != null) {
                return null;
            }

            if (force || loaders.graders[assignmentId] == null) {
                loaders.graders[assignmentId] = api.assignments
                    .getGraders(assignmentId)
                    .then(res => {
                        utils.vueDelete(loaders.graders, assignmentId);

                        let graders;
                        if (res.data == null) {
                            graders = null;
                        } else {
                            graders = res.data.map((grader: models.GraderServerData) => {
                                store.dispatch(
                                    'users/addOrUpdateUser',
                                    { user: grader },
                                    { root: true },
                                );
                                return models.Grader.fromServerData({
                                    userId: grader.id,
                                    weight: grader.weight,
                                    done: grader.done,
                                });
                            });
                        }

                        GradersStore.commitGraders({
                            assignmentId,
                            graders,
                        });
                    });
            }

            return loaders.graders[assignmentId];
        },
        'loadGraders',
    );
}
