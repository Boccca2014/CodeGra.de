<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="advanced-collapse">
    <div class="collapse-toggle d-flex flex-row justify-content-between"
         v-b-toggle="id">
        <div class="align-self-center text-muted font-italic">
            <icon name="caret-down" class="caret mr-2" />
            {{ name }}
        </div>

        <slot name="toggle" />
    </div>

    <b-collapse :id="id"
                class="advanced-collapse-inner"
                v-model="state">
        <div class="pt-2">
            <slot />
        </div>
    </b-collapse>
</div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/caret-down';

export default {
    name: 'advanced-collapse',

    props: {
        name: {
            type: String,
            default: 'Advanced options',
        },

        startOpen: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            id: `${this.$utils.getUniqueId()}`,
            state: this.startOpen,
        };
    },

    components: {
        Icon,
    },
};
</script>

<style lang="less">
.collapse-toggle {
    cursor: pointer;

    .fa-icon.caret {
        transform: translateY(-2px);
        transition: transform 250ms linear;
    }

    .x-collapsing .handle .fa-icon.caret,
    .x-collapsed .handle .fa-icon.caret,
    &.collapsed .fa-icon.caret {
        transform: translateY(-2px) rotate(-90deg);
    }
}
</style>
