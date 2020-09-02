import * as models from '@/models';

export interface GraderServerData {
    id: number;
    name: string;
    weight: number;
    done: boolean;
}

export type Graders = ReadonlyArray<Grader>;

export class Grader {
    static fromServerData(props: { userId: number; weight: number; done: boolean }) {
        const { userId, weight, done } = props;
        return new Grader(userId, weight, done);
    }

    constructor(
        public readonly userId: number,
        public readonly weight: number,
        public readonly done: boolean,
    ) {
        Object.freeze(this);
    }

    get user() {
        return models.User.findUserById(this.userId);
    }

    setStatus(value: boolean) {
        return new Grader(this.userId, this.weight, value);
    }
}
