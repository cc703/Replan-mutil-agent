<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { errorText } from './api'
import { actor, labId, labs, refreshLabs, saveActor, selectLab } from './state'

const links = [
  ['/plan', '设备计划'], ['/workbench', '重规划工作台'], ['/chat', '调度对话'],
  ['/versions', '版本与审计'], ['/resources', '资源'], ['/tasks', '任务'],
  ['/import', '导入实例'], ['/sim', '仿真'],
]
const error = ref('')
onMounted(async () => {
  try { await refreshLabs() } catch (cause) { error.value = errorText(cause) }
})
</script>
<template>
  <header class="top">
    <RouterLink to="/plan" class="identity"><span class="mark" aria-hidden="true">◫</span> 实验室调度</RouterLink>
    <div class="top-fields">
      <label>实验室 <select :value="labId" @change="selectLab(($event.target as HTMLSelectElement).value)">
        <option value="" disabled>请选择实验室</option>
        <option v-for="lab in labs" :key="lab.lab_id" :value="lab.lab_id">{{ lab.name }}</option>
      </select></label>
      <label>操作者 <input v-model="actor" maxlength="120" @change="saveActor"></label>
    </div>
  </header>
  <div class="shell">
    <nav aria-label="调度导航">
      <RouterLink v-for="[path, name] in links" :key="path" :to="path">{{ name }}</RouterLink>
    </nav>
    <main>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <RouterView v-slot="{ Component, route }">
        <component :is="Component" v-if="labId || ['/import', '/sim'].includes(route.path)" :key="route.path + ':' + (route.path === '/import' ? '' : labId)" />
        <section v-else class="panel"><h1>开始调度</h1><p>先导入一个实验室实例以生成计划。</p><RouterLink to="/import">导入实例</RouterLink></section>
      </RouterView>
    </main>
  </div>
</template>
