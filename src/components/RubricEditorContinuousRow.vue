<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="rubric-editor-row continuous"
     :class="{ grow }"
     @mouseenter="lockPopoverVisible = true"
     @mouseleave="lockPopoverVisible = false">
    <template v-if="editable">
        <b-input-group class="mb-3">
            <b-input-group-prepend is-text>
                Category name
            </b-input-group-prepend>

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

            <b-input-group-append v-else>
                <cg-submit-button variant="danger"
                                  class="delete-category"
                                  label="Remove category"
                                  :wait-at-least="0"
                                  :submit="() => {}"
                                  @after-success="$emit('delete')"
                                  confirm="Do you really want to delete this category?" />
            </b-input-group-append>
        </b-input-group>

        <b-input-group class="mb-3">
            <b-input-group-prepend is-text>
                Max points
            </b-input-group-prepend>

            <input class="points form-control"
                   type="number"
                   placeholder="Points"
                   :value="onlyItem.points"
                   @input="updatePoints"
                   @keydown.ctrl.enter="submitRubric" />
        </b-input-group>

        <previewable-markdown-editor
            class="category-description mb-3"
            placeholder="Description"
            :tabindex="active ? null : -1"
            :value="value.description"
            @input="updateProp($event, 'description')"
            @keydown.ctrl.enter.prevent="submitRubric" />
    </template>

    <div v-else>
        <template v-if="value.locked">
            <b-popover :show="lockPopoverVisible"
                       :target="`rubric-lock-${id}`"
                       :content="lockPopover"
                       triggers=""
                       placement="top" />

            <fa-icon name="lock"
                     class="float-right"
                     :id="`rubric-lock-${id}`" />
        </template>

        <p v-if="!value.description"
           class="mb-3 pb-3 border-bottom text-muted font-italic"
           >This category has no description.</p>
        <inner-markdown-viewer
            v-else-if="value.descriptionType === 'markdown'"
            :markdown="value.description" />
        <p v-else class="mb-3 pb-3 border-bottom text-wrap-pre"
           >{{ value.description }}</p>

        <p class="mb-0 pb-3">
            This is a continuous rubric category. You can score anywhere between
            <b>0</b> and <b>{{ onlyItem.points }} points</b> in this category.
        </p>
    </div>
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
        active: {
            type: Boolean,
            default: false,
        },
        grow: {
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

        deleteRow() {
            this.$emit('delete');
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
