export type Json = Record<string, unknown>
export type EventPayload = Json & { type: string }

export interface Lab {
  lab_id: string
  name: string
  active_version_no: number
  undecided_job_id?: string | null
  running_job_id?: string | null
  pending_event_count?: number
}
export interface Window {
  device_id: string
  start_iso: string
  end_iso: string
}
export interface Assignment extends Window {
  task_id: string
  late?: boolean
  changed?: boolean
}
export interface Block extends Window {
  type?: string
  kind: string
  reason?: string
}
export interface Schedule {
  devices: (string | { id: string; name?: string })[]
  assignments: Assignment[]
  blocked: Block[]
}
export interface Candidate {
  candidate_id: string
  label: string
  level: number
  f1: number
  f2: number
  f3: number
  validation: { passed: boolean }
  plan_sha256: string
  diff: import("./timeline").Change[] | { changes: import("./timeline").Change[] }
  view: Schedule
  explanation: unknown
}
export interface Job {
  job_id: string
  kind: string
  status: string
  result_status?: string
  base_version_no: number
  event_ids: string[]
  error?: unknown
  candidates?: Candidate[]
  conflict?: (Json & { minimal?: boolean }) | null
  relaxations?: unknown
}
export interface Version {
  version_no: number
  parent_version_no: number | null
  status: string
  created_at: string
  view?: Schedule
}
export type Action = 'EVENT_INJECT' | 'CONSTRAINT_CHANGE' | 'PLAN_COMMIT' | 'PLAN_ROLLBACK'
export interface Confirmation {
  confirmation_id: string
  level: 'L1' | 'L2'
  payload_hash: string
  preview: {
    payload: Json
    back_translation?: string
    warnings?: string[]
    f1?: number
    f2?: number
    f3?: number
    diff?: Candidate['diff']
    changes?: import('./timeline').Change[]
    validation?: { passed: boolean; violations?: unknown[] }
  }
  expires_at: string
  status: string
}
export interface EventRecord {
  event_id: string
  event: EventPayload
  status: string
  job_id?: string
  created_at: string
}
export interface Decision {
  decision_id: string
  actor: string
  action: string
  subject_id: string
  at: string
  details: Json
}
export interface AgentItem {
  item_id: string
  ir: Json
  back_translation: string
  ambiguities: unknown[]
  event?: EventPayload
  action: 'EVENT_INJECT' | 'CONSTRAINT_CHANGE'
}
export interface AgentTurn {
  session_id: string
  assistant_message: string
  clarifications: unknown[]
  pending_items: AgentItem[]
}
