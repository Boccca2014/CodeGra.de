// SPDX-License-Identifier: AGPL-3.0-only
// eslint-disable-next-line
import type { LTIProviderServerData } from '@/api/v1/lti';

import { AssertionError, mapToObject } from '@/utils/typed';

const defaultLTIProvider = Object.freeze(<const>{
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

function makeLTI1p1Provider(name: string, override: Omit<LTIProvider, 'lms'> | null = null): Readonly<LTIProvider> {
    return Object.freeze(
        Object.assign({}, defaultLTIProvider, override, { lms: name }),
    );
}

const blackboardProvider = makeLTI1p1Provider('Blackboard');

const brightSpaceProvider = makeLTI1p1Provider('Brightspace');

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
], prov => [prov.lms, prov]);

export function makeProvider(provider: LTIProviderServerData): LTIProvider {
    switch (provider.version) {
        case 'lti1.1':
            return LTI1p1Lookup[provider.lms];
        case 'lti1.3':
            return new LTI1p3ProviderCapabilties(provider.lms, provider.capabilities);
        default:
            return AssertionError.assertNever(provider);
    }
}
