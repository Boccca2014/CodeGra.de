<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div v-if="error"
     class="plagiarism-detail">
    <b-alert show
             variant="danger"
             style="margin-top: 1rem;">
        {{ error }}
    </b-alert>
</div>
<loader v-else-if="loadingData || assignment == null"/>
<div class="plagiarism-detail" v-else>
    <local-header :back-route="{ name: 'plagiarism_overview' }"
                  back-popover="Go back to overview">
        <template slot="title">
            Plagiarism comparison between &quot;<user :user="detail.users[0]"/>&quot; and
            &quot;<user :user="detail.users[1]"/>&quot; for assignment &quot;{{assignment.name}}&quot;
        </template>

        <div v-b-popover.top.hover="isJupyterRun ? 'Export is not possible yet for Jupyter notebook runs.' : ''">
            <b-btn v-b-modal.plagiarism-export
                   style="margin-left: 15px;"
                   :disabled="isJupyterRun"
                   >Export</b-btn>
        </div>
    </local-header>

    <b-modal id="plagiarism-export"
             title="Export"
             hide-footer
             static>
        <h6 style="text-align: center;">Select which matches should be exported</h6>
        <table class="range-table table table-striped table-hover">
            <thead>
                <tr>
                    <th class="shrink text-center">
                        <b-form-checkbox :checked="exportAll"
                                         @change="toggleAllMatches"
                                         v-b-popover.top.hover="'Toggle all'"/>
                    </th>
                    <th class="col-student-name"><user :user="detail.users[0]"/></th>
                    <th class="shrink text-center">Lines</th>
                    <th class="shrink text-center">Color</th>
                    <th class="col-student-name"><user :user="detail.users[1]"/></th>
                    <th class="shrink text-center">Lines</th>
                </tr>
            </thead>

            <tbody>
                <tr v-for="match in matchesSortedByRange"
                    @click="toggleExportMatch(match.id)">
                    <td><b-form-checkbox :checked="exportMatches[match.id]"
                                         @input="toggleExportMatch(match.id, $event)"
                                         @click.native.prevent /></td>
                    <td class="col-student-name">
                        {{ getFromFileTree(tree1, match.files[0]) }}
                    </td>
                    <td class="shrink text-center">{{ match.lines[0][0] + 1 }} - {{ match.lines[0][1] + 1 }}</td>
                    <td :style="`background: rgba(${getColorForMatch(match).background}, 0.4);`"></td>
                    <td class="col-student-name">
                        {{ getFromFileTree(tree2, match.files[1]) }}
                    </td>
                    <td class="shrink text-center">{{ match.lines[1][0] + 1 }} - {{ match.lines[1][1] + 1 }}</td>
                </tr>
            </tbody>
        </table>

        <div class="my-3 mx-n3">
            <collapse v-model="advancedOptionsCollapsed">
                <div slot="handle">
                    <div class="px-3">
                        <icon class="toggle flex-grow-1" name="chevron-down" :scale="0.75" />
                        <b>Options</b>
                    </div>
                </div>
                <div class="mt-2 px-3">
                    <b-form-group>
                        <template #label>
                            Render each listing on a new page

                            <cg-description-popover hug-text>
                                When turned on each block of code is rendered on a new page.
                            </cg-description-popover>
                        </template>
                        <cg-toggle v-model="exportOptions.newPage" />
                    </b-form-group>

                    <b-form-group>
                        <template #label>
                            Render matches side by side

                            <cg-description-popover hug-text>
                                When turned on matching blocks of code are rendered side by side
                                on a single page.
                            </cg-description-popover>
                        </template>

                        <cg-toggle v-model="exportOptions.matchesAlign"
                                   value-off="sequential"
                                   value-on="sidebyside" />
                    </b-form-group>

                    <b-form-group>
                        <template #label>
                            Context lines

                            <cg-description-popover hug-text>
                                Number of lines to be rendered before and after each match.
                            </cg-description-popover>
                        </template>

                        <input class="form-control"
                               placeholder="Number of context lines"
                               type="number"
                               step="1"
                               start="0"
                               :value="exportOptions.contextLines"
                               @input="updateContextLines" />
                    </b-form-group>

                    <b-form-group label="Output format">
                        <b-form-select v-model="outputFormat"
                                       :options="outputOptions" />
                    </b-form-group>
                </div>
            </collapse>
        </div>

        <b-button-toolbar justify>
            <b-button variant="outline-primary"
                      @click="$root.$emit('bv::hide::modal', 'plagiarism-export');">
                Cancel
            </b-button>
            <b-button-group v-b-popover.top.hover="exportDisabled ? 'Select at least one case to export' : ''">
                <submit-button label="Export"
                               :disabled="exportDisabled"
                               :submit="exportToDocument"
                               @success="afterExportToDocument"/>
            </b-button-group>
        </b-button-toolbar>
    </b-modal>

    <div class="range-table-wrapper">
        <table class="range-table table table-striped table-hover">
            <thead>
                <tr>
                    <th class="col-student-name"><user :user="detail.users[0]"/></th>
                    <th class="shrink text-center">Lines</th>
                    <th class="shrink text-center">Color</th>
                    <th class="col-student-name"><user :user="detail.users[1]"/></th>
                    <th class="shrink text-center">Lines</th>
                </tr>
            </thead>

            <tbody>
                <tr v-for="match in matchesSortedByRange"
                    @click="gotoLines(match.lines, match.files)">
                    <td class="col-student-name">
                        {{ getFromFileTree(tree1, match.files[0]) }}
                    </td>
                    <td class="shrink text-center">{{ match.lines[0][0] + 1 }} - {{ match.lines[0][1] + 1 }}</td>
                    <td :style="`background: rgba(${getColorForMatch(match).background}, 0.4);`"></td>
                    <td class="col-student-name">
                        {{ getFromFileTree(tree2, match.files[1]) }}
                    </td>
                    <td class="shrink text-center">{{ match.lines[1][0] + 1 }} - {{ match.lines[1][1] + 1 }}</td>
                </tr>
            </tbody>
        </table>
    </div>

    <div v-if="!contentLoaded" style="padding-top: 3em;">
        <loader :scale="3"/>
    </div>
    <div class="code-viewer border rounded" v-else>
        <div class="student-files"
                v-for="key in ['self', 'other']"
                :ref="`file-comparison-${key}`">
            <b-card class="student-file"
                    v-for="file in sortedFiles"
                    v-if="filesPerStudent[key].has(file.id)"
                    :key="`file-comparison-${key}-${getFromFileTree(key == 'self' ? tree1 : tree2, file)}`"
                    :header="file.file_name"
                    :ref="`file-comparison-${key}-${getFromFileTree(key == 'self' ? tree1 : tree2, file)}`">
                <router-link v-if="detail.assignment_ids[key == 'self' ? 0 : 1] == assignment.id"
                             slot="header"
                             :to="fileRoute(file, key == 'self' ? 0 : 1)">
                             {{ getFromFileTree(key == 'self' ? tree1 : tree2, file) }}
                </router-link>
                <span v-else
                     slot="header"
                     class="text-muted cursor-not-allowed"
                     v-b-popover.window.hover.top="'You can\'t view files from other assignments.'">
                    {{ getFromFileTree(key == 'self' ? tree1 : tree2, file) }}
                </span>

                <template v-for="data in [getFileDataToDisplay(file)]">
                    <b-alert show variant="danger" v-if="data instanceof Error">
                        Could not render file: {{ data.message }}
                    </b-alert>
                    <inner-ipython-viewer
                        :assignment="null"
                        :editable="false"
                        v-else-if="isJupyterRun"
                        :submission="null"
                        :file-id="-1"
                        :output-cells="data"
                        :show-whitespace="false"
                        :can-use-snippets="false"
                        without-feedback
                        />
                    <inner-code-viewer
                        v-else
                        class="border rounded"
                        :assignment="assignment"
                        :submission="null"
                        :code-lines="data"
                        :feedback="{}"
                        :file-id="file.id"
                        :warn-no-newline="false"/>
                </template>
            </b-card>
        </div>
    </div>
