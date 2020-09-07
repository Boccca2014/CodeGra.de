<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="manage-course">
    <local-header always-show-extra-slot>
        <b-form-fieldset class="filter-input">
            <input v-model="filter"
                    class="form-control"
                    placeholder="Type to Search"/>
        </b-form-fieldset>

        <template slot="extra">
            <category-selector
                v-if="course"
                slot="extra"
                class="cat-selector"
                v-model="selectedCat"
                default="members"
                :categories="categories"/>
        </template>
    </local-header>

    <loader v-if="!course" page-loader/>

    <div class="content" v-else>
        <users-manager :class="{ hidden: selectedCat !== 'members'}"
                       class="cat-wrapper"
                       v-if="membersEnabled"
                       :course="course"
                       :filter="filter"/>
        <permissions-manager :class="{ hidden: selectedCat !== 'permissions' }"
                             v-if="permissionsEnabled"
                             class="cat-wrapper"
                             :course-id="course.id"
                             :filter="filter"/>
        <span :class="{ hidden: selectedCat !== 'groups' }"
              v-if="groupsEnabled"
              class="cat-wrapper">
            <group-set-manager :course="course"/>
        </span>

        <span :class="{ hidden: selectedCat !== 'snippets' }"
              class="cat-wrapper">
            <snippet-manager
                v-if="snippetsEnabled"
                :course="course"
                :editable="course.permissions.can_manage_course_snippets"/>
        </span>

        <div :class="{ hidden: selectedCat !== 'contact' }"
              class="cat-wrapper">
            <cg-catch-error capture>
                <template slot-scope="{ error }">
                    <b-alert v-if="error"
                             show
                             variant="danger">
                        {{ $utils.getErrorMessage(error) }}
                    </b-alert>

                    <student-contact
                        v-else
                        :initial-users="[]"
                        initially-everybody-by-default
                        reset-on-email
                        :course="course"
                        :default-subject="defaultEmailSubject"
                        no-cancel
                        :can-use-snippets="canUseSnippets"/>
                </template>
            </cg-catch-error>
        </div>
    </div>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import UsersManager from '@/components/UsersManager';
import PermissionsManager from '@/components/PermissionsManager';
import LocalHeader from '@/components/LocalHeader';
import Loader from '@/components/Loader';
import CategorySelector from '@/components/CategorySelector';
import GroupSetManager from '@/components/GroupSetManager';
import SnippetManager from '@/components/SnippetManager';
import StudentContact from '@/components/StudentContact';

import { setPageTitle } from './title';

export default {
    name: 'manage-course-page',

    data() {
        return {
            selectedCat: '',
            filter: '',
        };
    },

    computed: {
        ...mapGetters('courses', ['getCourse']),
        ...mapGetters('user', {
            userPerms: 'permissions',
        }),

        course() {
            return this.getCourse(this.courseId).extract();
        },

        courseId() {
            return Number(this.$route.params.courseId);
        },

        membersEnabled() {
            return this.course && this.course.permissions.can_edit_course_users;
        },

        permissionsEnabled() {
            return this.course && this.course.permissions.can_edit_course_roles;
        },

        groupsEnabled() {
            return (
                UserConfig.features.groups &&
                this.course &&
                this.course.permissions.can_edit_group_set
            );
        },

        snippetsEnabled() {
            return (
                this.course &&
                (this.course.permissions.can_manage_course_snippets ||
                    this.course.permissions.can_view_course_snippets)
            );
        },

        contactEnabled() {
            return (
                UserConfig.features.email_students &&
                    this.$utils.getProps(this.course, false, 'permissions', 'can_email_students')
            );
        },

        categories() {
            return [
                {
                    id: 'members',
                    name: 'Members',
                    enabled: this.membersEnabled,
                },
                {
                    id: 'permissions',
                    name: 'Permissions',
                    enabled: this.permissionsEnabled,
                },
                {
                    id: 'groups',
                    name: 'Groups',
                    enabled: this.groupsEnabled,
                },
                {
                    id: 'snippets',
                    name: 'Snippets',
                    enabled: this.snippetsEnabled,
                },
                {
                    id: 'contact',
                    name: 'Contact students',
                    enabled: this.contactEnabled,
                },
            ];
        },

        defaultEmailSubject() {
            return `[CodeGrade - ${this.course.name}] …`;
        },
        canUseSnippets() {
            return !!this.userPerms.can_use_snippets;
        },
    },

    watch: {
        courseId: {
            immediate: true,
            handler() {
                this.loadSingleCourse({ courseId: this.courseId });
            },
        },

        course() {
            if (this.course == null) {
                this.loadSingleCourse({ courseId: this.courseId });
            } else {
                setPageTitle(this.course.name);
            }
        },
    },

    methods: {
        ...mapActions('courses', ['loadSingleCourse']),
    },

    components: {
        UsersManager,
        PermissionsManager,
        LocalHeader,
        Loader,
        CategorySelector,
        GroupSetManager,
        SnippetManager,
        StudentContact,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.manage-course {
    display: flex;
    flex-direction: column;
}
.manage-course > .content {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
}

.filter-input {
    flex: 1 1 auto;
    margin-bottom: 0;
}

.cat-wrapper {
    transition: opacity @transition-duration ease-out;
    height: 100%;
    padding-top: 5px;

    &.hidden {
        height: 0;
        overflow: hidden;
        padding: 0;
        transition: none;
        opacity: 0;
        max-height: 0;
    }
}
</style>
