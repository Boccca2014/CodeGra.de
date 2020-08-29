import * as models from '@/models';
import axios, { AxiosResponse } from 'axios';
import { buildUrl } from '@/utils';

interface PeerFeedbackConnection {
    subject: models.UserServerData;
    peer: models.UserServerData;
}

/* eslint-disable camelcase */
interface PatchablePropsBase {
    state?: 'hidden' | 'open' | 'done';
    name?: string;
    deadline?: string;
    max_grade?: number | null;
    group_set_id?: number | null;
    available_at?: string | null;
    send_login_links?: boolean;
    kind?: models.AssignmentKind;

    files_upload_enabled?: boolean;
    webhook_upload_enabled?: boolean;

    max_submissions?: number | null;
    cool_off_period?: number;
    amount_in_cool_off_period?: number;
}

type PatchagePropsWithCGIgnore = PatchablePropsBase & {
    ignore: any;
    ignore_verison: 'IgnoreFilterManager' | 'EmptySubmissionFilter' | 'SubmissionValidator';
};

export type PatchableProps = PatchablePropsBase | PatchagePropsWithCGIgnore;
/* eslint-enable camelcase */

export function getPeerFeedbackSubjects(
    assignmentId: number,
    userId: number,
): Promise<AxiosResponse<PeerFeedbackConnection[]>> {
    return axios.get(`/api/v1/assignments/${assignmentId}/users/${userId}/peer_feedback_subjects/`);
}

export function getCommentsByUser(
    assignmentId: number,
    userId: number,
): Promise<AxiosResponse<models.FeedbackLineServerData[]>> {
    return axios.get(`/api/v1/assignments/${assignmentId}/users/${userId}/comments/`);
}

export function getGraders(
    assignmentId: number,
): Promise<AxiosResponse<models.GraderServerData[]>> {
    return axios.get(`/api/v1/assignments/${assignmentId}/graders/`);
}

export function patch(
    assignmentId: number,
    props: PatchableProps,
): Promise<AxiosResponse<models.AssignmentServerProps>> {
    const url = buildUrl(['api', 'v1', 'assignments', assignmentId], {
        query: { no_course_in_assignment: true },
    });
    return axios.patch(url, props);
}

export async function getCourse(assignmentId: number) {
    const response: AxiosResponse<models.CourseExtendedServerData> = await axios.get(
        buildUrl(['api', 'v1', 'assignments', assignmentId, 'course'], {
            query: {
                extended: true,
                no_course_in_assignment: true,
            },
        }),
    );
    return response.data;
}
