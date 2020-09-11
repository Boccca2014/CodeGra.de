/* import { VNode, CreateElement } from 'vue'; */
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';

// @ts-ignore
import InnerMarkdownViewer from './InnerMarkdownViewer';

const PreviewableMarkdownEditor = tsx.component({
    props: {
        value: p(String).required,
        rows: p(Number).default(5),
        placeholder: p(String).default(''),
        tabindex: p.ofType<number | undefined>().default(undefined),
    },

    data() {
        return { preview: false };
    },

    render(h) {
        let innerViewer = this.$utils.ifExpr(
            this.preview,
            () =>
                <InnerMarkdownViewer
                    markdown={this.value}
                    class="px-3 py-2" />,
            () =>
                <textarea value={this.value}
                          class="form-control border-0"
                          rows={this.rows}
                          placeholder={this.placeholder}
                          tabindex={this.tabindex}
                          onInput={$event => this.$emit('input', $event)} />,
        );

        return <div class="border rounded">
            {innerViewer}
            <div class="border-top clearfix">
                <a href="#"
                   onClick={tsx.modifiers.prevent(() => this.preview = !this.preview)}
                   class="px-2 float-right inline-link">
                    <small>Toggle preview</small>
                </a>
            </div>
        </div>;
    },
});

export default PreviewableMarkdownEditor;
