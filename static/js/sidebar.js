(() => {
    "use strict";

    const STORAGE_KEY = "cairnmark.sidebar.v1";
    const DEFAULT_WIDTH = 292;
    const MIN_WIDTH = 232;
    const MAX_WIDTH = 440;
    const body = document.body;
    const toggle = document.getElementById("sidebar-toggle");
    const resizer = document.getElementById("sidebar-resizer");
    const widthReadout = document.getElementById("width-readout");

    if (!toggle || !resizer || !widthReadout) {
        return;
    }

    const maximumWidth = () =>
        Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, window.innerWidth - 200));

    const clampWidth = (width) =>
        Math.round(Math.min(maximumWidth(), Math.max(MIN_WIDTH, width)));

    const readState = () => {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
        } catch (_error) {
            return {};
        }
    };

    const savedState = readState();
    let expandedWidth = clampWidth(Number(savedState.width) || DEFAULT_WIDTH);
    let collapsed =
        typeof savedState.collapsed === "boolean"
            ? savedState.collapsed
            : window.matchMedia("(max-width: 720px)").matches;

    const saveState = () => {
        try {
            localStorage.setItem(
                STORAGE_KEY,
                JSON.stringify({ collapsed, width: expandedWidth })
            );
        } catch (_error) {
            // The controls remain functional when browser storage is unavailable.
        }
    };

    const applyWidth = (width, persist = false) => {
        expandedWidth = clampWidth(width);
        document.documentElement.style.setProperty(
            "--sidebar-expanded-width",
            `${expandedWidth}px`
        );
        widthReadout.textContent = `${expandedWidth} px`;
        resizer.setAttribute("aria-valuenow", String(expandedWidth));
        resizer.setAttribute("aria-valuemax", String(maximumWidth()));
        if (persist) {
            saveState();
        }
    };

    const applyCollapsedState = (persist = false) => {
        body.classList.toggle("sidebar-collapsed", collapsed);
        toggle.setAttribute("aria-expanded", String(!collapsed));
        toggle.title = collapsed
            ? "Expand to icon and text navigation"
            : "Collapse to icon rail";
        if (persist) {
            saveState();
        }
    };

    toggle.addEventListener("click", () => {
        collapsed = !collapsed;
        applyCollapsedState(true);
    });

    let mouseResizing = false;

    resizer.addEventListener("mousedown", (event) => {
        if (event.button !== 0 || collapsed) {
            return;
        }
        mouseResizing = true;
        body.classList.add("is-resizing");
        event.preventDefault();
    });

    window.addEventListener("mousemove", (event) => {
        if (!mouseResizing) {
            return;
        }
        applyWidth(event.clientX);
    });

    window.addEventListener("mouseup", () => {
        if (!mouseResizing) {
            return;
        }
        mouseResizing = false;
        body.classList.remove("is-resizing");
        saveState();
    });

    resizer.addEventListener("pointerdown", (event) => {
        if (event.pointerType === "mouse" || collapsed) {
            return;
        }
        body.classList.add("is-resizing");
        resizer.setPointerCapture(event.pointerId);
        event.preventDefault();
    });

    resizer.addEventListener("pointermove", (event) => {
        if (
            event.pointerType === "mouse" ||
            !resizer.hasPointerCapture(event.pointerId)
        ) {
            return;
        }
        applyWidth(event.clientX);
    });

    const finishPointerResize = (event) => {
        if (
            event.pointerType === "mouse" ||
            !resizer.hasPointerCapture(event.pointerId)
        ) {
            return;
        }
        resizer.releasePointerCapture(event.pointerId);
        body.classList.remove("is-resizing");
        saveState();
    };

    resizer.addEventListener("pointerup", finishPointerResize);
    resizer.addEventListener("pointercancel", finishPointerResize);

    resizer.addEventListener("dblclick", () => {
        applyWidth(DEFAULT_WIDTH, true);
    });

    resizer.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
            return;
        }
        const direction = event.key === "ArrowRight" ? 1 : -1;
        const step = event.shiftKey ? 32 : 8;
        applyWidth(expandedWidth + direction * step, true);
        event.preventDefault();
    });

    window.addEventListener("resize", () => {
        applyWidth(expandedWidth, true);
    });

    applyWidth(expandedWidth);
    applyCollapsedState();
})();
