import * as utils from '@/utils';
import { keys } from 'ts-transformer-keys';
import { mapToObject, Nothing } from '@/utils';

export enum UIPreference {
    RubricEditorV2 = 'rubric_editor_v2',

    HideReleaseMessageMosaic1 = 'no_msg_for_mosaic_1',
    HideReleaseMessageMosaic2 = 'no_msg_for_mosaic_2',
}

export type UIPreferenceMap = Record<UIPreference, utils.Maybe<utils.Maybe<boolean>>>;

const MutableDefaultUIPreferenceMap: UIPreferenceMap = mapToObject(
    keys<UIPreferenceMap>(),
    key => [key, Nothing] as const,
);
export const DefaultUIPreferenceMap: Readonly<UIPreferenceMap> = Object.freeze(
    MutableDefaultUIPreferenceMap,
);
