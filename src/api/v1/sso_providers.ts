import axios, { AxiosResponse } from 'axios';
import * as models from '@/models';

export async function get() {
    const response: AxiosResponse<models.Saml2ProviderServerData[]> = await axios.get(
        '/api/v1/sso_providers/',
    );
    return response.data.map(item => models.makeSSOProvider(item));
}
