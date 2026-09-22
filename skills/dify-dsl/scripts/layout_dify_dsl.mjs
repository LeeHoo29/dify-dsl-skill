#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import ELK from 'elkjs/lib/elk.bundled.js'
import YAML from 'yaml'

const DEFAULT_WIDTH = 244
const DEFAULT_HEIGHT = 90
const ROOT_OFFSET = 80
const CHILD_PADDING_X = 40
const CHILD_PADDING_TOP = 80
const CHILD_PADDING_BOTTOM = 60
const elk = new ELK()

const ROOT_OPTIONS = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.edgeRouting': 'SPLINES',
  'elk.layered.layering.strategy': 'NETWORK_SIMPLEX',
  'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
  'elk.layered.nodePlacement.favorStraightEdges': 'true',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
  'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
  'elk.layered.crossingMinimization.forceNodeModelOrder': 'true',
  'elk.layered.spacing.nodeNodeBetweenLayers': '100',
  'elk.spacing.nodeNode': '80',
  'elk.spacing.edgeNode': '50',
  'elk.spacing.componentComponent': '100',
}

const CHILD_OPTIONS = {
  ...ROOT_OPTIONS,
  'elk.layered.spacing.nodeNodeBetweenLayers': '80',
  'elk.spacing.nodeNode': '60',
  'elk.spacing.edgeNode': '40',
}

function parseArgs(argv) {
  const result = { files: [], write: false, check: false }
  for (const argument of argv) {
    if (argument === '--write') result.write = true
    else if (argument === '--check') result.check = true
    else if (argument.startsWith('-')) throw new Error(`unknown option: ${argument}`)
    else result.files.push(argument)
  }
  if (!result.files.length) throw new Error('provide at least one Dify DSL YAML file')
  if (result.write === result.check) throw new Error('choose exactly one of --write or --check')
  return result
}

function nodeType(node) {
  return node?.data?.type || node?.type || ''
}

function dimensions(node) {
  return {
    width: Number(node.width || node.data?.width || DEFAULT_WIDTH),
    height: Number(node.height || node.data?.height || DEFAULT_HEIGHT),
  }
}

function orderedOutgoing(node, edges) {
  const outgoing = edges.filter(edge => edge.source === node.id)
  const type = nodeType(node)
  if (type === 'if-else') {
    const order = new Map((node.data?.cases || []).map((item, index) => [String(item.case_id || item.id), index]))
    return outgoing.sort((left, right) => {
      const leftHandle = String(left.sourceHandle || '')
      const rightHandle = String(right.sourceHandle || '')
      const leftOrder = leftHandle === 'false' ? 10000 : (order.get(leftHandle) ?? 5000)
      const rightOrder = rightHandle === 'false' ? 10000 : (order.get(rightHandle) ?? 5000)
      return leftOrder - rightOrder
    })
  }
  if (type === 'question-classifier') {
    const classes = node.data?.classes || node.data?.topics || []
    const order = new Map(classes.map((item, index) => [String(item.id || item.case_id), index]))
    return outgoing.sort((left, right) =>
      (order.get(String(left.sourceHandle || '')) ?? 5000)
      - (order.get(String(right.sourceHandle || '')) ?? 5000))
  }
  return outgoing
}

function buildElkGraph(id, nodes, edges, options) {
  const nodeIds = new Set(nodes.map(node => String(node.id)))
  const validEdges = edges.filter(edge => nodeIds.has(String(edge.source)) && nodeIds.has(String(edge.target)))
  const sourcePorts = new Map()
  const children = nodes.map((node) => {
    const outgoing = orderedOutgoing(node, validEdges)
    const ports = outgoing.map((edge, index) => {
      const portId = `${node.id}-out-${index}`
      sourcePorts.set(String(edge.id || `${edge.source}-${edge.target}-${index}`), portId)
      return {
        id: portId,
        layoutOptions: {
          'elk.port.side': 'EAST',
          'elk.port.index': String(index),
        },
      }
    })
    return {
      id: String(node.id),
      ...dimensions(node),
      ...(ports.length ? {
        ports,
        layoutOptions: { 'elk.portConstraints': 'FIXED_ORDER' },
      } : {}),
    }
  })
  const elkEdges = validEdges.map((edge, index) => {
    const edgeId = String(edge.id || `${edge.source}-${edge.target}-${index}`)
    const sourcePort = sourcePorts.get(edgeId)
    return {
      id: `edge-${index}-${edgeId}`,
      sources: [sourcePort || String(edge.source)],
      targets: [String(edge.target)],
    }
  })
  return { id, layoutOptions: options, children, edges: elkEdges }
}

async function layoutGroup(id, nodes, edges, options) {
  if (!nodes.length) return new Map()
  const graph = await elk.layout(buildElkGraph(id, nodes, edges, options))
  const result = new Map()
  for (const child of graph.children || []) {
    result.set(String(child.id), {
      x: Number(child.x || 0),
      y: Number(child.y || 0),
      width: Number(child.width || DEFAULT_WIDTH),
      height: Number(child.height || DEFAULT_HEIGHT),
    })
  }
  return result
}

function groupBounds(layout) {
  if (!layout.size) return { minX: 0, minY: 0, maxX: 0, maxY: 0 }
  const values = [...layout.values()]
  return {
    minX: Math.min(...values.map(item => item.x)),
    minY: Math.min(...values.map(item => item.y)),
    maxX: Math.max(...values.map(item => item.x + item.width)),
    maxY: Math.max(...values.map(item => item.y + item.height)),
  }
}

