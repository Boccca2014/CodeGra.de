<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-input-group class="submission-nav-bar">
    <b-button-group class="nav-wrapper">
        <b-button-group v-if="showUserButtons && filteredSubmissions.length > 1"
                        v-b-popover.hover.bottom="prevSub == null ? 'No previous submission' : generatePopoverTitle(prevSub)">
            <b-button :disabled="prevSub == null"
                      @click="selectSub(prevSub)"
                      class="prev flex-grow-0">
                <icon name="angle-left"/>
            </b-button>
        </b-button-group>

        <b-dropdown @show="onDropdownShow" v-if="curSub"
                    class="title navbar-old-subs-dropdown"
                    :class="subLate(curSub) ? 'current-sub-late' : ''">
            <span slot="button-content"
                  class="text-center flex-grow-1">
                <user :user="curSub.user"/> at {{ curSub.formattedCreatedAt }}
                <webhook-name :submission="curSub" />
                <late-submission-icon :submission="curSub"
                                      :assignment="assignment"/>
                <icon name="exclamation-triangle"
                      class="text-warning ml-1"
                      style="margin-bottom: -1px;"
                      v-b-popover.top.hover="'You are currently not viewing the latest submission.'"
                      v-if="notLatest"/>
                <icon name="exclamation-triangle"
                      class="text-warning ml-1"
                      style="margin-bottom: -1px;"
                      v-b-popover.top.hover="`This user is member of the group ${quote}${groupOfUser.group.name}${quote}, which also created a submission.`"
                      v-else-if="groupOfUser"/>
            </span>

            <template v-if="!loadingOldSubs && loadedOldSubs">
                <b-dropdown-item v-if="oldSubmissions.length === 0">
                    <b>No submissions found on the server</b>
                </b-dropdown-item>

                <b-dropdown-item v-else
                                 v-for="sub in oldSubmissions"
                                 :key="sub.id"
                                 href="#"
                                 @click="selectSub(sub)"
                                 class="text-center"
                                 :active="sub.id === curSub.id"
                                 :class="{'sub-late': subLate(sub)}">
                    <template v-if="hasMixedSubmissions">
                        <user :user="sub.user" /> at
                    </template>
                    {{ sub.formattedCreatedAt }}
                    <webhook-name :submission="sub" />
                    <template v-if="sub.grade != null">
                        graded with a {{ sub.grade }}
                    </template>
                    <template v-if="sub === oldSubmissions[0]">
                        <i>(Newest version)</i>
                    </template>
                    <late-submission-icon
                        hide-popover
                        :submission="sub"
                        :assignment="assignment"/>
                </b-dropdown-item>
            </template>

            <b-dropdown-item v-else>
                <loader :scale="1"
                        class="text-center m-2"
                        :center="true"/>
            </b-dropdown-item>
        </b-dropdown>

        <div class="title placeholder" v-else>
            -
        </div>
        <b-button-group v-if="showUserButtons && filteredSubmissions.length > 1"
                        v-b-popover.hover.bottom="nextSub == null ? 'No next submission' : generatePopoverTitle(nextSub)">
            <b-button :disabled="nextSub == null"
                      @click="selectSub(nextSub)"
                      class="next flex-grow-0">
                <icon name="angle-right"/>
            </b-button>
        </b-button-group>
    </b-button-group>
</b-input-group>
</template>

<script>
import { parseBool, nameOfUser } from '@/utils';
import FilterSubmissionsManager from '@/utils/FilterSubmissionsManager';
import { mapGetters, mapActions } from 'vuex';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/angle-left';
import 'vue-awesome/icons/exclamation-triangle';
import 'vue-awesome/icons/angle-right';

import * as models from '@/models';

import User from './User';
import Loader from './Loader';
import LateSubmissionIcon from './LateSubmissionIcon';
import WebhookName from './WebhookName';

