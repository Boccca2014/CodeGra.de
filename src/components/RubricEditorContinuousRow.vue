<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="rubric-editor-row continuous">
    <template v-if="editable">
        <b-form-group label="Category name">
            <input class="category-name form-control"
                   placeholder="Category name"
                   :value="value.header"
                   @input="updateProp($event, 'header')"
                   @keydown.ctrl.enter="submitRubric" />
        </b-form-group>

        <b-form-group label="Category description">
            <previewable-markdown-editor
                class="category-description"
                :rows="3"
                placeholder="Description"
                :value="value.description"
                @input="updateProp($event, 'description')"
                @submit="submitRubric"
                :hide-toggle="!value.isMarkdown">
                <template #empty>
                    No description.
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
        <p v-if="!value.description"
           class="text-muted font-italic">
            This category has no description.
        </p>
        <inner-markdown-viewer
            v-else-if="value.isMarkdown"
            :markdown="value.description" />
        <p v-else class="mb-3 text-wrap-pre"
            >{{ value.description }}</p>

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
        };
    },

    computed: {
        onlyItem() {
            // The only item in a continuous row.
            return this.value.items[0];
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
            const item = this.onlyItem.update({
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
