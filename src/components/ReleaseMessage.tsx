/* SPDX-License-Identifier: AGPL-3.0-only */
import * as tsx from 'vue-tsx-support';
import { VNode } from 'vue';
import * as moment from 'moment';

import { UIPrefsStore, SiteSettingsStore } from '@/store';
import * as utils from '@/utils';

export default tsx.component({
    functional: true,

    render(h, ctx): VNode {
        const maxTime = moment.duration(
            SiteSettingsStore.getSetting()('RELEASE_MESSAGE_MAX_TIME'),
            'seconds',
        );

        return utils.ifJustOrEmpty(
            SiteSettingsStore.releaseInfo()
                .chain(release => (release.version == null ? utils.Nothing : utils.Just(release)))
                .chain(
                    utils.Maybe.fromPredicate(
                        release =>
                            ctx.parent.$root.$now.diff(release.date, 's') < maxTime.asSeconds(),
                    ),
                )
                .chain(release =>
                    UIPrefsStore.getUIPref()(release.uiPreference)
                        .ifNothing(() =>
                            UIPrefsStore.loadUIPreference({ preference: release.uiPreference }),
                        )
                        .chain(hide => {
                            // If ``hide`` is ``Nothing`` it means that we have not
                            // yet set a preference, so we want to show the message in
                            // this case.
                            const shouldShow = hide.orDefault(false);
                            if (shouldShow) {
                                return utils.Nothing;
                            }
                            return utils.Just(release);
                        }),
                ),
            release => {
                const onAlertDismissed = () => {
                    UIPrefsStore.patchUIPreference({ name: release.uiPreference, value: true });
                };

                return (
                    <b-alert show={true} dismissible={true} onDismissed={onAlertDismissed}>
                        A new version of CodeGrade has been released: <b>{release.version}</b>.{' '}
                        {release.message} You can check the entire changelog{' '}
                        <a
                            href="https://docs.codegra.de/about/changelog.html"
                            target="_blank"
                            class="alert-link"
                        >
                            here
                        </a>
                        .
                    </b-alert>
                );
            },
        );
    },
});
