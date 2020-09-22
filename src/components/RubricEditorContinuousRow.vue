<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="rubric-editor-row continuous"
     @mouseenter="lockPopoverVisible = true"
     @mouseleave="lockPopoverVisible = false">
    <template v-if="editable">
        <b-form-group label="Category name">
            <b-input-group>
                <input class="category-name form-control"
                       placeholder="Category name"
                       :value="value.header"
                       @input="updateProp($event, 'header')"
                       @keydown.ctrl.enter="submitRubric" />

                <b-input-group-append v-if="value.locked"
                                      class="cursor-help"
                                      is-text
                                      v-b-popover.top.hover="lockPopover">
                    <fa-icon class="lock-icon" name="lock" />
                </b-input-group-append>
            </b-input-group>
        </b-form-group>

        <b-form-group label="Category description">
            <previewable-markdown-editor
                class="category-description"
                :rows="5"
                placeholder="Description"
                :value="value.description"
                @input="updateProp($event, 'description')"
                @submit="submitRubric"
                :hide-toggle="!value.isMarkdown">
                <template #empty>
                    No description...
                </template>
            </previewable-markdown-editor>
        </b-form-group>

        <b-form-group label="Max points">
            <input class="points form-control"
                   type="number"
                   placeholder="Points"
                   :value="onlyItem.points"
                   @input="updatePoints"
                   @keydown.ctrl.enter="submitRubric" />
        </b-form-group>
    </template>

    <template v-else>
        <h4 class="mb-3">
            <!-- Put the lock before the header text so that the header text
                 wraps around it rather than pushing the lock to a new line. -->
            <template v-if="value.locked">
                <b-popover :show="lockPopoverVisible"
                           :target="`rubric-lock-${id}`"
                           :content="lockPopover"
                           triggers=""
                           placement="top" />

                <fa-icon name="lock"
                         class="mt-1 float-right"
                         :id="`rubric-lock-${id}`" />
            </template>

            {{ value.header }}
        </h4>

        <template v-if="value.description">
            <inner-markdown-viewer
                v-if="value.isMarkdown"
                :markdown="value.description" />
            <p v-else class="mb-3 text-wrap-pre"
               >{{ value.description }}</p>
        </template>

        <hr />

        <p>
            This is a continuous rubric category. You can score anywhere
            between <b>0</b> and <b>{{ onlyItem.points }} points</b> in this
            category.
        </p>
    </template>
</div>
</template>

<script>
import 'vue-awesome/icons/lock';

import InnerMarkdownViewer from './InnerMarkdownViewer';
import PreviewableMarkdownEditor from './PreviewableMarkdownEditor';

export default {
    name: 'rubric-editor-continuous-row',

    props: {
        value: {
            type: Object,
            required: true,
        },
        assignment: {
            type: Object,
            required: true,
        },
        autoTest: {
            type: Object,
            default: null,
        },
        editable: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            id: this.$utils.getUniqueId(),
            lockPopoverVisible: false,
        };
    },

    computed: {
        onlyItem() {
            // The only item in a continuous row.
            return this.value.items[0];
        },

        lockPopover() {
            return this.value.lockMessage(this.autoTest, null, null);
        },
    },

    methods: {
        ensureEditable() {
            if (!this.editable) {
                throw new Error('This rubric row is not editable!');
            }
        },

        updateProp(event, prop) {
            this.ensureEditable();
            this.$emit(
                'input',
                this.value.update({
                    [prop]: event.target.value,
                }),
            );
        },

        updatePoints(event) {
            const item = Object.assign({}, this.onlyItem, {
                points: parseFloat(event.target.value),
            });
            this.$emit(
                'input',
                this.value.update({
                    items: [item],
                }),
            );
        },

        submitRubric() {
            this.$emit('input', this.value);
            this.$nextTick(() => {
                this.$emit('submit');
            });
        },
    },

    components: {
        InnerMarkdownViewer,
        PreviewableMarkdownEditor,
    },
};
</script>

<style lang="less" scoped>

</style>
