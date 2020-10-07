<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="sidebar"
     :class="{ floating }"
     id="global-sidebar">
    <div class="main-menu" :class="{ show: mobileVisible }">
        <component :is="$inLTI ? 'div' : 'router-link'"
                   class="sidebar-top-item logo"
                   :class="{ 'cursor-default': $inLTI, 'no-hover': $inLTI }"
                   :to="$inLTI ? undefined : ({ name: 'home' })"
                   @click="$inLTI && closeSubMenu(true)">
            <cg-logo :small="!mobileVisible"
                     :inverted="!darkMode && $inLTI" />
        </component>
        <hr class="separator">
        <div class="sidebar-top">
            <transition v-for="entry in entries"
                        :key="`sidebar-transition-${entry.name}`"
                        v-if="maybeCall(entry.condition)"
                        name="pop-in"
                        :appear="loaded"
                        :enter-active-class="entry.animate || entry.animateAdd ? 'pop-in-enter-active' : ''"
                        :leave-active-class="entry.animate || entry.animateRemove ? 'pop-in-leave-active' : ''">
                <a @click="openUpperSubMenu(entry, true)"
                   class="sidebar-top-item sidebar-entry position-relative"
                   :class="{ selected: currentEntry && entry.name === currentEntry.name, [`sidebar-entry-${entry.name}`]: true }">
                    <icon :name="entry.icon"
                          :scale="mobileVisible ? 1.5 : 2.25"
                          :label="maybeCall(entry.title || entry.header)"/>
                    <icon name="bell"
                          :scale="0.75"
                          class="notification-bell"
                          :style="{ opacity: entry.hasNotification() ? 1 : 0 }"
                          v-b-popover.top.hover.window="'You have unread notifications'"
                          v-if="entry.canHaveNotification"
                          :label="maybeCall(entry.title || entry.header)"/>
                    <small class="name">{{ maybeCall(entry.title || entry.header) }}</small>
                </a>
            </transition>
        </div>

        <hr class="separator"/>

        <div v-if="canManageCurrentLtiAssignment">
            <div class="sidebar-bottom">
                <submit-button :submit="openRouteInTab"
                               class="new-tab-link sidebar-bottom-item d-inline border-0 rounded-0 shadow-none"
                               variant="secondary"
                               @success="afterOpenRouteInTab"
                               v-b-popover.top.hover="'Open this page in a new tab'">
                    <div class="new-tab-wrapper">
                        <icon name="share-square-o" :scale="1" class="mr-2" />
                        <small class="name new-tab">New tab</small>
                    </div>
                </submit-button>
            </div>

            <hr class="separator"/>
        </div>

        <div v-if="canManageSite">
            <div class="sidebar-bottom">
                <router-link :to="{ name: 'admin' }"
                             class="sidebar-bottom-item"
                             v-b-popover.hover.top="'Manage site'">
                    <icon name="tachometer"/>
                </router-link>
            </div>

            <hr class="separator"/>
        </div>

        <div class="sidebar-bottom">
            <a :href="`https://docs.codegra.de/?v=${version}`"
               target="_blank"
               class="sidebar-bottom-item"
               v-b-popover.hover.top="'Documentation'">
                <icon name="question"/>
            </a>

            <a href="#" @click="logout"
               class="sidebar-bottom-item"
               v-b-popover.hover.top="'Log out'"
               v-if="loggedIn && !$inLTI">
                <icon name="power-off"/>
            </a>
        </div>
    </div>

    <div class="shadow-overlay"/>

    <div class="submenu-container"
         :class="{ 'use-space': dimmingUseSpace, }"
         ref="subMenuContainer"
         v-if="subMenus.length">

        <div class="submenus">
            <div v-for="subMenu, i in subMenus"
                 class="submenu"
                 :id="`submenu-${i}`"
                 :style="subMenuStyle(subMenu)">
                <header>
                    <div class="action back-button"
                         v-b-popover.hover.bottom="i ? maybeCall(subMenus[i - 1].header) : 'Close submenu'"
                         @click="closeSubMenu()">
                        <icon :name="i ? 'arrow-left' : 'times'"/>
                    </div>

                    <h4 class="submenu-header">{{ maybeCall(subMenu.header) }}</h4>

                    <div v-if="subMenu.reload || loading"
                         @click="refreshItems"
                         class="action refresh-button"
                         v-b-popover.hover.bottom="'Refresh'">
                        <icon name="refresh"
                              :spin="loading"/>
                    </div>
                    <div v-else-if="loading"
                         class="action refresh-button"
                         v-b-popover.hover.bottom="'Refresh'">
                        <icon name="refresh"
                              spin/>
                    </div>
                </header>

                <hr class="separator"/>

                <component :is="subMenu.component"
                            v-show="subMenu.showWhenLoading || !loading"
                            :data="maybeCall(subMenu.data)"
                            @loading="loading = true"
                            @loaded="loading = false"
                            @open-menu="openSubMenu"
                            @close-menu="closeSubMenu(true)"/>
                <cg-loader v-if="loading && !subMenu.showWhenLoading"
                           :scale="1"
                           class="pt-2"/>
            </div>
        </div>
    </div>

    <div class="page-overlay"
         v-if="dimPage"
         @click="closeSubMenu(true)"/>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/arrow-left';
