export type Template = {
  id: number
  scene_key: string
  style: string
  label: string
  content: string
  is_builtin: number
  metadata_json: Record<string, any> | null
  _editContent: string
  _saving: boolean
}

export type Scene = {
  key: string
  label: string
  styles: string[]
  category_id?: number
  category_code?: string
  category_l1?: string
  category_l2?: string
  category_l3?: string
}

export type CategoryL3Node = {
  id: number
  name: string
  code?: string
  sort_order: number
  template_count: number
  scenes: Scene[]
}

export type CategoryL2Node = {
  id: number
  name: string
  code?: string
  sort_order: number
  children: CategoryL3Node[]
}

export type CategoryL1Node = {
  id: number
  name: string
  code?: string
  sort_order: number
  children: CategoryL2Node[]
}
