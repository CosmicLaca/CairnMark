(() => {
    "use strict";

    const button = document.querySelector("[data-application-update]");
    if (!button) return;

    const label = button.querySelector("[data-update-label]");
    const updateUrl = button.dataset.updateUrl;
    const statusUrl = button.dataset.updateStatusUrl;

    const readJson = async (response) => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.error || `Update request failed (${response.status}).`);
        }
        return payload;
    };

    const waitForRestart = async () => {
        const deadline = Date.now() + 120000;
        while (Date.now() < deadline) {
            await new Promise((resolve) => setTimeout(resolve, 1500));
            try {
                const response = await fetch(statusUrl, {
                    headers: { Accept: "application/json" },
                    cache: "no-store",
                });
                const status = await readJson(response);
                if (status.update_in_progress) continue;
                if (status.last_error) throw new Error(status.last_error);
                if (!status.update_available) {
                    window.location.reload();
                    return;
                }
            } catch (error) {
                // Connection failures are expected while the server restarts.
                if (error instanceof TypeError) continue;
                window.alert(`CairnMark update failed: ${error.message || error}`);
                button.disabled = false;
                button.classList.remove("is-updating");
                if (label) label.textContent = "Update";
                return;
            }
        }
        window.alert(
            "The update did not finish within two minutes. Check instance/application-update.log."
        );
        button.disabled = false;
        button.classList.remove("is-updating");
        if (label) label.textContent = "Update";
    };

    button.addEventListener("click", async () => {
        const confirmed = window.confirm(
            "Update CairnMark now? The local server will restart automatically."
        );
        if (!confirmed) return;

        button.disabled = true;
        button.classList.add("is-updating");
        if (label) label.textContent = "Updating";
        try {
            const response = await fetch(updateUrl, {
                method: "POST",
                headers: { Accept: "application/json" },
            });
            await readJson(response);
            await waitForRestart();
        } catch (error) {
            window.alert(`CairnMark update could not start: ${error.message || error}`);
            button.disabled = false;
            button.classList.remove("is-updating");
            if (label) label.textContent = "Update";
        }
    });
})();
