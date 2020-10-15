/* SPDX-License-Identifier: AGPL-3.0-only */
import { VNode } from 'vue';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';
import { ansiToHTML } from '@/utils/ansi';

export default tsx.component({
    name: 'ansi-colored-text',
    functional: true,

    props: {
        text: p(String).required,
    },

    render(h, ctx): VNode {
        return <pre domPropsInnerHTML={ansiToHTML(ctx.props.text)} />;
    },
});
