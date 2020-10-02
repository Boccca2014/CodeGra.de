import axios, { AxiosResponse } from 'axios';
import * as utils from '@/utils';

type ValueOf<T> = T[keyof T];

export enum UIPreference {
    RubricEditorV2 = 'rubric_editor_v2',
}
export type UIPreferenceName = ValueOf<UIPreference>;

export async function getUIPreferences(): Promise<
    AxiosResponse<Record<UIPreference, utils.Maybe<boolean>>>
> {
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
