/* SPDX-License-Identifier: AGPL-3.0-only */
import { CreateElement, VNode } from 'vue';
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';

import * as utils from '@/utils';

import { CodeQualityWrapper } from '@/code_quality_wrappers';

interface SelectedWrapper {
    wrapper?: CodeQualityWrapper;
    program: string;
    args: string,
}

const inputToString = (value: string | number | string[] | undefined) => {
    if (value == undefined) {
        return '';
    } else if (typeof value === 'number') {
        return value.toString(10);
    } else if (Array.isArray(value)) {
        return value.join('\n');
    } else {
        return value;
    }
}

export default tsx.component({
    name: 'code-quality-program-selector',
    functional: true,

    props: {
        wrapper: p.ofType<CodeQualityWrapper | undefined>().required,
        program: p(String).required,
        args: p(String).required,
    },

    render(h, { props, listeners }) {
        const inputHandlers = utils.ensureArray(listeners.input) || [() => {}];

        const emit = (event: Partial<SelectedWrapper>) => {
            const data = Object.assign({
                wrapper: props.wrapper,
                program: props.program,
                args: props.args,
            }, event);

            for (let handler of inputHandlers) {
                handler(data);
            }
        };

        const updateWrapper = (wrapper: CodeQualityWrapper) => {
            emit({ wrapper });
        }

        const updateProgram = (program?: string | number | string[]) => {
            emit({ program: inputToString(program) });
        };

        const updateArgs = (args?: string | number | string[]) => {
            emit({ args: inputToString(args) });
        };

        const renderOption = (opt: CodeQualityWrapper) =>
            <b-form-select-option value={opt}>
                {opt}
            </b-form-select-option>;

        const renderSelect = (wrapper: CodeQualityWrapper | undefined) =>
            <b-form-select value={wrapper}
                           onInput={updateWrapper}>
                {Object.values(CodeQualityWrapper).map(renderOption)}
            </b-form-select>;

        const renderCustomInput = (program: string) =>
            <b-form-group label="Custom program">
                <input class="form-control"
                       placeholder="Custom program to run"
                       value={program}
                       onInput={ev => updateProgram(ev.target.value)} />
            </b-form-group>;

        const renderArgsInput = (args: string) =>
            <b-form-group label="Extra arguments">
                <input class="form-control"
                       placeholder="Extra arguments"
                       value={args}
                       onInput={ev => updateArgs(ev.target.value)} />
            </b-form-group>;

        return <div class="mb-3">
            <b-form-group label="Wrapper script">
                {renderSelect(props.wrapper)}
            </b-form-group>

            {utils.ifOrEmpty(
                props.wrapper != null,
                () => utils.ifExpr(
                    props.wrapper === CodeQualityWrapper.custom,
                    () => renderCustomInput(props.program),
                    () => renderArgsInput(props.args),
                ),
            )}
        </div>;
    },
});
