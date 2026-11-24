import type { Assignment, Schedule } from './types'

export interface Change {
  task_id: string
  before?: Assignment | null
  after?: Assignment | null
  added?: boolean
  removed?: boolean
  moved?: boolean
  device_changed?: boolean
  person_changed?: boolean
  start_delta?: number
}
export function changesOf(diff?: Change[] | { changes: Change[] }): Change[] {
  return Array.isArray(diff) ? diff : diff?.changes ?? []
}
const windowClasses: Record<string, string> = { CLOSED: 'closed', MAINT: 'maint', FAULT: 'fault', RUNNING: 'running' }
export function timelineRows(view: Schedule, changes: Change[]) {
  const groups = new Map<string, { id: string; content: string }>()
  for (const device of view.devices) {
    const id = typeof device === 'string' ? device : device.id
    groups.set(id, { id, content: typeof device === 'string' ? device : device.name ?? id })
  }
  const old = changes.flatMap(change => change.before ? [change.before] : [])
  const changed = new Set(changes.map(change => change.task_id))
  for (const row of [...view.assignments, ...view.blocked, ...old]) {
    if (!groups.has(row.device_id)) groups.set(row.device_id, { id: row.device_id, content: row.device_id })
  }
  const assignment = (row: Assignment, index: number, previous: boolean) => ({
    id: (previous ? 'old:' : 'task:') + index,
    group: row.device_id,
    content: row.task_id,
    start: row.start_iso,
    end: row.end_iso,
    type: 'range' as const,
    className: previous ? 'old' : row.late ? 'late' : row.changed || changed.has(row.task_id) ? 'new' : 'task',
  })
  const items = [
    ...view.blocked.map((row, index) => ({
      id: 'window:' + index, group: row.device_id, content: row.kind,
      start: row.start_iso, end: row.end_iso,
      className: windowClasses[row.kind] ?? 'closed',
      type: 'background' as const,
    })),
    ...old.map((row, index) => assignment(row, index, true)),
    ...view.assignments.map((row, index) => assignment(row, index, false)),
  ]
  return { groups: Array.from(groups.values()), items }
}
