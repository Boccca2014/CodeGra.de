<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="linter">
    <div class="align-middle description">
        <p>{{ description }}</p>
        <hr>
        <div v-if="state == 'new'"
             :class="{ 'lonely-start-button-wrapper' : Object.keys(options).length == 0 }">
            <div v-if="Object.keys(options).length > 0">
                <b-button-toolbar justify>
                    <b-dropdown :text="selectedOption">
                        <b-dropdown-header>Select your config file</b-dropdown-header>
                        <b-dropdown-item v-for="(_, optionName) in options"
                                         @click="clicked(false, optionName)"
                                         :key="optionName">
                            {{ optionName }}
                        </b-dropdown-item>
                        <b-dropdown-divider/>
                        <b-dropdown-item @click="clicked(true, 'Custom config')">Custom config</b-dropdown-item>
                    </b-dropdown>
                    <submit-button label="Run"
                                   :submit="run"
                                   @after-success="afterRun"
                                   :disabled="runButtonDisabled"/>
                </b-button-toolbar>

                <b-collapse :id="`sub_collapse_${name}_${assignment.id}`">
                    <form>
                        <textarea class="form-control mt-3"
                                  rows="10"
                                  placeholder="Enter your custom config"
                                  v-model="config"/>
                    </form>
                </b-collapse>
            </div>

            <submit-button v-else
                           label="Run"
                           :submit="run"
                           @after-success="afterRun"/>
        </div>
        <div v-else-if="state != 'new' && working > 0">
            <b-progress :value="done + crashed"
                        :max="done + working + crashed"
                        animated/>
            <div class="text-center my-3">
                {{ done + crashed }} out of {{ working + crashed + done }}
            </div>
        </div>
        <div v-if="state !== 'new'">
            <b-button-toolbar justify>
                <submit-button class="delete-button"
                               :disabled="state === 'new'"
                               variant="danger"
                               confirm="Are you sure you want to delete the
                                        output?"
                               :submit="deleteFeedback"
                               @after-success="afterDeleteFeedback">
                    Remove output
                </submit-button>
                <div v-b-popover.top.hover="hasCrashedRuns && !showMoreInfo ? 'Some runs did not exit successfully.' : ''">
                    <submit-button
                        label="moreInformation"
                        :submit="getInformation"
                        @success="showMoreInfo = !showMoreInfo"
                        :duration="0"
                        variant="secondary">
                        <span v-if="showMoreInfo">Hide more information</span>
                        <span v-else>
                            <icon v-if="hasCrashedRuns" name="exclamation-triangle"/>
                            Show more information
                        </span>
                    </submit-button>
                </div>
            </b-button-toolbar>
            <b-collapse :id="`linter-more-info-${compId}`"
                        class="mt-3"
                        v-model="showMoreInfo">
                <!-- Null is used as initial value, so we want to show the loader
                if the data is not loaded yet -->
                <input class="form-control"
                       placeholder="Type to search runs"
                       v-model="infoFilter"/>
                <div class="table-wrapper border rounded mt-3">
                    <table class="table table-striped mb-0">
                        <thead>
                            <tr>
                                <th class="border-top">Student</th>
                                <th class="border-top shrink">Status</th>
                                <th class="border-top shrink"/>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="test in sortedFilteredTests">
                                <td class="col-xs-9 detail-run-user"><user :user="test.work.user"/></td>
                                <td class="state col-xs-3 shrink">
                                    <span class="detail-run-state">{{ test.state }}</span>
                                    <loader :center="false"
                                            class="detail-run-loader"
                                            v-if="test.state === 'running'"
                                            :scale="1"/>
                                    <icon class="detail-run-crashed"
                                          :id="`detail-linter-crash-button-${test.id}`"
                                          v-else-if="test.state === 'crashed'"
                                          name="exclamation-triangle"/>
                                    <b-popover v-if="test.state === 'crashed'"
                                               triggers="click blur"
                                               title="The linter crashed!"
                                               :target="`detail-linter-crash-button-${test.id}`">
                                        <inner-markdown-viewer :markdown="test.error_summary"
                                                               class="linter-error-summary"
                                                               disable-math/>
                                    </b-popover>
                                </td>
                                <td class="shrink">
                                    <div v-b-popover.top.hover="'Download the output of the linter.'"
                                         v-if="test.state === 'crashed'">
                                        <submit-button size="sm"
                                                       :submit="() => downloadLog(test)"
                                                       @success="afterDownloadLog"
                                                       class="download-log-btn">
                                            <icon name="download"/>
                                        </submit-button>
                                    </div>
                                </td>
                            </tr>
                            <tr v-if="sortedFilteredTests.length === 0">
                                <td colspan="3" class="text-muted text-center">
                                    No runs found
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </b-collapse>
        </div>
    </div>
</div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/exclamation-triangle';
import 'vue-awesome/icons/download';

import { downloadFile, nameOfUser } from '@/utils';

import SubmitButton from './SubmitButton';
import InnerMarkdownViewer from './InnerMarkdownViewer';
import Loader from './Loader';
import User from './User';

let compId = 0;

