<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-button :id="btnId"
          class="submit-button"
          :class="`state-${state} ${invertColors ? 'invert-colors border-0' : ''}`"
          :tabindex="tabindex"
          :disabled="isDisabled && !modalVisible"
          :style="{ opacity: modalVisible ? 1 : undefined }"
          :variant="currentVariant"
          :size="size"
          @click.prevent.stop="onClick">

    <span class="label success">
        <slot name="success-label">
            <icon name="check" :scale="iconScale"/>
        </slot>
    </span>
    <span class="label warning">
        <slot name="warning-label">
            <icon name="warning" :scale="iconScale"/>
        </slot>
    </span>
    <span class="label error">
        <slot name="error-label">
            <icon name="times" :scale="iconScale"/>
        </slot>
    </span>
    <span class="label pending">
        <slot name="pending-label">
            <loader :scale="iconScale"/>
        </slot>
    </span>
    <span class="label default">
        <slot>
            {{ label }}
        </slot>
    </span>

    <b-popover :id="`${btnId}-error-popover`"
               :placement="popoverPlacement"
               :show="!!error"
               v-if="!mounting"
               :container="innerContainer"
               :target="btnId"
               triggers=""
               variant="danger"
               @shown="$refs.errorPopover.focus()"
               @hidden="onHideError">
        <div class="submit-button-error"
             ref="errorPopover"
             tabindex="-1"
             style="outline: 0;"
             @blur.capture="hideError">
            <icon name="times"
                  class="hide-button"
                  @click.native="hideError"/>

            <span v-if="error">
                <slot name="error" :error="error">
                    {{ stringifiedError }}
                </slot>
            </span>
        </div>
    </b-popover>

    <b-popover :id="`${btnId}-warning-popover`"
               :placement="popoverPlacement"
               :show="!!warning"
               :container="innerContainer"
               v-if="!mounting"
               :target="btnId"
               triggers=""
               variant="warning"
               @shown="$refs.warningPopover.focus()"
               @hidden="onHideWarning">
        <div class="submit-button-warning"
             ref="warningPopover"
             tabindex="-1"
             style="outline: 0;"
             @blur.capture="hideWarning">
            <icon name="times"
                  class="hide-button"
                  @click.native="hideWarning"/>

            <span v-if="warning && warning.messages.length > 0">
                <slot name="warning" :warning="warning">
                    <template v-if="isWarningHeader(warning) && warning.messages.length > 1">
                        <ul class="p-0 text-left pl-3 m-0">
                            <li v-for="w in warning.messages">{{ w.text }}</li>
                        </ul>
                    </template>
                    <template v-else-if="isWarningHeader(warning)">
                        {{ warning.messages[0].text }}
                    </template>
                    <template v-else>
                        {{ warning.messages }}
                    </template>
                </slot>
            </span>
        </div>
    </b-popover>

    <template>
        <b-modal v-if="confirmInModal"
                 style="pointer: initial;"
                 class="submit-button-confirm-modal"
                 title="Are you sure?"
                 @hide="$nextTick(() => resetConfirm(true))"
                 :visible="confirmVisible"
                 :id="`${btnId}-modal`">
            <slot name="confirm">
                <div class="text-left text-wrap">
                    {{ confirm }}
                </div>
            </slot>

            <template slot="modal-footer">
                <div class="w-100 d-flex justify-content-between">
                    <b-btn variant="outline-danger"
                           @click="acceptConfirm">
                        Confirm
                    </b-btn>
                    <b-btn variant="primary"
                           @click="resetConfirm(true)">
                        Cancel
                    </b-btn>
                </div>
            </template>
        </b-modal>

        <b-popover v-else-if="confirm && confirm.length > 0"
                   :no-fade="duration < 100"
                   :id="`${btnId}-confirm-popover`"
                   :placement="popoverPlacement"
                   :container="innerContainer"
                   :show="confirmVisible"
                   :target="btnId"
                   triggers=""
                   @hide="resetConfirm(true)">
            <div class="submit-button-confirm text-justify">
                <slot name="confirm">
                    <p class="confirm-message">
                        {{ confirm }}
                    </p>
                </slot>

                <b-button-toolbar justify
                                  class="mt-2">
                    <b-button size="sm"
                              variant="outline-primary"
                              class="confirm-button confirm-button-accept mr-2"
                              @click="acceptConfirm">
                        Yes
                    </b-button>
                    <div class="sep"/>
                    <b-button size="sm"
                              variant="primary"
                              class="confirm-button confirm-button-reject"
                              @click="resetConfirm(true)">
                        No
                    </b-button>
                </b-button-toolbar>
            </div>
        </b-popover>
    </template>
