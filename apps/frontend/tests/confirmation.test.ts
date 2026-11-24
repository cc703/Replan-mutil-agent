import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import Confirmation from '../src/components/confirmation.vue'
import { labId } from '../src/state'

const globals = {
  stubs: {
    ElDialog: { props: ['modelValue'], template: '<div v-if="modelValue"><slot/><slot name="footer"/></div>' },
    ElButton: { template: '<button><slot/></button>' },
  },
}
const preview = {
  confirmation_id: 'conf', expires_at: '2026-11-24T08:00:00+08:00', payload_hash: 'hash',
  status: 'PENDING', preview: { payload: { key: 'value' }, back_translation: '回译内容', warnings: ['注意'] },
}
function response(body: object, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }))
}
function setup() {
  labId.value = 'lab'
  const fetcher = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetcher)
  const vm = mount(Confirmation, { global: globals })
  const start = () => vm.vm.start({
    action: 'EVENT_INJECT', payload: { key: 'value' }, endpoint: '/events', body: { client_event_id: 'event' },
  })
  async function button(text: string) {
    const target = vm.findAll('button').find(control => control.text() === text)
    expect(target).toBeDefined()
    await target?.trigger('click')
    await flushPromises()
  }
  return { vm, fetcher, start, button }
}
afterEach(() => vi.unstubAllGlobals())

it('独立预览、确认、应用，重试同一步复用请求键', async () => {
  const { vm, fetcher, start, button } = setup()
  fetcher.mockImplementationOnce(() => response(preview, 201))
    .mockImplementationOnce(() => response({ status: 'CONFIRMED' }))
    .mockRejectedValueOnce(new Error('连接中断'))
    .mockImplementationOnce(() => response({ status: 'RECEIVED' }, 202))
  await start()
  expect(vm.text()).toContain('回译内容')
  expect(vm.text()).toContain('注意')
  expect(vm.findAll('button').map(control => control.text())).not.toContain('注入事件')
  await button('确认 L1')
  expect(fetcher).toHaveBeenCalledTimes(2)
  expect(vm.text()).toContain('已确认，请执行操作')
  await button('注入事件')
  expect(vm.text()).toContain('连接中断')
  await button('注入事件')
  expect(vm.emitted('completed')).toHaveLength(1)
  expect(fetcher.mock.calls.map(call => call[0])).toEqual([
    '/api/v1/labs/lab/confirmations', '/api/v1/labs/lab/confirmations/conf/confirm',
    '/api/v1/labs/lab/events', '/api/v1/labs/lab/events',
  ])
  const keys = fetcher.mock.calls.map(call => (call[1]?.headers as Headers).get('Idempotency-Key'))
  expect(new Set(keys.slice(0, 3)).size).toBe(3)
  expect(keys[2]).toBe(keys[3])
})

it('预览失败时可重试，拒绝时不应用', async () => {
  const { vm, fetcher, start, button } = setup()
  fetcher.mockImplementationOnce(() => response({ error: { code: 'STALE_BASE_VERSION', message: 'changed' } }, 409))
    .mockImplementationOnce(() => response(preview, 201))
    .mockImplementationOnce(() => response({ status: 'REJECTED' }))
  await start()
  expect(vm.text()).toContain('基础版本已变化')
  await button('重试预览')
  await button('拒绝')
  expect(vm.emitted('completed')).toBeUndefined()
  expect(fetcher.mock.calls[2][0]).toBe('/api/v1/labs/lab/confirmations/conf/reject')
})

it('确认过期保留操作错误并阻止执行', async () => {
  const { vm, fetcher, start, button } = setup()
  fetcher.mockImplementationOnce(() => response(preview, 201))
    .mockImplementationOnce(() => response({ error: { code: 'CONFIRMATION_EXPIRED', message: 'expired' } }, 409))
  await start()
  await button('确认 L1')
  expect(vm.text()).toContain('确认已过期')
  expect(vm.findAll('button').map(control => control.text())).not.toContain('注入事件')
})

it('候选 L2 在确认前展示服务器任务变化、独立校验和数值为零的目标', async () => {
  const { vm, fetcher } = setup()
  fetcher.mockImplementationOnce(() => response({
    ...preview,
    preview: {
      payload: { candidate_id: 'candidate' },
      diff: [{ task_id: 'moved-task', moved: true }],
      f1: 0, f2: 2.5, f3: 4,
      validation: { passed: true },
    },
  }, 201))
  await vm.vm.start({ action: 'PLAN_COMMIT', payload: {}, endpoint: '/plans/commit', body: {} })
  expect(vm.text()).toContain('独立校验通过。')
  expect(vm.text()).toContain('moved-task')
  expect(vm.text()).toContain('f1 加权逾期（槽）0')
  expect(vm.text()).toContain('f2 扰动成本2.5')
  expect(vm.text()).toContain('f3 急件结束槽之和4')
  expect(fetcher).toHaveBeenCalledTimes(1)
})

it('回滚 L2 使用 changes，并在校验失败时禁用确认', async () => {
  const { vm, fetcher, button } = setup()
  fetcher.mockImplementationOnce(() => response({
    ...preview,
    preview: {
      payload: { target_version_no: 1 },
      changes: [{ task_id: 'rollback-task', moved: true }],
      validation: { passed: false, violations: ['回滚任务与停机冲突'] },
    },
  }, 201))
  await vm.vm.start({ action: 'PLAN_ROLLBACK', payload: {}, endpoint: '/plans/rollback', body: {} })
  expect(vm.text()).toContain('rollback-task')
  expect(vm.text()).toContain('计划未通过独立校验，无法确认。')
  expect(vm.text()).toContain('回滚任务与停机冲突')
  expect(vm.text()).not.toContain('f1 加权逾期')
  const approve = vm.findAll('button').find(control => control.text() === '确认 L2')
  expect(approve?.attributes()).toHaveProperty('disabled')
  await button('确认 L2')
  expect(fetcher).toHaveBeenCalledTimes(1)
})

it('L2 缺少校验证据时不允许确认', async () => {
  const { vm, fetcher, button } = setup()
  fetcher.mockImplementationOnce(() => response(preview, 201))
  await vm.vm.start({ action: 'PLAN_COMMIT', payload: {}, endpoint: '/plans/commit', body: {} })
  expect(vm.text()).toContain('暂未取得独立校验结论，无法确认。')
  await button('确认 L2')
  expect(fetcher).toHaveBeenCalledTimes(1)
})
