<script setup lang="ts">
import { computed, ref } from 'vue'
import { pretty } from '../state'
import { changesOf } from '../timeline'
import type { Candidate, Job } from '../types'
import Diff from './diff.vue'
import Timeline from './timeline.vue'

const props = defineProps<{ job: Job; currentVersion: number }>()
const emit = defineEmits<{ commit: [candidate: Candidate]; discard: [reason: string] }>()
const chosenId = ref('')
const reason = ref('')
const candidates = computed(() => {
  if (props.job.status !== 'SUCCEEDED' || props.job.base_version_no !== props.currentVersion) return []
  return props.job.candidates?.filter(row => row.validation.passed === true) ?? []
})
const selected = computed(() => candidates.value.find(row => row.candidate_id === chosenId.value))
const changes = computed(() => changesOf(selected.value?.diff))
</script>
<template>
  <section class="panel">
    <h2>未决重规划结果</h2>
    <p>基础版本 v{{ job.base_version_no }} · {{ job.event_ids.length }} 项事件</p>
    <p class="notice">此结果会阻塞下一批作业。提交候选或明确放弃后，队列才能继续。</p>
    <template v-if="job.result_status === 'TIMEOUT'">
      <h3>求解超时</h3><p>预算内未得出结论。当前可行性未知。</p>
    </template>
    <template v-else-if="job.result_status === 'INFEASIBLE'">
      <h3>已证明不可行</h3>
      <template v-if="job.conflict">
        <p>{{ job.conflict.minimal === true ? '已证明冲突核不可约。' : '已证明冲突，未证明冲突核不可约。' }}</p>
        <pre>{{ pretty(job.conflict.descriptions ?? job.conflict) }}</pre>
      </template>
      <p v-else>未获得可展示的冲突核。</p>
      <template v-if="Array.isArray(job.relaxations) && job.relaxations.length">
        <h3>假设提案</h3><p>仅限可协商截止期。代价单位为任务权重 × 截止期延后槽数。未授权，不可采纳。</p>
        <pre>{{ pretty(job.relaxations) }}</pre>
      </template>
    </template>
    <template v-else-if="candidates.length">
      <h3>已通过独立校验的候选</h3>
      <div class="table-scroll"><table>
        <thead><tr><th>选择</th><th>候选策略</th><th>f1 加权逾期（槽）</th><th>f2 扰动成本</th><th>f3 急件结束槽之和</th></tr></thead>
        <tbody><tr v-for="row in candidates" :key="row.candidate_id">
          <td><input v-model="chosenId" type="radio" name="candidate" :value="row.candidate_id" :aria-label="'选择 ' + row.label"></td>
          <td>{{ row.label }}</td><td>{{ row.f1 }}</td><td>{{ row.f2 }}</td><td>{{ row.f3 }}</td>
        </tr></tbody>
      </table></div>
      <template v-if="selected">
        <h3 class="spaced">任务差异 · {{ selected.label }}</h3>
        <Diff :changes="changes" />
        <Timeline :view="selected.view" :changes="changes" />
        <details v-if="selected.explanation"><summary>查看候选解释</summary><pre>{{ pretty(selected.explanation) }}</pre></details>
        <p><ElButton type="primary" @click="emit('commit', selected)">预览提交（L2）</ElButton></p>
      </template>
    </template>
    <p v-else class="notice">当前没有可提交的候选。</p>
    <form class="fields spaced" @submit.prevent="emit('discard', reason.trim())">
      <label>放弃原因 <input v-model="reason" required maxlength="500"></label>
      <ElButton native-type="submit" :disabled="!reason.trim()">放弃本次结果</ElButton>
    </form>
  </section>
</template>
