(() => {
    "use strict";

    const wire = (container, type) => {
        if (!container || container.dataset.wired === "1") return;
        const media = container.querySelector(type);
        if (!media) return;
        container.dataset.wired = "1";
        const toggle = container.querySelector(`.chat-${type}-toggle`);
        const rewind = container.querySelector(`.chat-${type}-back`);
        const sync = () => {
            if (!toggle) return;
            toggle.textContent = media.paused ? "▶" : "⏸";
            toggle.title = media.paused ? "Play" : "Pause";
        };
        toggle?.addEventListener("click", () => {
            if (media.paused) media.play().catch(() => {});
            else media.pause();
        });
        rewind?.addEventListener("click", () => { media.currentTime = 0; });
        media.addEventListener("play", sync);
        media.addEventListener("pause", sync);
        media.addEventListener("ended", () => {
            media.currentTime = 0;
            sync();
        });
        sync();
    };

    const createAudio = (src, name = "", compact = true, { preload = "metadata" } = {}) => {
        const player = document.createElement("div");
        player.className = compact
            ? "chat-audio-player chat-audio-player--compact"
            : "chat-audio-player";
        player.innerHTML = `
            <audio hidden></audio>
            <button type="button" class="chat-audio-toggle" title="Play">▶</button>
            <button type="button" class="chat-audio-back" title="Rewind to beginning">⏪</button>
        `;
        const audio = player.querySelector("audio");
        audio.preload = preload;
        audio.src = src;
        if (name) {
            const label = document.createElement("span");
            label.className = "chat-attachment-name";
            label.textContent = name;
            label.title = name;
            player.appendChild(label);
        }
        wire(player, "audio");
        return player;
    };

    window.CairnmarkChatMedia = Object.freeze({ wire, createAudio });
})();
