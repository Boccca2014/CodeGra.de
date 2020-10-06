import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';

import * as api from '@/api/v1';
import * as models from '@/models';
import * as utils from '@/utils';
import * as comp from '@/components';

// @ts-ignore
import RubricEditorV2 from './v2';
// @ts-ignore
import RubricEditorV1 from './v1';

export default tsx.component({
    name: 'rubric-editor-wrapper',
    functional: true,

    props: {
        assignment: p.ofType<models.Assignment>().required,
        editable: p(Boolean).default(false),
        grow: p(Boolean).default(false),
    },

    render(h, { props }) {
        return <comp.PreferredUI prefName={models.UIPreference.RubricEditorV2}
                                 componentName="rubric interface">
            <template slot="ifUnset">
                {utils.ifExpr(
                    props.editable,
                    () => 'An improved version of the rubric editor is available!',
                    () => 'An improved version of the rubric overview is available!',
                )}
            </template>

            <RubricEditorV2
                slot="ifTrue"
                assignment={props.assignment}
                editable={props.editable} />

            <RubricEditorV1
                slot="ifFalse"
                assignment={props.assignment}
                editable={props.editable}
                grow={props.grow} />
        </comp.PreferredUI>
    },
});
