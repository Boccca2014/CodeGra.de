import axios, { AxiosResponse } from 'axios';
import * as utils from '@/utils';

export enum UIPreference {
    RubricEditorV2 = 'rubric_editor_v2',
}

export type UIPreferenceMap = Record<UIPreference, utils.Maybe<boolean>>;

export async function getUIPreferences(): Promise<AxiosResponse<UIPreferenceMap>> {
    const res = await axios.get('/api/v1/settings/ui_preferences/');
    res.data = utils.mapObject(res.data, utils.Maybe.fromNullable);
    return res;
}

export function patchUIPreference(
    name: UIPreference,
    value: boolean,
): Promise<AxiosResponse<null>> {
    return axios.patch('/api/v1/settings/ui_preferences/', { name, value });
}
