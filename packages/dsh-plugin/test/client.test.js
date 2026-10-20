import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { NATIVE_TOOLS } from '../dsh/native-tools.mjs'
import { ARGO_ENV_SPECS } from '../dsh/index.js'

/** 在最小沙箱里执行 lazy-CJS bundle，返回 ModuleLoader 收到的定义。 */
function loadBundle() {
  let definition
  const sandbox = {
    window: { __ModuleLoader__: { load: (value) => { definition = value } } },
    console,
  }
  sandbox.globalThis = sandbox
  vm.runInNewContext(readFileSync(new URL('../dsh/client.js', import.meta.url), 'utf8'), sandbox)
  return definition
}

function factory(definition) {
  const React = {
    createElement: () => null,
    useState: () => [undefined, () => {}],
    useEffect: () => {},
    useRef: () => ({ current: new Set() }),
  }
  return definition.factory((id) => {
    if (id === 'react') return React
    throw new Error(`unexpected require: ${id}`)
  })
}

/** 带状态的 React 替身：单次渲染口径，足够驱动 ArgoPanel 完整执行一遍。
 *  register 测试用无状态 factory（只要模块能加载）；渲染测试要真跑组件函数，
 *  所以 useState/useRef 按调用序记进 hooks，测试可预置 tab 再渲染。 */
function statefulReact() {
  const hooks = []
  let idx = 0
  const react = {
    createElement: (type, props, ...children) => ({ type, props: props || {}, children }),
    useState: (init) => {
      const i = idx++
      if (!(i in hooks)) hooks[i] = typeof init === 'function' ? init() : init
      return [hooks[i], (v) => { hooks[i] = typeof v === 'function' ? v(hooks[i]) : v }]
    },
    useEffect: () => {},
    useRef: (init) => {
      const i = idx++
      if (!(i in hooks)) hooks[i] = { current: init }
      return hooks[i]
    },
  }
  return { react, hooks, reset: () => { idx = 0 } }
}

test('client bundle: registers both settings seats for the wide-research namespace', () => {
  const definition = loadBundle()
  assert.equal(definition.id, '@taxueseek/argo-dsh')
  const mod = factory(definition)
  assert.equal(JSON.stringify(mod.inject), JSON.stringify(['slots', 'locale', 'configForms', 'remote', 'remote.credentials']))
  assert.equal(typeof mod.ArgoPanel, 'function')

  const registered = []
  let served = 0
  const form = {
    getSnapshot: () => ({ status: 'ready', value: {}, writable: true }),
    subscribe: () => () => {},
    set: async () => true,
    mutate: async () => true,
  }
  const ctx = {
    configForms: {
      get: (namespace) => {
        assert.equal(namespace, 'wide-research')
        return form
      },
      whileServed: (namespaces, register) => {
        served += 1
        assert.equal(JSON.stringify(namespaces), JSON.stringify(['wide-research']))
        return register(new Set(namespaces))
      },
    },
    slots: {
      inject: (_name, register) => register(),
      register: (options, component) => {
        registered.push({ options, component })
        return () => {}
      },
    },
    locale: { getSnapshot: () => ({ active: 'zh' }), subscribe: () => () => {} },
    remote: { credentials: {}, $on: () => () => {} },
    effect: (callback) => {
      const off = callback()
      if (typeof off === 'function') off()
    },
  }

  mod.apply(ctx)

  assert.equal(served, 1)
  assert.deepEqual(
    registered.map((entry) => entry.options.name).sort(),
    ['plugins.item', 'settings.section'],
  )
  for (const entry of registered) {
    assert.equal(entry.options.id, 'argo')
    assert.equal(entry.options.order, entry.options.name === 'settings.section' ? 26 : 50)
    assert.equal(typeof entry.component, 'function')
    const injected = entry.options.inject()
    assert.equal(injected.hooks.argoForm, form)
    assert.equal(typeof injected.set, 'function')
    assert.equal(typeof injected.mutate, 'function')
  }
})

test('client TOOLS mirror native-tools.mjs (drift gate)', () => {
  // 面板工具表是 native-tools.mjs（mcp_tools.py 生成产物）的手工镜像：argo
  // 增删工具时两边必须同步，否则面板会给出不存在的勾选或漏掉新工具。
  // 注意 [...mod.TOOLS]：client.js 跑在 vm 沙箱里，其数组带沙箱的
  // Array.prototype，直接 map/deepStrictEqual 会因原型不同假红。
  const mod = factory(loadBundle())
  const specNames = Object.keys(NATIVE_TOOLS).sort()
  const toolIds = [...mod.TOOLS].map((tool) => tool.id).sort()
  assert.deepEqual(toolIds, specNames, '面板 TOOLS 与原生工具规格表漂移，请同步两边')
  for (const tool of mod.TOOLS) {
    assert.ok(tool.zh && tool.en, `tool ${tool.id} 缺双语标签`)
    assert.ok(tool.group === 'core' || tool.group === 'long', `tool ${tool.id} 分组非法`)
  }
})

