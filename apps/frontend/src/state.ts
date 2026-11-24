import { ref } from 'vue'
import { request } from './api'
import type { Lab } from './types'

export const labs = ref<Lab[]>([])
export const labId = ref(sessionStorage.getItem('p7-lab') ?? '')
export const actor = ref(sessionStorage.getItem('p7-actor') ?? '本地操作者')

export function selectLab(id: string) {
  labId.value = id
  sessionStorage.setItem('p7-lab', id)
}
export function saveActor() {
  sessionStorage.setItem('p7-actor', actor.value)
}
export async function refreshLabs() {
  labs.value = await request<Lab[]>('/labs')
  if (!labs.value.some(lab => lab.lab_id === labId.value)) {
    selectLab(labs.value[0]?.lab_id ?? '')
  }
}
export function labPath(path = '', id = labId.value) {
  return '/labs/' + encodeURIComponent(id) + path
}
export function pretty(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2) ?? ''
}
export function parseObject(text: string): Record<string, unknown> {
  const value: unknown = JSON.parse(text)
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('请输入 JSON 对象。')
  }
  return value as Record<string, unknown>
}
const shanghai = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'medium', hourCycle: 'h23',
})
export function displayDate(value?: string | null): string {
  return value && Number.isFinite(Date.parse(value)) ? shanghai.format(new Date(value)) : '—'
}