export default {
    name: 'linter',

    props: ['name', 'options', 'initialState', 'initialId', 'assignment', 'serverDescription'],

    data() {
        return {
            selectedOption: 'Select config file',
            show: {},
            state: 'new',
            config: '',
            deleting: false,
            id: undefined,
            done: 0,
            working: 0,
            crashed: 0,
            compId: compId++,
            showMoreInfo: false,
            destroyed: false,
            infoFilter: '',
            tests: null,
        };
    },

    beforeDestroy() {
        this.destroyed = true;
    },

    computed: {
        description() {
            return this.serverDescription;
        },

        hasCrashedRuns() {
            return this.state === 'crashed' || this.crashed > 0;
        },

        runButtonDisabled() {
            return (
                Object.keys(this.options).length > 0 && this.selectedOption === 'Select config file'
            );
        },

        sortedFilteredTests() {
            const done = [];
            const crashed = [];
            const running = [];

            let tests = this.tests || [];
            if (this.infoFilter) {
                const filter = this.infoFilter.toLowerCase().split(' ');
                tests = tests.filter(t =>
                    filter.every(
                        f =>
                            t.state.indexOf(f) >= 0 ||
                            nameOfUser(t.work.user)
                                .toLowerCase()
                                .includes(f),
                    ),
                );
            }

            tests
                .sort((a, b) => {
                    const nameA = nameOfUser(a.work.user);
                    const nameB = nameOfUser(b.work.user);
                    return nameA.localeCompare(nameB);
                })
                .forEach(test => {
                    if (test.state === 'running') {
                        running.push(test);
                    } else if (test.state === 'crashed') {
                        crashed.push(test);
                    } else {
                        done.push(test);
                    }
                });

            return [...running, ...crashed, ...done];
        },
    },

    mounted() {
        this.state = this.initialState;
        this.id = this.initialId;
        if (this.state === 'running') {
            this.startUpdateLoop();
        }
    },

    components: {
        Loader,
        Icon,
        SubmitButton,
        User,
        InnerMarkdownViewer,
    },

    methods: {
        getInformation() {
            if (!this.showMoreInfo && this.tests == null) {
                return this.$http.get(`/api/v1/linters/${this.id}?extended`).then(({ data }) => {
                    this.updateData(data);
                });
            } else {
                return Promise.resolve();
            }
        },

        downloadLog(test) {
            return this.$http
                .get(`/api/v1/linters/${this.id}/linter_instances/${test.id}`)
                .then(({ data }) => ({
                    data: `${data.error_summary}\n${data.stdout}\n${data.stderr}`,
                    user: test.work.user,
                }));
        },

        afterDownloadLog({ data, user }) {
            const filename = `Linter log for ${nameOfUser(user)}.txt`;
            downloadFile(data, filename, 'text/plain');
        },

        changeSubCollapse(state) {
            if (Boolean(this.collapseState) !== state) {
                this.$root.$emit(
                    'bv::toggle::collapse',
                    `sub_collapse_${this.name}_${this.assignment.id}`,
                );
                this.collapseState = !this.collapseState;
            }
        },

        clicked(collapseState, selectedName) {
            this.selectedOption = selectedName;
            this.$nextTick(() => {
                this.linter = this.changeSubCollapse(collapseState);
            });
        },

        deleteFeedback() {
            return this.$http.delete(`/api/v1/linters/${this.id}`);
        },

        afterDeleteFeedback() {
            this.showMoreInfo = false;
            this.tests = null;
            this.state = 'new';
        },

        startUpdateLoop() {
            if (!this.destroyed) {
                let url = `/api/v1/linters/${this.id}`;
                if (this.tests != null) {
                    url += '?extended';
                }
                this.$http.get(url).then(
                    ({ data }) => this.updateData(data),
                    this.$utils.makeHttpErrorHandler({
                        // The linter may have stopped in the meantime.
                        404: () => {},
                    }),
                );
            }
        },

        updateData(data) {
            if (data.tests != null) {
                this.done = 0;
                this.working = 0;
                this.crashed = 0;
                data.tests.forEach(test => {
                    if (test.state === 'running') {
                        this.working += 1;
                    } else if (test.state === 'done') {
                        this.done += 1;
                    } else if (test.state === 'crashed') {
                        this.crashed += 1;
                    }
                });
                this.tests = data.tests;
            } else {
                this.done = data.done;
                this.working = data.working;
                this.crashed = data.crashed;
            }
            this.id = data.id;

            if (this.working === 0) {
                this.state = 'done';
            } else {
                this.state = this.crashed > 0 ? 'crashed' : 'running';
                this.$nextTick(() => {
                    setTimeout(this.startUpdateLoop, data.tests == null ? 1000 : 5000);
                });
            }
        },

        run() {
            let cfg;
            if (this.selectedOption === 'Custom config') {
                cfg = this.config;
            } else if (this.selectedOption) {
                cfg = this.options[this.selectedOption];
            }

            this.done = 0;
            this.working = 0;
            this.crashed = 0;

            return this.$http.post(`/api/v1/assignments/${this.assignment.id}/linter`, {
                name: this.name,
                cfg: cfg || '',
            });
        },

        afterRun(response) {
            this.updateData(response.data);
        },
    },
};
</script>

<style lang="less" scoped>
@import '~mixins';

.center-table {
    text-align: center;
}

.center-table th {
    text-align: center;
}

.lonely-start-button-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 15px;
}

.table-wrapper {
    max-height: 20rem;
    overflow-y: auto;
    width: 100%;

    .table thead th {
        border-top: none;
    }

    td {
        vertical-align: middle;
    }
}

.state {
    text-transform: capitalize;
}

.detail-run-loader,
.detail-run-crashed {
    margin-left: 5px;
    vertical-align: middle;
}

.detail-run-crashed {
    cursor: help;
}

.detail-loader {
    margin: 0 1rem;
}
</style>

<style>
.linter-error-summary p {
    margin-bottom: 0;
}
</style>
