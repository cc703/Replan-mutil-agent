<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { errorText, request } from '../api'
import { labPath, pretty } from '../state'
import type { Json } from '../types'

const route = useRoute()
const taskPage = computed(() => route.path === '/tasks')
const data = ref<Record<string, Json[]>>()
const error = ref('')
const tables = computed(() => taskPage.value
  ? [{ key: 'tasks', name: '任务', cols: { id: '任务', experiment_id: '实验', type: '类型', duration: '时长（槽）', release: '释放（槽）', deadline: '截止（槽）', deadline_level: '截止级别', compatible_devices: '兼容设备', status: '状态' } }]
  : [
      { key: 'devices', name: '设备', cols: { id: '设备', type: '类型', capacity: '容量', capabilities: '能力' } },
      { key: 'persons', name: '人员', cols: { id: '人员', skills: '技能' } },
      { key: 'blocked', name: '设备窗口', cols: { device_id: '设备', kind: '类型', start: '开始（槽）', end: '结束（槽）' } },
    ])
onMounted(async () => {
  try { data.value = await request<Record<string, Json[]>>(labPath('/instance')) }
  catch (cause) { error.value = errorText(cause) }
})
function cell(value: unknown) {
  return value === null || value === undefined ? '—' : Array.isArray(value) ? value.join('、') : pretty(value)
}
</script>
<template>
  <h1>{{ taskPage ? '任务' : '资源' }}</h1>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-else-if="!data" role="status">正在加载…</p>
  <section v-for="table in data ? tables : []" :key="table.key" class="panel">
    <h2>{{ table.name }}</h2>
    <p v-if="!data?.[table.key]?.length" class="muted">暂无记录。</p>
    <div v-else class="table-scroll"><table>
      <thead><tr><th v-for="(heading, key) in table.cols" v-show="heading" :key="key">{{ heading }}</th></tr></thead>
      <tbody><tr v-for="(row, index) in data[table.key]" :key="index">
        <td v-for="(heading, key) in table.cols" v-show="heading" :key="key">{{ cell(row[key]) }}</td>
      </tr></tbody>
    </table></div>
  </section>
</template>
