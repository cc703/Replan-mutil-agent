<script setup lang="ts">
import { ref } from 'vue'
import { errorText } from '../api'
import { parseObject } from '../state'
import type { EventPayload } from '../types'

defineProps<{ devices: { id: string }[] }>()
const emit = defineEmits<{ preview: [event: EventPayload] }>()
const type = ref('DEVICE_OUTAGE')
const device = ref('')
const start = ref('')
const end = ref('')
const urgent = ref('')
const error = ref('')
function preview() {
  error.value = ''
  try {
    if (type.value === 'DEVICE_OUTAGE') {
      if (start.value >= end.value) throw new Error('结束时间须晚于开始时间。')
      emit('preview', {
        type: type.value, device_id: device.value,
        start: start.value + '+08:00', end: end.value + '+08:00',
      })
      return
    }
    const body = parseObject(urgent.value)
    if (!Array.isArray(body.tasks) || !body.tasks.length) throw new Error('急件须含有 tasks 数组。')
    emit('preview', { ...body, type: type.value })
  } catch (cause) { error.value = errorText(cause) }
}
</script>
<template>
  <form @submit.prevent="preview">
    <div class="fields">
      <label>事件类型 <select v-model="type"><option value="DEVICE_OUTAGE">设备停机</option><option value="URGENT_INSERT">插入急件</option></select></label>
      <template v-if="type === 'DEVICE_OUTAGE'">
        <label>设备 <select v-model="device" aria-label="设备" required>
          <option value="" disabled>选择设备</option>
          <option v-for="row in devices" :key="row.id" :value="row.id">{{ row.id }}</option>
        </select></label>
        <label>停机开始（北京时间） <input v-model="start" type="datetime-local" required></label>
        <label>停机结束（北京时间） <input v-model="end" type="datetime-local" required></label>
      </template>
    </div>
    <template v-if="type === 'URGENT_INSERT'">
      <p class="muted">编辑急件 JSON。tasks 中每项需含 id、experiment_id、type、duration_minutes、compatible_devices。可选 release 和 deadline 使用带时区偏移的时间。precedences 可指定先后关系。</p>
      <label>急件 JSON <textarea v-model="urgent" class="code" rows="8" required spellcheck="false"></textarea></label>
    </template>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p><ElButton type="primary" native-type="submit">预览事件（L1）</ElButton></p>
  </form>
</template>
