(() => {
    "use strict";

    class ApiError extends Error {
        constructor(message, status, payload) {
            super(message);
            this.name = "ApiError";
            this.status = status;
            this.payload = payload;
        }
    }

    const request = async (url, options = {}) => {
        const response = await fetch(url, options);
        const payload = await response.json().catch(() => ({}));
        const serverError = payload && typeof payload === "object"
            ? payload.error
            : null;
        if (!response.ok || serverError) {
            throw new ApiError(
                serverError || `HTTP ${response.status}`,
                response.status,
                payload
            );
        }
        return payload;
    };

    const json = (url, { body, headers, ...options } = {}) => request(url, {
        ...options,
        headers: { "Content-Type": "application/json", ...headers },
        body: body === undefined ? undefined : JSON.stringify(body),
    });

    const eventStream = async function* (url, options = {}) {
        const response = await fetch(url, {
            ...options,
            headers: { Accept: "text/event-stream", ...options.headers },
        });
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new ApiError(
                payload.error || `HTTP ${response.status}`,
                response.status,
                payload
            );
        }
        if (!response.body) {
            throw new Error("Streaming is not supported by this browser.");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        const parseBlock = (block) => {
            const data = block
                .split(/\r?\n/)
                .filter((line) => line.startsWith("data:"))
                .map((line) => line.slice(5).trimStart())
                .join("\n");
            if (!data) return null;
            try {
                return JSON.parse(data);
            } catch (error) {
                throw new Error("The server returned an invalid stream event.");
            }
        };

        while (true) {
            const { done, value } = await reader.read();
            buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
            const blocks = buffer.split(/\r?\n\r?\n/);
            buffer = blocks.pop() || "";
            for (const block of blocks) {
                const event = parseBlock(block);
                if (event !== null) yield event;
            }
            if (done) break;
        }
        if (buffer.trim()) {
            const event = parseBlock(buffer);
            if (event !== null) yield event;
        }
    };

    window.CairnmarkApi = Object.freeze({ ApiError, eventStream, json, request });
})();
