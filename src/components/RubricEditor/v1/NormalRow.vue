<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="rubric-editor-row normal"
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
                                  @after-success="deleteRow"
                                  confirm="Do you really want to delete this category?" />
            </b-input-group-append>
        </b-input-group>

        <textarea class="category-description form-control mb-3"
                  placeholder="Category description"
                  :tabindex="active ? null : -1"
                  :value="value.description"
                  @input="updateProp($event, 'description')"
                  @keydown.ctrl.enter.prevent="submitRubric" />
    </template>

    <div v-else
         class="mb-3 pb-3 border-bottom">
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

        <p v-if="value.description"
           class="mb-0 text-wrap-pre"
           >{{ value.description }}</p>
        <p v-else
           class="mb-0 text-muted font-italic">
            This category has no description.
        </p>
    </div>

    <div class="item-container row d-flex flex-row flex-wrap">
        <div v-for="item, i in value.items"
             :key="item.id || -item.trackingId"
             class="rubric-item col-6 col-lg-4 mb-3 d-flex flex-column"
             ref="rubricItems">
            <template v-if="editable">
                <b-input-group>
                    <input type="number"
                           class="points form-control rounded-bottom-0 px-2"
                           step="any"
                           :tabindex="active ? null : -1"
                           placeholder="Pts."
                           :value="item.points"
                           @input="updateItem(i, 'points', $event)"
                           @keydown.ctrl.enter="submitRubric" />

                    <input type="text"
                           class="header form-control rounded-bottom-0"
                           placeholder="Header"
                           :tabindex="active ? null : -1"
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

                <textarea class="description form-control border-top-0 rounded-top-0"
                          :rows="8"
                          placeholder="Description"
                          :tabindex="active ? null : -1"
                          :value="item.description"
                          @input="updateItem(i, 'description', $event)"
                          @keydown.ctrl.enter.prevent="submitRubric" />
            </template>

            <template v-else>
                <span class="flex-grow-0 px-1">
                    <b class="points pr-1">{{ item.points }}</b>
                    -
                    <b class="header pl-1">{{ item.header }}</b>
                </span>

                <!-- Weird formatting required for text-wrap-pre formatting. -->
                <p class="description flex-grow-1 border rounded mb-0 px-3 py-2 text-wrap-pre"
                    ><template v-if="item.description">{{ item.description }}</template
                    ><span v-else class="text-muted font-italic">No description.</span>
                </p>
            </template>
        </div>

        <div v-if="editable && canChangeItems"
             class="rubric-item add-button col-6 col-lg-4 mb-3"
             @click="createItem">
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

            <textarea class="description form-control border-top-0 rounded-top-0"
                      :rows="8"
                      placeholder="Description"
                      disabled />

            <div class="overlay rounded cursor-pointer">
                <fa-icon name="plus" :scale="3" />
            </div>
        </div>
    </div>
</div>
</template>

<script>
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/plus';
import 'vue-awesome/icons/lock';

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
        canChangeItems() {
            const runs = this.$utils.getProps(this.autoTest, [], 'runs');
            return this.editable && !(this.value.locked && runs.length);
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

        deleteRow() {
            this.$emit('delete');
        },
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.item-container {
    position: relative;
}

.item-container,
.rubric-item {
    padding: 0 0.5rem 0 0.5rem;
}

.add-buton {
    position: relative;
}

.add-button .overlay {
    height: 100%;
    top: 0;
    left: 0.5rem;
    right: 0.5rem;
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
        opacity: 0.8;
    }
}

input.points {
    max-width: 3rem;
}

p.description {
    background-color: rgba(0, 0, 0, 0.0325);

    .rubric-editor-row.normal:not(.grow) & {
        height: 10rem;
    }
}
</style>

<style lang="less">
.rubric-editor-row.normal {
    .input-group-append.rounded-bottom-0 .input-group-text {
        border-bottom-left-radius: 0 !important;
        border-bottom-right-radius: 0 !important;
    }
}
</style>
