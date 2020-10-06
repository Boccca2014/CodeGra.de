import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';

import * as api from '@/api/v1';
import * as models from '@/models';
import * as utils from '@/utils';
import * as comp from '@/components';
import { store } from '@/store';
import { NONEXISTENT } from '@/constants';

// @ts-ignore
import RubricEditorV2 from './v2';
// @ts-ignore
import RubricEditorV1 from './v1';

export default tsx.component({
    name: 'rubric-editor-wrapper',

    props: {
        assignment: p.ofType<models.Assignment>().required,
        editable: p(Boolean).default(false),
        grow: p(Boolean).default(false),
    },

    computed: {
        rubric() {
            const allRubrics = store.getters['rubrics/rubrics'];
            const rubric = allRubrics[this.assignment.id];
            return rubric === NONEXISTENT ? null : rubric;
        },
    },

    render(h) {
        return <comp.PreferredUI hideSwitcher={this.rubric == null}
                                 prefName={models.UIPreference.RubricEditorV2}
                                 componentName="rubric interface">
            <template slot="ifUnset">
                {utils.ifExpr(
                    this.editable,
                    () => 'An improved version of the rubric editor is available!',
                    () => 'An improved version of the rubric overview is available!',
                )}
            </template>

            <RubricEditorV2
                slot="ifTrue"
                assignment={this.assignment}
                editable={this.editable} />

            <RubricEditorV1
                slot="ifFalse"
                assignment={this.assignment}
                editable={this.editable}
                grow={this.grow} />
        </comp.PreferredUI>
    },
});
