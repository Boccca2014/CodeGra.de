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
            <b-alert v-if="error" show variant="danger">
                {{ $utils.getErrorMessage(error) }}
            </b-alert>
            <div v-else-if="assignment">
                <p>
                    Hi {{ user.readableName }},
                </p>

                <template v-if="canLogin">
                    <p>
                        <template v-if="isExam">
                            You can start the exam by clicking the button
                            below.
                        </template>
                        <template v-else>
                            You can access the assignment by clicking the
                            button below.
                        </template>
                    </p>

                    <p v-if="isExam">
                        The exam started {{ canLoginIn }} and ends {{ deadlineIn }}.
                    </p>
                    <p v-else>
                        The assignment became available {{ canLoginIn }} and the
                        deadline of this assignment is {{ deadlineIn }}.
                    </p>
                </template>
                <template v-else>
                    <p>
                        <template v-if="isExam">
                            You can log in to start the exam from this page once it
                            has started.
                        </template>
                        <template v-else>
                            You can access the assignment from this page once it has
                            become available.
                        </template>

                        Please do not delete the e-mail you received with the
                        link to this page as you will need it when the exam
                        starts.
                    </p>

                    <p>
                        The {{ assignmentType }} will become available
                        {{ canLoginIn }} and ends {{ deadlineIn }}. You can
                        click the button below to log in once the
                        {{ assignmentType }} is available.
                    </p>
                </template>

                <div class="my-3 text-center">
                    <div v-b-popover.top.hover="canLogin ? '' : 'You can not log in yet.'">
                        <cg-submit-button style="height: 10rem; width: 10rem;"
                                        variant="secondary"
                                        class="align-self-center"
                                        :icon-scale="4"
                                        :submit="login"
                                        ref="loginBtn"
                                        :disabled="!canLogin"
                                        @after-success="success">
                            <fa-icon name="sign-in" :scale="6" />
                            <div>Start</div>
                        </cg-submit-button>
                    </div>
                </div>

                <template v-if="!canLogin && canLoginInSeconds < 60 * 60">
                    <p>
                        Set the toggle below to "Yes" to log in automatically
                        when the {{ assignmentType }} starts.
                    </p>

                    <cg-toggle v-model="autoLogin"
                                label-on="Yes"
                                label-off="No"/>
                </template>
            </div>
            <cg-loader page-loader v-else />
        </div>
    </div>
</div>
</template>

<script lang="ts">
import { Vue, Component, Watch } from 'vue-property-decorator';

import 'vue-awesome/icons/sign-in';

// @ts-ignore
import LocalHeader from '@/components/LocalHeader';
import { mapActions } from 'vuex';
import { AxiosResponse } from 'axios';

import * as models from '@/models';

@Component({
    components: { LocalHeader },
    methods: {
        ...mapActions('user', {
            storeLogin: 'login',
        }),
    },
})
export default class AssignmentLogin extends Vue {
    private assignment: models.Assignment | null = null;

    private user: models.User | null = null;

    private error: Error | null = null;

    public autoLogin: boolean = false;

    storeLogin!: (response: AxiosResponse) => Promise<unknown>;

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

    get isExam(): boolean {
        if (this.assignment == null) {
            return false;
        } else {
            return this.assignment.kind === 'exam';
        }
    }

    get assignmentType(): string {
        return this.isExam ? 'exam' : 'assignment';
    }

    get canLogin(): boolean {
        return this.loginTime?.isBefore(this.$root.$epoch) ?? false;
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
                return `${seconds.toFixed(0)} seconds`;
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
        if (diff < 45) {
            return `in ${diff.toFixed(0)} seconds`;
        } else if (diff <= 15 * 60) {
            return deadline.from(now);
        } else {
            return deadline.local().calendar(now);
        }
    }

    @Watch('canLogin')
    async onCanLoginChange() {
        if (this.canLogin && this.autoLogin) {
            this.autoLogin = false;
            const btn = await this.$waitForRef('loginBtn');
            if (btn) {
                (btn as any).onClick();
            }
        }
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

    login() {
        return this.$http.post(this.$utils.buildUrl(['api', 'v1', 'login_links', this.loginUuid, 'login']));
    }

    success(response: AxiosResponse) {
        this.storeLogin(response).then(() => {
            this.$router.replace({ name: 'home' });
        });
    }
}
</script>
