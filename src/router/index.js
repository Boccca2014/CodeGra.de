/* SPDX-License-Identifier: AGPL-3.0-only */
import Vue from 'vue';
import Router from 'vue-router';
import { store } from '@/store';
import {
    ResetPassword,
    LTILaunch,
    Home,
    Login,
    ForgotPassword,
    Register,
    ManageCourse,
    ManageAssignment,
    Submission,
    Submissions,
    Admin,
    Groups,
    LoginAndRedirect,
    UnsubscribePage,
    LTIProviderSetup,
    AssignmentLogin,
    CourseEnroll,
    SsoLogin,
} from '@/pages';

import { PlagiarismOverview, PlagiarismDetail } from '@/components';
import { NO_LOGIN_ALLOWED_ROUTES, NO_LOGIN_REQUIRED_ROUTES } from '@/constants';
import { resetPageTitle } from '@/pages/title';

Vue.use(Router);

const router = new Router({
    mode: 'history',

    routes: [
        {
            path: '/',
            name: 'home',
            component: Home,
        },
        {
            path: '/login',
            name: 'login',
            component: Login,
        },
        {
            path: '/forgot',
            name: 'forgot',
            component: ForgotPassword,
        },
        {
            path: '/register',
            name: 'register',
            component: Register,
        },
        {
            path: '/reset_password',
            name: 'reset-password',
            component: ResetPassword,
        },
        {
            path: '/lti_launch/',
            name: 'lti-launch',
            component: LTILaunch,
        },
        {
            path: '/admin',
            name: 'admin',
            component: Admin,
        },
        {
            path: '/courses/:courseId/assignments/:assignmentId/submissions/:submissionId',
            name: 'submission',
            component: Submission,
        },
        {
            path:
                '/courses/:courseId/assignments/:assignmentId/submissions/:submissionId/files/:fileId',
            name: 'submission_file',
            component: Submission,
        },
        {
            path: '/courses/:courseId/assignments/:assignmentId/submissions/',
            name: 'assignment_submissions',
            component: Submissions,
        },
        {
            path: '/courses/:courseId',
            name: 'manage_course',
            component: ManageCourse,
        },
        {
            path: '/courses/:courseId/assignments/:assignmentId',
            name: 'manage_assignment',
            component: ManageAssignment,
        },
        {
            path: '/courses/:courseId/group_sets/:groupSetId',
            name: 'manage_groups',
            component: Groups,
        },
        {
            path: '/courses/:courseId/assignments/:assignmentId/plagiarism/:plagiarismRunId/cases/',
            name: 'plagiarism_overview',
            component: PlagiarismOverview,
        },
        {
            path:
                '/courses/:courseId/assignments/:assignmentId/plagiarism/:plagiarismRunId/cases/:plagiarismCaseId',
            name: 'plagiarism_detail',
            component: PlagiarismDetail,
        },
        {
            path: '/login_and_redirect/:loginFile',
            name: 'login_and_redirect',
            component: LoginAndRedirect,
        },
        {
            path: '/unsubscribe/email_notifications/',
            name: 'unsubscribe',
            component: UnsubscribePage,
        },
        {
            path: '/lti_providers/:ltiProviderId/setup',
            name: 'lti_provider_setup',
            component: LTIProviderSetup,
        },
        {
            path: '/assignments/:assignmentId/login/:loginUuid',
            name: 'assignment_login',
            component: AssignmentLogin,
        },
        {
            path: '/courses/:courseId/enroll/:linkId',
            name: 'course_enroll',
            component: CourseEnroll,
        },
        {
            path: '/sso_login/:blobId',
            name: 'sso_login',
            component: SsoLogin,
        },
    ],
});

// Stores path of page that requires login when user is not
// logged in, so we can restore it when the user logs in.
let restoreRoute = null;

export function setRestoreRoute(route) {
    restoreRoute = Object.assign({}, route);
}

let previousRoute = null;
export function getPreviousRoute() {
    return previousRoute;
}

router.getRestoreRoute = function getRestoreRoute() {
    return restoreRoute;
};

router.beforeEach((to, from, next) => {
    // Unset page title. Pages will set title,
    // this is mostly to catch pages that don't.
    previousRoute = Object.assign({}, from);
    resetPageTitle();

    const loggedIn = store.getters['user/loggedIn'];
    if (loggedIn) {
        if (restoreRoute) {
            // Reset restoreRoute before calling (synchronous) next.
            const route = restoreRoute;
            restoreRoute = null;
            next(route);
        } else if (NO_LOGIN_ALLOWED_ROUTES.has(to.name)) {
            next('/');
        } else {
            next();
        }
    } else if (!NO_LOGIN_REQUIRED_ROUTES.has(to.name)) {
        setRestoreRoute(to);
        next('/login');
    } else {
        next();
    }
});

export default router;
