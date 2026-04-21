type HeadingItem = {
  id: string
  level: number
  text: string
}

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const escapeAttr = (value: string) => escapeHtml(value)

const slugify = (value: string, index: number) => {
  const normalized = value
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fa5-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
  return normalized || `section-${index + 1}`
}

const renderInline = (input: string) => {
  const placeholders: string[] = []
  let html = escapeHtml(input)

  const store = (raw: string) => {
    const key = `__MD_PLACEHOLDER_${placeholders.length}__`
    placeholders.push(raw)
    return key
  }

  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, url) =>
    store(`<img src="${escapeAttr(url)}" alt="${escapeAttr(alt)}" class="md-image" />`)
  )

  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, url) =>
    store(
      `<a href="${escapeAttr(url)}" target="_blank" rel="noreferrer" class="md-link">${text}</a>`
    )
  )

  html = html.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')

  placeholders.forEach((value, index) => {
    html = html.replace(`__MD_PLACEHOLDER_${index}__`, value)
  })
  return html
}

export const extractMarkdownHeadings = (markdown: string): HeadingItem[] => {
  const lines = markdown.split(/\r?\n/)
  const headings: HeadingItem[] = []
  let headingIndex = 0

  lines.forEach((line) => {
    const match = line.match(/^(#{1,6})\s+(.+)$/)
    if (!match) return
    const text = match[2].trim()
    headings.push({
      id: slugify(text, headingIndex),
      level: match[1].length,
      text,
    })
    headingIndex += 1
  })

  return headings
}

export const renderMarkdown = (markdown: string) => {
  const lines = markdown.replace(/\t/g, '  ').split(/\r?\n/)
  const htmlParts: string[] = []
  let index = 0
  let headingIndex = 0

  const isUnordered = (line: string) => /^[-*]\s+/.test(line)
  const isOrdered = (line: string) => /^\d+\.\s+/.test(line)

  while (index < lines.length) {
    const line = lines[index]
    const trimmed = line.trim()

    if (!trimmed) {
      index += 1
      continue
    }

    if (/^```/.test(trimmed)) {
      const codeLines: string[] = []
      index += 1
      while (index < lines.length && !/^```/.test(lines[index].trim())) {
        codeLines.push(lines[index])
        index += 1
      }
      if (index < lines.length) index += 1
      htmlParts.push(
        `<pre class="md-code-block"><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`
      )
      continue
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/)
    if (headingMatch) {
      const level = headingMatch[1].length
      const text = headingMatch[2].trim()
      const id = slugify(text, headingIndex)
      headingIndex += 1
      htmlParts.push(
        `<h${level} id="${id}" class="md-heading md-heading-${level}">${renderInline(text)}</h${level}>`
      )
      index += 1
      continue
    }

    if (/^---+$/.test(trimmed)) {
      htmlParts.push('<hr class="md-divider" />')
      index += 1
      continue
    }

    if (/^>\s?/.test(trimmed)) {
      const quoteLines: string[] = []
      while (index < lines.length && /^>\s?/.test(lines[index].trim())) {
        quoteLines.push(lines[index].trim().replace(/^>\s?/, ''))
        index += 1
      }
      htmlParts.push(`<blockquote class="md-blockquote">${renderInline(quoteLines.join('<br />'))}</blockquote>`)
      continue
    }

    if (isUnordered(trimmed) || isOrdered(trimmed)) {
      const ordered = isOrdered(trimmed)
      const items: string[] = []
      while (index < lines.length) {
        const listLine = lines[index].trim()
        if (!(ordered ? isOrdered(listLine) : isUnordered(listLine))) break
        items.push(renderInline(listLine.replace(ordered ? /^\d+\.\s+/ : /^[-*]\s+/, '')))
        index += 1
      }
      const tag = ordered ? 'ol' : 'ul'
      htmlParts.push(`<${tag} class="md-list">${items.map(item => `<li>${item}</li>`).join('')}</${tag}>`)
      continue
    }

    const paragraphLines: string[] = []
    while (index < lines.length) {
      const current = lines[index]
      const currentTrimmed = current.trim()
      if (!currentTrimmed) break
      if (
        /^```/.test(currentTrimmed) ||
        /^(#{1,6})\s+/.test(currentTrimmed) ||
        /^>\s?/.test(currentTrimmed) ||
        /^---+$/.test(currentTrimmed) ||
        isUnordered(currentTrimmed) ||
        isOrdered(currentTrimmed)
      ) {
        break
      }
      paragraphLines.push(currentTrimmed)
      index += 1
    }
    htmlParts.push(`<p class="md-paragraph">${renderInline(paragraphLines.join('<br />'))}</p>`)
  }

  return htmlParts.join('\n')
}
