<template>
<div class="row">
    <div class="col-xl-6" v-if="error != null">
        <b-alert show variant="danger">
            {{ $utils.getErrorMessage(error) }}
        </b-alert>
    </div>
    <div class="col-xl-6" v-else>
        <b-card v-if="canAssignGraders" no-body>
            <template #header>
                Divide submissions

                <cg-description-popover>
                    <template #description>
                        Divide this assignment. When dividing users are assigned to
                        submissions based on weights.  When new submissions are
                        uploaded graders are also automatically assigned. When
                        graders assign themselves the weights are not updated to
                        reflect this. To read more about dividing graders please
                        read our
                        <a href="https://docs.codegra.de/user/management.html#dividing-submissions"
                        target="_blank"
                        class="inline-link">documentation</a>.
                    </template>
                </cg-description-popover>
            </template>

            <cg-loader class="m-3 text-center" v-if="gradersLoading && !gradersLoadedOnce"/>

            <divide-submissions
                v-else
                :assignment="assignment"
                @divided="loadGraders"
                :graders="graders" />
        </b-card>
    </div>

    <div class="col-xl-6">
        <b-card v-if="permissions.canUpdateGraderStatus"
                no-body
                class="finished-grading-card">
            <template #header>
                Finished grading

                <cg-description-popover>
                    Indicate that a grader is done with grading. All
                    graders that have indicated that they are done will
                    not receive notification e-mails.
                </cg-description-popover>
            </template>

            <cg-loader class="m-3 text-center" v-if="gradersLoading"/>

            <finished-grader-toggles
                :assignment="assignment"
                :graders="graders"
                v-else/>
        </b-card>

        <b-card v-if="canUpdateCourseNotifications">
            <template #header>
                Notifications

                <cg-description-popover>
                    Send a reminder e-mail to the selected graders on
                    the selected time if they have not yet finished
                    grading.
                </cg-description-popover>
            </template>

            <notifications
                :assignment="assignment"
                class="reminders"/>
        </b-card>
    </div>
</div>
</template>

<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';

import * as models from '@/models';
import { CoursePermission as CPerm } from '@/permissions';
import { GradersStore } from '@/store/modules/graders';

// @ts-ignore
import FinishedGraderToggles from './FinishedGraderToggles';
// @ts-ignore
import DivideSubmissions from './DivideSubmissions';
// @ts-ignore
import Notifications from './Notifications';

@Component({
    components: {
        FinishedGraderToggles,
        DivideSubmissions,
        Notifications,
    },
})
export default class AssignmentGraderSettings extends Vue {
    @Prop({ required: true })
    assignment!: models.Assignment;

    error: Error | null = null;

    gradersLoading: boolean = true;

    gradersLoadedOnce: boolean = false;

    get graders(): models.Graders | null {
        return GradersStore.getGraders()(this.assignmentId);
    }

    get assignmentId(): number {
        return this.assignment.id;
    }

    @Watch('assignmentId', { immediate: true })
    onAssignmentIdChanged(newVal: number, oldVal: number) {
        if (newVal == null) {
            this.gradersLoading = true;
            this.gradersLoadedOnce = false;
        } else if (newVal !== oldVal) {
            this.loadGraders();
        }
    }

    get permissions() {
        return new models.AssignmentCapabilities(this.assignment);
    }

    get canAssignGraders() {
        return this.assignment.hasPermission(CPerm.canAssignGraders);
    }

    get canUpdateCourseNotifications() {
        return this.assignment.hasPermission(CPerm.canUpdateCourseNotifications);
    }

    async loadGraders() {
        this.error = null;
        this.gradersLoading = true;

        try {
            await GradersStore.loadGraders({
                assignmentId: this.assignmentId,
            });
        } catch (e) {
            this.error = e;
            return;
        }

        this.gradersLoading = false;
        this.gradersLoadedOnce = true;
    }
}
</script>
