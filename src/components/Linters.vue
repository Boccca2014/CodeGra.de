<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<!-- TODO: Fix issues with iterations by relying on order !-->
<div class="row justify-content-md-center linters" v-if="loading">
    <loader/>
</div>
<div v-else class="linters">
    <b-alert show variant="warning">
        Linters are now integrated with AutoTest, which allows for more
        flexibility, and you can now also assign grades based on the linter
        output. The new linters can be found under the “Code Quality” step. This
        linter tab is deprecated and will be removed at the end of 2020.
    </b-alert>

    <b-tabs no-fade
            content-class="p-3 border border-top-0 rounded-bottom">
        <b-tab :title="linter.name"
               :key="linter.id"
               v-for="linter in linters">
            <linter :name="linter.name"
                    :options="linter.opts"
                    :server-description="linter.desc"
                    :initialId="linter.id"
                    :initialState="linter.state"
                    :assignment="assignment"/>
        </b-tab>
    </b-tabs>
</div>
</template>

<script>
import Icon from 'vue-awesome/components/Icon';
import 'vue-awesome/icons/check';
import 'vue-awesome/icons/times';

import Loader from './Loader';
import Linter from './Linter';

export default {
    name: 'linters',

    props: {
        assignment: {
            type: Object,
            default: null,
        },
    },

    data() {
        return {
            linters: null,
            loading: true,
            show: {},
        };
    },

    components: {
        Loader,
        Icon,
        Linter,
    },

    mounted() {
        this.getLinters();
    },

    methods: {
        getLinters() {
            this.$http.get(`/api/v1/assignments/${this.assignment.id}/linters/`).then(data => {
                this.linters = data.data;
                this.loading = false;
            });
        },
    },
};
</script>
