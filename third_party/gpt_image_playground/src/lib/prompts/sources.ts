// 提示词库数据源：复用 yukkcat/image-prompts 聚合 registry（已把多个 GitHub 提示词仓库标准化成 JSON）。
// 不自己爬各仓库，直接 fetch 这个 registry 的每个 source JSON。

export type PromptSource = {
  id: string
  name: string
  homepage: string
}

export const REGISTRY_BASE =
  'https://raw.githubusercontent.com/yukkcat/image-prompts/main/dist/sources'

export const ALL_SOURCES_OPTION = 'all'

// 6 个内置源（id 对应 registry 的 <id>.json 文件名）
export const PROMPT_SOURCES: PromptSource[] = [
  { id: 'banana-prompt-quicker', name: 'Banana Prompt Quicker', homepage: 'https://github.com/glidea/banana-prompt-quicker' },
  { id: 'davidwu-gpt-image2-prompts', name: 'DavidWu GPT Image 2', homepage: 'https://github.com/davidwuw0811-boop/awesome-gpt-image2-prompts' },
  { id: 'awesome-gpt-image', name: 'Awesome GPT Image', homepage: 'https://github.com/ZeroLu/awesome-gpt-image' },
  { id: 'awesome-gpt4o-image-prompts', name: 'Awesome GPT-4o', homepage: 'https://github.com/ImgEdify/Awesome-GPT4o-Image-Prompts' },
  { id: 'youmind-gpt-image-2', name: 'YouMind GPT Image 2', homepage: 'https://github.com/YouMind-OpenLab/awesome-gpt-image-2' },
  { id: 'youmind-nano-banana-pro', name: 'YouMind Nano Banana Pro', homepage: 'https://github.com/YouMind-OpenLab/awesome-nano-banana-pro-prompts' },
]

export const SOURCE_NAME_MAP: Record<string, string> = Object.fromEntries(
  PROMPT_SOURCES.map((s) => [s.id, s.name]),
)

export function registryUrl(sourceId: string): string {
  return `${REGISTRY_BASE}/${sourceId}.json`
}

export function sourceName(sourceId: string): string {
  return SOURCE_NAME_MAP[sourceId] || sourceId
}
