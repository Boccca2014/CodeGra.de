// SPDX-License-Identifier: AGPL-3.0-only
const defaultLTIProvider = Object.create(null, {
    addBorder: {
        value: false,
    },
    supportsDeadline: {
        value: false,
    },
    supportsBonusPoints: {
        value: false,
    },
    supportsStateManagement: {
        value: false,
    },
});

const blackboardProvider = Object.create(defaultLTIProvider);

const brightSpaceProvider = Object.create(defaultLTIProvider);

const moodleProvider = Object.create(defaultLTIProvider);

const canvasProvider = Object.create(defaultLTIProvider, {
    addBorder: {
        value: true,
    },
    supportsDeadline: {
        value: true,
    },
    supportsBonusPoints: {
        value: true,
    },
    supportsStateManagement: {
        value: true,
    },
});

export default {
    Blackboard: blackboardProvider,
    BrightSpace: brightSpaceProvider,
    Canvas: canvasProvider,
    Moodle: moodleProvider,
};