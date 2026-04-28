/**
 * Streaming chunk buffer — safely close half-open Markdown before rendering.
 */

/** Close unclosed Markdown constructs so markdown-it can parse cleanly. */
export function safeCloseMarkdown(raw: string): string {
  if (!raw) return raw

  // 1. Unclosed fenced code blocks (``` sequences)
  let result = raw
  const fencePattern = /(^|\n)```/g
  let fenceCount = 0
  let match: RegExpExecArray | null
  while ((match = fencePattern.exec(result)) !== null) {
    fenceCount++
  }
  if (fenceCount % 2 !== 0) {
    result += '\n```'
  }

  // 1.5. Unclosed block math ($$)
  // Only check outside fences — after fence closing, count standalone $$ lines
  const blockMathPattern = /^\$\$$/gm
  let mathCount = 0
  while (blockMathPattern.exec(result) !== null) {
    mathCount++
  }
  if (mathCount % 2 !== 0) {
    result += '\n$$'
  }

  // 2. Unclosed inline code (single/double backtick not part of fence)
  //    Only check last line for simplicity
  const lastNewline = result.lastIndexOf('\n')
  const lastLine = result.slice(lastNewline + 1)
  // Skip if last line looks like a fence line
  if (!lastLine.startsWith('```')) {
    const inlineBacktickCount = (lastLine.match(/(?<!`)`(?!`)/g) || []).length
    if (inlineBacktickCount % 2 !== 0) {
      result += '`'
    }
  }

  // 3. Unclosed bold (**)
  const boldCount = (result.match(/\*\*/g) || []).length
  if (boldCount % 2 !== 0) {
    result += '**'
  }

  // 4. Unclosed italic — count single * not part of **
  // Remove all ** first, then count remaining *
  const withoutBold = result.replace(/\*\*/g, '')
  const italicCount = (withoutBold.match(/(?<!\*)\*(?!\*)/g) || []).length
  if (italicCount % 2 !== 0) {
    result += '*'
  }

  return result
}
