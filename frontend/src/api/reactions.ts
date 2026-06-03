import { api } from './client'

export interface Reaction {
  emoji: string
  count: number
  reacted_by_me: boolean
}

type CommentPath = {
  project_id: string
  task_id: string
  comment_id: string
}

const base = ({ project_id, task_id, comment_id }: CommentPath) =>
  `/projects/${project_id}/tasks/${task_id}/comments/${comment_id}/reactions`

export const reactionsApi = {
  list: (path: CommentPath) => api.get<Reaction[]>(base(path)),
  add: (path: CommentPath, emoji: string) =>
    api.post<Reaction>(base(path), { emoji }),
  remove: (path: CommentPath, emoji: string) =>
    api.delete(`${base(path)}/${emoji}`),
}
