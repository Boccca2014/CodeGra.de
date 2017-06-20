import Vue from 'vue';
import Router from 'vue-router';
import {
    Assignments,
    Submission,
    Home,
    Login,
    ManageAssignments,
    Submit,
    Submissions,
    User,
} from '@/pages';

Vue.use(Router);

export default new Router({
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
            path: '/logout',
            name: 'logout',
            redirect: { name: 'home' },
        },
        {
            path: '/me',
            name: 'me',
            component: User,
        },
        {
            path: '/courses/:courseId/assignments/:assignmentId/submissions/:submissionId',
            name: 'submission',
            component: Submission,
        },
        {
            path: '/courses/:courseId/assignments/:assignmentId/submissions/:submissionId/files/:fileId',
            name: 'submission_file',
            component: Submission,
        },
        {
            path: '/courses/:courseId/assignments/:assignmentId/submissions/',
            name: 'assignment_submissions',
            component: Submissions,
        },
        {
            path: '/assignments/',
            name: 'assignments',
            component: Assignments,
        },
        {
            path: '/courses/:courseId/assignments/:assignmentId/submit',
            name: 'assignment_submit',
            component: Submit,
        },
        {
            path: '/courses/:courseId/manage',
            name: 'assignment_manage',
            component: ManageAssignments,
        },
    ],
});
