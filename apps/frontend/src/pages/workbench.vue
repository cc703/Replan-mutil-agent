<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { errorText, request } from '../api'
import { actor, displayDate, labPath, pretty } from '../state'
import type { Candidate, EventPayload, EventRecord, Job, Lab } from '../types'
import Confirmation from '../components/confirmation.vue'
import EventForm from '../components/event-form.vue'
import JobResult from '../components/job-result.vue'

const scope = labPath()
const lab = ref<Lab>()
const jobs = ref<Job[]>([])
const events = ref<EventRecord[]>([])
const devices = ref<{ id: string }[]>([])
const error = ref('')
const pollingError = ref('')
const notice = ref('')
const busy = ref(false)
const confirmation = ref<InstanceType<typeof Confirmation>>()
const undecided = computed(() => jobs.value.find(job => job.job_id === lab.value?.undecided_job_id))
const inProgress = computed(() => jobs.value.some(job => ['QUEUED', 'RUNNING'].includes(job.status)))
const statusLabels: Record<string, string> = {
  QUEUED: '排队中', RUNNING: '求解中', SUCCEEDED: '未决', FAILED: '失败', COMMITTED: '已提交',
  DISCARDED: '已放弃', STALE: '已失效', RECEIVED: '已接收', BATCHED: '已组批',
  APPLIED: '已纳入计划', RELEASED: '待再次处理', REJECTED: '已拒绝',
}
let timer: ReturnType<typeof setInterval> | undefined
let refreshing = false
let rerun = false
let disposed = false
async function refresh() {
  if (refreshing) {
    rerun = true
    return
  }
  refreshing = true
  try {
    const [nextLab, nextJobs, nextEvents, instance] = await Promise.all([
      request<Lab>(scope), request<Job[]>(scope + '/jobs'), request<EventRecord[]>(scope + '/events'),
      request<{ devices: { id: string }[] }>(scope + '/instance'),
    ])
    lab.value = nextLab
    const previous = new Map(jobs.value.map(job => [job.job_id, job]))
    jobs.value = nextJobs.map(job => {
      const before = previous.get(job.job_id)
      return before && JSON.stringify(before) === JSON.stringify(job) ? before : job
    })
    events.value = nextEvents
    devices.value = instance.devices
    pollingError.value = ''
  } catch (cause) { pollingError.value = errorText(cause) }
  finally { refreshing = false }
  if (rerun && !disposed) {
    rerun = false
    await refresh()
  }
}
onMounted(() => { void refresh(); timer = setInterval(refresh, 1400) })
onBeforeUnmount(() => { disposed = true; clearInterval(timer) })

async function mutate(endpoint: string, fields: object, message: string) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    if (!actor.value.trim()) throw new Error('请在顶部填写操作者。')
    await request(scope + endpoint, endpoint === '/plans/initial' ? fields : { ...fields, actor: actor.value.trim() })
    notice.value = message
    await refresh()
  } catch (cause) { error.value = errorText(cause) }
  finally { busy.value = false }
}
function preview(event: EventPayload) {
  void confirmation.value?.start({ action: 'EVENT_INJECT', payload: event, endpoint: '/events',
    body: { client_event_id: crypto.randomUUID(), event } })
}
function commit(candidate: Candidate) {
  if (!undecided.value) return
  const { job_id, base_version_no } = undecided.value
  const body = { job_id, candidate_id: candidate.candidate_id, base_version_no }
  void confirmation.value?.start({ action: 'PLAN_COMMIT', endpoint: '/plans/commit',
    payload: { ...body, plan_sha256: candidate.plan_sha256 }, body })
}
function discard(reason: string) {
  if (undecided.value) void mutate('/jobs/' + encodeURIComponent(undecided.value.job_id) + '/discard', { reason }, '已放弃本次作业结果。')
}
function completed() {
  notice.value = '操作已完成。'
  void refresh()
}
</script>
<template>
  <h1>重规划工作台</h1>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="pollingError" class="error" role="alert">{{ pollingError }}</p>
  <p v-if="notice" class="success" role="status">{{ notice }}</p>
  <p v-if="!lab && !pollingError" role="status">正在加载…</p>
  <template v-if="lab">
    <section class="panel">
      <h2>{{ lab.active_version_no ? '当前正式计划 · v' + lab.active_version_no : '初始计划' }}</h2>
      <p v-if="!lab.active_version_no">先生成初始候选，经 L2 确认后提交为 v1。</p>
      <div class="actions">
        <ElButton v-if="!lab.active_version_no" type="primary" :disabled="busy || inProgress || !!lab.undecided_job_id"
          @click="mutate('/plans/initial', {}, '初始作业已入队。')">生成初始计划</ElButton>
        <ElButton v-if="lab.active_version_no && lab.pending_event_count" :disabled="busy || inProgress || !!lab.undecided_job_id"
          @click="mutate('/jobs/retry', {}, '重规划作业已入队。')">重试待处理事件</ElButton>
        <RouterLink v-if="lab.active_version_no" to="/plan">查看设备计划</RouterLink>
      </div>
    </section>
    <section v-if="lab.active_version_no" class="panel"><h2>注入事件</h2>
      <EventForm :devices="devices" @preview="preview" />
    </section>
    <JobResult v-if="undecided" :key="undecided.job_id" :job="undecided"
      :current-version="lab.active_version_no" @commit="commit" @discard="discard" />
    <section class="panel"><h2>作业队列</h2>
      <p v-if="!jobs.length" class="muted">暂无作业。</p>
      <div v-else class="table-scroll"><table>
        <thead><tr><th>作业</th><th>基础版本</th><th>状态</th><th>事件数</th><th>错误</th></tr></thead>
        <tbody><tr v-for="job in jobs" :key="job.job_id">
          <td><details><summary>{{ job.kind === 'INITIAL' ? '初始求解' : '重规划' }}</summary>{{ job.job_id }}</details></td>
          <td>v{{ job.base_version_no }}</td><td>{{ statusLabels[job.status] ?? job.status }}</td>
          <td>{{ job.event_ids.length }}</td><td>{{ job.error ? pretty(job.error) : '—' }}</td>
        </tr></tbody>
      </table></div>
    </section>
    <section class="panel"><h2>事件记录</h2>
      <p v-if="!events.length" class="muted">暂无事件。</p>
      <div v-else class="table-scroll"><table>
        <thead><tr><th>事件</th><th>状态</th><th>接收时间（北京时间）</th></tr></thead>
        <tbody><tr v-for="event in events" :key="event.event_id">
          <td><details><summary>{{ event.event.type === 'DEVICE_OUTAGE' ? '设备停机' : event.event.type === 'URGENT_INSERT' ? '插入急件' : '约束变更' }}</summary><pre>{{ pretty(event.event) }}</pre></details></td>
          <td>{{ statusLabels[event.status] ?? event.status }}</td><td>{{ displayDate(event.created_at) }}</td>
        </tr></tbody>
      </table></div>
    </section>
  </template>
  <Confirmation ref="confirmation" @completed="completed" />
</template>
