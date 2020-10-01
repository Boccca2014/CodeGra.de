/* SPDX-License-Identifier: AGPL-3.0-only */
import axios, { AxiosResponse } from 'axios';
import { buildUrl } from '@/utils';
import { LTI1p3Capabilities, LTI1p3ProviderName, LTI1p1ProviderTag } from '@/lti_providers';

/* eslint-disable camelcase */
type BaseLTIProviderServerData = {
    id: string;
    created_at: string;
    intended_use: string;
};

type BaseLTI1p1ProviderServerData = BaseLTIProviderServerData & {
    version: 'lti1.1';
    lms: LTI1p1ProviderTag;
};

export type NonFinalizedLTI1p1ProviderServerData = BaseLTI1p1ProviderServerData & {
    finalized: false;
    edit_secret: string;
    lms_consumer_secret: string;
    lms_consumer_key: string;
};

type FinalizedLTI1p1ProviderServerData = BaseLTI1p1ProviderServerData & {
    finalized: true;
};

type BaseLTI1p3ProviderServerData = BaseLTIProviderServerData & {
    capabilities: LTI1p3Capabilities;
    iss: string | null;
    lms: LTI1p3ProviderName;
    version: 'lti1.3';
};

export type NonFinalizedLTI1p3ProviderServerData = BaseLTI1p3ProviderServerData & {
    finalized: false;
    auth_login_url: string | null;
    auth_token_url: string | null;
    client_id: string | null;
    key_set_url: string | null;
    custom_fields: Record<string, string>;
    public_jwk: Record<string, string>;
    edit_key: string | null;
    edit_secret: string | null;
    public_key: string;
    auth_audience: string | null;
};

type FinalizedLTI1p3ProviderServerData = BaseLTI1p3ProviderServerData & {
    finalized: true;
    edit_secret: null;
};
/* eslint-enable camelcase */

export type LTI1p1ProviderServerData =
    | FinalizedLTI1p1ProviderServerData
    | NonFinalizedLTI1p1ProviderServerData;

export type LTI1p3ProviderServerData =
    | FinalizedLTI1p3ProviderServerData
    | NonFinalizedLTI1p3ProviderServerData;

export type LTIProviderServerData = LTI1p3ProviderServerData | LTI1p1ProviderServerData;

export function getLtiProvider(
    ltiProviderId: string,
    secret: string | null,
): Promise<AxiosResponse<LTIProviderServerData>> {
    const query: Record<string, string> = {};
    if (secret != null) {
        query.secret = secret;
    }

    return axios.get(buildUrl(['api', 'v1', 'lti', 'providers', ltiProviderId], { query }));
}

export function getLti1p3Provider(
    ltiProviderId: string,
    secret: string | null,
): Promise<AxiosResponse<LTI1p3ProviderServerData>> {
    const query: Record<string, string> = {};
    if (secret != null) {
        query.secret = secret;
    }

    return axios.get(buildUrl(['api', 'v1', 'lti1.3', 'providers', ltiProviderId], { query }));
}

export function getAllLtiProviders(): Promise<AxiosResponse<LTIProviderServerData[]>> {
    return axios.get('/api/v1/lti/providers/');
}

export function updateLti1p3Provider(
    ltiProvider: NonFinalizedLTI1p3ProviderServerData,
    secret: string | null,
    updatedData: {
        /* eslint-disable camelcase */
        client_id?: string;
        auth_token_url?: string;
        auth_login_url?: string;
        key_set_url?: string;
        finalize?: boolean;
        auth_audience?: string;
        iss?: string;
        /* eslint-enable camelcase */
    },
): Promise<AxiosResponse<LTI1p3ProviderServerData>> {
    const query: Record<string, string> = {};
    if (secret != null) {
        query.secret = secret;
    }

    return axios.patch(
        buildUrl(['api', 'v1', 'lti1.3', 'providers', ltiProvider.id], { query }),
        updatedData,
    );
}

export function finalizeLti1p1Provider(
    ltiProvider: NonFinalizedLTI1p1ProviderServerData,
    secret: string,
): Promise<AxiosResponse<FinalizedLTI1p1ProviderServerData>> {
    return axios.post(
        buildUrl(['api', 'v1', 'lti1.1', 'providers', ltiProvider.id, 'finalize'], {
            query: { secret },
        }),
    );
}
