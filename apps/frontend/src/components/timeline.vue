<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import moment, { type MomentInput } from 'moment'
import { Timeline } from 'vis-timeline/standalone'
import 'vis-timeline/styles/vis-timeline-graph2d.min.css'
import { timelineRows, type Change } from '../timeline'
import type { Schedule } from '../types'

const props = defineProps<{ view: Schedule; changes?: Change[] }>()
const container = ref<HTMLElement>()
let timeline: Timeline | undefined
function plainText(content: string): HTMLElement {
  const node = document.createElement('span')
  node.textContent = content
  return node
}
function render() {
  if (!container.value) return
  timeline?.destroy()
  const { items, groups } = timelineRows(props.view, props.changes ?? [])
  timeline = new Timeline(container.value, items, groups, {
    editable: false,
    showCurrentTime: false,
    maxHeight: '520px',
    horizontalScroll: true,
    zoomKey: 'ctrlKey',
    template: item => plainText(item?.content ?? ''),
    groupTemplate: group => plainText(group?.content ?? ''),
    moment: (date?: MomentInput) => moment(date).utcOffset(480),
    format: { minorLabels: { hour: 'HH:mm' }, majorLabels: { hour: 'YYYY-MM-DD' } },
  })
}
onMounted(render)
watch(() => [props.view, props.changes], render)
onBeforeUnmount(() => timeline?.destroy())
</script>
<template>
  <p class="muted">北京时间（UTC+08:00） · 拖动查看 · Ctrl + 滚轮缩放</p>
  <div class="legend" aria-label="时间线图例">
    <span style="--color:#c7e5df">任务</span><span style="--color:#dadddf">原安排</span>
    <span style="--color:#b5daca">新安排</span><span style="--color:#f5d4a4">延期</span>
    <span style="--color:#e0e6ea">关闭</span><span style="--color:#f7e8bf">维护</span>
    <span style="--color:#f9d9d6">故障</span><span style="--color:#dce3f8">运行中</span>
  </div>
  <div ref="container" class="timeline" aria-label="设备排程时间线"></div>
</template>
