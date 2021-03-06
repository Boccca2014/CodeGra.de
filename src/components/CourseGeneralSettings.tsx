/* SPDX-License-Identifier: AGPL-3.0-only */
import * as tsx from 'vue-tsx-support';
import { VNode, CreateElement } from 'vue';
import { modifiers as m } from 'vue-tsx-support';
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';

import * as models from '@/models';
import { CoursesStore } from '@/store';
import { CoursePermission as CPerm } from '@/permissions';

@Component
export default class CourseGeneralSettings extends Vue {
    _tsx!: tsx.DeclareProps<tsx.AutoProps<CourseGeneralSettings>>;

    @Prop({ required: true })
    course!: models.Course;

    private newCourseName: string = this.course.name;

    @Watch('course')
    private onCourseChange(newVal: models.Course, oldVal: models.Course) {
        if (newVal.id !== oldVal.id) {
            this.newCourseName = this.course.name;
        }
    }

    private renderDangerZone(h: CreateElement): VNode {
        const title = this.course.isArchived ? 'Unarchive course' : 'Archive course';

        const detail = this.course.isArchived
            ? 'Unarchive this course. This makes the course visible again for all students.'
            : 'Archive this course. This makes the course invisible for all students.';

        const confirm = this.course.isArchived
            ? 'Unarchiving the course makes it available again for all students.'
            : 'Archiving this course makes it invisible for all students.';

        return (
            <b-card
                header="Danger zone"
                class="mt-3"
                border-variant="danger"
                header-text-variant="danger"
                header-border-variant="danger"
            >
                <div class="d-flex justify-content-between">
                    <div>
                        <strong class="d-block">{title}</strong>

                        <small>{detail}</small>
                    </div>
                    <div>
                        <cg-submit-button
                            submit={this.archiveCourse}
                            confirm={confirm}
                            confirm-in-modal={false}
                            variant="danger"
                        >
                            {title}
                        </cg-submit-button>
                    </div>
                </div>
            </b-card>
        );
    }

    private get nameDisabledReason(): string | null {
        if (this.course.isLTI) {
            return 'You cannot edit the name of an LTI assignment.';
        } else if (!this.course.hasPermission(CPerm.canEditCourseInfo)) {
            return 'You do not have the permission to edit the name.';
        }
        return null;
    }

    private get submitButtonDisabledReason(): string | null {
        if (this.newCourseName === '') {
            return 'The name should contain atleast one character.';
        } else if (this.course.name === this.newCourseName) {
            return 'Nothing has changed';
        }
        return null;
    }

    private renderNameSettings(h: CreateElement): VNode {
        const submitButton = this.$utils.ifOrEmpty(this.nameDisabledReason == null, () => (
            <div class="float-right" v-b-popover_top_hover={this.submitButtonDisabledReason ?? ''}>
                <cg-submit-button
                    submit={this.submitName}
                    disabled={this.submitButtonDisabledReason != null}
                    ref="submitNameBtn"
                />
            </div>
        ));
        return (
            <b-card header="General">
                <b-form-group scopedSlots={{ label: () => 'Course name' }}>
                    <div v-b-popover_top_hover={this.nameDisabledReason ?? ''}>
                        <input
                            class="form-control"
                            disabled={this.nameDisabledReason != null}
                            onKeydown={m.ctrl.enter(this.clickOnButton)}
                            v-model={this.newCourseName}
                        />
                    </div>
                </b-form-group>

                {submitButton}
            </b-card>
        );
    }

    private archiveCourse() {
        return CoursesStore.patchCourse({
            courseId: this.course.id,
            data: {
                state: this.course.isArchived
                    ? models.CourseState.visible
                    : models.CourseState.archived,
            },
        });
    }

    private submitName() {
        return CoursesStore.patchCourse({
            courseId: this.course.id,
            data: { name: this.newCourseName },
        });
    }

    private clickOnButton() {
        return (this.$refs.submitNameBtn as any).onClick();
    }

    render(h: CreateElement) {
        return (
            <div class="course-general-settings">
                {this.renderNameSettings(h)}
                {this.course.hasPermission(CPerm.canArchiveCourses) && this.renderDangerZone(h)}
            </div>
        );
    }
}