import 'vue-awesome/icons/book';
import 'vue-awesome/icons/edit';
import 'vue-awesome/icons/user-circle-o';
import 'vue-awesome/icons/power-off';
import 'vue-awesome/icons/rocket';
import 'vue-awesome/icons/question';
import 'vue-awesome/icons/tachometer';
import 'vue-awesome/icons/refresh';
import 'vue-awesome/icons/search';
import 'vue-awesome/icons/files-o';
import 'vue-awesome/icons/users';
import 'vue-awesome/icons/share-square-o';
import 'vue-awesome/icons/sign-in';
import 'vue-awesome/icons/bell';

import { Loader } from '@/components';
import SubmitButton from '@/components/SubmitButton';

import { NotificationStore } from '@/store/modules/notification';

import UserInfo from './UserInfo';
import CourseList from './CourseList';
import AssignmentList from './AssignmentList';
import PlagiarismCaseList from './PlagiarismCaseList';
import SubmissionsSidebarList from './SubmissionsSidebarList';
import GroupList from './GroupList';
import CgLogo from '../CgLogo';

import { MANAGE_SITE_PERIMSSIONS } from '../../constants';

const floatingRoutes = new Set([
    'home',
    'forgot',
    'submission',
    'submission_file',
    'plagiarism_overview',
    'plagiarism_detail',
]);
const hideRoutes = new Set([...floatingRoutes, 'login', 'register', 'reset-password', 'unsubscribe']);

