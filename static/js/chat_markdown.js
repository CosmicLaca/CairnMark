(() => {
    "use strict";

    const escapeHtml = (value) => String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");

    const safeLink = (label, href) => {
        try {
            const url = new URL(href, window.location.origin);
            if (!["http:", "https:", "mailto:"].includes(url.protocol)) {
                return label;
            }
            return `<a href="${escapeHtml(url.href)}" target="_blank" rel="noopener">${label}</a>`;
        } catch (error) {
            return label;
        }
    };

    const renderInline = (value) => value
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/__([^_]+)__/g, "<strong>$1</strong>")
        .replace(/\*([^*]+)\*/g, "<em>$1</em>")
        .replace(/_([^_]+)_/g, "<em>$1</em>")
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_match, label, href) => (
            safeLink(label, href)
        ));

    const render = (text) => {
        if (!text) return "";
        const codeBlocks = [];
        let working = String(text).replace(
            /```(\w*)\n([\s\S]*?)```/g,
            (_match, language, code) => {
                const index = codeBlocks.length;
                codeBlocks.push(
                    `<pre><code class="lang-${escapeHtml(language)}">${escapeHtml(code.replace(/\n$/, ""))}</code></pre>`
                );
                return `@@CODEBLOCK${index}@@`;
            }
        );
        working = escapeHtml(working).replace(
            /@@CODEBLOCK(\d+)@@/g,
            (_match, index) => codeBlocks[Number(index)]
        );

        const output = [];
        let paragraph = [];
        let listType = null;
        const flushParagraph = () => {
            if (paragraph.length) {
                output.push(`<p>${paragraph.join("<br>")}</p>`);
                paragraph = [];
            }
        };
        const closeList = () => {
            if (listType) output.push(`</${listType}>`);
            listType = null;
        };
        const openList = (type) => {
            if (listType === type) return;
            closeList();
            output.push(`<${type}>`);
            listType = type;
        };

        for (const line of working.split("\n")) {
            if (/^@@CODEBLOCK\d+@@$/.test(line.trim())) {
                flushParagraph();
                closeList();
                output.push(line.trim());
                continue;
            }
            const heading = line.match(/^(#{1,6})\s+(.*)$/);
            if (heading) {
                flushParagraph();
                closeList();
                const level = heading[1].length;
                output.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
                continue;
            }
            const unorderedItem = line.match(/^[-*+]\s+(.*)$/);
            if (unorderedItem) {
                flushParagraph();
                openList("ul");
                output.push(`<li>${renderInline(unorderedItem[1])}</li>`);
                continue;
            }
            const orderedItem = line.match(/^\d+\.\s+(.*)$/);
            if (orderedItem) {
                flushParagraph();
                openList("ol");
                output.push(`<li>${renderInline(orderedItem[1])}</li>`);
                continue;
            }
            if (!line.trim()) {
                flushParagraph();
                closeList();
                continue;
            }
            const quote = line.match(/^>\s?(.*)$/);
            if (quote) {
                flushParagraph();
                closeList();
                output.push(`<blockquote>${renderInline(quote[1])}</blockquote>`);
                continue;
            }
            closeList();
            paragraph.push(renderInline(line));
        }
        flushParagraph();
        closeList();
        return output.join("\n");
    };

    window.CairnmarkMarkdown = Object.freeze({ render });
})();
