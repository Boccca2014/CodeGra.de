import axios from 'axios';

export class TaskResult {
    constructor(private readonly id: number) {
        Object.freeze(this);
    }

    poll(waitTime = 5000): { promise: Promise<unknown>; stop: () => void } {
        let stop = false;

        const promise = new Promise((resolve, reject) => {
            const poll = async () => {
                let response;
                try {
                    response = await axios.get(`/api/v1/task_results/${this.id}`);
                } catch (e) {
                    reject(e);
                    return;
                }
                const state = response.data.state;

                if (state === 'finished' || stop) {
                    resolve(response);
                } else if (state === 'crashed' || state === 'failed') {
                    // eslint-disable-next-line
                    reject({ response: { data: response.data.result } });
                } else {
                    setTimeout(() => {
                        poll();
                    }, waitTime);
                }
            };

            poll();
        });

        return {
            promise,
            stop: () => {
                stop = true;
            },
        };
    }
}
