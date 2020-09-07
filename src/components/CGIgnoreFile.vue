<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="cgignore-file">
    <div v-if="oldRemoteVersion && editable">
        <b-alert show variant="warning">
            A previous version of the submission validator was used. This old format
            is deprecated, and can no longer be edited. The contents of this old
            file are:
            <div class="old-cgignore">
                <pre>{{ oldCgignore }}</pre>
            </div>
        </b-alert>
        <cg-submit-button :submit="deleteIgnore"
                          @after-success="afterUpdateIgnore"
                          variant="danger"
                          confirm="Are you sure you want to delete this old validator?"
                          label="Clear and use new version"/>
    </div>
    <div v-else-if="oldRemoteVersion">
        <pre>{{ oldCgignore }}</pre>
    </div>
    <div v-else-if="!editable && !policy"
         class="font-italic text-muted">
        No validation set.
    </div>
    <div v-else-if="!assignmentHasInstructions && showImporter">
        <h4 class="text-center mb-3">
            Select an assignment to copy from
        </h4>

        <b-input-group class="mb-3">
            <multiselect
                class="assignment-selector"
                v-model="importAssignment"
                :loading="!retrievedAllCourses"
                :options="otherAssignmentsWithInstructions"
                :searchable="true"
                :custom-label="getImportLabel"
                :multiple="false"
                track-by="id"
                label="label"
                :close-on-select="true"
                :hide-selected="false"
                placeholder="Type to search an assignment"
                :internal-search="true">
                <span slot="noResult">
                    No results were found.
                </span>
            </multiselect>
        </b-input-group>

        <b-button-toolbar justify>
            <b-button @click="showImporter = false">
                Go back
            </b-button>

            <cg-submit-button :disabled="!importAssignment"
                              label="Import"
                              :submit="copyIgnore"
                              @after-success="afterUpdateIgnore"/>
        </b-button-toolbar>
    </div>
    <div v-else-if="!rules"
         class="d-flex flex-row justify-content-center">
        <cg-wizard-button
            class="mr-3"
            label="Create new hand-in instructions"
            icon="plus"
            @click="createInstructions" />

        <cg-wizard-button
            label="Copy instructions"
            icon="copy"
            @click="showImporter = true" />
    </div>
    <template v-else-if="!summaryMode">
        <b-form-group class="policy-form"
                      :class="policy ? '' : 'policy-form-only'"
                      label-class="font-weight-bold pt-0 policy-form-label"
                      label-cols="9"
                      horizontal>
            <template slot="label">
                By default
                <cg-description-popover hug-text>
                    <p class="mb-1">
                        This determines what happens to files by default.  With
                        both options you can specify required files, that students
                        must upload.
                    </p>

                    <p class="mb-1">
                        <b>Deny all files</b> denies all files by default, which
                        determines exactly which files a student is allowed to
                        upload.
                    </p>

                    <p class="mb-1">
                        <b>Allow all files</b> allows all files by default, which
                        allows you to specify which files a student is not allowed
                        to upload.
                    </p>
                </cg-description-popover>
            </template>
            <b-form-radio-group
                class="option-button"
                :disabled="!editable || policyDisabled"
                v-b-popover.top.hover="policyDisabled && editable ? 'You cannot change the policy after you have created rules.' : ''"
                v-model="policy"
                size="sm"
                :options="policyOptions"
                button-variant="primary"
                buttons />
        </b-form-group>

        <b-button v-if="!assignmentHasInstructions && !policy"
                  @click="resetValues"
                  class="mt-3">
            Go back
        </b-button>
    </template>

    <transition :name="disabledAnimations ? '' : 'collapse'">
        <div v-if="policy" class="collapse-entry">
            <table v-if="!summaryMode" class="table table-striped">
                <thead>
                    <tr>
                        <th colspan="2">Options</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="option in options">
                        <td>
                            {{ option.name }}
                            <cg-description-popover hug-text :description="option.description"/>
                        </td>
                        <td>
                            <b-form-group horizontal
                                          class="mb-0">
                                <b-form-radio-group
                                    class="option-button"
                                    size="sm"
                                    :disabled="!editable"
                                    v-model="option.value"
                                    :options="option.options"
                                    button-variant="primary"
                                    buttons />
                            </b-form-group>
                        </td>
                    </tr>
                </tbody>
            </table>
            <div>
                <div v-if="summaryMode"
                     class="rules-header p-3">
                    <b>
                        By default all files are
                        <i>{{ policyOptions.find(x => x.value === policy).shortText }}</i>.
                        Exceptions and requirements:
                    </b>
                </div>
                <ul v-if="!loadingRules"
                    class="rules-list striped-list"
                    :class="{ 'background-enabled': !disableBackgroundAnimation }">
                    <transition-group :name="disabledAnimations ? '' : 'list'">
                        <li v-for="ruleIndex in sortedRuleIndices"
                            v-if="!rules[ruleIndex].removed"
                            class="list-item"
                            :key="ruleIndex">
                            <div class="rule-wrapper">
                                <file-rule v-model="rules[ruleIndex]"
                                           :all-rules="rules"
                                           :editing="!!rules[ruleIndex].editing"
                                           :editable="editable"
                                           :policy="policy"
                                           :focus="!!rules[ruleIndex].focus"
                                           @file-sep-click="addNewRule"
                                           @done-editing="$set(rules[ruleIndex], 'editing', false)"/>
                                <b-button-group v-if="editable && !rules[ruleIndex].editing">
                                    <cg-submit-button confirm="Are you sure you want to delete this rule?"
                                                      v-b-popover.top.hover="'Delete this rule'"
                                                      :submit="ruleDeleterAt(ruleIndex)"
                                                      :duration="0"
                                                      :wait-at-least="0"
                                                      variant="danger">
                                        <fa-icon name="times"/>
                                    </cg-submit-button>
                                    <b-btn variant="primary"
                                           class="edit-rule-btn"
                                           v-b-popover.top.hover="'Edit this rule'"
                                           @click="$set(rules[ruleIndex], 'editing', true)">
                                        <fa-icon name="pencil"/>
                                    </b-btn>
                                </b-button-group>
                            </div>
                        </li>
                    </transition-group>
                    <li class="new-file-rule"
                        v-if="editable">
                        <file-rule v-model="newRule"
                                   editing
                                   :all-rules="rules"
                                   :policy="policy"/>
                    </li>
                </ul>
            </div>

            <template v-if="editable">
                <div class="help-text">
                    <p>
                        Add rules by specifying the required, allowed or denied path
                        in the text area above. Use <code>/</code> or <code>\</code>
                        as a directory separator to specify that certain files are
                        required, allowed or denied in a directory. Start the rule
                        with a directory separator (<code>/</code>
                        or <code>\</code>) to specify that a file is required,
                        allowed or denied in the top level directory.
                    </p>

                    <p class="mb-0">
                        To match more than one file, you can use a single wildcard
                        for the name of the file, by using a <code>*</code>. For
                        example <code>/src/*.py</code> matches any file ending
                        with <code>.py</code> in the directory <code>src</code> that
                        is directly in the top level directory of the submission.
                    </p>
                </div>

                <b-button-toolbar justify class="pt-3 border-top">
                    <cg-submit-button v-if="assignmentHasInstructions"
                                      :submit="deleteIgnore"
                                      @after-success="afterUpdateIgnore"
                                      variant="danger"
                                      confirm="Are you sure you want to delete this validator?"
                                      label="Delete"/>

                    <b-button v-else @click="resetValues">
                        Go back
                    </b-button>

                    <cg-submit-button :submit="submitIgnore"
                                      @success="afterUpdateIgnore"
                                      class="submit-ignore"
                                      :disabled="!configurationValid">
                        <template slot="error" slot-scope="e">
                            <span v-if="getProps(e, null, 'error', 'response', 'data', 'code') === 'PARSING_FAILED'">
                                {{ e.error.response.data.message }}: {{ e.error.response.data.description }}
                            </span>
                            <span v-else-if="getProps(e, null, 'error', 'response', 'data', 'message')">
                                {{ e.error.response.data.message }}
                            </span>
                            <span v-else>
                                Something unknown went wrong!
                            </span>
                        </template>
                    </cg-submit-button>
                </b-button-toolbar>
            </template>
        </div>
    </transition>
</div>
</template>

<script>
import Multiselect from 'vue-multiselect';

import 'vue-awesome/icons/times';
import 'vue-awesome/icons/copy';
import 'vue-awesome/icons/plus';

import { mapActions, mapGetters } from 'vuex';

import { range, getProps } from '@/utils';
import * as models from '@/models';

import FileRule from './FileRule';

let optionId = 0;
function getOptionId() {
    return `ignore-option-${optionId++}`;
}

export default {
    name: 'ignore-file',

    props: {
        assignment: {
            type: models.Assignment,
            required: true,
        },
        editable: {
            type: Boolean,
            default: true,
        },
        summaryMode: {
            type: Boolean,
            default: false,
        },
    },

    computed: {
        ...mapGetters('courses', ['retrievedAllCourses', 'getCourse']),
        ...mapGetters('assignments', ['allAssignments']),

        remoteIgnoreFile() {
            return [
                getProps(this.assignment, null, 'cgignore'),
                getProps(this.assignment, null, 'cgignore_version'),
            ];
        },

        policyDisabled() {
            return this.rules.some(r => !r.removed && r.rule_type !== 'require');
        },

        configurationValid() {
            return (
                this.policy &&
                    this.options.every(o => o.value != null) &&
                    this.rules.some(r => !r.removed)
            );
        },

        sortedRuleIndices() {
            return range(this.rules.length).sort((indexA, indexB) => {
                const a = this.rules[indexA];
                const b = this.rules[indexB];

                if (a.name === '' || b.name === '') {
                    return b.name.length - a.name.length;
                } else if (a.name[0] === '/' && b.name[0] !== '/') {
                    return -1;
                } else if (a.name[0] !== '/' && b.name[0] === '/') {
                    return 1;
                }

                const partsA = a.name.split('/');
                const partsB = b.name.split('/');

                for (let i = 0; i < Math.min(partsA.length, partsB.length); ++i) {
                    const cmp = partsA[i].localeCompare(partsB[i]);
                    if (cmp !== 0) {
                        return cmp;
                    }
                }
                const lengthDiff = partsA.length - partsB.length;
                if (lengthDiff !== 0) {
                    return lengthDiff;
                }
                // Make sure we sort stable, by using the index as the tie breaker.
                return indexA - indexB;
            });
        },

        policyOptions() {
            return [
                {
                    text: 'Deny all files',
                    shortText: 'denied',
                    value: 'deny_all_files',
                },
                {
                    text: 'Allow all files',
                    shortText: 'allowed',
                    value: 'allow_all_files',
                },
            ];
        },

        assignmentHasInstructions() {
            return !!this.assignment.cgignore;
        },

        otherAssignmentsWithInstructions() {
            // We cannot (!) use real models here as all getters will be removed
            // by vue-multiselect as it tries to copy the objects, however that
            // doesn't work with getters.
            return this.allAssignments.filter(assig =>
                assig.cgignore_version === 'SubmissionValidator' && assig.id !== this.assignmentId,
            ).map(a => ({
                id: a.id,
                name: a.name,
                cgignore: a.cgignore,
                cgignore_version: a.cgignore_version,
                courseId: a.courseId,
            }));
        },
    },

    watch: {
        newRule() {
            if (this.newRule.name) {
                this.rules.push(this.newRule);
                this.newRule = this.getNewRule();
            }
        },

        remoteIgnoreFile: {
            handler([file, version]) {
                this.copyRemoteValues(file, version);
            },
            immediate: true,
        },

        showImporter(newVal) {
            if (newVal) {
                this.loadAllCourses();
            }
        },
    },

    mounted() {
        this.disabledAnimations = false;
    },

    data() {
        return {
            getProps,
            disableBackgroundAnimation: false,
            newRule: this.getNewRule(),
            deleting: false,
            disabledAnimations: true,
            policy: null,
            loadingRules: false,
            content: '',
            rules: null,
            options: this.getDefaultOptions(),
            oldRemoteVersion: false,
            oldCgignore: '',

            showImporter: false,
            importAssignment: null,
        };
    },

    methods: {
        ...mapActions('assignments', ['patchAssignment']),
        ...mapActions('courses', ['loadAllCourses']),

        createInstructions() {
            this.rules = [];
        },

        copyRemoteValues(ignore, version) {
            if (version === 'IgnoreFilterManager' || (version == null && ignore != null)) {
                this.oldCgignore = ignore;
                this.oldRemoteVersion = true;
                this.resetValues();
            } else if (version === 'EmptySubmissionFilter' || ignore == null) {
                this.oldRemoteVersion = false;
                this.resetValues();
            } else {
                this.oldRemoteVersion = false;
                this.policy = ignore.policy;
                this.rules = ignore.rules.map(r => Object.assign({}, r));
                this.options = this.getDefaultOptions().map(opt => {
                    const remote = ignore.options.find(o => o.key === opt.key);
                    if (remote != null) {
                        opt.value = remote.value;
                    }
                    return opt;
                });
            }
        },

        resetValues() {
            this.policy = null;
            this.rules = null;
            this.options = this.getDefaultOptions();
        },

        getDefaultOptions() {
            const onOff = [{ text: 'Enabled', value: true }, { text: 'Disabled', value: false }];

            return [
                {
                    key: 'delete_empty_directories',
                    description:
                        'If this option is enabled, this will automatically delete empty directories without any files in submissions.',
                    value: false,
                    name: 'Delete empty directories',
                    options: onOff,
                    id: getOptionId(),
                },
                {
                    key: 'remove_leading_directories',
                    description:
                    'If this option is enabled, this will automatically delete any extra leading directories in a submission. For example, if all the files and/or directories are in a subdirectory, this will remove the top level directory.',
                    value: true,
                    name: 'Delete leading directories',
                    options: onOff,
                    id: getOptionId(),
                },
                {
                    key: 'allow_override',
                    value: false,
                    description:
                    'If this option is enabled, this will allow students to press an override button to hand in a submission, even if it does not follow the hand-in requirements. Students will, however, get a warning that their submission does not follow the hand-in requirements.',
                    name: 'Allow overrides by students',
                    options: onOff,
                    id: getOptionId(),
                },
            ];
        },

        deleteIgnore() {
            return this.updateIgnore('', 'EmptySubmissionFilter');
        },

        submitIgnore() {
            return this.updateIgnore(
                {
                    policy: this.policy,
                    options: this.options.map(o => ({ key: o.key, value: o.value })),
                    rules: this.rules.filter(r => !r.removed).map(r => ({
                        name: r.name,
                        file_type: r.file_type,
                        rule_type: r.rule_type,
                    })),
                },
                'SubmissionValidator',
            );
        },

        updateIgnore(ignore, ignoreVersion) {
            return this.patchAssignment({
                assignmentId: this.assignment.id,
                assignmentProps: {
                    ignore,
                    ignore_version: ignoreVersion,
                },
            });
        },

        addNewRule(name) {
            this.rules.push({
                name,
                file_type: name[name.length - 1] === '/' ? 'directory' : 'file',
                rule_type: 'require',
                editing: true,
                focus: true,
            });
            this.rules = this.rules;
        },

        async afterUpdateIgnore(response) {
            // We need to set `loadingRules` to `true` so that we can update the
            // rules without having any issue with animations.
            // eslint-disable-next-line camelcase
            const { cgignore, cgignore_version } = response.data;
            this.loadingRules = true;
            await this.$nextTick();
            this.showImporter = false;
            this.copyRemoteValues(cgignore, cgignore_version);
            this.loadingRules = false;
        },

        ruleDeleterAt(index) {
            return () => this.deleteRule(index);
        },

        deleteRule(ruleIndex) {
            this.$set(this.rules[ruleIndex], 'removed', true);
            this.disableBackgroundAnimation = true;
            setTimeout(() => {
                this.disableBackgroundAnimation = false;
            }, 600);
        },

        getNewRule() {
            return {
                rule_type: 'require',
                file_type: 'directory',
                name: '',
            };
        },

        copyIgnore() {
            return this.updateIgnore(
                this.importAssignment.cgignore,
                this.importAssignment.cgignore_version,
            );
        },

        getImportLabel(assigLike) {
            return this.getCourse(assigLike.courseId).mapOrDefault(
                course => `${course.name} - ${assigLike.name}`,
                `… - ${assigLike.name}`,
            );
        },
    },

    components: {
        FileRule,
        Multiselect,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

td {
    vertical-align: middle;
}

.rule-wrapper {
    display: flex;
    justify-content: space-between;
}

.collapse-enter-active {
    transition: all 0.5s;
    max-height: 35rem;
    overflow: hidden;
}
.collapse-enter,
.collapse-leave-to,
.collapse-enter .collapse-entry {
    max-height: 0;
}

.list-enter-active {
    transition: all 0.9s;
    background-color: fade(@color-success, 50%) !important;
}
.list-leave-active {
    transition: opacity 0.6s;
    background-color: rgb(217, 83, 79) !important;
}

.list-leave-to {
    background-color: rgb(217, 83, 79) !important;
}
.list-enter,
.list-leave-to {
    opacity: 0;
}

.old-cgignore {
    padding: 1rem;
    margin-top: 1rem;
    border: 1px solid currentColor;
    border-radius: @border-radius;
}

pre {
    margin: 0;
    padding: 0;
}

.rules-list.background-enabled .list-item {
    transition: all 0.3s;
}

.btn.policy-btn {
    float: right;
    cursor: default;
    box-shadow: none !important;

    &:hover {
        background-color: @color-primary;
    }
}

.btn.edit-rule-btn {
    margin-left: 0px;
}
</style>

<style lang="less">
@import '~mixins.less';

.cgignore-file {
    .option-button {
        .btn {
            border-color: @color-primary;
        }

        .btn:not(.disabled) {
            cursor: pointer;
            box-shadow: none;
        }

        &.btn-group {
            float: right;
        }

        .btn.active {
            text-decoration: underline;
            background-color: @color-primary;
            border-color: @color-primary;

            @{dark-mode} {
                background-color: @color-primary-darker;
                border-color: @color-primary-darker;
            }
        }

        .btn:not(.active) {
            background-color: transparent;
            color: @text-color;

            &:not(.disabled):hover {
                background-color: rgba(0, 0, 0, 0.1);
            }

            @{dark-mode} {
                border-color: @color-primary-darker;
                color: @text-color-dark;
            }
        }
    }

    .policy-form {
        padding-left: 0.75rem;
        vertical-align: middle;

        &-only {
            margin-bottom: 0;
        }

        .form-row {
            align-items: center;
        }

        .policy-form-label {
            padding-bottom: 0;
        }
    }
}
</style>