export default {
    name: 'sidebar',

    data() {
        return {
            loading: true,
            loaded: false,
            entries: [
                {
                    name: 'login',
                    icon: 'sign-in',
                    title: 'Login',
                    condition: () => !this.loggedIn,
                    onClick: () => {
                        this.$router.push({ name: 'login' });
                    },
                },
                {
                    name: 'register',
                    icon: 'rocket',
                    header: 'Register',
                    condition: () => UserConfig.features.register && !this.loggedIn,
                    onClick: () => {
                        this.$router.push({ name: 'register' });
                    },
                },
                {
                    name: 'user',
                    icon: 'user-circle-o',
                    canHaveNotification: true,
                    hasNotification: () => NotificationStore.getHasUnreadNotifications(),
                    title: () => this.name,
                    header: 'User',
                    width: () => {
                        if (this.$root.$isLargeWindow) {
                            return 800;
                        } else {
                            return Math.min(800, this.$root.screenWidth - 100);
                        }
                    },
                    component: 'user-info',
                    condition: () => this.loggedIn,
                    animateAdd: true,
                },
                {
                    name: 'courses',
                    icon: 'book',
                    header: 'Courses',
                    component: 'course-list',
                    condition: () => this.loggedIn && !this.$inLTI,
                    reload: true,
                    animateAdd: true,
                    showWhenLoading: true,
                },
                {
                    name: 'assignments',
                    icon: 'edit',
                    header: 'Assignments',
                    component: 'assignment-list',
                    condition: () => this.loggedIn && !this.$inLTI,
                    reload: true,
                    animateAdd: true,
                    showWhenLoading: true,
                },
                {
                    name: 'ltiAssignments',
                    icon: 'edit',
                    title: 'Assignments',
                    header: () => this.ltiAssignment.mapOrDefault(
                        assig => assig.course.name,
                        'Assignments',
                    ),
                    component: 'assignment-list',
                    condition: () => this.canManageCurrentLtiAssignment,
                    reload: true,
                    data: () => this.ltiAssignment.extract(),
                    animateAdd: true,
                },
                {
                    name: 'groups',
                    icon: 'users',
                    header: 'Groups',
                    component: 'group-list',
                    data: () => ({ course: this.course }),
                    condition: () =>
                        UserConfig.features.groups &&
                        this.loggedIn &&
                        this.course &&
                        this.course.groupSets.length > 0,
                    reload: true,
                    animateAdd: true,
                },
                {
                    name: 'cases',
                    icon: 'search',
                    header: 'Plagiarism Cases',
                    component: 'plagiarism-case-list',
                    condition: () => this.loggedIn && this.$route.name === 'plagiarism_detail',
                    reload: true,
                    animate: true,
                },
                {
                    name: 'submissions',
                    icon: 'files-o',
                    header: 'Submissions',
                    component: 'submissions-sidebar-list',
                    condition: () =>
                        this.loggedIn &&
                        (this.$route.name === 'submission_file' ||
                            this.$route.name === 'submission'),
                    reload: true,
                    animate: true,
                },
            ],
            currentEntry: null,
            subMenus: [],
            mobileVisible: false,
            dimmingUseSpace: true,
            version: UserConfig.release.version,
        };
    },

    computed: {
        ...mapGetters('courses', ['getCourse']),
        ...mapGetters('assignments', ['getAssignment']),

        ...mapGetters('user', ['loggedIn', 'name', 'dangerousJwtToken']),
        ...mapGetters('user', { globalPermissions: 'permissions' }),

        ...mapGetters('pref', ['darkMode']),

        canManageSite() {
            return MANAGE_SITE_PERIMSSIONS.some(x => this.globalPermissions[x]);
        },

        ltiAssignment() {
            return this.getAssignment(this.$LTIAssignmentId);
        },

        canManageCurrentLtiAssignment() {
            if (this.loggedIn && this.$inLTI) {
                return this.ltiAssignment
                    .mapOrDefault(
                        assig => (
                            assig.course.canManage ||
                                assig.course.assignments.some(a => a.canManage)
                        ),
                        false,
                    );
            }
            return false;
        },

        course() {
            return this.getCourse(this.courseId).extractNullable();
        },

        courseId() {
            return this.$routeParamAsId('courseId');
        },

        assignmentId() {
            return this.$routeParamAsId('assignmentId');
        },

        assignment() {
            return this.getAssignment(this.assignment).extract();
        },

        floating() {
            return (
                this.$inLTI ||
                !this.$root.$isMediumWindow ||
                this.mobileVisible ||
                floatingRoutes.has(this.$route.name)
            );
        },

        dimPage() {
            // Make sure all properties are accessed so vue's caching works correctly.
            const isFloating = this.floating;
            const isMenuOpen = this.subMenus.length > 0 || this.mobileVisible;
            const customWidth = this.currentEntry && this.maybeCall(this.currentEntry.width);

            return !!((isFloating && isMenuOpen) || customWidth);
        },

        hideInitialEntries() {
            const route = this.$route.name;
            return this.$inLTI || !this.$root.$isMediumWindow || hideRoutes.has(route);
        },
    },

    watch: {
        $route(newVal, oldVal) {
            if (newVal.name === oldVal.name) {
                return;
            }
            if (this.hideInitialEntries) {
                this.closeSubMenu(true);
            } else {
                this.setInitialEntry();
            }
        },

        subMenus() {
            this.$nextTick(this.fixAppMargin);
        },

        assignmentId: {
            immediate: true,
            handler(newVal) {
                if (newVal) {
                    this.loadSingleAssignment({
                        assignmentId: newVal,
                        courseId: this.courseId,
                    });
                }
            },
        },

        $LTIAssignmentId: {
            immediate: true,
            handler(newVal) {
                if (newVal) {
                    this.loadSingleAssignment({ assignmentId: newVal });
                }
            },
        },
    },

    async mounted() {
        this.fixAppMargin();

        this.$root.$on('sidebar::show', submenu => {
            if (submenu === undefined) {
                this.toggleMobileSidebar();
            } else {
                this.openUpperSubMenu(this.findEntry(submenu), false);
            }
        });

        await this.loadCurrentCourse();
        this.$on('sidebar::close', this.onCloseSidebarEvent);
        this.$root.$on('cg::sidebar::close', this.onCloseSidebarEvent);

        this.setInitialEntry();
        this.loaded = true;
    },

    destroyed() {
        this.$root.$off('cg::sidebar::close', this.onCloseSidebarEvent);
    },

    methods: {
        ...mapActions('assignments', ['loadSingleAssignment']),
        ...mapActions('courses', ['loadSingleCourse']),
        ...mapActions('user', {
            logoutUser: 'logout',
        }),

        onCloseSidebarEvent() {
            if (this.floating || this.mobileVisible) {
                this.closeSubMenu(true);
            }
        },

        fixAppMargin() {
            if (
                this.$root.isEdge ||
                (this.$el && getComputedStyle(this.$el).position === 'fixed')
            ) {
                const app = document.querySelector('#app');
                app.style.marginLeft = `${this.$el.clientWidth}px`;
                this.$el.style.position = 'fixed';
                this.$el.style.left = 0;
            }
        },

        logout() {
            this.logoutUser();
            this.closeSubMenu(true);
            this.$router.push({ name: 'login' });
        },

        refreshItems() {
            this.loading = true;
            this.$root.$emit('sidebar::reload');
        },

        findEntry(name) {
            return this.entries.find(entry => entry.name === name);
        },

        setInitialEntry() {
            if (this.$route.name === 'login' || this.$route.name === 'register') {
                this.currentEntry = this.findEntry(this.$route.name);
            } else if (this.$route.name == null || !this.loggedIn || this.hideInitialEntries) {
                // NOOP
            } else if (this.$route.query.sbloc === 'm') {
                this.openMenuStack([this.findEntry('user')]);
            } else if (this.$route.query.sbloc === 'a') {
                this.openMenuStack([this.findEntry('assignments')]);
            } else if (this.$route.query.sbloc === 'c') {
                this.openMenuStack([this.findEntry('courses')]);
            } else if (this.$route.query.sbloc === 'g') {
                this.openMenuStack([this.findEntry('groups')]);
            } else {
                const menuStack = [this.findEntry('courses')];
                if (this.course != null) {
                    menuStack.push({
                        header: this.course.name,
                        component: 'assignment-list',
                        data: { course: this.course },
                        reload: true,
                    });
                }
                this.openMenuStack(menuStack);
            }
        },

        openMenuStack(stack) {
            if (stack.length === 0) {
                return;
            }

            this.openUpperSubMenu(stack[0]);

            const subMenus = stack.slice(1);
            for (let i = 0; i < subMenus.length; i++) {
                this.openSubMenu(subMenus[i]);
            }
        },

        openUpperSubMenu(entry, toggle = false) {
            if (entry.onClick != null) {
                this.currentEntry = entry;
                entry.onClick();
            } else if (toggle && this.currentEntry && entry.name === this.currentEntry.name) {
                this.closeSubMenu(true);
            } else {
                const hadSubMenuOpen = this.subMenus.length > 0;

                this.currentEntry = entry;
                this.subMenus = [];
                this.openSubMenu(entry);

                this.dimmingUseSpace = (
                    (this.dimPage && hadSubMenuOpen) ||
                    !this.maybeCall(entry.width)
                );
            }
        },

        openSubMenu(entry) {
            this.loading = false;
            this.subMenus.push(entry);
        },

        closeSubMenu(closeAll = false) {
            this.loading = false;

            this.$root.$emit('sidebar::submenu-closed');

            if (closeAll) {
                this.subMenus = [];
                this.currentEntry = null;
            } else {
                this.subMenus.pop();

                if (this.subMenus.length === 0) {
                    this.currentEntry = null;
                }
            }

            if ((closeAll || this.subMenus.length === 0) && this.mobileVisible) {
                this.toggleMobileSidebar();
            }
        },

        toggleMobileSidebar() {
            this.mobileVisible = !this.mobileVisible;

            // Make document (un)scrollable
            if (this.mobileVisible) {
                document.body.style.height = '100%';
                document.body.style.overflow = 'hidden';
            } else {
                document.body.style.height = '';
                document.body.style.overflow = '';
            }
        },

        maybeCall(fun) {
            switch (typeof fun) {
                case 'function':
                    return fun.bind(this)();
                default:
                    return fun;
            }
        },

        subMenuStyle(subMenu) {
            const style = {};
            const width = this.maybeCall(subMenu.width);

            if (width) {
                style.width = '100vw';
                style.maxWidth = `${width}px`;
            }

            return style;
        },

        openRouteInTab() {
            return this.$http.post('/api/v1/files/', this.dangerousJwtToken);
        },

        afterOpenRouteInTab({ data: loginFile }) {
            const curRoute = JSON.stringify({
                name: this.$route.name,
                params: this.$route.params,
                query: this.$route.query,
                hash: this.$route.hash,
            });
            const newRoute = this.$router.resolve({
                name: 'login_and_redirect',
                params: {
                    loginFile,
                },
                query: {
                    next: curRoute,
                },
            });

            window.open(newRoute.href, '_blank');
        },

        loadCurrentCourse() {
            if (this.courseId == null) {
                return Promise.resolve();
            } else {
                return this.loadSingleCourse({ courseId: this.courseId });
            }
        },
    },

    components: {
        Icon,
        Loader,
        UserInfo,
        CourseList,
        AssignmentList,
        PlagiarismCaseList,
        SubmissionsSidebarList,
        SubmitButton,
        GroupList,
        CgLogo,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.sidebar {
    position: fixed;
    position: sticky;
    // Must be greater than .sticky-top, .local-header, and modals
    z-index: 1035;
    top: 0;
    height: 100vh;

    &:not(.floating) {
        display: flex;
        flex-direction: row;
    }

    a {
        text-decoration: none;
        color: inherit;
    }
}


.fa-icon.notification-bell {
    position: absolute;
    right: 1em;
    color: @color-warning;
    transition: opacity @transition-duration;
    cursor: help;

    .selected & {
        color: @color-warning-dark;
    }
}

.main-menu {
    @main-menu-width: 6rem;

    display: flex;
    flex-direction: column;
    min-width: @main-menu-width;
    height: 100%;
    color: white;
    background-color: @color-primary;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.5);

    body:not(.cg-dark-mode).cg-in-lti & {
        background-color: white;
        color: @text-color;
    }

    @media @media-no-small {
        width: @main-menu-width;
    }

    @media @media-small {
        position: absolute;
        right: 100%;
        transform: none;

        &.show {
            transform: translateX(100%);
        }
    }

    // Draw a box shadow around the main menu. This can't be done with the
    // box-shadow property on .main-class, because the z-indices of
    // .main-menu and .submenu must be equal, so that modals spawned in the
    // latter can have a higher z-index than .main-menu.
    & + .shadow-overlay {
        position: absolute;
        top: 0;
        left: 0;
        bottom: 0;
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.5);
        z-index: 1;
        pointer-events: none;

        @media @media-no-small {
            width: @main-menu-width;
        }

        @media @media-small {
            right: 0;
        }
    }

    .sidebar-top {
        flex: 1 1 auto;
        overflow-y: auto;
    }

    .sidebar-top-item {
        display: flex;
        flex-direction: column;
        padding: 0.75rem 0.5rem;

        @media @media-small {
            flex-direction: row;
            align-items: center;
            padding: 0.5rem;
        }

        &.logo {
            flex: 0 0 auto;
            display: block;
            padding: 1rem 0.5rem;

            &.no-hover {
                background-color: transparent !important;
            }

            img {
                width: 90%;
                margin: 0 auto;
                display: block;
            }
        }

        .fa-icon {
            @media @media-no-small {
                display: block;
                margin: 0 auto;
                margin-bottom: 5px;
            }

            @media @media-small {
                margin-right: 0.5rem;
            }
        }

        .name {
            text-align: center;
            overflow: hidden;
            text-overflow: ellipsis;
        }
    }

    .sidebar-bottom {
        display: flex;
        flex-direction: row;
        flex: 0 0 auto;
    }

    .sidebar-bottom-item {
        flex: 1 1 auto;
        padding: 0.5rem 0.25rem 0.25rem;
        text-align: center;

        .fa-icon {
            transform: translateY(-2px);
        }
    }
}