function applyRelativeLayout(nodes, layout) {
  const bounds = groupBounds(layout)
  for (const node of nodes) {
    const item = layout.get(String(node.id))
    if (!item) continue
    node.position = {
      x: item.x - bounds.minX + CHILD_PADDING_X,
      y: item.y - bounds.minY + CHILD_PADDING_TOP,
    }
    node.width = item.width
    node.height = item.height
    node.selected = false
  }
  return {
    width: Math.max(320, bounds.maxX - bounds.minX + CHILD_PADDING_X * 2),
    height: Math.max(180, bounds.maxY - bounds.minY + CHILD_PADDING_TOP + CHILD_PADDING_BOTTOM),
  }
}

function updateAbsolutePositions(nodes, nodeById) {
  for (const node of nodes) {
    if (!node.parentId) {
      node.positionAbsolute = { ...node.position }
      continue
    }
    const parent = nodeById.get(String(node.parentId))
    if (!parent?.position || !node.position) continue
    node.positionAbsolute = {
      x: Number(parent.position.x) + Number(node.position.x),
      y: Number(parent.position.y) + Number(node.position.y),
    }
  }
}

function rectanglesOverlap(left, right) {
  const a = { ...dimensions(left), ...(left.position || {}) }
  const b = { ...dimensions(right), ...(right.position || {}) }
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y
}

function overlapIssues(nodes) {
  const issues = []
  const groups = new Map()
  for (const node of nodes) {
    if (node.type === 'custom-note') continue
    const key = String(node.parentId || '<root>')
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(node)
  }
  for (const [group, members] of groups) {
    for (let left = 0; left < members.length; left += 1) {
      for (let right = left + 1; right < members.length; right += 1) {
        if (rectanglesOverlap(members[left], members[right])) {
          issues.push(`${group}: nodes ${members[left].id} and ${members[right].id} overlap`)
        }
      }
    }
  }
  return issues
}

function layoutProjection(data) {
  const nodes = data?.workflow?.graph?.nodes || []
  return {
    nodes: nodes.map(node => ({
      id: String(node.id),
      position: node.position || null,
      positionAbsolute: node.positionAbsolute || null,
      width: node.width || null,
      height: node.height || null,
      dataWidth: node.data?.width || null,
      dataHeight: node.data?.height || null,
    })),
    viewport: data?.workflow?.graph?.viewport || null,
  }
}

async function applyLayout(data) {
  const graph = data?.workflow?.graph
  if (!graph || !Array.isArray(graph.nodes) || !Array.isArray(graph.edges)) {
    throw new Error('workflow.graph.nodes and workflow.graph.edges must be arrays')
  }
  const nodes = graph.nodes
  const nodeById = new Map(nodes.map(node => [String(node.id), node]))

  const containers = nodes.filter(node => ['iteration', 'loop'].includes(nodeType(node)))
  for (const container of containers) {
    const children = nodes.filter(node => String(node.parentId || '') === String(container.id))
    const childIds = new Set(children.map(node => String(node.id)))
    const childEdges = graph.edges.filter(edge => childIds.has(String(edge.source)) && childIds.has(String(edge.target)))
    const layout = await layoutGroup(`container-${container.id}`, children, childEdges, CHILD_OPTIONS)
    const size = applyRelativeLayout(children, layout)
    container.width = size.width
    container.height = size.height
    container.data = { ...(container.data || {}), width: size.width, height: size.height }
  }

  const topLevel = nodes.filter(node => !node.parentId && node.type !== 'custom-note')
  const topIds = new Set(topLevel.map(node => String(node.id)))
  const rootEdges = graph.edges.filter(edge => topIds.has(String(edge.source)) && topIds.has(String(edge.target)))
  const rootLayout = await layoutGroup('workflow-root', topLevel, rootEdges, ROOT_OPTIONS)
  const bounds = groupBounds(rootLayout)
  for (const node of topLevel) {
    const item = rootLayout.get(String(node.id))
    if (!item) continue
    node.position = {
      x: item.x - bounds.minX + ROOT_OFFSET,
      y: item.y - bounds.minY + ROOT_OFFSET,
    }
    node.width = item.width
    node.height = item.height
    node.selected = false
  }

  const notes = nodes.filter(node => !node.parentId && node.type === 'custom-note')
  let noteX = ROOT_OFFSET
  const noteY = Math.max(ROOT_OFFSET, bounds.maxY - bounds.minY + ROOT_OFFSET * 2)
  for (const note of notes) {
    note.position = { x: noteX, y: noteY }
    note.selected = false
    noteX += dimensions(note).width + 60
  }

  updateAbsolutePositions(nodes, nodeById)
  graph.viewport = { x: 0, y: 0, zoom: 0.8 }
  return overlapIssues(nodes)
}

async function processFile(file, options) {
  const absolute = path.resolve(file)
  const originalText = fs.readFileSync(absolute, 'utf8')
  const data = YAML.parse(originalText)
  const before = JSON.stringify(layoutProjection(data))
  const overlap = await applyLayout(data)
  if (overlap.length) throw new Error(overlap.join('; '))
  const after = JSON.stringify(layoutProjection(data))
  const changed = before !== after
  if (options.check && changed) {
    console.error(`ERROR: ${file}: layout differs; run with --write`)
    return false
  }
  if (options.write && changed) {
    fs.writeFileSync(absolute, YAML.stringify(data, { lineWidth: 0 }), 'utf8')
  }
  console.log(`${file}: layout ${changed ? (options.write ? 'updated' : 'differs') : 'ok'}; overlaps=0`)
  return true
}

async function main() {
  try {
    const options = parseArgs(process.argv.slice(2))
    let success = true
    for (const file of options.files) success = await processFile(file, options) && success
    process.exitCode = success ? 0 : 1
  } catch (error) {
    console.error(`ERROR: ${error.message}`)
    process.exitCode = 2
  }
}

await main()
