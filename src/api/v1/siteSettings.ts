import axios, { AxiosResponse } from 'axios';
import { FrontendSiteSettings, SiteSettings } from '@/models';

export async function getAll(): Promise<FrontendSiteSettings | SiteSettings> {
    const response: AxiosResponse<FrontendSiteSettings | SiteSettings> = await axios.get(
        '/api/v1/site_settings/',
    );
    return response.data;
}
