import * as models from '@/models';
import axios, { AxiosResponse } from 'axios';

export function getFeedbacks(
    submissionId: number,
): Promise<AxiosResponse<models.FeedbackServerData>> {
    return axios.get(`/api/v1/submissions/${submissionId}/feedbacks/?with_replies`);
}

export function update(
    submissionId: number,
    payload: { feedback: string },
): Promise<AxiosResponse> {
    return axios.patch(`/api/v1/submissions/${submissionId}`, {
        feedback: payload.feedback,
    });
}
