// Convert ordinary Markdown to MDX-safe Markdown without rewriting code literals.
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkStringify from 'remark-stringify';
import remarkGfm from 'remark-gfm';

export async function markdown(source, refs = {}) {
  return String(await unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(() => (tree) => {
      function link(node) {
        if (!node.children || ['link', 'linkReference', 'heading'].includes(node.type)) return;
        node.children = node.children.map(child => {
          if (child.type === 'inlineCode' && refs[child.value]) {
            return {type: 'link', url: refs[child.value], children: [child]};
          }
          link(child);
          return child;
        });
      }
      link(tree);
    })
    .use(remarkStringify, {
      fences: true,
      resourceLink: true,
      unsafe: [{character: '{', inConstruct: 'phrasing'}, {character: '}', inConstruct: 'phrasing'}],
    })
    .process(source));
}

let input = '';
for await (const chunk of process.stdin) input += chunk;
const pages = JSON.parse(input);
const result = {};
for (const [path, { body, refs }] of Object.entries(pages)) result[path] = await markdown(body, refs);
process.stdout.write(JSON.stringify(result));
