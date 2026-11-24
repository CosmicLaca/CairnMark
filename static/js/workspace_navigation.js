(() => {
    "use strict";

    const NAVIGATION_SELECTOR = ".sidebar-nav .menu-item";
    const PERSISTENT_ATTRIBUTE = "data-navigation-persist";
    const prefetchedPages = new Map();
    let navigationController = null;

    const sameDocumentUrl = (left, right) =>
        left.origin === right.origin
        && left.pathname === right.pathname
        && left.search === right.search;

    const canHandle = (link, event) => {
        if (!link || link.target || link.hasAttribute("download")) return false;
        if (event && (event.button !== 0 || event.metaKey || event.ctrlKey
            || event.shiftKey || event.altKey)) return false;
        const target = new URL(link.href, window.location.href);
        return target.origin === window.location.origin;
    };

    const fetchPage = (url, signal) => fetch(url, {
        headers: {
            Accept: "text/html",
            "X-Cairnmark-Navigation": "workspace",
        },
        cache: "no-store",
        signal,
    }).then(async (response) => {
        if (!response.ok) throw new Error(`Navigation failed (${response.status}).`);
        const contentType = response.headers.get("content-type") || "";
        if (!contentType.includes("text/html")) {
            throw new Error("Navigation did not return an HTML page.");
        }
        return {
            html: await response.text(),
            url: response.url || url,
        };
    });

    const prefetch = (url) => {
        const target = new URL(url, window.location.href);
        if (target.origin !== window.location.origin || prefetchedPages.has(target.href)) {
            return;
        }
        const request = fetchPage(target.href).catch(() => {
            prefetchedPages.delete(target.href);
            return null;
        });
        prefetchedPages.set(target.href, request);
    };

    const pageRequest = async (url, signal) => {
        const target = new URL(url, window.location.href);
        const prefetched = prefetchedPages.get(target.href);
        prefetchedPages.delete(target.href);
        if (prefetched) {
            const page = await prefetched;
            if (page) return page;
        }
        return fetchPage(target.href, signal);
    };

    const stageStyles = (targetDocument) => {
        const targetLinks = [
            ...targetDocument.head.querySelectorAll(
                `link[rel="stylesheet"]:not([${PERSISTENT_ATTRIBUTE}])`
            ),
        ];
        return Promise.all(targetLinks.map((source) => new Promise((resolve) => {
            const link = document.createElement("link");
            [...source.attributes].forEach((attribute) => {
                link.setAttribute(attribute.name, attribute.value);
            });
            link.href = source.href;
            link.media = "not all";
            link.dataset.navigationNext = "true";
            link.addEventListener("load", resolve, { once: true });
            link.addEventListener("error", resolve, { once: true });
            document.head.appendChild(link);
            window.setTimeout(resolve, 3000);
        })));
    };

    const activateStagedStyles = () => {
        document.head.querySelectorAll(
            `link[rel="stylesheet"]:not([${PERSISTENT_ATTRIBUTE}]):not([data-navigation-next])`
        ).forEach((link) => link.remove());
        document.head.querySelectorAll("link[data-navigation-next]").forEach((link) => {
            link.media = "all";
            delete link.dataset.navigationNext;
        });
    };

    const discardStagedStyles = () => {
        document.head.querySelectorAll("link[data-navigation-next]")
            .forEach((link) => link.remove());
    };

    const routeScripts = (targetDocument) => [
        ...targetDocument.body.querySelectorAll(
            `script:not([${PERSISTENT_ATTRIBUTE}])`
        ),
    ];

    const removeCurrentRouteScripts = () => {
        document.body.querySelectorAll(`script:not([${PERSISTENT_ATTRIBUTE}])`)
            .forEach((script) => script.remove());
    };

    const copyScriptAttributes = (source, target) => {
        [...source.attributes].forEach((attribute) => {
            if (attribute.name !== "src" && attribute.name !== "defer") {
                target.setAttribute(attribute.name, attribute.value);
            }
        });
    };

    const executeRouteScripts = async (scripts) => {
        const inlineScripts = scripts.filter((script) => !script.src);
        const externalScripts = scripts.filter((script) => script.src);

        inlineScripts.forEach((source) => {
            const script = document.createElement("script");
            copyScriptAttributes(source, script);
            script.textContent = source.textContent;
            document.body.appendChild(script);
        });

        for (const source of externalScripts) {
            await new Promise((resolve, reject) => {
                const script = document.createElement("script");
                copyScriptAttributes(source, script);
                script.src = source.src;
                script.async = false;
                script.addEventListener("load", resolve, { once: true });
                script.addEventListener("error", () => {
                    reject(new Error(`Could not load ${source.src}`));
                }, { once: true });
                document.body.appendChild(script);
            });
        }
    };

    const updateNavigationState = (targetDocument) => {
        const targetActive = targetDocument.querySelector(`${NAVIGATION_SELECTOR}.active`);
        const targetHref = targetActive
            ? new URL(targetActive.href, window.location.href).pathname
            : "";
        document.querySelectorAll(NAVIGATION_SELECTOR).forEach((link) => {
            const active = new URL(link.href, window.location.href).pathname === targetHref;
            link.classList.toggle("active", active);
            if (active) {
                link.setAttribute("aria-current", "page");
            } else {
                link.removeAttribute("aria-current");
            }
        });

        const currentRoute = document.querySelector(".workspace-route");
        const targetRoute = targetDocument.querySelector(".workspace-route");
        if (currentRoute && targetRoute) currentRoute.textContent = targetRoute.textContent;
    };

    const swapWorkspace = (targetDocument) => {
        const currentCanvas = document.querySelector(".workspace-canvas");
        const targetCanvas = targetDocument.querySelector(".workspace-canvas");
        if (!currentCanvas || !targetCanvas) {
            throw new Error("The target page has no workspace canvas.");
        }
        const nextCanvas = document.importNode(targetCanvas, true);
        nextCanvas.scrollTop = 0;
        activateStagedStyles();
        removeCurrentRouteScripts();
        currentCanvas.replaceWith(nextCanvas);
        updateNavigationState(targetDocument);
        document.title = targetDocument.title;
        document.body.classList.remove("modal-open", "is-resizing");
    };

    const navigate = async (url, { push = true, force = false } = {}) => {
        const requestedUrl = new URL(url, window.location.href);
        if (!force && sameDocumentUrl(requestedUrl, new URL(window.location.href))) {
            document.querySelector(".workspace-canvas")?.scrollTo({ top: 0, behavior: "smooth" });
            return;
        }

        if (navigationController) return;
        const controller = new AbortController();
        navigationController = controller;
        document.documentElement.classList.add("is-workspace-navigating");
        document.dispatchEvent(new CustomEvent("cairnmark:navigation-before"));

        try {
            const page = await pageRequest(requestedUrl.href, controller.signal);
            const targetDocument = new DOMParser().parseFromString(page.html, "text/html");
            if (!targetDocument.querySelector(".workspace-canvas")) {
                throw new Error("The target page cannot be loaded inside the workspace.");
            }
            const scripts = routeScripts(targetDocument);
            await stageStyles(targetDocument);

            const update = () => swapWorkspace(targetDocument);
            if (document.startViewTransition) {
                const transition = document.startViewTransition(update);
                await transition.updateCallbackDone;
            } else {
                update();
            }

            const finalUrl = new URL(page.url, window.location.href);
            if (push) history.pushState({ cairnmarkWorkspace: true }, "", finalUrl);
            await executeRouteScripts(scripts);
            document.dispatchEvent(new CustomEvent("cairnmark:navigation-after"));
        } catch (error) {
            if (error.name === "AbortError") return;
            discardStagedStyles();
            window.location.assign(requestedUrl.href);
        } finally {
            if (navigationController === controller) navigationController = null;
            document.documentElement.classList.remove("is-workspace-navigating");
        }
    };

    document.addEventListener("click", (event) => {
        const link = event.target.closest(NAVIGATION_SELECTOR);
        if (!canHandle(link, event)) return;
        event.preventDefault();
        navigate(link.href);
    });

    document.addEventListener("pointerover", (event) => {
        const link = event.target.closest(NAVIGATION_SELECTOR);
        if (canHandle(link)) prefetch(link.href);
    });

    document.addEventListener("focusin", (event) => {
        const link = event.target.closest(NAVIGATION_SELECTOR);
        if (canHandle(link)) prefetch(link.href);
    });

    window.addEventListener("popstate", () => {
        navigate(window.location.href, { push: false, force: true });
    });
})();
