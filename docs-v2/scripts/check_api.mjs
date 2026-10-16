// Compile generated references and verify canonical links without a dev server.
import { readFile, readdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { compile } from '@mdx-js/mdx';
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';

const root = resolve(import.meta.dirname, '..');
const paths = ['api-reference.mdx', ...(await readdir(resolve(root, 'api'))).filter(p => p.endsWith('.mdx')).map(p => `api/${p}`)];
const anchors = new Map();
const links = [];
for (const path of paths) {
  const source = await readFile(resolve(root, path), 'utf8');
  const body = source.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '');
  try {
    await compile({value: body, path}, {remarkPlugins: [remarkGfm]});
  } catch (error) {
    throw new Error(`${path}: ${error.message}`, {cause: error});
  }
  const ids = [...body.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
  if (new Set(ids).size !== ids.length) throw new Error(`Duplicate anchors: ${path}`);
  anchors.set('/' + path.slice(0, -4), new Set(ids));
  function walk(node) {
    if (node.type === 'link' && node.url.startsWith('/api')) links.push([path, node.url]);
    for (const child of node.children ?? []) walk(child);
  }
  walk(unified().use(remarkParse).use(remarkGfm).parse(body));
  const hrefs = new Set();
  for (const match of body.matchAll(/\bhref="(\/api[^"]+)"/g)) hrefs.add(match[1]);
  for (const href of hrefs) links.push([path, href]);
}
for (const [source, url] of links) {
  const [page, id] = url.split('#');
  if (!anchors.has(page) || (id && !anchors.get(page).has(id))) {
    throw new Error(`Broken API reference in ${source}: ${url}`);
  }
}
console.log(`ok: ${paths.length} MDX references compiled; ${links.length} API links verified`);
