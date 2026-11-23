(() => {
    "use strict";

    const escapeHtml = (value) => String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");

    const IMAGE_PATH_PATTERN = /\.(?:avif|bmp|gif|jpe?g|png|webp)$/i;
    const AUDIO_PATH_PATTERN = /\.(?:aac|flac|m4a|mp3|oga|ogg|opus|wav)$/i;
    const AUDIO_LABEL_PATTERN = /^\s*(?:(?:direct\s+)?(?:audio\s+)?stream|audio|listen|play|radio)(?:\s+url)?\s*$/i;
    const AUDIO_CONTEXT_PATTERN = /\b(?:(?:direct\s+)?(?:audio\s+)?stream|listen)(?:\s+url)?\s*[:=-]?\s*$/i;

    const videoEmbed = (url) => {
        const hostname = url.hostname.toLowerCase().replace(/^www\./, "");
        if (["youtube.com", "m.youtube.com", "music.youtube.com"].includes(hostname)) {
            const parts = url.pathname.split("/").filter(Boolean);
            const videoId = url.searchParams.get("v")
                || (["embed", "shorts", "live"].includes(parts[0]) ? parts[1] : "");
            if (/^[A-Za-z0-9_-]{11}$/.test(videoId || "")) {
                return {
                    provider: "YouTube",
                    url: `https://www.youtube-nocookie.com/embed/${videoId}`,
                };
            }
        }
        if (hostname === "youtu.be") {
            const videoId = url.pathname.split("/").filter(Boolean)[0] || "";
            if (/^[A-Za-z0-9_-]{11}$/.test(videoId)) {
                return {
                    provider: "YouTube",
                    url: `https://www.youtube-nocookie.com/embed/${videoId}`,
                };
            }
        }
        if (["vimeo.com", "player.vimeo.com"].includes(hostname)) {
            const videoId = url.pathname.split("/").filter(Boolean)
                .reverse()
                .find((part) => /^\d+$/.test(part));
            if (videoId) {
                return {
                    provider: "Vimeo",
                    url: `https://player.vimeo.com/video/${videoId}`,
                };
            }
        }
        return null;
    };

    const splitLinkSuffix = (value) => {
        let href = String(value);
        let suffix = "";
        const entitySuffix = href.match(/(?:&(?:quot|gt|lt|#39);)+$/);
        if (entitySuffix) {
            suffix = entitySuffix[0];
            href = href.slice(0, -entitySuffix[0].length);
        }
        while (/[.,!?;:\]}]$/.test(href)) {
            suffix = href.slice(-1) + suffix;
            href = href.slice(0, -1);
        }
        while (href.endsWith(")")) {
            const openCount = (href.match(/\(/g) || []).length;
            const closeCount = (href.match(/\)/g) || []).length;
            if (closeCount <= openCount) break;
            suffix = `)${suffix}`;
            href = href.slice(0, -1);
        }
        return { href, suffix };
    };

    const safeLink = (
        label,
        href,
        {
            previewImage = false,
            previewAudio = false,
            embeddedVideos = null,
        } = {}
    ) => {
        try {
            const decodedHref = String(href)
                .replace(/&amp;/g, "&")
                .replace(/&quot;/g, "\"")
                .replace(/&#39;/g, "'");
            const url = new URL(decodedHref, window.location.origin);
            if (!["http:", "https:", "mailto:"].includes(url.protocol)) {
                return label;
            }
            if (
                previewImage
                && ["http:", "https:"].includes(url.protocol)
                && IMAGE_PATH_PATTERN.test(url.pathname)
            ) {
                const safeUrl = escapeHtml(url.href);
                return `<span class="chat-markdown-image-preview" data-chat-image-preview data-image-url="${safeUrl}">`
                    + `<a class="chat-markdown-image-fallback" href="${safeUrl}" target="_blank" rel="noopener noreferrer">${safeUrl}</a>`
                    + `<a class="chat-markdown-image-link" href="${safeUrl}" target="_blank" rel="noopener noreferrer">`
                    + `<img class="chat-markdown-image" alt="External image preview"></a>`
                    + `<button class="chat-markdown-image-reverse" type="button" data-reverse-image-src="${safeUrl}" title="Reverse image search" aria-label="Reverse image search">⌕</button>`
                    + `<button class="chat-markdown-image-download" type="button" title="Download image" aria-label="Download image">⇩</button>`
                    + `</span>`;
            }
            const safeUrl = escapeHtml(url.href);
            const embed = ["http:", "https:"].includes(url.protocol)
                ? videoEmbed(url)
                : null;
            if (embed) {
                if (embeddedVideos?.has(embed.url)) {
                    return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${label}</a>`;
                }
                embeddedVideos?.add(embed.url);
                const safeEmbedUrl = escapeHtml(embed.url);
                return `<span class="chat-markdown-video-preview">`
                    + `<a class="chat-markdown-video-source" href="${safeUrl}" target="_blank" rel="noopener noreferrer">${label}</a>`
                    + `<span class="chat-markdown-video-frame">`
                    + `<iframe src="${safeEmbedUrl}" title="Embedded ${embed.provider} video" loading="lazy" `
                    + `referrerpolicy="strict-origin-when-cross-origin" `
                    + `allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>`
                    + `</span></span>`;
            }
            if (
                ["http:", "https:"].includes(url.protocol)
                && (
                    previewAudio
                    || AUDIO_PATH_PATTERN.test(url.pathname)
                    || AUDIO_LABEL_PATTERN.test(String(label).replace(/<[^>]*>/g, ""))
                )
            ) {
                return `<span class="chat-markdown-audio-preview" data-chat-audio-preview data-audio-url="${safeUrl}">`
                    + `<a class="chat-markdown-audio-source" href="${safeUrl}" target="_blank" rel="noopener noreferrer">${label}</a>`
                    + `<span class="chat-markdown-audio-player" data-chat-audio-player></span>`
                    + `</span>`;
            }
            const previewAttribute = ["http:", "https:"].includes(url.protocol)
                && !IMAGE_PATH_PATTERN.test(url.pathname)
                ? ` data-webpage-preview-url="${safeUrl}"`
                : "";
            const imageInspectAttribute = ["http:", "https:"].includes(url.protocol)
                && !IMAGE_PATH_PATTERN.test(url.pathname)
                ? ` data-external-image-candidate="${safeUrl}"`
                : "";
            return `<a href="${safeUrl}"${previewAttribute}${imageInspectAttribute} target="_blank" rel="noopener noreferrer">${label}</a>`;
        } catch (error) {
            return label;
        }
    };

    const renderInline = (
        value,
        { audioHint = false, embeddedVideos = null } = {}
    ) => {
        const protectedParts = [];
        const protect = (html) => {
            const index = protectedParts.length;
            protectedParts.push(html);
            return `@@INLINE${index}@@`;
        };
        let rendered = String(value)
            .replace(/`([^`]+)`/g, (_match, code) => {
                if (/^https?:\/\/\S+$/i.test(code)) {
                    return protect(safeLink(`<code>${code}</code>`, code, {
                        previewImage: true,
                        embeddedVideos,
                    }));
                }
                return protect(`<code>${code}</code>`);
            })
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_match, label, href) => (
                protect(safeLink(label, href, {
                    previewAudio: audioHint,
                    embeddedVideos,
                }))
            ))
            .replace(/\bhttps?:\/\/[^\s<]+/g, (match, offset, input) => {
                let { href, suffix } = splitLinkSuffix(match);
                const prefix = input.slice(Math.max(0, offset - 48), offset);
                for (const marker of ["**", "__", "*", "_"]) {
                    if (prefix.endsWith(marker) && href.endsWith(marker)) {
                        href = href.slice(0, -marker.length);
                        suffix = marker + suffix;
                        break;
                    }
                }
                const previewAudio = audioHint || AUDIO_CONTEXT_PATTERN.test(prefix);
                return protect(`${safeLink(href, href, {
                    previewImage: true,
                    previewAudio,
                    embeddedVideos,
                })}${suffix}`);
            })
            .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
            .replace(/__([^_]+)__/g, "<strong>$1</strong>")
            .replace(/\*([^*]+)\*/g, "<em>$1</em>")
            .replace(/_([^_]+)_/g, "<em>$1</em>");
        return rendered.replace(/@@INLINE(\d+)@@/g, (_match, index) => (
            protectedParts[Number(index)]
        ));
    };

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

    const tableCell = (
        tag,
        value,
        alignment,
        { audioHint = false, embeddedVideos = null } = {}
    ) => {
        const className = alignment === "left"
            ? ""
            : ` class="markdown-table-align-${alignment}"`;
        return `<${tag}${className}>${renderInline(value, {
            audioHint,
            embeddedVideos,
        })}</${tag}>`;
    };

    const renderQuoteLines = (lines, embeddedVideos) => {
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
                output.push(`<h${level}>${renderInline(heading[2], {
                    embeddedVideos,
                })}</h${level}>`);
                return;
            }
            if (!line.trim()) {
                flushParagraph();
                return;
            }
            paragraph.push(renderInline(line, { embeddedVideos }));
        });
        flushParagraph();
        return output.join("\n");
    };

    const render = (text) => {
        if (!text) return "";
        const codeBlocks = [];
        const embeddedVideos = new Set();
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
                output.push(`<h${level}>${renderInline(heading[2], {
                    embeddedVideos,
                })}</h${level}>`);
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
                    tableCell("th", cell, alignments[index], { embeddedVideos })
                )).join("");
                const rows = [];
                lineIndex += 2;
                while (lineIndex < lines.length && lines[lineIndex].includes("|")) {
                    const cells = splitTableRow(lines[lineIndex]);
                    const normalized = alignments.map((_alignment, index) => cells[index] || "");
                    rows.push(`<tr>${normalized.map((cell, index) => (
                        tableCell("td", cell, alignments[index], {
                            audioHint: /\b(?:audio|listen|radio|stream)\b/i.test(
                                headerCells[index] || ""
                            ),
                            embeddedVideos,
                        })
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
                output.push(`<li>${renderInline(unorderedItem[1], {
                    embeddedVideos,
                })}</li>`);
                continue;
            }
            const orderedItem = line.match(/^\d+\.\s+(.*)$/);
            if (orderedItem) {
                flushParagraph();
                openList("ol");
                output.push(`<li>${renderInline(orderedItem[1], {
                    embeddedVideos,
                })}</li>`);
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
                output.push(`<blockquote>${renderQuoteLines(
                    quoteLines,
                    embeddedVideos
                )}</blockquote>`);
                continue;
            }
            closeList();
            paragraph.push(renderInline(line, { embeddedVideos }));
        }
        flushParagraph();
        closeList();
        return output.join("\n");
    };

    window.CairnmarkMarkdown = Object.freeze({ render });
})();
