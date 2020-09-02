import * as models from '@/models';
import axios, { AxiosResponse } from 'axios';

interface PeerFeedbackConnection {
    subject: models.UserServerData;
    peer: models.UserServerData;
}

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
