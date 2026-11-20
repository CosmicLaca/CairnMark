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

    const splitTableRow = (value) => {
        let row = String(value).trim();
        if (row.startsWith("|")) row = row.slice(1);
        let trailingBackslashes = 0;
        for (let index = row.length - 2; index >= 0 && row[index] === "\\"; index -= 1) {
            trailingBackslashes += 1;
        }
        if (row.endsWith("|") && trailingBackslashes % 2 === 0) {
            row = row.slice(0, -1);
        }

        const cells = [];
        let cell = "";
        let escaped = false;
        for (const character of row) {
            if (character === "|" && !escaped) {
                cells.push(cell.trim());
                cell = "";
                continue;
            }
            if (character === "\\" && !escaped) {
                escaped = true;
                cell += character;
                continue;
            }
            cell += character;
            escaped = false;
        }
        cells.push(cell.trim());
        return cells.map((item) => item.replace(/\\\|/g, "|"));
    };

    const tableAlignments = (value) => {
        const cells = splitTableRow(value);
        if (!cells.length || !cells.every((cell) => /^:?-{3,}:?$/.test(cell))) {
            return null;
        }
        return cells.map((cell) => {
            if (cell.startsWith(":") && cell.endsWith(":")) return "center";
            if (cell.endsWith(":")) return "right";
            return "left";
        });
    };

    const tableCell = (tag, value, alignment) => {
        const className = alignment === "left"
            ? ""
            : ` class="markdown-table-align-${alignment}"`;
        return `<${tag}${className}>${renderInline(value)}</${tag}>`;
    };

    const renderQuoteLines = (lines) => {
        const output = [];
        let paragraph = [];
        const flushParagraph = () => {
            if (!paragraph.length) return;
            output.push(`<p>${paragraph.join("<br>")}</p>`);
            paragraph = [];
        };
        lines.forEach((line) => {
            const heading = line.match(/^(#{1,6})\s+(.*)$/);
            if (heading) {
                flushParagraph();
                const level = heading[1].length;
                output.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
                return;
            }
            if (!line.trim()) {
                flushParagraph();
                return;
            }
            paragraph.push(renderInline(line));
        });
        flushParagraph();
        return output.join("\n");
    };

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

        const lines = working.split("\n");
        for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
            const line = lines[lineIndex];
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
            const alignments = line.includes("|") && lineIndex + 1 < lines.length
                ? tableAlignments(lines[lineIndex + 1])
                : null;
            const headerCells = alignments ? splitTableRow(line) : [];
            if (alignments && headerCells.length === alignments.length) {
                flushParagraph();
                closeList();
                const header = headerCells.map((cell, index) => (
                    tableCell("th", cell, alignments[index])
                )).join("");
                const rows = [];
                lineIndex += 2;
                while (lineIndex < lines.length && lines[lineIndex].includes("|")) {
                    const cells = splitTableRow(lines[lineIndex]);
                    const normalized = alignments.map((_alignment, index) => cells[index] || "");
                    rows.push(`<tr>${normalized.map((cell, index) => (
                        tableCell("td", cell, alignments[index])
                    )).join("")}</tr>`);
                    lineIndex += 1;
                }
                lineIndex -= 1;
                output.push(
                    `<div class="markdown-table-wrap"><table><thead><tr>${header}</tr></thead>`
                    + `<tbody>${rows.join("")}</tbody></table></div>`
                );
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
            const quote = line.match(/^&gt;\s?(.*)$/);
            if (quote) {
                flushParagraph();
                closeList();
                const quoteLines = [quote[1]];
                while (lineIndex + 1 < lines.length) {
                    const nextQuote = lines[lineIndex + 1].match(/^&gt;\s?(.*)$/);
                    if (!nextQuote) break;
                    quoteLines.push(nextQuote[1]);
                    lineIndex += 1;
                }
                output.push(`<blockquote>${renderQuoteLines(quoteLines)}</blockquote>`);
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
