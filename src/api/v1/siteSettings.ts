import axios, { AxiosResponse } from 'axios';
import { FrontendOptions } from '@/models';

export async function getAll(): Promise<FrontendOptions> {
    const response: AxiosResponse<FrontendOptions> = await axios.get('/api/v1/site_settings/');
    return response.data;
}
