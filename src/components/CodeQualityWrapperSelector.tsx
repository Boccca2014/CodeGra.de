/* SPDX-License-Identifier: AGPL-3.0-only */
import * as tsx from 'vue-tsx-support';
import p from 'vue-strict-prop';

import * as utils from '@/utils';

import {
    codeQualityWrappers,
    CodeQualityWrapper,
    CodeQualityWrappers,
} from '@/code_quality_wrappers';

interface SelectedWrapper {
    wrapper?: CodeQualityWrappers | undefined;
    program: string;
    args: string;
}

type Events = {
    input: SelectedWrapper;
};

const inputToString = (value: string | number | string[] | undefined) => {
    if (value === undefined) {
        return '';
    } else if (typeof value === 'number') {
        return value.toString(10);
    } else if (Array.isArray(value)) {
        return value.join('\n');
    } else {
        return value;
    }
};

export default tsx.componentFactoryOf<Events>().create({
    name: 'code-quality-program-selector',
    functional: true,

    props: {
        wrapper: p.ofType<CodeQualityWrappers | undefined>().required,
        program: p(String).required,
        args: p(String).required,
    },

    render(h, { props, listeners }) {
        const inputHandlers =
            listeners.input == null ? [() => {}] : utils.ensureArray(listeners.input);

        const emit = (event: Partial<SelectedWrapper>) => {
            const data = Object.assign(
                {
                    wrapper: props.wrapper,
                    program: props.program,
                    args: props.args,
                },
                event,
            );

            for (const handler of inputHandlers) {
                handler(data);
            }
        };

        const updateWrapper = (wrapper: CodeQualityWrappers) => {
            emit({ wrapper });
        };

        const updateProgram = (program?: string | number | string[]) => {
            emit({ program: inputToString(program) });
        };

        const updateArgs = (args?: string | number | string[]) => {
            emit({ args: inputToString(args) });
        };

        const renderOption = (opt: CodeQualityWrapper) => (
            <b-form-select-option value={opt.key}>{opt.name}</b-form-select-option>
        );

        const renderSelect = (wrapper: CodeQualityWrapper | undefined) => (
            <b-form-select value={wrapper?.key} onInput={updateWrapper}>
                {Object.values(codeQualityWrappers).map(renderOption)}
            </b-form-select>
        );

        const renderCustomInput = (program: string) => (
            <b-form-group label="Custom program">
                <input
                    class="form-control"
                    placeholder="Custom program to run"
                    value={program}
                    onInput={ev => updateProgram(ev.target.value)}
                />
            </b-form-group>
        );

        const renderArgsInput = (args: string) => (
            <b-form-group label="Extra arguments">
                <input
                    class="form-control"
                    placeholder="Extra arguments"
                    value={args}
                    onInput={ev => updateArgs(ev.target.value)}
                />
            </b-form-group>
        );

        const getSelectedWrapper = () => {
            if (props.wrapper == null) {
                return undefined;
            } else {
                return codeQualityWrappers[props.wrapper];
            }
        };

        return (
            <div class="mb-3">
                <b-form-group label="Linter">{renderSelect(getSelectedWrapper())}</b-form-group>

                {utils.ifOrEmpty(props.wrapper != null, () =>
                    utils.ifExpr(
                        props.wrapper === codeQualityWrappers.custom.name,
                        () => renderCustomInput(props.program),
                        () => renderArgsInput(props.args),
                    ),
                )}
            </div>
        );
    },
});
