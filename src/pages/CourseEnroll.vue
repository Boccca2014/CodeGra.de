<template>
<div class="course-enroll">
    <local-header show-logo :logo-is-link="loggedIn">
        <template #title>
            Enroll in the course
            <template v-if="link">
                "{{ link.course.name }}"
            </template>
            <template v-else>
                &hellip;
            </template>
        </template>
    </local-header>

    <b-alert v-if="error" variant="danger" show class="m-3">
        {{ $utils.getErrorMessage(error) }}
    </b-alert>

    <div class="justify-content-center row" v-else-if="link">
        <div class="d-flex justify-content-around col-12 row">
            <div class="mb-3 col-lg-6">
                <b-card v-show="loggedIn">
                    <template #header>
                        <div>
                            <span>Join as logged in user ({{ loggedInName }})</span>

                            <a href="#"
                               class="inline-link float-right"
                               @click.prevent="storeLogout">Logout</a>
                        </div>
                    </template>
                    <div class="text-center">
                        <div v-b-popover.top.hover="alreadyInCourse ? 'You are already enrolled in this course.' : ''">
                            <cg-submit-button :submit="joinWithCurrentAccount"
                                              ref="joinWithCurrent"
                                              @after-success="afterJoin"
                                              label="Join" />
                        </div>
                    </div>
                </b-card>

                <b-card header="Login and join" v-show="!loggedIn">
                    <login hide-forget
                           @login="clickOnJoin"
                           @saml-login="doSamlLogin"
                           login-label="Login and join" />
                </b-card>
            </div>

            <div class="col-lg-6" v-if="allowRegister">
                <b-card header="Join as a new user">
                    <register :registration-url="registrationUrl"
                              :redirect-route="redirectRoute"/>
                </b-card>
            </div>
        </div>
    </div>
    <cg-loader v-else page-loader />
</div>
</template>

<script lang="ts">
import { Vue, Component, Watch } from 'vue-property-decorator';
import { mapGetters, mapActions } from 'vuex';

// @ts-ignore
import LocalHeader from '@/components/LocalHeader';
// @ts-ignore
import Register from '@/components/Register';
// @ts-ignore
import Login from '@/components/Login';

import * as models from '@/models';

import { setPageTitle } from './title';

@Component({
    components: { LocalHeader, Register, Login },
    computed: {
        ...mapGetters('user', {
            loggedIn: 'loggedIn',
            loggedInUsername: 'username',
            loggedInName: 'name',
        }),
        ...mapGetters('courses', {
            allCourses: 'courses',
        }),
    },
    methods: {
        ...mapActions('user', {
            storeLogin: 'login',
            storeLogout: 'logout',
        }),
        ...mapActions('courses', ['reloadCourses']),
    },
})
export default class CourseEnroll extends Vue {
    private link: Record<string, any> | null = null;

    private error: Error | null = null;

    private uniqueId: string = `${this.$utils.getUniqueId()}`;

    private loginData: { username: string, password: string } = {
        username: '',
        password: '',
    };

    readonly loggedIn!: boolean;

    readonly loggedInUsername!: string | null;

    readonly storeLogin!: (data: any) => Promise<unknown>;

    readonly storeLogout!: () => Promise<unknown>;

    readonly reloadCourses!: () => Promise<unknown>;

    readonly allCourses!: Record<number, unknown>;

    get courseId(): number {
        return parseInt(this.$route.params.courseId, 10);
    }

    get linkId(): string {
        return this.$route.params.linkId;
    }

    get redirectRoute() {
        return {
            name: 'home',
            query: {
                sbloc: 'm',
                filter: this.link?.course.name,
            },
        };
    }

    get directEnroll() {
        return this.$utils.parseBool(this.$route.query.directEnroll, false);
    }

    get allowRegister() {
        // eslint-disable-next-line camelcase
        return this.$userConfig.features.course_register && (this.link?.allow_register ?? false);
    }

    @Watch('directEnroll', { immediate: true })
    onDirectEnrollChange() {
        if (this.directEnroll && this.loggedIn) {
            this.clickOnJoin();
        }
    }

    async clickOnJoin() {
        const btn = await this.$waitForRef('joinWithCurrent');
        if (btn) {
            (btn as any).onClick();
        }
    }

    afterJoin() {
        this.$router.push(this.redirectRoute);
    }

    joinWithCurrentAccount() {
        if (this.link == null) {
            return Promise.reject(new Error('Link not found'));
        }

        return this.$http.post(
            this.$utils.buildUrl(
                ['api', 'v1', 'courses', this.link.course.id, 'registration_links', this.link.id, 'join'],
            ),
        ).then(async res => {
            await this.reloadCourses();
            return res;
        });
    }

    get registrationUrl() {
        if (this.link == null) {
            return null;
        }
        return this.$utils.buildUrl(
            ['api', 'v1', 'courses', this.link.course.id, 'registration_links', this.link.id, 'user'],
        );
    }

    get alreadyInCourse() {
        if (this.link == null) {
            return false;
        }
        return this.link.course.id in this.allCourses;
    }

    @Watch('link', { immediate: true })
    onLinkChange() {
        if (this.link) {
            setPageTitle(`Enroll in ${this.link.course.name}`);
            if (this.directEnroll && this.loggedIn) {
                this.clickOnJoin();
            }
        } else {
            setPageTitle('Enroll in ...');
        }
    }

    @Watch('courseId', { immediate: true })
    @Watch('linkId')
    async loadData() {
        this.link = null;
        this.error = null;

        try {
            this.link = (await this.$http.get(this.$utils.buildUrl([
                'api', 'v1', 'courses', this.courseId, 'registration_links', this.linkId,
            ]))).data;
        } catch (error) {
            this.error = error;
        }
    }

    doSamlLogin(provider: models.SSOProvider) {
        window.location.replace(this.$utils.buildUrl(
            provider.loginUrl,
            {
                query: {
                    next: this.$utils.buildUrl(
                        ['courses', this.courseId, 'enroll', this.linkId],
                        { query: { directEnroll: true } },
                    ),
                },
            },
        ));
    }
}
</script>
