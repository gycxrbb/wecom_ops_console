import MarkdownIt from 'markdown-it'
import taskLists from 'markdown-it-task-lists'
import DOMPurify from 'dompurify'

let instance: MarkdownIt | null = null

const ALLOWED_TAGS = [
  'p', 'br', 'strong', 'em', 'u', 's', 'ul', 'ol', 'li', 'blockquote',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'code', 'pre', 'table', 'thead',
  'tbody', 'tr', 'th', 'td', 'a', 'img', 'hr', 'input', 'span', 'del',
  'sup', 'sub', 'dd', 'dt', 'dl', 'div',
]

const ALLOWED_ATTR = [
  'href', 'src', 'alt', 'title', 'class', 'target', 'rel', 'id',
  'type', 'checked', 'disabled', 'colspan', 'rowspan',
  'loading', 'decoding',
]

function createInstance(): MarkdownIt {
  const md = new MarkdownIt({
    html: false,
    linkify: true,
    breaks: false,
    typographer: false,
  })

  md.use(taskLists, { disabled: true, label: true, labelAfter: true })

  // Links: open in new tab, prevent javascript: protocol
  const defaultRender =
    md.renderer.rules.link_open ||
    ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

  md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
    const hrefIdx = tokens[idx].attrIndex('href')
    if (hrefIdx >= 0) {
      const href = tokens[idx].attrs![hrefIdx][1]
      if (href && href.toLowerCase().startsWith('javascript:')) {
        tokens[idx].attrs![hrefIdx][1] = '#'
      }
    }
    tokens[idx].attrSet('target', '_blank')
    tokens[idx].attrSet('rel', 'noopener noreferrer')
    return defaultRender(tokens, idx, options, env, self)
  }

  // Images: lazy loading + domain whitelist
  const IMAGE_DOMAIN_WHITELIST = ['cdn.mengfugui.com']

  md.renderer.rules.image = (tokens, idx) => {
    const token = tokens[idx]
    const src = token.attrGet('src') || ''
    const alt = token.content || ''
    const title = token.attrGet('title') || ''
    let domain = ''
    try { domain = new URL(src, 'https://localhost').hostname } catch { /* ignore */ }
    const isWhitelisted = IMAGE_DOMAIN_WHITELIST.includes(domain) || src.startsWith('/api/')
    const attrs = [
      `src="${src}"`,
      `alt="${alt}"`,
      'loading="lazy"',
      'decoding="async"',
      `class="md-img${isWhitelisted ? '' : ' md-img--external'}"`,
    ]
    if (title) attrs.push(`title="${title}"`)
    return `<img ${attrs.join(' ')} />`
  }

  // Tables: wrap in scrollable div
  const defaultTableOpen =
    md.renderer.rules.table_open ||
    ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))
  md.renderer.rules.table_open = (tokens, idx, options, env, self) => {
    return '<div class="md-table-scroll">' + defaultTableOpen(tokens, idx, options, env, self)
  }

  const defaultTableClose =
    md.renderer.rules.table_close ||
    ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))
  md.renderer.rules.table_close = (tokens, idx, options, env, self) => {
    return defaultTableClose(tokens, idx, options, env, self) + '</div>'
  }

  return md
}

export function sanitize(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ADD_ATTR: ['target', 'onerror'],
  })
}

export function useMarkdownIt(): { md: MarkdownIt; render: (src: string) => string } {
  if (!instance) {
    instance = createInstance()
  }
  return {
    md: instance,
    render: (src: string) => sanitize(instance!.render(src)),
  }
}
