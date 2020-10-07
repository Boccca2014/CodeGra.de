import axios from 'axios';
import * as utils from '@/utils';
import * as types from '@/types';
import * as models from '@/models';

export async function getUIPreferences(): Promise<types.APIResponse<models.UIPreferenceMap>> {
    const res = await axios.get('/api/v1/settings/ui_preferences/');
    res.data = utils.mapObject(res.data, utils.Maybe.fromNullable);
    return res;
}

export function patchUIPreference(
    name: models.UIPreference,
    value: boolean,
): Promise<types.APIResponse<null>> {
    return axios.patch('/api/v1/settings/ui_preferences/', { name, value });
}
