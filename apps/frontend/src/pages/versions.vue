<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { errorText, request } from '../api'
import { displayDate, labPath, pretty } from '../state'
import type { Decision, Lab, Version } from '../types'
import type { Change } from '../timeline'
import Diff from '../components/diff.vue'
import Timeline from '../components/timeline.vue'
import Confirmation from '../components/confirmation.vue'

const lab = ref<Lab>()
const versions = ref<Version[]>([])
const decisions = ref<Decision[]>([])
const selected = ref<Version>()
const changes = ref<Change[]>([])
const confirmation = ref<InstanceType<typeof Confirmation>>()
const isActive = computed(() => selected.value?.version_no === lab.value?.active_version_no)
const error = ref('')
const loading = ref(false)
let generation = 0
async function reload() {
  try {
    const scope = labPath()
    const result = await Promise.all([
      request<Lab>(scope), request<Version[]>(scope + '/plans'), request<Decision[]>(scope + '/decisions'),
    ])
    ;[lab.value, versions.value, decisions.value] = result
  } catch (cause) { error.value = errorText(cause) }
}
async function open(version: Version) {
  const run = ++generation
  loading.value = true
  error.value = ''
  selected.value = undefined
  try {
    const path = labPath('/plans/' + version.version_no)
    const plan = await request<Version>(path)
    const diff = plan.view && version.parent_version_no
      ? await request<{ changes: Change[] }>(path + '/diff?base=' + version.parent_version_no)
      : { changes: [] }
    if (run !== generation) return
    selected.value = plan
    changes.value = diff.changes
  } catch (cause) { if (run === generation) error.value = errorText(cause) }
  finally { if (run === generation) loading.value = false }
}
function rollback() {
  if (!selected.value || !lab.value || isActive.value) return
  const payload = { target_version_no: selected.value.version_no, base_version_no: lab.value.active_version_no }
  void confirmation.value?.start({ action: 'PLAN_ROLLBACK', payload, endpoint: '/plans/rollback', body: payload })
}
async function rolledBack() {
  selected.value = undefined
  await reload()
}
onMounted(reload)
</script>
<template>
  <h1>版本与审计</h1>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <section class="panel">
    <h2>计划版本</h2>
    <p v-if="!versions.length" class="muted">暂无计划版本。</p>
    <div v-else class="table-scroll"><table>
      <thead><tr><th>版本</th><th>父版本</th><th>状态</th><th>创建时间（北京时间）</th><th>详情</th></tr></thead>
      <tbody><tr v-for="version in versions" :key="version.version_no">
        <td>v{{ version.version_no }}</td><td>{{ version.parent_version_no ? 'v' + version.parent_version_no : '—' }}</td>
        <td>{{ version.version_no === lab?.active_version_no ? '当前版本' : '历史版本' }}</td>
        <td>{{ displayDate(version.created_at) }}</td>
        <td><ElButton @click="open(version)">查看 v{{ version.version_no }}</ElButton></td>
      </tr></tbody>
    </table></div>
  </section>
  <p v-if="loading" role="status">正在加载版本…</p>
  <section v-if="selected" class="panel">
    <h2>{{ isActive ? '当前版本' : '历史版本' }} · v{{ selected.version_no }}</h2>
    <p v-if="selected.status === 'NEEDS_REPLAN'" class="notice">当前事实下的计划需重规划。</p>
    <template v-if="selected.view">
      <p v-if="!isActive" class="muted">使用该版本归档时的校验证据。</p>
      <Timeline :view="selected.view" :changes="changes" />
      <h3>与父版本的任务变化</h3><Diff :changes="changes" />
      <p v-if="!isActive"><ElButton @click="rollback">预览回滚（L2）</ElButton></p>
    </template>
  </section>
  <section class="panel"><h2>决策日志</h2>
    <p v-if="!decisions.length" class="muted">暂无决策记录。</p>
    <div v-else class="table-scroll"><table>
      <thead><tr><th>时间（北京时间）</th><th>操作者</th><th>动作</th><th>对象</th><th>明细</th></tr></thead>
      <tbody><tr v-for="row in decisions" :key="row.decision_id">
        <td>{{ displayDate(row.at) }}</td><td>{{ row.actor }}</td><td>{{ row.action }}</td><td>{{ row.subject_id }}</td>
        <td><details><summary>查看</summary><pre>{{ pretty(row.details) }}</pre></details></td>
      </tr></tbody>
    </table></div>
  </section>
  <Confirmation ref="confirmation" @completed="rolledBack" />
</template>
