import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';

const LabelledHr = tsx.component({
    functional: true,

    props: {
        label: p(String).required,
    },

    render(h, ctx) {
        const { props } = ctx;

        const hrStyle = {
            position: 'relative',
        };

        const labelStyle = {
            position: 'absolute',
            backgroundColor: 'white',
            transform: 'translateY(-50%)',
        };

        return <hr style={hrStyle}>
            <small class="pr-2 d-inline-block text-muted font-italic"
                   style={labelStyle}>
                {props.label}
            </small>
        </hr>;
    },
});

export default LabelledHr;
