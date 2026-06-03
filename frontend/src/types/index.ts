export type UserRole = 'admin' | 'member' | 'viewer'
export type ProjectRole = 'owner' | 'manager' | 'member' | 'viewer'
export type TaskStatus = 'todo' | 'in_progress' | 'review' | 'done'
export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent'
export type MilestoneStatus = 'planned' | 'in_progress' | 'completed' | 'cancelled'
export type DailyTaskStatus = 'pending' | 'in_progress' | 'done' | 'cancelled'

export interface User {
  id: string
  email: string
  display_name: string
  role: UserRole
  is_active: boolean
  avatar_url: string | null
  created_at: string
}

export interface Project {
  id: string
  name: string
  description: string | null
  color: string
  is_archived: boolean
  created_at: string
  updated_at: string
  member_count: number
}

export interface ProjectMember {
  id: string
  user: User
  role: ProjectRole
  joined_at: string
}

export interface Milestone {
  id: string
  project_id: string
  name: string
  description: string | null
  status: MilestoneStatus
  due_date: string | null
  created_at: string
  task_count: number
}

export interface TaskComment {
  id: string
  task_id: string
  author: User
  content: string
  created_at: string
}

export interface SubTask {
  id: string
  project_id: string
  parent_task_id: string | null
  title: string
  description: string | null
  status: TaskStatus
  priority: TaskPriority
  progress: number
}

export interface TimeLog {
  id: string
  task_id: string
  user_id: string
  started_at: string
  ended_at: string | null
  minutes: number
  note: string | null
  created_at: string
}

export interface Notification {
  id: string
  type: string
  message: string
  ref_id: string | null
  ref_type: string | null
  read_at: string | null
  created_at: string
}

export interface Task {
  id: string
  project_id: string
  milestone_id: string | null
  parent_task_id: string | null
  title: string
  description: string | null
  status: TaskStatus
  priority: TaskPriority
  position: number
  due_date: string | null
  start_date: string | null
  end_date: string | null
  actual_end_date: string | null
  progress: number
  subtask_count: number
  subtask_done_count: number
  created_at: string
  updated_at: string
  assignees: User[]
  comments: TaskComment[]
}

export interface Token {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface DailyTask {
  id: string
  user_id: string
  title: string
  description: string | null
  status: DailyTaskStatus
  progress: number
  date: string
  started_at: string | null
  ended_at: string | null
  notify_at: string | null
  work_minutes: number
  created_at: string
  updated_at: string
  labels: string[]
}

export interface TemplateTask {
  id: string
  title: string
  description: string | null
  priority: string
  day_offset_start: number
  day_offset_end: number | null
  position: number
}

export interface ProjectTemplate {
  id: string
  name: string
  description: string | null
  color: string
  created_by: string
  created_at: string
  updated_at: string
  tasks: TemplateTask[]
}

export interface CalendarEvent {
  id: string
  title: string
  date: string
  type: 'task' | 'daily'
  status: string
  priority?: string
  progress: number
  project_id?: string
  project_name?: string
  labels: string[]
}

export interface MilestoneLog {
  id: string
  project_id: string
  task_id: string | null
  task_title: string
  completed_by: string | null
  completed_by_name: string | null
  work_minutes: number
  note: string | null
  completed_at: string
}

export interface ProjectField {
  id: string
  project_id: string
  name: string
  field_type: 'text' | 'number' | 'date' | 'select'
  options: { choices?: string[] } | null
  position: number
}

export interface FieldValue {
  field_id: string
  value: string | null
}

export interface TaskDependency {
  id: string
  from_task_id: string
  to_task_id: string
  dep_type: string
}

export type WsEvent =
  | { type: 'task_created'; task: string }
  | { type: 'task_updated'; task_id: string }
  | { type: 'task_moved'; task_id: string; status: TaskStatus; position: number }
  | { type: 'task_deleted'; task_id: string }
  | { type: 'comment_added'; task_id: string }
  | { type: 'presence'; user_id: string; action: 'joined' | 'left' }
