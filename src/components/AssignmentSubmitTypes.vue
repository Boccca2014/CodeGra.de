<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<b-list-group class="assignment-submit-types">
    <b-list-group-item>
        <b-form-checkbox v-model="files">
            File uploader

            <cg-description-popover hug-text>
                Your students will be able to upload files via a file uploader.
                They can submit archives which are automatically extracted or
                regular files. If you set up hand-in requirements, the handed
                in files will be checked on these requirements.
            </cg-description-popover>
        </b-form-checkbox>
    </b-list-group-item>

    <b-list-group-item>
        <b-form-checkbox v-model="webhook">
            GitHub/GitLab

            <cg-description-popover hug-text>
                Your students will be able to hand in via a GitHub or GitLab
                webhook. Instructions on how to set this up will be shown on
                the hand in page. Hand-in requirements will be ignored on
                submissions handed in through this method.
            </cg-description-popover>
        </b-form-checkbox>
    </b-list-group-item>
</b-list-group>
</template>

<script lang="ts">
import { Vue, Component, Prop, Watch } from 'vue-property-decorator';
import { Either, Left, Right } from '@/utils';

export type AssignmentSubmitTypesValue = Either<Error, {
    files: boolean;
    webhook: boolean;
}>;

@Component({})
export default class AssignmentSubmitTypes extends Vue {
    @Prop({ required: true })
    value!: AssignmentSubmitTypesValue;

    @Prop({ default: 'assignment-submit-types' })
    inputId!: string;

    files: boolean = true;

    webhook: boolean = true;

    @Watch('value', { immediate: true })
    onValueChanged() {
        this.value.ifRight(value => {
            this.webhook = value.webhook;
            this.files = value.files;
        });
    }

    @Watch('files')
    @Watch('webhook')
    emitValue() {
        let value: AssignmentSubmitTypesValue;
        if (this.webhook || this.files) {
            value = Right({ webhook: this.webhook, files: this.files });
        } else {
            value = Left(new Error('Enable at least one way of uploading.'));
        }
        this.$emit('input', value);
    }
}
</script>
