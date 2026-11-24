<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElButton, ElDialog } from 'element-plus'
import { errorText, request } from '../api'
import { actor, displayDate, labPath, pretty } from '../state'
import type { Action, Confirmation, Json } from '../types'
import { changesOf } from '../timeline'
import Diff from './diff.vue'

const emit = defineEmits<{ completed: [] }>()
const labels: Record<Action, string> = {
  EVENT_INJECT: '注入事件', CONSTRAINT_CHANGE: '应用约束',
  PLAN_COMMIT: '提交正式计划', PLAN_ROLLBACK: '回滚计划',
}
interface Operation {
  action: Action
  payload: Json
  endpoint: string
  body: Json
}
const visible = ref(false)
const busy = ref(false)
const accepted = ref(false)
const error = ref('')
const confirmation = ref<Confirmation>()
const operation = ref<Operation>()
const level = computed(() => operation.value?.action.startsWith('PLAN_') ? 'L2' : 'L1')
const planPreview = computed(() => level.value === 'L2' ? confirmation.value?.preview : undefined)
const planChanges = computed(() => changesOf(planPreview.value?.diff ?? planPreview.value?.changes))
const canConfirm = computed(() => level.value === 'L1' || planPreview.value?.validation?.passed === true)
const objectiveLabels = {
  f1: 'f1 加权逾期（槽）',
  f2: 'f2 扰动成本',
  f3: 'f3 急件结束槽之和',
} as const
const objectives = computed(() => Object.entries(objectiveLabels).flatMap(([key, label]) => {
  const value = planPreview.value?.[key as keyof typeof objectiveLabels]
  return typeof value === 'number' && Number.isFinite(value) ? [{ label, value }] : []
}))
let scope = ''
let operator = ''
let previewKey = ''
let confirmKey = ''
let actionKey = ''
let rejectKey = ''

async function perform(task: () => Promise<void>) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try { await task() } catch (cause) { error.value = errorText(cause) }
  finally { busy.value = false }
}
async function loadPreview() {
  const input = operation.value
  if (!input) return
  await perform(async () => {
    if (!operator) throw new Error('请在顶部填写操作者。')
    confirmation.value = await request<Confirmation>(scope + '/confirmations',
      { action: input.action, level: level.value, payload: input.payload, actor: operator }, previewKey)
  })
}
async function start(input: Operation) {
  if (busy.value || visible.value) return
  operation.value = input
  scope = labPath()
  operator = actor.value.trim()
  previewKey = crypto.randomUUID()
  confirmKey = crypto.randomUUID()
  actionKey = crypto.randomUUID()
  rejectKey = crypto.randomUUID()
  accepted.value = false
  confirmation.value = undefined
  visible.value = true
  await loadPreview()
}
async function respond(response: 'confirm' | 'reject') {
  const item = confirmation.value
  if (!item || (response === 'confirm' && !canConfirm.value)) return
  await perform(async () => {
    await request(scope + '/confirmations/' + encodeURIComponent(item.confirmation_id) + '/' + response,
      { actor: operator, payload_hash: item.payload_hash }, response === 'confirm' ? confirmKey : rejectKey)
    if (response === 'confirm') accepted.value = true
    else visible.value = false
  })
}
async function apply() {
  const item = confirmation.value
  const input = operation.value
  if (!item || !input || !accepted.value || !canConfirm.value) return
  await perform(async () => {
    await request(scope + input.endpoint,
      { ...input.body, actor: operator, confirmation_id: item.confirmation_id }, actionKey)
    visible.value = false
    emit('completed')
  })
}
defineExpose({ start })
</script>
<template>
  <ElDialog v-model="visible" :title="level + ' 操作确认'" :close-on-click-modal="false"
    :close-on-press-escape="!busy" :show-close="!busy" width="640px">
    <p v-if="operation"><strong>{{ labels[operation.action] }}</strong> · {{ operator }}</p>
    <p v-if="busy" role="status">正在处理…</p>
    <template v-if="confirmation">
      <p>有效期至 {{ displayDate(confirmation.expires_at) }}（北京时间）</p>
      <p v-if="confirmation.preview?.back_translation">{{ confirmation.preview.back_translation }}</p>
      <p v-for="warning in confirmation.preview?.warnings ?? []" :key="warning" class="notice">{{ warning }}</p>
      <section v-if="level === 'L2'" aria-label="计划预览">
        <p v-if="planPreview?.validation?.passed === true" class="success">独立校验通过。</p>
        <template v-else-if="planPreview?.validation?.passed === false">
          <p class="error" role="alert">计划未通过独立校验，无法确认。</p>
          <pre v-if="planPreview.validation.violations?.length">{{ pretty(planPreview.validation.violations) }}</pre>
        </template>
        <p v-else class="notice">暂未取得独立校验结论，无法确认。</p>
        <dl v-if="objectives.length" class="actions">
          <div v-for="metric in objectives" :key="metric.label">
            <dt>{{ metric.label }}</dt><dd>{{ metric.value }}</dd>
          </div>
        </dl>
        <h3>任务变化</h3>
        <Diff v-if="planPreview?.diff != null || planPreview?.changes != null" :changes="planChanges" />
        <p v-else class="muted">服务未返回任务变化。</p>
      </section>
      <details open><summary>确认内容</summary><pre>{{ pretty(confirmation.preview?.payload ?? operation?.payload) }}</pre></details>
      <p v-if="accepted" class="success" role="status">已确认，请执行操作。</p>
    </template>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <template #footer>
      <ElButton :disabled="busy" @click="visible = false">关闭</ElButton>
      <ElButton v-if="!confirmation && error && operator" :disabled="busy" @click="loadPreview">重试预览</ElButton>
      <template v-if="confirmation && !accepted">
        <ElButton :disabled="busy" @click="respond('reject')">拒绝</ElButton>
        <ElButton type="primary" :disabled="busy || !canConfirm" @click="respond('confirm')">确认 {{ level }}</ElButton>
      </template>
      <ElButton v-if="accepted && operation" type="primary" :disabled="busy" @click="apply">{{ labels[operation.action] }}</ElButton>
    </template>
  </ElDialog>
</template>