</b-button>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/times';
import 'vue-awesome/icons/check';
import 'vue-awesome/icons/warning';

import { getErrorMessage, WarningHeader, waitAtLeast } from '@/utils';

import Loader from './Loader';

export const SubmitButtonCancelled = Object.create(Error);

export class SubmitButtonWarning {
    constructor(warning, data) {
        this.name = 'SubmitButtonWarning';
        this.warning = warning;
        this.data = data;
    }
}

let i = 0;

export default {
    name: 'submit-button',

    props: {
        label: {
            type: String,
            default: 'Submit',
        },
        submit: {
            type: Function,
            required: true,
        },
        filterSuccess: {
            type: Function,
            default: x => x,
        },
        filterError: {
            type: Function,
            default: x => {
                throw x;
            },
        },
        id: {
            type: String,
            default: null,
        },
        tabindex: {
            type: [Number, String],
            default: 0,
        },
        disabled: {
            type: Boolean,
            default: false,
        },
        size: {
            type: String,
            default: 'md',
        },
        variant: {
            type: String,
            default: 'primary',
        },
        duration: {
            type: Number,
            default: 750,
        },
        confirm: {
            type: String,
            default: '',
        },
        confirmInModal: {
            type: Boolean,
            default: false,
        },
        popoverPlacement: {
            type: String,
            default: 'top',
        },
        waitAtLeast: {
            type: Number,
            default: 250,
        },
        iconScale: {
            type: Number,
            default: 1,
        },
        container: {
            default: undefined,
        },

        invertColors: {
            type: Boolean,
            default: false,
        },
    },

    data() {
        return {
            state: 'default',
            btnId: this.id || `submit-button-${i++}`,
            mounting: true,
            error: null,
            warning: null,
            response: null,
            confirmVisible: false,
            confirmAccepted: false,
        };
    },

    mounted() {
        this.mounting = false;
    },

    computed: {
        currentVariant() {
            if (this.invertColors) {
                return 'secondary';
            }
            return {
                default: this.variant,
                pending: this.variant,
                success: 'success',
                error: 'danger',
                warning: 'warning',
            }[this.state];
        },

        stringifiedError() {
            return getErrorMessage(this.error);
        },

        modalVisible() {
            return this.state === 'pending' && this.confirmVisible && this.confirmInModal;
        },

        isDisabled() {
            return this.disabled || this.state !== 'default' || this.confirmVisible;
        },

        innerContainer() {
            if (this.container === 'self') {
                return `#${this.btnId}`;
            }
            return this.container;
        },
    },

    methods: {
        onClick() {
            if (this.isDisabled) {
                return;
            }

            if (this.confirm && this.confirm.length > 0) {
                this.showConfirm();
            } else {
                this.doSubmit();
            }
        },

        doSubmit() {
            this.state = 'pending';

            let promise = Promise.resolve().then(this.submit);
            if (this.waitAtLeast > 0) {
                promise = waitAtLeast(this.waitAtLeast, promise);
            }

            promise = promise.then(this.filterSuccess, this.filterError);
            promise.then(this.onSuccess, this.onError);
            promise.then(() => this.resetConfirm(false), () => this.resetConfirm(false));
        },

        maybeCall(data, prop) {
            if (data == null) {
                if (!this.$userConfig.isProduction) {
                    // eslint-disable-next-line
                    console.warn('A null object was returned from the :submit function');
                }
            } else if (typeof data[prop] === 'function') {
                data[prop]();
            } else if (!this.$userConfig.isProduction && Object.hasOwnProperty.call(data, prop)) {
                // eslint-disable-next-line
                console.warn(`The property ${prop} was found on ${data}, but was not a function`);
            }
        },

        onSuccess(data, fromWarning = false) {
            if (!fromWarning) {
                const dataArr = this.$utils.ensureArray(data);
                if (dataArr.some(el => el && el.headers && el.headers.warning)) {
                    this.onWarning(dataArr, data);
                    return;
                }
            }

            this.maybeCall(data, 'onSuccess');
            this.$emit('success', data);

            const done = () => {
                this.maybeCall(data, 'onAfterSuccess');
                this.$emit('after-success', data);
                this.state = 'default';
            };

            if (this.duration) {
                this.state = 'success';
                setTimeout(done, this.duration);
            } else if (this.confirm) {
                this.state = 'success';
                this.$afterRerender().then(done);
            } else {
                done();
            }
        },

        onWarning(warning, data) {
            this.maybeCall(data, 'onWarning');
            this.$emit('warning', { warning, data });
            this.state = 'warning';

            if (warning instanceof SubmitButtonWarning) {
                this.warning = warning.warning;
            } else {
                this.warning = warning.reduce(
                    (acc, w) => acc.merge(w),
                    WarningHeader.fromWarningStr(''),
                );
            }

            this.response = data;
        },

        hideWarning() {
            this.warning = null;
        },

        onHideWarning() {
            this.$emit('after-warning');
            this.state = 'default';
            this.warning = null;

            const res = this.response;
            this.response = null;
            this.onSuccess(res, true);
        },

        onError(err) {
            if (err === SubmitButtonCancelled) {
                this.maybeCall(err, 'onCancel');
                this.$emit('cancel', err);
                this.state = 'default';
                return;
            } else if (err instanceof SubmitButtonWarning) {
                this.onWarning(err, err.data);
                return;
            }

            this.maybeCall(err, 'onError');
            this.$emit('error', err);
            this.state = 'error';
            this.error = err;
        },

        hideError() {
            this.error = null;
        },

        onHideError() {
            this.$emit('after-error');
            this.state = 'default';
            this.error = null;
        },

        showConfirm() {
            this.state = 'pending';
            this.confirmVisible = true;
        },

        resetConfirm(resetState = false) {
            if (!this.confirmAccepted && this.confirmVisible && resetState) {
                this.state = 'default';
                this.$emit('reject-confirm');
            }
            this.confirmVisible = false;
            this.confirmAccepted = false;
        },

        acceptConfirm() {
            this.$emit('accept-confirm');
            this.confirmVisible = false;
            this.confirmAccepted = true;
            this.doSubmit();
        },

        isWarningHeader(warning) {
            return warning instanceof WarningHeader;
        },
    },

    components: {
        Icon,
        Loader,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins';

.submit-button {
    position: relative;
}

.label.default {
    opacity: 0;

    .state-default & {
        opacity: 1;
    }
}

.label.success,
.label.warning,
.label.error,
.label.pending {
    display: none;
    position: absolute;
    top: 50%;
    left: 50%;
    line-height: 1;
    transform: translate(-50%, -50%);
}

.state-success .label.success,
.state-warning .label.warning,
.state-error .label.error,
.state-pending .label.pending,
.state-default .label.default {
    display: initial;
}

.invert-colors .label {
    &.success .fa-icon {
        color: @color-success;
    }
    &.error .fa-icon {
        color: @color-danger;
    }
    &.warning .fa-icon {
        color: @color-warning;
    }
}

.hide-button {
    float: right;
    cursor: pointer;
    opacity: 0.75;
    margin: 0 0 0.25rem 0.5rem;

    &:hover {
        opacity: 1;
    }
}

.confirm-button {
    flex: 1 1 auto;
}
</style>

<style lang="less">
@import '~mixins.less';

.submit-button .loader {
    display: inline-block !important;
}

.submit-button .popover {
    min-width: 15rem;
    opacity: 1;
    background: unset;
}

.submit-button-confirm-modal {
    cursor: initial !important;
    pointer-events: all !important;
}
</style>
