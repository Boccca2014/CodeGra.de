/* SPDX-License-Identifier: AGPL-3.0-only */
export const pageTitleSep = '»';
let changed = false;

export function setPageTitle(title: string = ''): void {
    changed = true;
    if (title) {
        document.title = `${title} ${pageTitleSep} CodeGrade`;
    } else {
        document.title = 'CodeGrade';
    }
}

export function resetPageTitle(): void {
    changed = false;
    setTimeout(() => {
        if (!changed) {
            setPageTitle();
        }
    }, 500);
}
