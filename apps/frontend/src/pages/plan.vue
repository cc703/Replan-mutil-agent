<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { errorText, request } from '../api'
import { labPath } from '../state'
import type { Lab, Version } from '../types'
import Timeline from '../components/timeline.vue'

const plan = ref<Version>()
const loaded = ref(false)
const error = ref('')
onMounted(async () => {
  try {
    const lab = await request<Lab>(labPath())
    if (lab.active_version_no > 0) plan.value = await request<Version>(labPath('/plans/' + lab.active_version_no))
    loaded.value = true
  } catch (cause) { error.value = errorText(cause) }
})
</script>
<template>
  <h1>设备计划</h1>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-else-if="!loaded" role="status">正在加载…</p>
  <section v-else class="panel">
    <template v-if="plan">
      <h2>当前正式计划 · v{{ plan.version_no }}</h2>
      <p v-if="plan.status === 'NEEDS_REPLAN'" class="notice">当前事实下的计划需重规划。</p>
      <Timeline v-else-if="plan.view" :view="plan.view" />
    </template>
    <p v-else>尚未提交初始计划。</p>
    <RouterLink v-if="!plan?.view" to="/workbench">前往重规划工作台</RouterLink>
  </section>
</template>
