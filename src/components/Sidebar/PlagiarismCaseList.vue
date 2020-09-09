<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="plagiarism-case-list sidebar-list-wrapper">
    <div class="sidebar-filter">
        <input class="form-control"
               placeholder="Filter courses"
               v-model="filter"
               ref="filter">
    </div>

    <infinite-plagiarism-case-list
        class="sidebar-list"
        :filter="filter"
        v-if="cases.length > 0"
        :run="run">
        <ul style="padding: 0;"
            slot-scope="{ cases }">
            <li v-for="curCase in cases"
                class="sidebar-list-item"
                :class="{ 'light-selected': curCase.id ===  plagiarismCaseId }">
                <router-link class="sidebar-item name"
                             :to="caseRoute(curCase)">
                    <div class="name-user" style="width: 100%">
                        <user :user="curCase.users[0]"/>
                    </div>
                    <div style="display: flex;">
                        <div class="name-user" style="flex: 0 1 auto; margin-right: 5px">
                            <user :user="curCase.users[1]"/>
                        </div>
                        <div>
                            <sup v-b-popover.hover.top="getOtherAssignmentPlagiarismDesc(curCase, 1)"
                                 v-if="curCase.assignments[1].id != run.assignment.id"
                                 class="description"
                                 >*</sup>
                        </div>
                    </div>
                    <small style="display: block; line-height: 1.3em">
                        Avg. match: {{ curCase.match_avg.toFixed(0) }}% &ndash;
                        Max. match: {{ curCase.match_max.toFixed(0) }}%
                    </small>
                </router-link class="sidebar-item">
            </li>
        </ul>
    </infinite-plagiarism-case-list>
    <span v-else class="sidebar-list no-items-text">
        No plagiarism cases found
    </span>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';
import { getOtherAssignmentPlagiarismDesc } from '@/utils';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/plus';

import User from '@/components/User';
import InfinitePlagiarismCaseList from '@/components/InfinitePlagiarismCaseList';

export default {
    name: 'plagiarism-case-list',

    props: {
        data: {
            type: Object,
            default: null,
        },
    },

    data() {
        return {
            filter: '',
            getOtherAssignmentPlagiarismDesc,
        };
    },

    computed: {
        ...mapGetters('plagiarism', ['runs']),

        plagiarismRunId() {
            return `${this.$route.params.plagiarismRunId}`;
        },

        plagiarismCaseId() {
            return Number(this.$route.params.plagiarismCaseId);
        },

        run() {
            return this.runs[this.plagiarismRunId];
        },

        cases() {
            return (this.run && this.run.cases) || [];
        },
    },

    async mounted() {
        this.$root.$on('sidebar::reload', this.reload);

        if (this.run == null) {
            await this.reload();
        }

        await this.$nextTick();
        const activeEl = document.activeElement;
        if (
            !activeEl ||
            !activeEl.matches('input, textarea') ||
            activeEl.closest('.sidebar .submenu')
        ) {
            this.$refs.filter.focus();
        }
    },

    destroyed() {
        this.$root.$off('sidebar::reload', this.reload);
    },

    methods: {
        ...mapActions('plagiarism', ['refreshRun']),

        caseRoute(curCase) {
            return {
                name: 'plagiarism_detail',
                params: {
                    courseId: this.run.assignment.course_id,
                    assignmentId: this.run.assignment.id,
                    plagiarismRunId: this.run.id,
                    plagiarismCaseId: curCase.id,
                },
            };
        },

        reload() {
            this.$emit('loading');
            return this.refreshRun(this.plagiarismRunId).then(() => {
                this.$emit('loaded');
            });
        },
    },

    components: {
        Icon,
        User,
        InfinitePlagiarismCaseList,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

a {
    text-decoration: none;
    color: inherit;
    max-width: 100%;
    width: 100%;
    align-items: baseline;
    .name-user {
        white-space: nowrap;
        text-overflow: ellipsis;
        line-height: 1.5em;
        overflow-x: hidden;
    }
}

.load-more-cases-btn {
    display: block;
    margin: 15px auto;
}
</style>
