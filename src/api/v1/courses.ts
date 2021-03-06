import axios, { AxiosResponse } from 'axios';
import * as models from '@/models';
import { buildUrl } from '@/utils';

export interface PatchableProps {
    name?: string;
    state?: models.CourseState;
}

export async function get(props: { limit: number; offset: number }) {
    const response: AxiosResponse<models.CourseExtendedServerData[]> = await axios.get(
        buildUrl(['api', 'v1', 'courses'], {
            query: {
                extended: true,
                no_role_name: true,
                limit: props.limit,
                offset: props.offset,
                no_course_in_assignment: true,
            },
            addTrailingSlash: true,
        }),
    );

    return response.data;
}

export async function getById(courseId: number) {
    const response: AxiosResponse<models.CourseExtendedServerData> = await axios.get(
        buildUrl(['api', 'v1', 'courses', courseId], {
            query: { extended: true, no_role_name: true, no_course_in_assignment: true },
        }),
    );

    return response.data;
}

export async function create(data: { name: string }) {
    const response: AxiosResponse<models.CourseExtendedServerData> = await axios.post(
        buildUrl(['api', 'v1', 'courses'], {
            query: { extended: true, no_role_name: true, no_course_in_assignment: true },
            addTrailingSlash: true,
        }),
        { name: data.name },
    );

    return response;
}

export async function patch(courseId: number, data: PatchableProps) {
    const response: AxiosResponse<models.CourseExtendedServerData> = await axios.patch(
        buildUrl(['api', 'v1', 'courses', courseId], {
            query: { no_course_in_assignment: true },
        }),
        data,
    );

    return response;
}
