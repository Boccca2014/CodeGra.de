import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';

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
        return <comp.PreferredUI prefName="rubric_editor_v2">
            <template slot="ifUnset">
                {utils.ifExpr(
                    props.editable,
                    () => <p>
                        This is the new rubric editor! The new editor supports:

                        <ul>
                            <li>
                                A better overview of the categories and the
                                points that can be achieved per category.
                            </li>
                            <li>
                                Editing multiple categories at the same time.
                            </li>
                            <li>Reordering rubric categories.</li>
                            <li>Previewing markdown descriptions.</li>
                        </ul>
                    </p>,
                    () => <p>
                        This is the new rubric interface! The new interface gives
                        a better overview of the rubric categories and the points
                        that can be achieved per category.
                    </p>,
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