.submenu-container {
    width: 16rem;
    height: 100%;

    @media @media-small {
        z-index: 1;
    }

    .sidebar.floating & {
        position: absolute;
        top: 0;
        left: 100%;
    }

    .sidebar:not(.floating) &:not(.use-space) {
        width: 0;
    }

    header {
        display: flex;
        flex: 0 0 auto;

        .action {
            display: flex;
            align-items: center;
            flex: 0 0 auto;
            padding: 0.5rem 0.75rem;
            cursor: pointer;
        }

        .submenu-header {
            flex: 1 1 auto;
            margin: 0;
            padding: 0.5rem 0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
    }

    .submenus {
        position: relative;
        height: 100%;
    }

    .submenu {
        display: flex;
        flex-direction: column;
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;

        background-color: white;
        color: @color-primary;

        @{dark-mode} {
            background-color: @color-primary;
            color: white;
        }

        &:not(:last-child) {
            display: none;
        }

        // Draw a box shadow around the submenu. This can't be done with the
        // box-shadow property on .submenu, because the z-indices of
        // .main-menu and .submenu must be equal, so that modals spawned in the
        // latter can have a higher z-index than .main-menu.
        &::after {
            @shadow-size: 10px;

            content: '';
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            z-index: -1;
            pointer-events: none;
            box-shadow: 0 0 @shadow-size rgba(0, 0, 0, 0.75);
        }
    }
}

.page-overlay {
    background-color: rgba(0, 0, 0, 0.33);
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: -2;
}

.main-menu .new-tab-link.sidebar-bottom-item {
    padding: 0.5rem;

    &.submit-button:not(.state-default) .new-tab-wrapper {
        opacity: 0;
    }

    .fa-icon {
        transform: none;
    }
}

.new-tab-wrapper {
    display: flex;
    justify-content: center;
}
</style>

<style lang="less">
@import '~mixins.less';

.sidebar {
    & &-list-wrapper {
        display: flex;
        flex-direction: column;
        flex: 1 1 auto;
        max-height: 100%;
        margin: 0;
        padding: 0;
        overflow-y: hidden;
    }

    & &-footer {
        flex: 0 0 auto;
        display: flex;
        flex-direction: row;
    }

    & &-footer-button {
        flex: 1 1 auto;
        border: 0;
        border-radius: 0;

        background-color: transparent !important;
        color: @text-color;

        @{dark-mode} {
            color: @text-color-dark;
        }

        &:hover {
            background-color: @color-light-gray !important;

            @{dark-mode} {
                background-color: @color-primary-darker !important;
            }
        }

        &.active {
            background-color: @color-primary !important;
            color: white !important;

            @{dark-mode} {
                background-color: white !important;
                color: @color-primary !important;
            }
        }
    }

    & &-list {
        list-style: none;
        margin: 0;
        padding: 0;
        flex: 1 1 auto;
        overflow-y: auto;

        .separator {
            margin: 0.5rem;
        }

        &.no-items-text {
            color: @color-light-gray;
            padding: 0 0.75rem;
        }
    }

    & &-list-section-header {
        padding: 0 0.75rem 0.25rem;
    }

    & &-top-item,
    & &-bottom-item {
        cursor: pointer;

        &:hover {
            background-color: lighten(@color-primary-darker, 2%);

            body:not(.cg-dark-mode).cg-in-lti & {
                background-color: @color-lighter-gray;
            }
        }

        &:not(.light-selected) a:hover {
            background-color: @color-primary-darkest;

            body:not(.cg-dark-mode).cg-in-lti & {
                background-color: @color-light-gray;
            }
        }

        &.light-selected {
            background-color: lightgray;
            color: @color-primary;

            body:not(.cg-dark-mode).cg-in-lti & {
                background-color: lighten(@color-primary, 5%);
                color: white;
            }

            a:hover:not(.selected) {
                background-color: darken(lightgray, 7.9%);
                body:not(.cg-dark-mode).cg-in-lti & {
                    background-color: @color-primary-darkest;
                }
            }
        }

        .selected,
        &.selected {
            background-color: white;
            color: @color-primary;

            body:not(.cg-dark-mode).cg-in-lti & {
                color: white;
                background-color: @color-primary;
            }

            &:hover,
            a:hover {
                background-color: darken(white, 7.9%);
                color: @color-primary;

                body:not(.cg-dark-mode).cg-in-lti & {
                    background-color: darken(@color-primary, 2%);
                    color: white;
                }
            }
        }
    }

    & &-list-item {
        display: flex;
        flex-direction: row;
        cursor: pointer;

        &:hover {
            background-color: @color-lighter-gray;

            @{dark-mode} {
                background-color: lighten(@color-primary-darker, 2%);
            }
        }

        &:not(.light-selected) a:hover {
            background-color: @color-light-gray;

            @{dark-mode} {
                background-color: @color-primary-darkest;
            }
        }

        &.light-selected {
            background-color: lighten(@color-primary, 5%);
            color: white;

            @{dark-mode} {
                background-color: lightgray;
                color: @color-primary;
            }

            a:hover:not(.selected) {
                background-color: @color-primary-darkest;

                @{dark-mode} {
                    background-color: darken(lightgray, 7.9%);
                }
            }
        }

        .selected,
        &.selected {
            color: white;
            background-color: @color-primary;

            @{dark-mode} {
                background-color: white;
                color: @color-primary;
            }

            &:hover,
            a:hover {
                background-color: darken(@color-primary, 2%);
                color: white;

                @{dark-mode} {
                    background-color: darken(white, 7.9%);
                    color: @color-primary;
                }
            }
        }

        .fa-icon {
            transform: translateY(-1px);
        }
    }

    & &-item {
        padding: 0.5rem 0.75rem;
    }

    & &-filter {
        margin: 0.5rem;
    }

    hr.separator {
        margin: 0 0.5rem;
        border-top: 1px solid @color-primary-darkest;
    }

    .submenu hr.separator {
        position: relative;
        z-index: 10;
    }

    small {
        display: block;
        line-height: 1.3;
    }
}
</style>
