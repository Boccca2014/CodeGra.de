import UserConfig from '@/userConfig';
import { buildUrl } from '@/utils/typed';

/* eslint-disable camelcase */
interface LogoData {
    url: string;
    height: number;
    width: number;
}
export interface Saml2ProviderServerData {
    id: string;
    metadata_url: string;
    ui_info: {
        name: string;
        description: string | null;
        logo: null | LogoData;
    };
}
/* eslint-enable camelcase */

class Saml2Provider {
    constructor(
        public readonly id: string,
        public readonly idpMetadataUrl: string,
        public readonly name: string,
        public readonly description: string | null,
        public readonly logo: LogoData | null,
    ) {
        Object.freeze(this);
    }

    static fromServerData(data: Saml2ProviderServerData) {
        return new Saml2Provider(
            data.id,
            data.metadata_url,
            data.ui_info.name,
            data.ui_info.description,
            data.ui_info.logo,
        );
    }

    get loginUrl(): string {
        return buildUrl(['api', 'sso', 'saml2', 'login', this.id], {
            baseUrl: UserConfig.externalUrl,
        });
    }

    get metadataUrl(): string {
        return buildUrl(['api', 'sso', 'saml2', 'metadata', this.id], {
            baseUrl: UserConfig.externalUrl,
        });
    }
}

export type SSOProvider = Saml2Provider;

export function makeSSOProvider(data: Saml2ProviderServerData): SSOProvider {
    return Saml2Provider.fromServerData(data);
}
