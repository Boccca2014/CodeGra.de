<template>
<div class="assignment-login">
    <local-header show-logo>
        <span>
            Login for
            <template v-if="assignment">{{ assignment.name }}</template>
            <template v-else>&hellip;</template>
        </span>
    </local-header>

    <div class="row justify-content-center">
        <div class="col" style="max-width: 25rem;">
            <b-alert v-if="loggedIn && user && loggedInUserId != user.id"
                     show
                     variant="warning">
                <p>
                    Another user than the one trying to take the exam is
                    currently logged in. <a class="inline-link" href="#"
                    @click="storeLogout">Click here</a> to log the other user
                out.
                </p>

                <p class="mb-0">
                    Starting the exam by clicking the "Start" button below will
                    also log out the other user.
                </p>
            </b-alert>
            <b-alert v-if="error" show variant="danger">
                {{ $utils.getErrorMessage(error) }}
            </b-alert>
            <div v-else-if="assignment">
                <p>
                    Hi {{ user.readableName }},
                </p>

                <template v-if="canLogin">
                    <p>
                        You can start the exam by clicking the button below.
                    </p>

                    <p>
                        The exam started {{ canLoginIn }} and ends {{
                        deadlineIn }}; you have {{ examDuration }} to complete
                        the exam.
                    </p>
                </template>
                <template v-else-if="!isBeforeDeadline">
                    <p>
                        The exam ended {{ deadlineIn }}. You can not log in
                        anymore.
                    </p>
                </template>
                <template v-else>
                    <p>
                        You can log in to start the exam from this page once it
                        has started.

                        Please do not delete the e-mail you received with the
                        link to this page as you will need it when the exam
                        starts.
                    </p>

                    <p>
                        The exam will become available {{ canLoginIn }} and
                        ends {{ deadlineIn }}; you have {{ examDuration }} to
                        complete the exam. You can click the button below to
                        log in once the exam is available.
                    </p>
                </template>

                <div class="my-3 text-center">
                    <cg-wizard-button
                        icon="sign-in"
                        label="Start"
                        @click="login"
                        :disabled="!canLogin"
                        :popover="canLogin ? '' : 'You cannot log in yet.'" />

                    <b-alert v-if="loginError" show variant="danger" class="mt-4">
                        {{ $utils.getErrorMessage(loginError) }}
                    </b-alert>
                </div>
            </div>
            <cg-loader page-loader v-else />
        </div>
    </div>
</div>
</template>

<script lang="ts">
import { Vue, Component, Watch } from 'vue-property-decorator';
import moment from 'moment';

import 'vue-awesome/icons/sign-in';

// @ts-ignore
import LocalHeader from '@/components/LocalHeader';
import { mapActions, mapGetters } from 'vuex';
import { AxiosResponse } from 'axios';

import * as models from '@/models';

@Component({
    components: { LocalHeader },
    computed: {
        ...mapGetters('user', {
            loggedIn: 'loggedIn',
            loggedInUserId: 'id',
        }),
    },
    methods: {
        ...mapActions('user', {
            storeLogin: 'login',
            storeLogout: 'logout',
        }),
    },
})
export default class AssignmentLogin extends Vue {
    private assignment: models.Assignment | null = null;

    private user: models.User | null = null;

    private error: Error | null = null;

    private loginError: Error | null = null;

    private loading: boolean = false;

    loggedIn!: boolean;

    storeLogin!: (response: AxiosResponse) => Promise<unknown>;

    storeLogout!: () => Promise<unknown>;

    get assignmentId(): number {
        return parseInt(this.$route.params.assignmentId, 10);
    }

    get loginTime() {
        // Add some time for a possibly wrong clock.
        return this.assignment?.availableAt?.clone().add(15, 'seconds');
    }

    get loginUuid(): string {
        return this.$route.params.loginUuid;
    }

    get isAfterLoginTime() {
        return this.loginTime?.isBefore(this.$root.$epoch) ?? false;
    }

    get isBeforeDeadline() {
        return this.assignment?.deadline?.isAfter(this.$root.$epoch) ?? false;
    }

    get canLogin(): boolean {
        return this.isAfterLoginTime && this.isBeforeDeadline;
    }

    get canLoginInSeconds(): number | null {
        if (this.loginTime == null) {
            return null;
        }
        const now = this.$root.$epoch;
        return this.loginTime.diff(now) / 1000;
    }

    get canLoginIn(): string | null {
        const seconds = this.canLoginInSeconds;
        if (this.loginTime == null || seconds == null) {
            return null;
        }
        const now = this.$root.$epoch;
        if (seconds > 0) {
            if (seconds < 45) {
                return `in ${seconds.toFixed(0)} seconds`;
            } else if (seconds <= 15 * 60) {
                return this.loginTime.from(now);
            }
        }
        return this.loginTime?.clone().local().calendar(now);
    }

    get deadlineIn(): string | null {
        const deadline = this.assignment?.deadline?.clone();
        if (deadline == null) {
            return null;
        }

        const now = this.$root.$epoch;
        // moment.diff returns a value in milliseconds.
        const diff = deadline.diff(now) / 1000;
        if (diff >= 0 && diff < 45) {
            return `in ${diff.toFixed(0)} seconds`;
        } else if (diff <= 15 * 60) {
            return deadline.from(now);
        } else {
            return deadline.local().calendar(now);
        }
    }

    get examDuration() {
        const available = this.assignment?.availableAt;
        const deadline = this.assignment?.deadline;

        if (available == null || deadline == null) {
            return null;
        }

        return moment.duration(available.diff(deadline)).humanize();
    }

    @Watch('assignmentId', { immediate: true })
    onAssignmentIdChange() {
        this.loadData();
    }

    @Watch('loginUuid')
    onLoginUuidChange() {
        this.loadData();
    }

    loadData() {
        this.assignment = null;
        this.user = null;
        this.error = null;

        this.$http.get(this.$utils.buildUrl(
            ['api', 'v1', 'login_links', this.loginUuid],
            { query: { no_course_in_assignment: true } },
        )).then(({ data }) => {
            this.assignment = models.Assignment.fromServerData(data.assignment);
            this.user = models.makeUser(data.user);
        }, err => {
            this.error = err;
        });
    }

    async login() {
        if (this.loggedIn) {
            await this.storeLogout();
        }

        this.loading = true;

        return this.$http.post(
            this.$utils.buildUrl(['api', 'v1', 'login_links', this.loginUuid, 'login']),
        )
            .then(response => this.storeLogin(response))
            .then(
                () => {
                    const { assignment } = this;

                    if (assignment == null) {
                        this.$router.replace({ name: 'home' });
                    } else {
                        this.$router.replace({
                            name: 'assignment_submissions',
                            params: {
                                courseId: assignment?.courseId.toString(),
                                assignmentId: assignment?.id.toString(),
                            },
                        });
                    }
                },
                err => {
                    this.loginError = err;
                },
            );
    }
}
</script>
