export type User = { id: number; email: string };

export type Discussion = {
    id: number;
    title: string;
    created_at: string;
    updated_at: string;
};

export type Message = {
    id: number;
    discussion_id: number;
    role: "user" | "assistant";
    content: string;
    created_at: string;
};

export type PressReview = {
    id: number;
    discussion_id: number;
    title: string;
    content: string;
    created_at: string;
};