export default {
    name: 'submission-nav-bar',

    props: {
        latestSubmissions: {
            type: Array,
            required: true,
        },
        groupOfUser: {
            type: models.User,
            default: null,
        },
        currentSubmission: {
            type: Object,
            required: true,
        },
        notLatest: {
            type: Boolean,
            required: true,
        },
        showUserButtons: {
            type: Boolean,
            default: true,
        },
        assignment: {
            type: Object,
            required: true,
        },
    },

    data() {
        return {
            loadedOldSubs: false,
            loadingOldSubs: false,
            // For use in v-b-popover directives.
            quote: '"',
        };
    },

    watch: {
        assignmentId() {
            this.loadedOldSubs = false;
        },

        curUserId() {
            this.loadedOldSubs = false;
        },

        showUserButtons() {
            this.loadedOldSubs = false;
        },
    },

    computed: {
        ...mapGetters({
            loggedInUserId: 'user/id',
        }),
        ...mapGetters('submissions', ['getGroupSubmissionOfUser', 'getSubmissionsByUser']),

        userIdsToShow() {
            const res = [this.curSub.userId];

            // If the prev/next buttons are disabled, try to load all
            // submissions by the current user, so if this is a single user
            // submission, also load submissions by the user's group, and
            // vice versa.
            if (!this.showUserButtons) {
                let userId;

                if (this.curSub.user.group != null) {
                    userId = this.loggedInUserId;
                } else {
                    userId = this.$utils.getProps(
                        this.getGroupSubmissionOfUser(this.assignmentId, this.loggedInUserId),
                        null,
                        'userId',
                    );
                }

                if (userId != null) {
                    res.push(userId);
                }
            }

            return res;
        },

        oldSubmissions() {
            const subs = this.userIdsToShow.reduce((acc, userId) => {
                acc.push(...this.getSubmissionsByUser(this.assignmentId, userId));
                return acc;
            }, []);
            subs.sort((a, b) => b.createdAt - a.createdAt);
            return subs;
        },

        curUserId() {
            return this.$utils.getProps(this.curSub, null, 'user', 'id');
        },

        curSub() {
            return this.currentSubmission;
        },

        loading() {
            return this.curSub == null;
        },

        assignmentId() {
            return this.assignment.id;
        },

        submissionId() {
            return Number(this.$route.params.submissionId);
        },

        filterAssignee() {
            return parseBool(this.$route.query.mine, true);
        },

        sortBy() {
            return this.$route.query.sortBy || 'user';
        },

        filter() {
            return this.$route.query.search;
        },

        sortAsc() {
            return parseBool(this.$route.query.sortAsc);
        },

        filterSubmissionsManager() {
            return new FilterSubmissionsManager(
                this.submissionId,
                this.$route.query.forceInclude,
                this.$route,
                this.$router,
            );
        },

        filteredSubmissions() {
            return this.filterSubmissionsManager.filter(this.latestSubmissions, {
                mine: this.filterAssignee,
                userId: this.loggedInUserId,
                filter: this.filter,
                sortBy: this.sortBy,
                asc: this.sortAsc,
            });
        },

        optionIndex() {
            if (this.loading) {
                return null;
            }
            return this.filteredSubmissions.findIndex(sub => sub.userId === this.curSub.userId);
        },

        prevSub() {
            if (this.loading) {
                return null;
            }
            if (this.optionIndex > 0 && this.optionIndex < this.filteredSubmissions.length) {
                return this.filteredSubmissions[this.optionIndex - 1];
            }
            return null;
        },

        nextSub() {
            if (this.loading) {
                return null;
            }
            if (this.optionIndex >= 0 && this.optionIndex < this.filteredSubmissions.length - 1) {
                return this.filteredSubmissions[this.optionIndex + 1];
            }
            return null;
        },

        hasMixedSubmissions() {
            const hasSingle = this.oldSubmissions.find(s => s.user.group == null);
            const hasGroup = this.oldSubmissions.find(s => s.user.group != null);

            return hasSingle && hasGroup;
        },
    },

    methods: {
        ...mapActions('submissions', ['loadSingleSubmission', 'loadSubmissionsByUser']),

        subLate(sub) {
            return sub.isLate();
        },

        selectSub(sub) {
            if (sub == null) {
                return;
            } else if (sub.id === this.curSub.id) {
                return;
            }

            this.$router.push(
                this.$utils.deepExtend({}, this.$route, {
                    name: 'submission',
                    params: {
                        submissionId: sub.id,
                        fileId: undefined,
                    },
                    query: {
                        revision: undefined,
                    },
                    hash: undefined,
                }),
            );
        },

        async onDropdownShow() {
            const sub = this.curSub;
            if (this.loadedOldSubs || sub == null) {
                return;
            }

            const assignmentId = this.assignment.id;

            this.loadingOldSubs = true;
            const promises = this.userIdsToShow.map(userId =>
                this.loadSubmissionsByUser({
                    assignmentId,
                    userId,
                }),
            );

            await Promise.all(promises);

            if (this.curSub && this.curSub.id === sub.id) {
                this.loadedOldSubs = true;
                this.loadingOldSubs = false;
            }
        },

        generatePopoverTitle(sub) {
            if (sub == null) {
                return '';
            }
            return `Go to ${sub && nameOfUser(sub.user)}'s submission`;
        },
    },

    components: {
        Icon,
        User,
        Loader,
        LateSubmissionIcon,
        WebhookName,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.nav-wrapper {
    flex: 1 1 auto;
}

.submission-nav-bar .dropdown button {
    width: 100%;
    font-size: 1rem;
    padding: 0.5rem;
}

.nav-wrapper .title {
    .default-text-colors;

    flex: 1;
    text-align: center;

    &.placeholder {
        background-color: white;
        border: 1px solid rgb(204, 204, 204);
        padding: 0.375rem 0.75rem;
    }
}
</style>

<style lang="less">
@import '~mixins.less';

.navbar-old-subs-dropdown {
    .dropdown-toggle {
        display: flex;
        align-items: center;
    }

    .dropdown-menu {
        width: 100%;
        overflow: auto;
        padding: 0;
    }

    &.current-sub-late .dropdown-toggle,
    .sub-late .dropdown-item {
        background-color: @color-danger-table-row !important;

        @{dark-mode} {
            color: @text-color !important;
            background-color: @color-danger-dark !important;
        }

        &:hover {
            background-color: saturate(darken(@color-danger-table-row, 5%), -20%) !important;

            @{dark-mode}.btn-secondary:not(.btn-success):not(.btn-danger):not(.btn-warning):not(.btn-info) {
                background-color: saturate(darken(@color-danger-dark, 5%), -20%) !important;
            }
        }
    }

    .fa-icon {
        transform: translateY(-2px);
    }
}
</style>
