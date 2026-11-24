const messages: Record<string, string> = {
  VALIDATION_ERROR: '提交的数据有误，请检查输入。',
  TIME_NOT_ALIGNED: '请检查时间是否与实验室的时间槽对齐。',
  UNKNOWN_ENTITY: '指定的设备或任务不存在。',
  UNSUPPORTED_EVENT: '此事件类型暂不支持。',
  UNSUPPORTED_CONSTRAINT_TYPE: '此约束类型暂不支持。',
  INVALID_EVENT: '事件无法用于当前实例，请检查内容。',
  INVALID_INSTANCE: '实例数据无效，请检查 JSON。',
  NOT_FOUND: '记录不存在，请刷新页面。',
  STALE_BASE_VERSION: '基础版本已变化，请刷新后重新选择和确认。',
  IDEMPOTENCY_KEY_REUSED: '同一请求标识已用于其他内容，请重新发起操作。',
  DUPLICATE_EVENT_CONFLICT: '同一事件标识已用于不同内容，请核对事件列表。',
  JOB_NOT_COMMITTABLE: '作业当前无法提交，请刷新并查看结果。',
  CANDIDATE_NOT_FOUND: '候选已不可用，请刷新结果。',
  CONFIRMATION_REQUIRED: '缺少确认，请先完成所需级别的确认。',
  CONFIRMATION_NOT_CONFIRMED: '确认尚未完成，请先确认。',
  CONFIRMATION_CONSUMED: '该确认已使用，请核对操作是否已生效。',
  CONFIRMATION_EXPIRED: '确认已过期，请重新预览。',
  CONFIRMATION_MISMATCH: '确认的内容或实验室已变化，请重新预览。',
  CONFIRMATION_LEVEL_INSUFFICIENT: '确认级别不符，请重新发起正确级别的确认。',
  LAB_BUSY: '实验室仍有运行中或未决的作业，请先处理。',
  PAYLOAD_TOO_LARGE: '数据超过 8 MiB，请缩小输入。',
  VALIDATION_FAILED: '计划未通过独立校验，请处理当前作业。',
  ROLLBACK_INFEASIBLE: '目标计划在当前事实下未通过校验，回滚被拒绝。',
  PLAN_INTEGRITY_ERROR: '计划完整性检查失败。',
  SCHEDULER_UNAVAILABLE: '调度服务暂不可用。',
  LLM_UNAVAILABLE: '对话服务暂不可用。',
  LLM_OUTPUT_INVALID: '对话输出未通过校验，请重新描述需求。',
  SCHEDULER_TIMEOUT: '调度服务请求已超时，请核对作业状态。',
  INTERNAL_ERROR: '服务处理失败，请按追踪号检查日志。',
}

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
export function apiError(code: string, message: string, trace?: string): Error {
  return new Error([messages[code], message, trace && '追踪号 ' + trace].filter(Boolean).join(' '))
}
export async function request<T>(path: string, body?: object, key: string = crypto.randomUUID()): Promise<T> {
  const headers = new Headers({ 'X-Trace-Id': crypto.randomUUID() })
  if (body !== undefined) {
    headers.set('Content-Type', 'application/json')
    headers.set('Idempotency-Key', key)
  }
  const response = await fetch('/api/v1' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const error = data?.error
    throw apiError(error?.code, error?.message ?? 'HTTP ' + response.status,
      error?.trace_id ?? response.headers.get('X-Trace-Id'))
  }
  return data as T
}
