// Convert ordinary Markdown to MDX-safe Markdown without rewriting code literals.
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkStringify from 'remark-stringify';
import remarkGfm from 'remark-gfm';

export async function markdown(source, refs = {}) {
  // Supply definitions so Remark owns [label][symbol] syntax, including inline-code labels.
  const definitions = Object.entries(refs).map(([id, url]) => `[${id}]: ${url}`).join('\n');
  const targets = new Map(Object.entries(refs).map(([id, url]) => [id.toLowerCase(), url]));
  return String(await unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(() => (tree) => {
      function walk(node) {
        if (node.type === 'linkReference') {
          const url = targets.get(String(node.identifier).toLowerCase());
          if (url) {
            node.type = 'link';
            node.url = url;
            delete node.identifier;
            delete node.label;
            delete node.referenceType;
          }
        } else if (node.type === 'text') {
          // Unknown CommonMark references remain prose. Code and existing links are opaque.
          const missing = node.value.match(/\]\[(agentconnect\.[^\]]+)\]/);
          if (missing) throw new Error(`Unresolved reference: ${missing[1]}`);
        }
        if (node.type !== 'link') {
          for (const child of node.children ?? []) walk(child);
        }
      }
      walk(tree);
      tree.children = tree.children.filter(node => node.type !== 'definition' || !targets.has(String(node.identifier).toLowerCase()));
    })
    .use(remarkStringify, {
      fences: true,
      resourceLink: true,
      unsafe: [{character: '{', inConstruct: 'phrasing'}, {character: '}', inConstruct: 'phrasing'}],
    })
    .process(source + '\n\n' + definitions));
}

let input = '';
for await (const chunk of process.stdin) input += chunk;
const pages = JSON.parse(input);
const result = {};
for (const [path, { body, refs }] of Object.entries(pages)) result[path] = await markdown(body, refs);
process.stdout.write(JSON.stringify(result));
