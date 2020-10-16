<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div id="app">
    <loader v-if="loading" class="main-page-loager" page-loader/>
    <template v-else>
        <sidebar ref="sidebar" v-if="showSidebar"/>
        <div class="container-fluid">
            <!-- We have an extra data element, `showContent`, to make sure we
            first render the sidebar, to make sure the logo request (for the
            svg) is done first, as otherwise the max requests the browser can do
            is reached, and it is empty for quite a long time. However, we still
            need this container-fluid div, as otherwise the sidebar will not be
            in the correct position. -->
            <main class="row justify-content-center" id="main-content">
                <router-view class="page col-lg-12" v-if="showContent"/>
                <div class="page col-lg-12" v-else />
                <footer-bar v-if="showFooter"/>
            </main>
        </div>
    </template>
    <div v-if="showFrameBorder" class="frame-border border"/>

    <b-toast v-for="toast in toasts"
             :key="toast.tag"
             toaster="b-toaster-top-right"
             :variant="toast.variant"
             :title="toast.title"
             :href="toast.href"
             visible
             no-auto-hide
             solid
             @hide="deleteToast(toast)">
        <div v-if="toast.onClick" @click="toast.onClick">
            {{ toast.message }}
        </div>
        <template v-else>
            {{ toast.message }}
        </template>
    </b-toast>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';

import { setRestoreRoute } from '@/router';
import { Loader, FooterBar, Sidebar } from '@/components';
import { NO_LOGIN_ALLOWED_ROUTES, NO_LOGIN_REQUIRED_ROUTES, NO_SIDEBAR_ROUTES, NO_FOOTER_ROUTES } from '@/constants';

export default {
    name: 'app',

    computed: {
        ...mapGetters('user', ['loggedIn', 'jwtClaims']),
        ...mapGetters('pref', ['darkMode']),
        ...mapGetters('courses', ['getCourse']),
        ...mapGetters('assignments', ['getAssignment']),

        canManageLTICourse() {
            if (this.$LTIAssignmentId == null) {
                return false;
            }
            return this.getAssignment(this.$LTIAssignmentId).mapOrDefault(
                assig => assig.course.canManage,
                false,
            );
        },

        showSidebar() {
            return !(NO_SIDEBAR_ROUTES.has(this.$route.name)
                     || (this.$inLTI && !this.canManageLTICourse));
        },

        showFooter() {
            return !NO_FOOTER_ROUTES.has(this.$route.name);
        },

        showFrameBorder() {
            return window !== window.top && this.$ltiProvider && this.$ltiProvider.addBorder;
        },

        forCourseId() {
            return this.jwtClaims.for_course;
        },

        forCourse() {
            if (this.forCourseId == null) {
                return null;
            }
            return this.getCourse(this.forCourseId).mapOrDefault(course => course.name, null);
        },
    },

    data() {
        return {
            loading: true,
            showContent: false,
            toasts: [],
        };
    },

    watch: {
        darkMode: {
            immediate: true,
            handler() {
                if (this.darkMode) {
                    document.body.classList.add('cg-dark-mode');
                } else {
                    document.body.classList.remove('cg-dark-mode');
                }
            },
        },

        $inLTI: {
            immediate: true,
            handler() {
                if (this.$inLTI) {
                    document.body.classList.add('cg-in-lti');
                } else {
                    document.body.classList.remove('cg-in-lti');
                }
            },
        },

        forCourse: {
            immediate: true,
            handler(newValue, oldValue) {
                if (oldValue != null) {
                    this.deleteToast(this.makeForCourseToast(oldValue));
                }
                if (newValue != null) {
                    this.addToast(this.makeForCourseToast(newValue));
                }
            },
        },

        forCourseId: {
            immediate: true,
            handler(newValue) {
                if (newValue != null) {
                    this.loadSingleCourse({ courseId: newValue });
                }
            },
        },

        $LTIAssignmentId: {
            immediate: true,
            handler(newValue) {
                if (newValue != null) {
                    this.loadSingleAssignment({ assignmentId: newValue });
                }
            },
        },
    },

    methods: {
        ...mapActions('courses', ['loadSingleCourse']),
        ...mapActions('assignments', ['loadSingleAssignment']),
        ...mapActions('user', ['verifyLogin']),
        ...mapActions('siteSettings', ['loadSettings']),

        makeForCourseToast(courseName) {
            return {
                tag: 'forCourse',
                title: 'Limited login enabled',
                message: `You are currently only logged in for the course "${courseName}". This means you can only see data from this course.`,
                variant: 'warning',
            };
        },

        addToast(toast) {
            if (!this.toasts.find(other => other.tag === toast.tag)) {
                this.toasts.push(toast);
            }
        },

        deleteToast(toast) {
            this.toasts = this.toasts.filter(other => other.tag !== toast.tag);
        },
    },

    created() {
        if (this.$route.query.inLTI !== undefined) {
            this.$inLTI = true;
        }

        document.body.addEventListener(
            'click',
            event => {
                if (
                    !event.target.closest('.popover-body') &&
                        !event.target.closest('.sidebar') &&
                        this.$refs.sidebar
                ) {
                    this.$refs.sidebar.$emit('sidebar::close');
                }
            },
            true,
        );

        document.body.addEventListener(
            'keyup',
            event => {
                if (event.key === 'Escape') {
                    this.$root.$emit('bv::hide::popover');
                }
            },
            true,
        );
    },

    mounted() {
        this.$root.$on('cg::app::toast', this.addToast);

        Promise.all([
            this.loadSettings(),
            this.verifyLogin().then(
                () => {
                    const route = this.$route.name;

                    if (NO_LOGIN_ALLOWED_ROUTES.has(route)) {
                        this.$router.push({ name: 'home' });
                    }
                },
                () => {
                    const route = this.$route.name;

                    if (!route || !NO_LOGIN_REQUIRED_ROUTES.has(route)) {
                        setRestoreRoute(this.$route);
                        this.$router.push({ name: 'login' });
                    }
                },
            ),
        ]).then(async () => {
            this.loading = false;
            if (this.showSidebar) {
                await this.$afterRerender();
            }
            this.showContent = true;
        });
    },

    destroyed() {
        this.$root.$off('cg::app::toast', this.addToast);
    },

    components: {
        Loader,
        FooterBar,
        Sidebar,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

#app {
    display: flex;
    flex-direction: row;
    min-height: 100vh;
}

.container-fluid {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    width: auto;
    min-width: 0;

    main {
        position: relative;
        display: flex;
        flex-direction: column;
        flex: 1 1 auto;

        .default-background;
        .default-color;
    }

    .page {
        flex: 1 1 auto;
        margin-bottom: 1rem;
    }
}

.frame-border {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    pointer-events: none;

    // Must be greater than .sticky-top and .local-header
    z-index: 1030;

    @{dark-mode} {
        display: none;
    }
}
</style>
