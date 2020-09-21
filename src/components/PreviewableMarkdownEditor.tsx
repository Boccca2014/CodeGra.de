import { VNode, CreateElement } from 'vue';
import * as tsx from 'vue-tsx-support';
import { modifiers as m } from 'vue-tsx-support';
import p from 'vue-strict-prop';

// @ts-ignore
import InnerMarkdownViewer from './InnerMarkdownViewer';

const PreviewableMarkdownEditor = tsx.component({
    props: {
        value: p(String).required,
        rows: p(Number).default(0),
        placeholder: p(String).default(''),
        disabled: p(Boolean).default(false),
        tabindex: p.ofType<number | undefined>().default(undefined),
        hideToggle: p(Boolean).default(false),
    },

    data() {
        return { preview: false };
    },

    render(h: CreateElement) {
        const innerViewer = this.$utils.ifExpr(
            this.preview,
            () => this.$utils.ifExpr(
                !!this.value,
                () =>
                    <InnerMarkdownViewer
                        markdown={this.value}
                        class="px-3 py-2" />,
                () =>
                    <div class="empty px-3 py-2 text-muted font-italic">
                        {this.$slots.empty || 'Field is empty...'}
                    </div>,
            ),
            () =>
                <textarea
                    value={this.value}
                    class="form-control border-0"
                    rows={this.rows}
                    placeholder={this.placeholder}
                    tabindex={this.tabindex}
                    disabled={this.disabled}
                    onInput={$event => this.$emit('input', $event)}
                    onKeyup={m.ctrl.enter(() => this.$emit('submit'))} />,
        );

        let toggle = this.$utils.ifOrEmpty(
            !this.hideToggle,
            () => <div class="border-top clearfix">
                <a href="#"
                   onClick={m.prevent(() => this.preview = !this.preview)}
                   class="px-2 float-right inline-link">
                    <small>Toggle preview</small>
                </a>
            </div>,
        );

        return <div class="border rounded">
            {innerViewer}
            {toggle}
        </div>;
    },
});

export default PreviewableMarkdownEditor;
