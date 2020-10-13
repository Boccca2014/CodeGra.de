import axios, { AxiosResponse } from 'axios';
import * as utils from '@/utils';
import * as models from '@/models';

export async function getUIPreferences(): Promise<models.UIPreferenceMap> {
    const res: AxiosResponse<Record<models.UIPreference, null | boolean>> = await axios.get(
        '/api/v1/settings/ui_preferences/',
    );
    return utils.mapObject(res.data, val => utils.Just(utils.Maybe.fromNullable(val)));
}

export async function patchUIPreference(name: models.UIPreference, value: boolean): Promise<void> {
    await axios.patch('/api/v1/settings/ui_preferences/', { name, value });
}
