import * as utils from '@/utils';

export enum UIPreference {
    RubricEditorV2 = 'rubric_editor_v2',
}

export type UIPreferenceMap = Record<UIPreference, utils.Maybe<boolean>>;
