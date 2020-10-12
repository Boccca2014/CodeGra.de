import axios, { AxiosResponse } from 'axios';
import { FrontendSiteSettings } from '@/models';

export type AboutData = {
    version: unknown;
    commit: unknown;
    features: unknown;
    settings: FrontendSiteSettings;
    release: {
        date?: string;
        message?: string;
        version?: string;
        commit: string;
    };
};

export async function get(): Promise<AboutData> {
    const response: AxiosResponse<AboutData> = await axios.get('/api/v1/about');
    return response.data;
}
