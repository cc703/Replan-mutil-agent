<script setup lang="ts">
import { displayDate } from '../state'
import type { Change } from '../timeline'
defineProps<{ changes: Change[] }>()
</script>
<template>
  <p v-if="!changes.length" class="muted">任务安排无变化。</p>
  <div v-else class="table-scroll">
    <table>
      <thead><tr><th>任务</th><th>原设备 / 开始</th><th>新设备 / 开始</th><th>变化</th></tr></thead>
      <tbody><tr v-for="row in changes" :key="row.task_id">
        <td>{{ row.task_id }}</td>
        <td>{{ row.before?.device_id ?? '—' }} / {{ displayDate(row.before?.start_iso) }}</td>
        <td>{{ row.after?.device_id ?? '—' }} / {{ displayDate(row.after?.start_iso) }}</td>
        <td>{{ [row.added && '新增', row.removed && '移除', row.moved && '移动', row.device_changed && '换设备', row.person_changed && '换人员'].filter(Boolean).join('、') }}</td>
      </tr></tbody>
    </table>
  </div>
</template>
