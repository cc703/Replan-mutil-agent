<script setup lang="ts">
import { ref } from 'vue'
import { errorText, request } from '../api'
import { actor, labPath, parseObject, pretty } from '../state'
import type { AgentItem, AgentTurn, EventPayload } from '../types'
import Confirmation from '../components/confirmation.vue'

const scope = labPath()
const text = ref('')
const session = ref<string>()
const history = ref<{ text: string; turn: AgentTurn }[]>([])
const drafts = ref<Record<string, string>>({})
const editing = ref(new Set<string>())
const handled = ref(new Set<string>())
const confirmation = ref<InstanceType<typeof Confirmation>>()
const activeItem = ref('')
const success = ref('')
const busy = ref(false)
const error = ref('')
async function send() {
  const message = text.value.trim()
  if (!message || busy.value) return
  if (!actor.value.trim()) {
    error.value = '请在顶部填写操作者。'
    return
  }
  error.value = ''
  success.value = ''
  busy.value = true
  try {
    const turn = await request<AgentTurn>(scope + '/agent/turn', { text: message, session_id: session.value, actor: actor.value.trim() })
    session.value = turn.session_id
    history.value.push({ text: message, turn })
    for (const item of turn.pending_items ?? []) drafts.value[item.item_id] = pretty(item.event ?? item.ir)
    text.value = ''
  } catch (cause) { error.value = errorText(cause) }
  finally { busy.value = false }
}
function lowConfidenceFields(value: unknown, prefix = ''): string[] {
  if (!value || typeof value !== 'object') return []
  const fields = Object.entries(value)
  return fields.flatMap(([key, child]) => {
    if (key === 'confidence' && typeof child === 'number' && child < 0.8) return [prefix + ' (' + child + ')']
    return lowConfidenceFields(child, prefix ? prefix + '.' + key : key)
  })
}
function edit(item: AgentItem) {
  if (item.event) editing.value.add(item.item_id)
  else text.value = '请修订以下截止期提案，并重新预览。' + item.back_translation
}
function preview(item: AgentItem) {
  activeItem.value = item.item_id
  error.value = ''
  try {
    if (item.action === 'CONSTRAINT_CHANGE') {
      const payload = { ir_item_id: item.item_id }
      void confirmation.value?.start({ action: item.action, payload, endpoint: '/constraints', body: payload })
      return
    }
    const event = parseObject(drafts.value[item.item_id] ?? '') as EventPayload
    if (event.type !== 'DEVICE_OUTAGE' && event.type !== 'URGENT_INSERT') throw new Error('请选择设备停机或插入急件。')
    void confirmation.value?.start({ action: 'EVENT_INJECT', payload: event, endpoint: '/events',
      body: { client_event_id: crypto.randomUUID(), event } })
  } catch (cause) { error.value = errorText(cause) }
}
function completed() {
  handled.value.add(activeItem.value)
  success.value = '已确认并登记。可在重规划工作台查看处理状态。'
}
</script>
<template>
  <h1>调度对话</h1>
  <p class="muted">描述设备停机、急件或截止期变更。请检查回译与待确认内容。</p>
  <section v-for="(entry, index) in history" :key="index" class="panel">
    <h2>对话回合 {{ index + 1 }}</h2>
    <p><strong>你</strong> · {{ entry.text }}</p>
    <p><strong>调度助手</strong> · {{ entry.turn.assistant_message }}</p>
    <div v-if="entry.turn.clarifications?.length" class="notice">
      <h3>需要澄清</h3>
      <ul><li v-for="(question, questionIndex) in entry.turn.clarifications" :key="questionIndex">{{ pretty(question) }}</li></ul>
    </div>
    <fieldset v-for="item in entry.turn.pending_items ?? []" :key="item.item_id">
      <legend>L1 确认卡片</legend>
      <p>{{ item.back_translation }}</p>
      <p v-if="item.ambiguities?.length || lowConfidenceFields(item.ir).length" class="notice">
        低置信度或待核对字段 · {{ pretty(item.ambiguities?.length ? item.ambiguities : lowConfidenceFields(item.ir).join('、')) }}
      </p>
      <label v-if="editing.has(item.item_id)">事件字段 <textarea v-model="drafts[item.item_id]" class="code" rows="7"></textarea></label>
      <details v-else><summary>查看提案字段</summary><pre>{{ drafts[item.item_id] }}</pre></details>
      <p v-if="handled.has(item.item_id)" class="success">已登记</p>
      <div v-else class="actions spaced">
        <ElButton @click="edit(item)">{{ item.event ? '编辑事件字段' : '通过对话修订截止期' }}</ElButton>
        <ElButton type="primary" @click="preview(item)">预览并确认（L1）</ElButton>
      </div>
    </fieldset>
  </section>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="success" class="success" role="status">{{ success }}</p>
  <form class="panel" @submit.prevent="send">
    <label>调度需求或澄清回复 <textarea v-model="text" rows="4" required></textarea></label>
    <p><ElButton type="primary" native-type="submit" :loading="busy">发送</ElButton></p>
  </form>
  <Confirmation ref="confirmation" @completed="completed" />
</template>
