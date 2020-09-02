<template>
<div class="junit-result w-100">
    <div class="p-3" v-if="junit.suites.length === 0">
        <b-alert variant="info" show>
            This test contains no suites.
        </b-alert>
    </div>
    <div v-for="suite in junit.suites"
         class="junit-suite p-3">
        <div class="d-flex align-items-center mb-1">
            <b-badge v-if="hasSuiteWeights"
                     class="mr-2 text-small-uppercase">
                weight: {{ suite.weight }}
            </b-badge>
            <h5 class="mb-0">{{ suite.name }} ({{ suite.successful }} / {{ suite.runTests }})</h5>
        </div>

        <!-- The masonry would not change the number of columns when resizing
             the window for some unknown reason, but doing the comparison
             ourselves does the trick. -->
        <masonry :cols="{ default: $root.$windowWidth <= $root.mediumWidth ? 1 : 2 }"
                 gutter="1rem">
            <div v-if="suite.cases.length === 0"
                 class="py-1">
                <b-alert variant="info" show>
                    This suite contains no cases.
                </b-alert>
            </div>
            <div v-for="testCase in suite.cases"
                 v-else
                 class="py-1">
                <div class="border rounded overflow-hidden">
                    <div class="d-flex flex-row p-2">
                        <div class="flex-grow-1">
                            <b-badge v-if="hasCaseWeights"
                                     class="text-small-uppercase">
                                weight: {{ testCase.weight }}
                            </b-badge>
                            <div class="badge classname">
                                <code>{{ testCase.classname }}</code>
                            </div>
                            {{ testCase.name }}
                        </div>

                        <div :title="statePopover(testCase.state)"
                             class="flex-grow-0 ml-2">
                            <fa-icon :name="testCase.fontAwesomeIcon.icon"
                                     style="width: 1rem;"
                                     :class="testCase.fontAwesomeIcon.cls" />
                        </div>
                    </div>

                    <pre v-if="testCase.message.isJust()"
                         class="px-3 pb-2 mb-0"
                         style="white-space: pre-wrap;"
                         >{{ testCase.message.extract() }}</pre>
                    <div>
                        <div v-if="testCase.content.isJust()"
                             class="output-wrapper">
                            <b v-if="testCase.stdout.isJust() || testCase.stderr.isJust()"
                               class="output-title">Error location</b>
                            <inner-code-viewer
                                class="border-top"
                                :assignment="assignment"
                                :code-lines="testCase.content.extract().map($utils.htmlEscape)"
                                file-id="-1"
                                :feedback="{}"
                                :start-line="0"
                                :show-whitespace="true"
                                :warn-no-newline="false"
                                :empty-file-message="'No stack trace.'" />
                        </div>

                        <div v-if="testCase.stdout.isJust()"
                             class="output-wrapper">
                            <b class="output-title">Output</b>
                            <inner-code-viewer
                                class="border-top"
                                :assignment="assignment"
                                :code-lines="testCase.stdout.extract().map($utils.htmlEscape)"
                                file-id="-1"
                                :feedback="{}"
                                :start-line="0"
                                :show-whitespace="true"
                                :warn-no-newline="false"
                                :empty-file-message="'No output.'" />
                        </div>

                        <div v-if="testCase.stderr.isJust()"
                             class="output-wrapper">
                            <b class="output-title">Error output</b>
                            <inner-code-viewer
                                class="border-top"
                                :assignment="assignment"
                                :code-lines="testCase.stderr.extract().map($utils.htmlEscape)"
                                file-id="-1"
                                :feedback="{}"
                                :start-line="0"
                            :show-whitespace="true"
                            :warn-no-newline="false"
                            :empty-file-message="'No output.'" />
                    </div>
                    </div>
                </div>
            </div>
        </masonry>
    </div>
</div>
</template>

<script lang="ts">
import 'vue-awesome/icons/ban';
import 'vue-awesome/icons/check';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/exclamation';
import 'vue-awesome/icons/question';
import { Vue, Component, Prop } from 'vue-property-decorator';
import { CGJunit } from '@/utils/junit';
import { Assignment } from '@/models';

// @ts-ignore
import InnerCodeViewer from './InnerCodeViewer';

@Component({
    components: {
        InnerCodeViewer,
    },
})
export default class JunitResult extends Vue {
    @Prop({ required: true })
    junit!: CGJunit;

    @Prop({ required: true })
    assignment!: Assignment;

    // eslint-disable-next-line class-methods-use-this
    statePopover(state: string) {
        switch (state) {
            case 'success':
                return 'This test passed!';
            case 'failure':
                return 'This test failed.';
            case 'error':
                return 'An error occurred while running this test...';
            case 'skipped':
                return 'This test was skipped.';
            default:
                return 'The testing framework returned an unknown state.';
        }
    }

    get hasSuiteWeights(): boolean {
        return this.junit.suites.some(
            suite => suite.weight !== 1.0,
        );
    }

    get hasCaseWeights(): boolean {
        return this.junit.suites.some(
            suite => suite.cases.some(
                testCase => testCase.weight !== 1.0,
            ),
        );
    }
}
</script>

<style lang="less" scoped>
@import "~mixins.less";

.junit-suite:not(:last-child) {
    border-bottom: 1px solid @border-color;
}

.badge.classname {
    background: none !important;

    code {
        font-size: 100% !important;
    }
}

.output-wrapper .output-title {
    display: block;
    padding-left: 0.5rem;
    padding-right: 0.5rem;
    padding-bottom: 0.5rem;
}
.output-wrapper:not(:first-child) .output-title {
    padding-top: 0.5rem;
}

.output-wrapper:not(:last-child) .inner-code-viewer {
    border-bottom: 1px solid @border-color;
}
</style>
