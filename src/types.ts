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
