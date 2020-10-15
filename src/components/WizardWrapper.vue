<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="wizard-wrapper">
    <component :is="useLocalHeader ? 'local-header' : 'div'"
               class="d-flex mb-4">
        <slot name="header-wrapper" position="prepend" />

        <b-btn @click="gotoPrevPage"
               :style="{ opacity: (showPrevBtn ? 1 : 0), pointerEvents: (showPrevBtn ? 'all' : 'none') }"
               v-b-popover.top.hover="showPrevBtn ? 'Go to previous step.' : ''"
               class="prev-button">
            <icon name="arrow-left" />
        </b-btn>

        <div class="flex-grow d-flex justify-content-center">
            <h4 class="mx-3 my-0 align-self-center">
                <slot name="title" :page="curPage" :totalPages="totalPages" />
            </h4>
        </div>

        <div v-b-popover.top.hover="nextPageDisabledPopover || 'Go to next step'"
             :style="{ opacity: (showNextBtn ? 1 : 0), pointerEvents: (showNextBtn ? 'all' : 'none') }">
            <b-btn @click="gotoNextPage"
                   :disabled="!!nextPageDisabledPopover"
                   class="next-button">
                <icon name="arrow-right" />
            </b-btn>
        </div>

        <slot name="header-wrapper" position="append" />
    </component>

    <div class="wizard-step-wrapper">
        <slot :name="`page-${curPage}`"
              class="wizard-step"
              :next-page="gotoNextPage"
              :prev-page="gotoPrevPage"/>
    </div>
</div>
</template>

<script lang="ts">
/* TODO: Make it possible to use this component non linearly
 *
 * The wizard is now purely linear. If we want to use it more in the future it
 * will probably be nice to conditionally skip or include certain pages. But
 * we can wait with that until the need actually arises. Might be nice if we
 * could then also specify an identifier for a page other than its page
 * number, e.g. `<template slot="page-0-generate-blackboard-keys">`, so that
 * we can then do `goToPage('generate-blackboard-keys')`. Just an idea though
 * that I thought was worth mentioning.
 */

import { Vue, Component, Prop, Watch } from 'vue-property-decorator';

// @ts-ignore
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/arrow-right';
import 'vue-awesome/icons/arrow-left';

// @ts-ignore
import LocalHeader from './LocalHeader';

@Component({ components: { Icon, LocalHeader } })
export default class WizardWrapper extends Vue {
    curPage: number = 1;

    @Prop({ default: false }) useLocalHeader!: boolean;

    @Prop({ default: () => false })
    getNextPageDisabledPopover!: (currentPage: number) => string | null;

    @Prop({ default: 1 }) value!: number;

    @Watch('value', { immediate: true })
    onValueChange() {
        this.curPage = this.value;
    }

    @Watch('curPage')
    onCurPageChange() {
        this.$emit('input', this.curPage);
    }

    get totalPages(): number {
        const res = Object.keys(this.$scopedSlots).reduce((acc, item) => {
            if (item === 'title' || item === 'header-wrapper') {
                return acc;
            } else if (!item.startsWith('page')) {
                // eslint-disable-next-line
                console.warn('Wrong named slot found');
                return acc;
            } else {
                return acc + 1;
            }
        }, 0);

        if (!this.$isProduction) {
            for (let i = 1; i <= res; ++i) {
                this.$utils.AssertionError.assert(
                    this.$utils.hasAttr(this.$scopedSlots, `page-${i}`),
                    `Could not find slot for page ${i}`,
                );
            }
        }

        return res;
    }

    get showPrevBtn(): boolean {
        return this.curPage > 1;
    }

    get showNextBtn(): boolean {
        return this.curPage < this.totalPages;
    }

    get nextPageDisabledPopover() {
        return this.getNextPageDisabledPopover(this.curPage);
    }

    gotoPrevPage() {
        if (this.showPrevBtn) {
            this.curPage--;
        }
    }

    gotoNextPage() {
        if (this.showNextBtn && !this.nextPageDisabledPopover) {
            this.curPage++;
        }
    }
}
</script>

<style lang="less" scoped>
.wizard-step-wrapper {
    margin: 0 auto;
    max-width: 45rem;
}
</style>
