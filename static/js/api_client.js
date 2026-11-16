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

    window.CairnmarkApi = Object.freeze({ ApiError, json, request });
})();
