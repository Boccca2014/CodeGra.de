import axios, { AxiosResponse } from 'axios';
import * as models from '@/models';

export type AboutData = {
    version: unknown;
    commit: unknown;
    features: unknown;
    settings: models.FrontendSiteSettings;
    release: {
        date?: string;
        message?: string;
        version?: string;
        commit: string;
        // eslint-disable-next-line camelcase
        ui_preference: models.UIPreference;
    };
};

export async function get(): Promise<AboutData> {
    const response: AxiosResponse<AboutData> = await axios.get('/api/v1/about');
    return response.data;
}
