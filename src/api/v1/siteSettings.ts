import axios, { AxiosResponse } from 'axios';
import { SiteSettings } from '@/models';

export async function getAll(): Promise<SiteSettings> {
    const response: AxiosResponse<SiteSettings> = await axios.get('/api/v1/site_settings/');
    return response.data;
}

type PatchMap = { [K in keyof SiteSettings]: { name: K; value: SiteSettings[K] } };
export type PatchData = PatchMap[keyof PatchMap];

export async function patch(values: readonly PatchData[]): Promise<SiteSettings> {
    const response: AxiosResponse<SiteSettings> = await axios.patch(
        '/api/v1/site_settings/',
        { updates: values },
    );
    return response.data;
}
