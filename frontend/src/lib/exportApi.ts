export const jsonBody = (value: unknown): Pick<RequestInit, "method" | "body"> => ({
    method: "POST",
    body: JSON.stringify(value),
});

export class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
        super(message);
        this.status = status;
    }
}