/**
 * Plugin remark para los marcadores que escribe la IA en cualquier parte del markdown:
 *
 *   {{tag:backend}}            -> <tag-badge>backend</tag-badge>
 *   {{expired:10/03/2026}}     -> <expired-date>10/03/2026</expired-date>
 *
 * Solo toca nodos de texto, así que no afecta a bloques de código ni a código en línea.
 * Los elementos <tag-badge> y <expired-date> los renderiza MarkdownContent (prop `components`).
 */

const TOKEN_RE = /\{\{\s*(tag|expired)\s*:\s*([^{}]+?)\s*\}\}/g;

const ELEMENT_BY_KIND = {
    tag: "tag-badge",
    expired: "expired-date",
};

/** Divide un nodo de texto en [texto, token, texto, ...]. Devuelve el mismo nodo si no hay marcadores. */
export function splitTextNode(node) {
    const value = node.value;
    const out = [];
    let last = 0;
    let match;
    TOKEN_RE.lastIndex = 0;

    while ((match = TOKEN_RE.exec(value)) !== null) {
        if (match.index > last) {
            out.push({ type: "text", value: value.slice(last, match.index) });
        }
        out.push({
            type: "emphasis", // se sustituye por el elemento personalizado vía hName
            data: { hName: ELEMENT_BY_KIND[match[1]] },
            children: [{ type: "text", value: match[2].trim() }],
        });
        last = match.index + match[0].length;
    }

    if (out.length === 0) return [node];
    if (last < value.length) out.push({ type: "text", value: value.slice(last) });
    return out;
}

function transform(node) {
    if (!Array.isArray(node.children)) return;
    const next = [];
    for (const child of node.children) {
        if (child.type === "text") {
            next.push(...splitTextNode(child));
        } else {
            transform(child);
            next.push(child);
        }
    }
    node.children = next;
}

export default function remarkChatTokens() {
    return (tree) => transform(tree);
}