</div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex';
import decodeBuffer from '@/utils/decode';
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/chevron-down';

import { downloadFile, nameOfUser } from '@/utils';
import { getOutputCells } from '@/utils/ipython';
import { backends as documentBackends } from '@/utils/Document';
import { PlagiarismDocument } from '@/utils/Document/Plagiarism';

import {
    Loader,
    LocalHeader,
    SubmitButton,
    User,
    InnerCodeViewer,
    InnerIpythonViewer,
} from '@/components';

import Collapse from './Collapse';

export default {
    name: 'plagiarism-detail',

    data() {
        return {
            detail: null,
            contentLoaded: false,
            loadingData: true,
            tree1: null,
            tree2: null,
            fileContents: {},
            exportMatches: {},

            error: '',
            exportAll: false,
            exportOptions: {
                contextLines: 5,
                matchesAlign: 'sidebyside',
                newPage: true,
                entireFiles: false,
            },
            outputFormat: 'LaTeX',
            advancedOptionsCollapsed: false,

            Error,
        };
    },

    watch: {
        $route(newRoute, oldRoute) {
            if (
                newRoute.params.assignmentId !== oldRoute.params.assignmentId ||
                    newRoute.params.plagiarismRunId !== oldRoute.params.plagiarismRunId ||
                    newRoute.params.plagiarismCaseId !== oldRoute.params.plagiarismCaseId
            ) {
                this.loadDetail();
            }
        },

        numExported(newVal) {
            this.exportAll = newVal === this.matchIds.length;
        },

        assignmentId: {
            immediate: true,
            handler(assignmentId) {
                this.loadSingleAssignment({ assignmentId, courseId: this.courseId });
            },
        },
    },

    computed: {
        ...mapGetters('pref', ['fontSize', 'darkMode']),
        ...mapGetters('assignments', ['getAssignment']),
        ...mapGetters('plagiarism', ['runs']),
        ...mapGetters('users', ['getUser']),

        matchIds() {
            const matches = this.$utils.getProps(this.detail, [], 'matches');
            return matches.map(m => m.id);
        },

        numExported() {
            return this.matchIds.filter(id => this.exportMatches[id]).length;
        },

        outputOptions() {
            return Object.keys(documentBackends).map(name => ({
                text: name,
                value: name,
            }));
        },

        // This is a mapping between file id and object, containing a `name`
        // key, `id` key, `match` key, and a lines array. This array contains
        // arrays of length 2, where the first element is a number containing
        // the start of the match, end the second element is a number which is
        // the end of the match.
        fileMatches() {
            function makeOrAppend(accum, match, index) {
                if (accum[match.files[index].id]) {
                    accum[match.files[index].id].lines.push(match.lines[index]);
                    accum[match.files[index].id].lines.sort((x1, x2) => {
                        let diff = x1[0] - x2[0];
                        if (diff === 0) {
                            // If the start is the same, sort from short to long.
                            diff = x1[1] - x2[1];
                        }
                        return diff;
                    });
                } else {
                    accum[match.files[index].id] = {
                        name: match.files[index].name,
                        id: match.files[index].id,
                        lines: [match.lines[index]],
                        match,
                    };
                }
            }

            return this.detail.matches.reduce((accum, match) => {
                makeOrAppend(accum, match, 0);
                makeOrAppend(accum, match, 1);

                return accum;
            }, {});
        },

        // Get the files sorted by longest match first.
        sortedFiles() {
            return Object.values(this.fileMatches).sort((a, b) => {
                const lenA = a.lines.reduce((accum, item) => accum + (item[1] - item[0]), 0);
                const lenB = b.lines.reduce((accum, item) => accum + (item[1] - item[0]), 0);
                return lenA - lenB;
            });
        },

        colorPairs() {
            return [
                [0, 255, 0],
                [255, 0, 0],
                [0, 0, 255],
                [255, 251, 0],
                [0, 255, 255],
                [127, 0, 255],
            ].map(background => ({
                background,
                textColor: this.darkMode
                    ? background.map(item => Math.min(255, Math.max(25, item) * 4))
                    : background.map(item => item / 1.75),
            }));
        },

        courseId() {
            return this.$routeParamAsId('courseId');
        },

        assignmentId() {
            return Number(this.$route.params.assignmentId);
        },

        assignment() {
            return this.getAssignment(this.assignmentId).extract();
        },

        plagiarismRunId() {
            return this.$route.params.plagiarismRunId;
        },

        plagiarismRun() {
            return this.runs[this.plagiarismRunId];
        },

        isJupyterRun() {
            return !!this.$utils
                .getProps(this.plagiarismRun, [], 'config')
                .find(([opt, value]) => opt === 'lang' && value === 'Jupyter');
        },

        plagiarismCaseId() {
            return this.$route.params.plagiarismCaseId;
        },

        userIds() {
            return [this.$route.params.userId1, this.$route.params.userId2];
        },

        filesPerStudent() {
            const self = new Set();
            const other = new Set();

            this.detail.matches.forEach(match => {
                self.add(match.files[0].id);
                other.add(match.files[1].id);
            });

            return { self, other };
        },

        matchesSortedByRange() {
            return this.detail.matches.map(x => x).sort((a, b) => {
                const lenA = (a.lines[0][1] - a.lines[0][0] + (a.lines[1][1] - a.lines[1][0])) / 2;
                const lenB = (b.lines[0][1] - b.lines[0][0] + (b.lines[1][1] - b.lines[1][0])) / 2;
                return lenB - lenA;
            });
        },

        colorIndicesPerFile() {
            const colorsAmount = this.colorPairs.length;
            return this.matchesSortedByRange.reduce((accum, match, index) => {
                match.files.forEach((f, fIndex) => {
                    if (!accum[f.id]) {
                        accum[f.id] = {};
                    }
                    // If two matches have the same start index, we want to set
                    // the color of the largest match.
                    if (accum[f.id][match.lines[fIndex][0]] == null) {
                        accum[f.id][match.lines[fIndex][0]] = index % colorsAmount;
                    }
                });
                return accum;
            }, {});
        },

        exportDisabled() {
            return !Object.values(this.exportMatches).some(x => x);
        },
    },

    methods: {
        ...mapActions('assignments', ['loadSingleAssignment']),
        ...mapActions('code', {
            storeLoadCode: 'loadCode',
        }),
        ...mapActions('plagiarism', {
            loadPlagiarismRun: 'loadRun',
        }),

        getColorForMatch(match) {
            return this.colorPairs[this.colorIndicesPerFile[match.files[0].id][match.lines[0][0]]];
        },

        async renderPlagiarismDocument(matches) {
            const neededFileIds = matches.reduce((accum, match) => {
                accum.add(match.files[0].id);
                accum.add(match.files[1].id);
                return accum;
            }, new Set());

            const contents = {};
            neededFileIds.forEach(fileId => {
                contents[fileId] = this.storeLoadCode(fileId).then(data => {
                    const content = decodeBuffer(data, true);
                    return content.split('\n');
                });
            });

            const plagMatches = (await Promise.all(
                matches.map(async match => {
                    const [left, right] = await Promise.all([
                        contents[match.files[0].id],
                        contents[match.files[1].id],
                    ]);
                    const [user1, user2] = this.detail.userIds;

                    return {
                        color: this.getColorForMatch(match).background,
                        matchA: {
                            startLine: match.lines[0][0],
                            endLine: match.lines[0][1] + 1,
                            lines: left,
                            name: this.getFromFileTree(this.tree1, match.files[0]),
                            user: this.getUser(user1),
                        },
                        matchB: {
                            startLine: match.lines[1][0],
                            endLine: match.lines[1][1] + 1,
                            lines: right,
                            name: this.getFromFileTree(this.tree1, match.files[1]),
                            user: this.getUser(user2),
                        },
                    };
                }),
            ));

            return new PlagiarismDocument(this.outputFormat).render(
                plagMatches,
                this.exportOptions,
            );
        },

        getExtension(file) {
            return this.$utils.last(file.name.split('.'));
        },

        getFileDataToDisplay(file) {
            const ranges = this.fileMatches[file.id].lines;
            const colors = this.colorIndicesPerFile[file.id];
            const fileSource = this.fileContents[file.id];
            const colorPairs = this.colorPairs;
            let rangeIndex = 0;
            let curColor = null;

            function setColor(index, cb) {
                const range = ranges[rangeIndex];
                if (!range) {
                    return cb();
                }

                if (range[0] === index) {
                    curColor = colorPairs[colors[index]];
                }

                const res = cb();

                if (range[1] === index) {
                    curColor = null;
                    curColor = colorPairs[colors[index]];
                    rangeIndex++;

                    // Find the last match (which is the longest) which starts
                    // at this line.
                    for (let i = rangeIndex; i < ranges.length && ranges[i][0] === index; ++i) {
                        rangeIndex = i;
                    }
                }

                return res;
            }

            const highlightCode = (content, lang, offset) => {
                const res = this.$utils.highlightCode(content, lang).map((line, lineIndex) => {
                    const index = lineIndex + offset;
                    return setColor(index, () => {
                        if (curColor) {
                            return `<span style="color: rgb(${
                                curColor.textColor
                            }); background: rgba(${
                                curColor.background
                            }, .1);">${this.$utils.htmlEscape(content[lineIndex])}</span>`;
                        }
                        return line;
                    });
                });
                return res;
            };

            if (this.isJupyterRun) {
                return getOutputCells(JSON.parse(fileSource), highlightCode, cell =>
                    setColor(cell.feedback_offset, () => cell),
                );
            } else {
                return highlightCode(fileSource.split('\n'), this.getExtension(file), 0);
            }
        },

        async getFileContents() {
            this.contentLoaded = false;

            await Promise.all(
                Object.values(this.fileMatches).map(async file => {
                    const data = await this.storeLoadCode(file.id);
                    const content = decodeBuffer(data, true);

                    this.$set(this.fileContents, file.id, content);
                }),
            );

            this.contentLoaded = true;
        },

        fileRoute(file, index) {
            // We only generate file links to files from the same assignment.
            if (this.detail.assignment_ids[index] !== this.assignmentId) {
                return {};
            }
            return {
                name: 'submission_file',
                params: {
                    courseId: this.assignment.courseId,
                    assignmentId: this.assignment.id,
                    submissionId: this.detail.submissions[index].id,
                    fileId: file.id,
                },
                hash: '#code',
            };
        },

        gotoLines(lines, files) {
            this.gotoLineInTarget(lines[0], files[0], 'self');
            this.gotoLineInTarget(lines[1], files[1], 'other');
        },

        // target must be 'self' or 'other'.
        gotoLineInTarget(lines, file, target) {
            const ref = `file-comparison-${target}`;
            const name = this.getFromFileTree(target === 'self' ? this.tree1 : this.tree2, file);
            const codeViewer = this.$refs[`${ref}-${name}`][0];

            const line = lines[0];
            const item = codeViewer.querySelectorAll('li.line, .markdown-wrapper, .result-cell')[
                line
            ];

            if (item == null) {
                // Line not yet rendered, e.g. because the file has more than MAX_LINES lines.
                codeViewer.scrollIntoView();
                return;
            }

            item.scrollIntoView();

            // Because the file headers are sticky, they can overlap with the code when it is
            // scrolled into view, so correct for that. Add some more pixels to get some space
            // between the file header and the first plagiarized line.
            const { lineHeight } = getComputedStyle(item);
            const headerHeight = codeViewer.querySelector('.card-header').clientHeight;

            codeViewer.parentNode.scrollTop -= headerHeight + parseInt(lineHeight, 10);
        },

        async loadDetail() {
            this.loadingData = true;

            await this.loadPlagiarismRun(this.plagiarismRunId);

            this.$http
                .get(this.$utils.buildUrl(
                    ['api', 'v1', 'plagiarism', this.plagiarismRunId, 'cases', this.plagiarismCaseId],
                    {
                        query: {
                            no_course_in_assignment: true,
                            no_assignment_in_case: true,
                        },
                    },
                ))
                .then(
                    ({ data }) => {
                        data.userIds = data.users.map(
                            user => this.$utils.getProps(user, null, 'id'),
                        );
                        this.detail = data;

                        return Promise.all([
                            this.loadFileTrees(),
                            this.getFileContents(),
                        ]);
                    },
                    err => {
                        this.error = err.response.data.message;
                        if (err.response.status === 403) {
                            this.error +=
                                ' Make sure you have the `can_view_plagiarism` on both courses where the submissions originate.';
                        }
                    },
                )
                .then(() => {
                    this.loadingData = false;
                });
        },

        async loadFileTrees() {
            [this.tree1, this.tree2] = await Promise.all([
                this.$http
                    .get(`/api/v1/submissions/${this.detail.submissions[0].id}/files/`)
                    .then(a => this.processFileTree(a.data))
                    .catch(() => null),
                this.$http
                    .get(`/api/v1/submissions/${this.detail.submissions[1].id}/files/`)
                    .then(a => this.processFileTree(a.data))
                    .catch(() => null),
            ]);
        },

        getFromFileTree(tree, file) {
            const out = tree ? tree[file.id] : file.name;
            return out || file.name;
        },

        processFileTree(tree, base = '') {
            const newBase = base ? `${base}/${tree.name}` : tree.name;
            if (tree.entries) {
                return tree.entries.reduce(
                    (accum, e) => Object.assign(accum, this.processFileTree(e, newBase)),
                    {},
                );
            } else {
                return { [tree.id]: newBase };
            }
        },

        exportToDocument() {
            const matches = this.matchesSortedByRange.filter(a => this.exportMatches[a.id]);

            if (matches.length === 0) {
                throw new Error('Select at least one case.');
            }

            return this.renderPlagiarismDocument(matches);
        },

        afterExportToDocument(fileData) {
            this.$set(this, 'exportMatches', {});
            const [user1, user2] = this.detail.users.map(nameOfUser);
            const backend = documentBackends[this.outputFormat];
            const fileName = `plagiarism_case_${user1}+${user2}.${backend.fileExtension}`;
            downloadFile(fileData, fileName, backend.mimeType);
        },

        toggleExportMatch(id, value = null) {
            const newVal = value == null ? !this.exportMatches[id] : value;
            this.$set(this.exportMatches, id, newVal);
            this.$set(this, 'exportMatches', this.exportMatches);
        },

        toggleAllMatches(enabled) {
            this.matchIds.forEach(id => {
                this.$set(this.exportMatches, id, enabled);
            });
            this.$set(this, 'exportMatches', this.exportMatches);
        },

        updateContextLines(event) {
            let context = parseInt(event.target.value, 10);
            if (Number.isNaN(context)) {
                context = 0;
            }
            this.$set(this.exportOptions, 'contextLines', context);
        },
    },

    mounted() {
        this.loadDetail();
    },

    components: {
        Loader,
        LocalHeader,
        SubmitButton,
        User,
        Collapse,
        Icon,
        InnerCodeViewer,
        InnerIpythonViewer,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.plagiarism-detail {
    display: flex;
    flex-direction: column;
    height: 80vh;
    margin-bottom: 0 !important;
}

.local-header {
    flex: 0 0 auto;
}

.range-table-wrapper {
    max-height: 8em;
    flex: 0 0 auto;
    overflow-y: auto;
    border: 1px solid rgba(0, 0, 0, 0.125);
    border-radius: @border-radius;
}

.range-table {
    margin-bottom: 0;
    width: 100%;

    th,
    td {
        border-top: none;
        padding-top: 0rem;
        padding-bottom: 0rem;
    }

    .col-student-name {
        width: 50%;
    }

    #plagiarism-export & {
        word-break: break-all;
    }
}

.code-viewer {
    margin-top: 0.75rem;
    flex: 4 4 auto;
    overflow-y: auto;
}

.code-viewer {
    display: flex;
    flex-direction: row;
    padding: 0;
    margin-bottom: 1rem;
}

.student-files {
    flex: 0 0 50%;
    max-height: 100vh;
    overflow: auto;
    position: relative;

    &::after {
        content: '';
        display: block;
        height: ~'calc(100% - 10rem)';
    }
}

.student-file {
    margin-top: 0 !important;
    border-left: 0;
    border-right: 0;
    border-top: 0;

    &:last-child {
        border-bottom: 0;
    }

    &:not(:first-child) {
        margin-top: -1px;
        border-top-left-radius: 0;
        border-top-right-radius: 0;
    }

    &:not(:last-child) {
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
    }

    .student-files:not(:first-child) & {
        border-top-left-radius: 0;
        border-bottom-left-radius: 0;
    }

    .student-files:not(:last-child) & {
        border-top-right-radius: 0;
        border-bottom-right-radius: 0;
    }

    .card-header {
        position: relative;
        position: sticky;
        top: 0;
        z-index: 5;
        background-color: @linum-bg;
        margin-bottom: -1px;
    }
}

.inner-code-viewer {
    min-height: 5em;
    margin: 0;
    overflow: hidden;
}

.plagiarism-detail .input-group-prepend {
    margin-top: 0;
}
</style>

<style lang="less">
@export-modal-width: 75vw;
@export-modal-margin: (100vw - @export-modal-width) / 2;

#plagiarism-export .modal-dialog {
    max-width: @export-modal-width;
    margin-left: @export-modal-margin;
    margin-right: @export-modal-margin;

    .modal-content {
        width: @export-modal-width;
    }
}
</style>
