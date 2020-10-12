import { AxiosError, AxiosResponse } from 'axios';

export type APIResponse<T> = AxiosResponse<T> & {
    onSuccess?: (res: AxiosResponse<T>) => any;
    onAfterSuccess?: (res: AxiosResponse<T>) => any;
    onError?: (err: AxiosError<T>) => any;
    onAfterError?: (err: AxiosError<T>) => any;
};

const validVariants = Object.freeze({
    primary: true,
    secondary: true,
    light: true,
    dark: true,
    info: true,
    success: true,
    danger: true,
    warning: true,
} as const);

export type Variant = keyof typeof validVariants;

export function isVariant(obj: any): obj is Variant {
    return typeof obj === 'string' && Object.prototype.hasOwnProperty.call(validVariants, obj);
}
