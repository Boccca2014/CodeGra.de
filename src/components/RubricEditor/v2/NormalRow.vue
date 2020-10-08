<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="rubric-editor-row normal">
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
                placeholder="Category description"
                :value="value.description"
                @input="updateProp($event, 'description')"
                @submit="submitRubric"
                :hide-toggle="!value.isMarkdown">
                <template #empty>
                    No description.
                </template>
            </previewable-markdown-editor>
        </b-form-group>
    </template>

    <template v-else>
        <p v-if="!value.description"
           class="text-muted font-italic">
            This category has no description.
        </p>
        <inner-markdown-viewer
            v-if="value.isMarkdown"
            :markdown="value.description"
            class="mb-3" />
        <p v-else class="text-wrap-pre"
            >{{ value.description }}</p>

        <hr />
    </template>

    <b-form-group :label="editable ? 'Category items' : ''"
                  class="mb-0">
        <div class="item-container d-flex flex-row flex-wrap">
            <div v-for="item, i in value.items"
                 :key="item.id || -item.trackingId"
                 class="rubric-item col-12 col-md-6 col-xl-4 mb-3 d-flex flex-column"
                 ref="rubricItems">
                <template v-if="editable">
                    <b-input-group>
                        <input type="number"
                               class="points form-control rounded-bottom-0 px-2"
                               step="any"
                               placeholder="Pts."
                               :value="item.points"
                               @input="updateItem(i, 'points', $event)"
                               @keydown.ctrl.enter="submitRubric" />

                        <input type="text"
                               class="header form-control rounded-bottom-0"
                               placeholder="Header"
                               :value="item.header"
                               @input="updateItem(i, 'header', $event)"
                               @keydown.ctrl.enter="submitRubric" />

                        <b-input-group-append
                            v-if="canChangeItems"
                            is-text
                            class="delete-item rounded-bottom-0 text-muted cursor-pointer"
                            v-b-popover.top.hover="'Delete this item.'"
                            @click="deleteItem(i)">
                            <fa-icon name="times" />
                        </b-input-group-append>
                    </b-input-group>

                    <previewable-markdown-editor
                        class="description border-top-0 rounded-top-0"
                        :rows="5"
                        placeholder="Description"
                        :value="item.description"
                        @input="updateItem(i, 'description', $event)"
                        @submit="submitRubric"
                        :hide-toggle="!value.isMarkdown">
                        <template #empty>
                            No description...
                        </template>
                    </previewable-markdown-editor>
                </template>

                <template v-else>
                    <span class="flex-grow-0 px-1">
                        <b class="points pr-1">{{ item.points }}</b>
                        -
                        <b class="header pl-1">{{ item.header }}</b>
                    </span>

                    <!-- Weird formatting required for text-wrap-pre formatting. -->
                    <p v-if="!item.description"
                       class="description border rounded mb-0 px-3 py-2 text-muted font-italic">
                        No description.
                    </p>
                    <inner-markdown-viewer
                        v-else-if="value.isMarkdown"
                        :markdown="item.description"
                        class="border rounded px-3 pt-2"/>
                    <p v-else
                       class="description flex-grow-1 border rounded mb-0 px-3 py-2 text-wrap-pre"
                        >{{ item.description }}</p>
                </template>
            </div>

            <div v-if="canChangeItems"
                 class="rubric-item add-button col-12 col-md-6 col-xl-4 mb-3"
                 @click="createItem">
                <div class="wrapper">
                    <b-input-group>
                        <input type="number"
                               class="points form-control rounded-bottom-0 px-2"
                               step="any"
                               placeholder="Pts."
                               disabled />

                        <input type="text"
                               class="header form-control rounded-bottom-0"
                               placeholder="Header"
                               disabled />
                    </b-input-group>

                    <previewable-markdown-editor
                        class="description border-top-0 rounded-top-0"
                        value=""
                        :rows="5"
                        placeholder="Description"
                        disabled
                        :hide-toggle="!value.isMarkdown" />

                    <div class="overlay rounded cursor-pointer">
                        <fa-icon name="plus" :scale="3" />
                    </div>
                </div>
            </div>
        </div>
    </b-form-group>
</div>
</template>

<script>
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/plus';

import {
    InnerMarkdownViewer,
    PreviewableMarkdownEditor,
} from '@/components';

export default {
    name: 'rubric-editor-normal-row',

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
        canChangeItems() {
            const runs = this.$utils.getProps(this.autoTest, [], 'runs');
            return this.editable && !(this.value.locked && runs.length);
        },

        hasItemsWithDescription() {
            return this.value.items.some(item => !!item.description);
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

        updateItem(idx, prop, event) {
            this.ensureEditable();
            this.$emit('input', this.value.updateItem(idx, prop, event.target.value));
        },

        createItem() {
            this.ensureEditable();
            this.$emit('input', this.value.createItem());
            this.$nextTick().then(() => {
                const nitems = this.value.items.length;
                const el = this.$refs.rubricItems[nitems - 1];
                el.querySelector('input').focus();
            });
        },

        deleteItem(idx) {
            if (idx < 0 || idx >= this.value.items.length) {
                throw new Error('Invalid item index');
            }

            this.ensureEditable();
            this.$emit('input', this.value.deleteItem(idx));
        },

        submitRubric() {
            this.$emit('input', this.value);
            this.$nextTick().then(() => {
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
@import '~mixins.less';

.item-container {
    margin: 0 -0.5rem;
}

.rubric-item {
    padding: 0 0.5rem;
}

.add-button .wrapper {
    position: relative;
    opacity: 0.66;
}

.add-button .overlay {
    height: 100%;
    width: 100%;
    top: 0;
    left: 0;
    position: absolute;
    background-color: rgba(0, 0, 0, 0.0625);
    transition: background-color @transition-duration;

    &:hover {
        background-color: rgba(0, 0, 0, 0.125);
    }

    .fa-icon {
        position: absolute;
        left: 50%;
        top: 50%;
        transform: translate(-50%, -50%);
    }
}

input.points {
    max-width: 3rem;
}

.rubric-editor-row.normal p.description {
    max-height: 10rem;
    overflow: auto;
}
</style>

<style lang="less">
@import '~mixins';

.rubric-editor-row.normal {
    .input-group-append.rounded-bottom-0 .input-group-text {
        border-bottom-left-radius: 0 !important;
        border-bottom-right-radius: 0 !important;
    }

    .add-button [disabled] {
        .default-background;
    }
}
</style>
