<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { errorText, request } from '../api'
import { parseObject, refreshLabs, selectLab } from '../state'
import type { Lab } from '../types'

const name = ref('')
const json = ref('')
const busy = ref(false)
const error = ref('')
const router = useRouter()

async function readFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    if (file.size > 8 * 1024 * 1024) throw new Error('文件超过 8 MiB。')
    json.value = await file.text()
    error.value = ''
  } catch (cause) { error.value = errorText(cause) }
}
async function submit() {
  busy.value = true
  error.value = ''
  try {
    const lab = await request<Lab>('/labs', { name: name.value.trim(), instance: parseObject(json.value) })
    selectLab(lab.lab_id)
    await refreshLabs()
    await router.push('/workbench')
  } catch (cause) { error.value = errorText(cause) }
  finally { busy.value = false }
}
</script>
<template>
  <h1>导入实例</h1>
  <form class="panel" @submit.prevent="submit">
    <label>实验室名称 <input v-model="name" required maxlength="120"></label>
    <p><label>选择 JSON 文件 <input type="file" accept=".json,application/json" @change="readFile"></label></p>
    <label>实例 JSON <textarea v-model="json" class="code" rows="13" required spellcheck="false"></textarea></label>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p><ElButton native-type="submit" type="primary" :loading="busy">导入实例</ElButton></p>
  </form>
</template>
