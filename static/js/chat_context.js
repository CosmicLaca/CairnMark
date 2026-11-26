(() => {
    "use strict";

    class ChatContextState {
        constructor(messages = []) {
            this.messages = Array.isArray(messages) ? messages.slice() : [];
            this.maxTokens = null;
        }

        add(message) {
            this.messages.push(message || {});
        }

        removeLast() {
            return this.messages.pop();
        }

        clear() {
            this.messages.length = 0;
        }

        replace(messages) {
            this.clear();
            (messages || []).forEach((message) => this.add(message));
        }

        setMaxTokens(value) {
            const parsed = Number(value);
            this.maxTokens = Number.isFinite(parsed) && parsed > 0 ? parsed : null;
        }

        selected({ allPrevious = false, historyLimit = "" } = {}) {
            const lastCompacted = this.messages.findLastIndex(
                (message) => Boolean(message && message.compacted)
            );
            const active = lastCompacted >= 0
                ? this.messages.slice(lastCompacted)
                : this.messages.slice();
            const rawLimit = String(historyLimit ?? "").trim();
            const limit = rawLimit ? Number.parseInt(rawLimit, 10) : Number.NaN;
            if (allPrevious || !Number.isFinite(limit) || limit < 0) return active;
            if (active.length === 0 || limit <= 0) return [];
            return active.slice(Math.max(0, active.length - (limit * 2)));
        }

        usage(selection) {
            const used = this.selected(selection).reduce(
                (total, message) => total
                    + (Number(message && message.input_tokens) || 0)
                    + (Number(message && message.output_tokens) || 0),
                0
            );
            const ratio = this.maxTokens ? used / this.maxTokens : null;
            return {
                used,
                max: this.maxTokens,
                ratio,
                percent: ratio === null ? null : Math.round(ratio * 100),
            };
        }

        canCompact(selection) {
            const rawLimit = String(selection?.historyLimit ?? "").trim();
            const limit = rawLimit ? Number.parseInt(rawLimit, 10) : 0;
            const hasHistory = Boolean(selection?.allPrevious)
                || (Number.isFinite(limit) && limit > 0);
            const { ratio } = this.usage(selection);
            const last = this.messages[this.messages.length - 1];
            return this.messages.length > 0
                && hasHistory
                && !(ratio !== null && ratio > 1)
                && !Boolean(last && last.compacted)
                && (this.messages.length > 1 || (ratio !== null && ratio < 1));
        }

        shouldAutoCompact(selection, enabled, requestActive, threshold = 75) {
            const { ratio } = this.usage(selection);
            const triggerRatio = Number(threshold) / 100;
            return Boolean(enabled)
                && !requestActive
                && ratio !== null
                && Number.isFinite(triggerRatio)
                && ratio > triggerRatio;
        }
    }

    window.CairnmarkChatContextState = ChatContextState;
})();
