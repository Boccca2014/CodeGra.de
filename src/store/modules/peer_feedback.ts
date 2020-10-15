/* SPDX-License-Identifier: AGPL-3.0-only */
import { getStoreBuilder, BareActionContext } from 'vuex-typex';
import * as utils from '@/utils';
import * as api from '@/api/v1';

import * as models from '@/models';
import { RootState } from '@/store/state';

const storeBuilder = getStoreBuilder<RootState>();

export interface PeerFeedbackState {
    connections: {
        [assginmentId: number]: {
            [userId: number]: Set<number>;
        };
    };
}

const moduleBuilder = storeBuilder.module<PeerFeedbackState>('peer_feedback', {
    connections: {},
});

function addOrUpdateUser(
    context: BareActionContext<any, RootState, any>,
    user: models.UserServerData,
): Promise<unknown> {
    return (context as any).dispatch('users/addOrUpdateUser', { user }, { root: true });
}

export namespace PeerFeedbackStore {
    const loaders = {
        peerFeedbackConnections: <Record<number, Record<number, Promise<unknown>>>>{},
    };

    export const commitClearConnections = moduleBuilder.commit((state, _: void) => {
        state.connections = {};
        loaders.peerFeedbackConnections = {};
    }, 'commitClearConnections');

    export const commitSetConnectionsForUser = moduleBuilder.commit(
        (
            state,
            payload: {
                assignmentId: number;
                peerId: number;
                subjects: readonly models.UserServerData[];
            },
        ) => {
            if (state.connections[payload.assignmentId] == null) {
                utils.vueSet(state.connections, payload.assignmentId, {});
            }
            utils.vueSet(
                state.connections[payload.assignmentId],
                payload.peerId,
                new Set(payload.subjects.map(s => s.id)),
            );
        },
        'commitSetConnectsionsForUser',
    );

    // eslint-disable-next-line
    function _getConnectionsForUser(
        state: PeerFeedbackState,
    ): (assignmentId: number, userId: number) => utils.Maybe<ReadonlyArray<models.AnyUser>> {
        return (assignmentId: number, userId: number) => {
            const userIds = utils.Maybe.fromNullable(state.connections[assignmentId]?.[userId]);
            return userIds.map(ids =>
                utils.sortBy(
                    utils.filterMap(
                        Array.from(ids, id => models.User.findUserById(id)),
                        item => utils.Maybe.fromNullable(item),
                    ),
                    user => [user.readableName],
                ),
            );
        };
    }

    export const getConnectionsForUser = moduleBuilder.read(
        _getConnectionsForUser,
        'getConnectionsForUser',
    );

    export const loadConnectionsForUser = moduleBuilder.dispatch(
        (context, payload: { assignmentId: number; userId: number; force?: boolean }) => {
            const { assignmentId, userId, force = false } = payload;
            if (!force && _getConnectionsForUser(context.state)(assignmentId, userId).isJust()) {
                return null;
            }

            if (force || loaders.peerFeedbackConnections?.[assignmentId]?.[userId] == null) {
                const loader = api.assignments
                    .getPeerFeedbackSubjects(assignmentId, userId)
                    .then(async ({ data }) => {
                        utils.vueDelete(loaders.peerFeedbackConnections[assignmentId], userId);
                        const users = data.map(d => d.subject);
                        await Promise.all(users.map(user => addOrUpdateUser(context, user)));
                        if (data.length > 0) {
                            await addOrUpdateUser(context, data[0].peer);
                        }
                        PeerFeedbackStore.commitSetConnectionsForUser({
                            assignmentId,
                            peerId: userId,
                            subjects: users,
                        });
                    });
                utils.setProps(loaders.peerFeedbackConnections, loader, assignmentId, userId);
            }

            return loaders.peerFeedbackConnections[assignmentId][userId];
        },
        'loadConnectionsForUser',
    );
}
