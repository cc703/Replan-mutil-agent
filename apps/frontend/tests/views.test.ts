import { readFileSync } from 'node:fs'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { apiError } from '../src/api'
import { displayDate } from '../src/state'
import { changesOf, timelineRows } from '../src/timeline'
import type { Candidate, Job } from '../src/types'
import Diff from '../src/components/diff.vue'
import JobResult from '../src/components/job-result.vue'

function sample<T>(name: string): T {
  return JSON.parse(readFileSync(new URL('../../contracts/examples/' + name + '.json', import.meta.url), 'utf8'))
}
const fixture = sample<{ candidates: Candidate[] }>('replan-ok')
const candidate = fixture.candidates[0]
const base: Job = {
  job_id: 'job', kind: 'REPLAN', status: 'SUCCEEDED', result_status: 'OK',
  base_version_no: 1, event_ids: ['evt'], candidates: [candidate],
}
const global = {
  stubs: {
    Timeline: true,
    ElButton: { template: '<button><slot /></button>' },
  },
}

describe('候选与差异', () => {
  it('只展示独立校验通过且匹配当前版本的候选', async () => {
    const rejected = { ...candidate, candidate_id: 'bad', label: 'bad', validation: { passed: false } }
    const component = mount(JobResult, { props: { job: { ...base, candidates: [candidate, rejected] }, currentVersion: 1 }, global })
    expect(component.findAll('input[type=radio]')).toHaveLength(1)
    expect(component.text()).toContain('急件结束槽之和')
    await component.get('input[type=radio]').setValue(true)
    expect(component.text()).toContain('任务差异')
    await component.findAll('button').find(button => button.text().includes('预览提交'))?.trigger('click')
    expect(component.emitted('commit')?.[0]?.[0]).toEqual(candidate)
    await component.setProps({ currentVersion: 2 })
    expect(component.find('input[type=radio]').exists()).toBe(false)
  })

  it('展示已移动与新增任务的时刻和标识', () => {
    const component = mount(Diff, { props: { changes: changesOf(candidate.diff) } })
    expect(component.text()).toContain('task-a')
    expect(component.text()).toContain('移动')
    expect(component.text()).toContain('新增')
  })

  it('生成设备组、原安排、新安排及所有背景类型', () => {
    const view = { ...candidate.view, blocked: ['CLOSED', 'MAINT', 'FAULT', 'RUNNING'].map(kind => ({
      ...candidate.view.blocked[0], kind,
    })) }
    const { groups, items } = timelineRows(view, changesOf(candidate.diff))
    expect(groups.map(group => group.id)).toEqual(['device-a', 'device-b'])
    expect(items.filter(item => item.type === 'background').map(item => item.className)).toEqual(['closed', 'maint', 'fault', 'running'])
    expect(items.some(item => item.className === 'old')).toBe(true)
    expect(items.some(item => item.className === 'new')).toBe(true)
  })
})

describe('作业未决与提示', () => {
  it('超时保留未决放弃入口且隐藏核和松弛', () => {
    const component = mount(JobResult, { props: {
      job: { ...base, result_status: 'TIMEOUT', conflict: { minimal: true }, relaxations: [{}] }, currentVersion: 1,
    }, global })
    expect(component.text()).toContain('预算内未得出结论')
    expect(component.text()).not.toContain('不可行')
    expect(component.text()).not.toContain('冲突核')
    expect(component.text()).not.toContain('假设提案')
    expect(component.text()).toContain('放弃本次结果')
  })

  it('未证明不可约时不宣称最小，假设没有采纳操作', () => {
    const component = mount(JobResult, { props: {
      job: { ...base, result_status: 'INFEASIBLE', conflict: { minimal: false }, relaxations: [{ hypothetical: true }] }, currentVersion: 1,
    }, global })
    expect(component.text()).toContain('已证明冲突，未证明冲突核不可约')
    expect(component.text()).toContain('任务权重 × 截止期延后槽数')
    expect(component.findAll('button').map(button => button.text())).toEqual(['放弃本次结果'])
  })

  it('映射级别、过期、版本冲突和重复操作并保留追踪号', () => {
    expect(apiError('CONFIRMATION_LEVEL_INSUFFICIENT', '', 'trace').message).toContain('确认级别不符')
    expect(apiError('CONFIRMATION_EXPIRED', '', 'trace').message).toContain('已过期')
    expect(apiError('STALE_BASE_VERSION', '', 'trace').message).toContain('基础版本已变化')
    expect(apiError('DUPLICATE_EVENT_CONFLICT', '', 'trace').message).toContain('追踪号 trace')
  })

  it('固定北京时间', () => {
    expect(displayDate('2026-11-24T00:00:00Z')).toMatch(/08:00:00/)
  })
})
