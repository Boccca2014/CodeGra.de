// SPDX-License-Identifier: AGPL-3.0-only
import * as utils from '@/utils';

// eslint-disable-next-line
import type { LTIProviderServerData } from '@/api/v1/lti';

import { AssertionError, mapToObject } from '@/utils/typed';

const defaultLTI1p1Provider = Object.freeze(<const>{
    lms: 'LMS',
    addBorder: false,
    supportsDeadline: false,
    supportsBonusPoints: false,
    supportsStateManagement: false,
});
export type LTIProvider = {
    readonly lms: string;
    readonly addBorder: boolean;
    readonly supportsDeadline: boolean;
    readonly supportsBonusPoints: boolean;
    readonly supportsStateManagement: boolean;
};

type LTI1p1Provider = LTIProvider & { tag?: string };

function makeLTI1p1Provider(
    name: string,
    override: Partial<Omit<LTI1p1Provider, 'lms'>> | null = null,
): Readonly<LTI1p1Provider> {
    return Object.freeze(
        Object.assign({}, defaultLTI1p1Provider, override, { lms: name }),
    );
}

const blackboardProvider = makeLTI1p1Provider('Blackboard');

const brightSpaceProvider = makeLTI1p1Provider('Brightspace', {
    // In the backend we call Brightspace "BrightSpace" (with a capital S)
    // so we need to override the tag that is used to identify the correct
    // ltiProvider.
    tag: 'BrightSpace',
});

const moodleProvider = makeLTI1p1Provider('Moodle');

const sakaiProvider = makeLTI1p1Provider('Sakai');

const canvasProvider = makeLTI1p1Provider('Canvas', {
    addBorder: true,
    supportsDeadline: true,
    supportsBonusPoints: true,
    supportsStateManagement: true,
});

/* eslint-disable camelcase */
export const LTI1p3ProviderNames = Object.freeze(<const>[
    'Blackboard',
    'Brightspace',
    'Canvas',
    'Moodle',
]);
export type LTI1p3ProviderName = typeof LTI1p3ProviderNames[number];

export interface LTI1p3Capabilities {
    lms: LTI1p3ProviderName;
    set_deadline: boolean;
    set_state: boolean;
    test_student_name: string | null;
    cookie_post_message: string | null;
    supported_custom_replacement_groups: string[];
}
/* eslint-enable camelcase */

class LTI1p3ProviderCapabilties implements LTIProvider {
    readonly addBorder: boolean;

    readonly supportsDeadline: boolean;

    readonly supportsBonusPoints: boolean;

    readonly supportsStateManagement: boolean;

    constructor(public readonly lms: string, capabilities: LTI1p3Capabilities) {
        this.addBorder = capabilities.lms === 'Canvas';

        this.supportsDeadline = !capabilities.set_deadline;

        this.supportsBonusPoints = true;

        this.supportsStateManagement = !capabilities.set_state;
    }
}

const LTI1p1Lookup: Record<string, LTIProvider> = mapToObject([
    blackboardProvider,
    brightSpaceProvider,
    canvasProvider,
    moodleProvider,
    sakaiProvider,
], prov => [prov.tag || prov.lms, prov]);

export function makeProvider(provider: LTIProviderServerData): LTIProvider {
    switch (provider.version) {
        case 'lti1.1': {
            const prov = LTI1p1Lookup[provider.lms];
            if (prov == null) {
                utils.withSentry(Sentry => {
                    Sentry.captureMessage(`Unknown LTI provider: ${provider.lms}`);
                });
                return defaultLTI1p1Provider;
            } else {
                return prov;
            }
        }
        case 'lti1.3':
            return new LTI1p3ProviderCapabilties(provider.lms, provider.capabilities);
        default:
            return AssertionError.assertNever(provider);
    }
}
