(() => {
    "use strict";

    class ChatAttachmentPreferences {
        constructor({ api, initial = {}, controls = {}, onError = () => {} }) {
            this.api = api;
            this.controls = controls;
            this.onError = onError;
            this.state = {
                save_original_media: Boolean(initial.save_original_media),
                attach_audio: Boolean(initial.attach_audio),
            };
            Object.keys(this.state).forEach((name) => {
                this.render(name);
                this.controls[name]?.addEventListener("click", () => {
                    this.set(name, !this.get(name), true);
                });
            });
        }

        get(name) {
            return Boolean(this.state[name]);
        }

        set(name, enabled, persist = false) {
            if (!(name in this.state)) return;
            this.state[name] = Boolean(enabled);
            this.render(name);
            if (persist) {
                this.api.json("/chat/save_attachment_settings", {
                    method: "POST",
                    body: { [name]: this.state[name] },
                }).catch(this.onError);
            }
        }

        render(name) {
            this.controls[name]?.setAttribute(
                "aria-checked",
                this.state[name] ? "true" : "false"
            );
        }
    }

    window.CairnmarkChatAttachmentPreferences = ChatAttachmentPreferences;
})();
