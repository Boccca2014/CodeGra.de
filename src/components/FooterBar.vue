<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
    <footer class="footer">
        <small>
            &copy; {{ new Date().getFullYear() }} -
            CodeGrade (<a href="https://docs.codegra.de/about/changelog.html" target="_blank">{{ version }}</a>) -
            <a href="https://codegra.de/about" target="_blank">Made with ❤️ &amp; 🍺 </a> -
            <a :href="`mailto:${email}`">{{ email }}</a> -
            <a class="privacy-statement" @click="showModal = !showModal">Privacy statement</a> -
            <a :href="documentationLink" target="_blank">Help</a>
        </small>
        <b-modal id="privacyModal"
                 v-model="showModal"
                 :hide-footer="true">
            <privacy-note/>
        </b-modal>
    </footer>
</template>

<script>
import { mapGetters } from 'vuex';
import PrivacyNote from './PrivacyNote';

export default {
    name: 'footer-bar',

    data() {
        return {
            showModal: false,
        };
    },

    computed: {
        ...mapGetters('assignments', ['getAssignment']),
        ...mapGetters('siteSettings', ['getSetting', 'releaseInfo']),

        isStudent() {
            const assigId = this.$route.params.assignmentId;

            return this.getAssignment(assigId).mapOrDefault(
                a => a.course.isStudent, false,
            );
        },

        documentationLink() {
            if (this.isStudent) {
                return 'https://docs.codegra.de/guides/use-codegrade-as-a-student.html';
            } else {
                return `https://docs.codegra.de/?v=${this.version}`;
            }
        },

        email() {
            return this.getSetting('SITE_EMAIL');
        },

        version() {
            return this.releaseInfo.map(r => r.version || `#${r.commit.substring(0, 7)}`).orDefault('…');
        },
    },

    components: {
        PrivacyNote,
    },
};
</script>

<style lang="less" scoped>
@import '~mixins.less';

.footer {
    width: 100%;
    padding: 20px;

    /* Vertically center the text there */
    line-height: 100%;
    text-align: center;

    .default-footer-colors;

    a {
        .default-link-colors;
        cursor: pointer;

        &,
        &:hover {
            text-decoration: underline;
        }
    }
}
</style>

<style lang="less">
#privacyModal .modal-dialog.modal-md {
    max-width: 786px;
}
</style>