test('client ENGINE_TOGGLES mirror ARGO_ENV_SPECS (drift gate)', () => {
  // 面板引擎开关与 index.js 白名单同一份名单：名字、双语标签、数值域都要对得上。
  const mod = factory(loadBundle())
  const specNames = ARGO_ENV_SPECS.map((spec) => spec.name).sort()
  const toggleNames = [...mod.ENGINE_TOGGLES].map((spec) => spec.name).sort()
  assert.deepEqual(toggleNames, specNames, '面板 ENGINE_TOGGLES 与 index.js ARGO_ENV_SPECS 漂移，请同步两边')
  const specByName = new Map(ARGO_ENV_SPECS.map((spec) => [spec.name, spec]))
  for (const toggle of mod.ENGINE_TOGGLES) {
    const spec = specByName.get(toggle.name)
    assert.equal(toggle.kind, spec.kind, `${toggle.name} kind 不一致`)
    assert.equal(toggle.group, spec.group, `${toggle.name} group 不一致`)
    assert.equal(toggle.invert, spec.invert, `${toggle.name} invert 不一致`)
    assert.equal(toggle.def, spec.def, `${toggle.name} 默认值不一致`)
    assert.ok(toggle.zh && toggle.en && toggle.hintZh && toggle.hintEn, `${toggle.name} 缺双语文案`)
    if (toggle.kind === 'num') {
      assert.ok(toggle.min <= toggle.max, `${toggle.name} min>max`)
      assert.ok(toggle.def >= toggle.min && toggle.def <= toggle.max, `${toggle.name} 默认值越界`)
    }
  }
})

test('ArgoPanel renders every tab without undefined references', () => {
  // node --check 只查语法，查不出渲染路径里的未定义引用；注册测试又不跑组件。
  // 这里用带状态的 React 替身把六个 tab 各完整渲染一遍：任何 tab 的渲染函数
  // 抛错（拼错变量、漏定义助手）都会在这里红，而不是等用户在浏览器里点开。
  const definition = loadBundle()
  const { react, hooks, reset } = statefulReact()
  const mod = definition.factory((id) => {
    if (id === 'react') return react
    throw new Error(`unexpected require: ${id}`)
  })
  const value = {
    nativeTools: ['argo_search', 'argo_fetch'],
    keyRefs: ['DEEPSEEK_API_KEY'],
    argoEnv: ['ARGO_NO_CACHE=1', 'ARGO_PROXY=http://127.0.0.1:7890', 'ARGO_MINHASH_THRESHOLD=0.9'],
    searchProviderEnabled: true,
    fetchProviderEnabled: true,
    searchCommand: 'python3',
    searchArgs: ['mcp_server.py'],
  }
  const props = {
    useArgoForm: (select) => select({ status: 'ready', writable: true, value }),
    set: async () => true,
    mutate: async () => true,
    credentials: {
      describe: async () => ({ ok: true, value: { DEEPSEEK_API_KEY: { configured: true, writable: true, source: 'env' } } }),
      set: async () => ({ ok: true }),
      unset: async () => ({ ok: true }),
    },
    remote: { $on: () => () => {} },
    locale: { getSnapshot: () => ({ active: 'zh' }), subscribe: () => () => {} },
    view: 'page',
  }
  for (const tab of ['access', 'tools', 'engines', 'keys', 'research', 'advanced']) {
    reset()
    hooks.length = 0
    hooks[1] = tab // tab 是 ArgoPanel 的第 2 个 useState
    const tree = mod.ArgoPanel(props)
    assert.ok(tree && tree.type === 'div', `${tab} 应渲染出面板根节点`)
  }
  // 摘要视图（plugins.item 卡片的一行摘要）
  reset()
  hooks.length = 0
  assert.equal(typeof mod.ArgoPanel({ ...props, view: 'summary' }), 'string')

  // 引擎 tab 真实产出：七个分组卡 + 输入控件（防「渲染不抛错但内容是空」）
  reset()
  hooks.length = 0
  hooks[1] = 'engines'
  const flat = []
  // 迷你渲染器：createElement 替身不调用函数组件，这里补上——Card/Switch/
  // Field/PrimaryButton 都要真跑一遍，section/input 节点才存在，组件体里的
  // 未定义引用也才会在这里暴露。注意 React 语义：children 在 props.children
  // 上递给组件（单个 child 不是数组），替身只把 children 挂在节点上，这里补映射。
  const walk = (node) => {
    if (node === null || node === undefined) return
    if (Array.isArray(node)) { node.forEach(walk); return }
    if (typeof node !== 'object') return
    if (typeof node.type === 'function') {
      const props = { ...node.props }
      if (node.children && node.children.length > 0) {
        props.children = node.children.length === 1 ? node.children[0] : node.children
      }
      walk(node.type(props))
      return
    }
    flat.push(node)
    ;(node.children || []).forEach(walk)
  }
  walk(mod.ArgoPanel(props))
  const sections = flat.filter((node) => node.type === 'section')
  assert.ok(sections.length >= 7, `引擎 tab 应渲染 7 个分组卡，实际 ${sections.length}`)
  assert.ok(flat.some((node) => node.type === 'input'), '引擎 tab 应渲染输入控件')
  assert.ok(flat.some((node) => node.type === 'button'), '引擎 tab 应渲染保存按钮')

  // 只读态：表单不可写时渲染不崩（控件禁用由 props 下沉）
  reset()
  hooks.length = 0
  hooks[1] = 'engines'
  const roTree = mod.ArgoPanel({ ...props, useArgoForm: (select) => select({ status: 'ready', writable: false, value }) })
  assert.ok(roTree && roTree.type === 'div')
})
