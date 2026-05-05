import { useRef, useEffect, useState, useCallback } from 'react'

interface GraphNode {
  id: string
  label: string
  source_system: string
  group: string
  x?: number
  y?: number
  vx?: number
  vy?: number
}

interface GraphEdge {
  source: string
  target: string
  weight: number
}

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  width?: number
  height?: number
}

const DEPT_COLORS: Record<string, string> = {
  SHOP_EST: '#6ba8ff',
  FACTORIES: '#f5a524',
  LABOUR: '#2dd4a4',
  KSPCB: '#f24c5c',
  GST: '#a78bfa',
}

export default function ForceGraph({ nodes: inputNodes, edges, width = 500, height = 350 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null)
  const nodesRef = useRef<GraphNode[]>([])
  const animRef = useRef<number>(0)

  // Initialize node positions
  useEffect(() => {
    const cx = width / 2
    const cy = height / 2
    nodesRef.current = inputNodes.map((n, i) => ({
      ...n,
      x: cx + (Math.cos((2 * Math.PI * i) / inputNodes.length) * 100) + (Math.random() - 0.5) * 30,
      y: cy + (Math.sin((2 * Math.PI * i) / inputNodes.length) * 100) + (Math.random() - 0.5) * 30,
      vx: 0,
      vy: 0,
    }))
  }, [inputNodes, width, height])

  // Force simulation + render loop
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    canvas.width = width * dpr
    canvas.height = height * dpr
    ctx.scale(dpr, dpr)

    let frame = 0
    const maxFrames = 200
    const alpha = () => Math.max(0, 1 - frame / maxFrames)

    const simulate = () => {
      const nodes = nodesRef.current
      if (nodes.length === 0) return

      const cx = width / 2
      const cy = height / 2
      const a = alpha()

      // Forces
      for (const node of nodes) {
        node.vx = (node.vx || 0) * 0.85
        node.vy = (node.vy || 0) * 0.85

        // Center gravity
        node.vx! += (cx - node.x!) * 0.005 * a
        node.vy! += (cy - node.y!) * 0.005 * a
      }

      // Repulsion between all nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x! - nodes[i].x!
          const dy = nodes[j].y! - nodes[i].y!
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
          const force = (80 * a) / (dist * dist)
          nodes[i].vx! -= (dx / dist) * force
          nodes[i].vy! -= (dy / dist) * force
          nodes[j].vx! += (dx / dist) * force
          nodes[j].vy! += (dy / dist) * force
        }
      }

      // Edge attraction
      const nodeMap = new Map(nodes.map(n => [n.id, n]))
      for (const edge of edges) {
        const s = nodeMap.get(edge.source)
        const t = nodeMap.get(edge.target)
        if (!s || !t) continue
        const dx = t.x! - s.x!
        const dy = t.y! - s.y!
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
        const force = (dist - 80) * 0.01 * a
        s.vx! += (dx / dist) * force
        s.vy! += (dy / dist) * force
        t.vx! -= (dx / dist) * force
        t.vy! -= (dy / dist) * force
      }

      // Apply velocities + boundary
      for (const node of nodes) {
        node.x = Math.max(30, Math.min(width - 30, node.x! + node.vx!))
        node.y = Math.max(30, Math.min(height - 30, node.y! + node.vy!))
      }

      // ─── Draw ───
      ctx.clearRect(0, 0, width, height)

      // Edges
      for (const edge of edges) {
        const s = nodeMap.get(edge.source)
        const t = nodeMap.get(edge.target)
        if (!s || !t) continue
        ctx.beginPath()
        ctx.moveTo(s.x!, s.y!)
        ctx.lineTo(t.x!, t.y!)
        ctx.strokeStyle = 'rgba(46, 124, 255, 0.15)'
        ctx.lineWidth = 1.5
        ctx.stroke()
      }

      // Nodes
      for (const node of nodes) {
        const color = DEPT_COLORS[node.source_system] || '#6b7488'
        const isHovered = hoveredNode?.id === node.id
        const radius = isHovered ? 14 : 10

        // Glow
        if (isHovered) {
          ctx.beginPath()
          ctx.arc(node.x!, node.y!, 20, 0, 2 * Math.PI)
          ctx.fillStyle = color + '20'
          ctx.fill()
        }

        // Circle
        ctx.beginPath()
        ctx.arc(node.x!, node.y!, radius, 0, 2 * Math.PI)
        ctx.fillStyle = color
        ctx.fill()
        ctx.strokeStyle = isHovered ? '#fff' : color + '60'
        ctx.lineWidth = isHovered ? 2 : 1
        ctx.stroke()

        // Label
        ctx.font = `${isHovered ? '11px' : '9px'} Inter, sans-serif`
        ctx.fillStyle = isHovered ? '#e6ebf5' : '#9ba6b8'
        ctx.textAlign = 'center'
        ctx.fillText(node.label.slice(0, 18), node.x!, node.y! + radius + 14)

        // Dept badge
        ctx.font = '8px JetBrains Mono, monospace'
        ctx.fillStyle = color + 'aa'
        ctx.fillText(node.source_system, node.x!, node.y! + radius + 24)
      }

      frame++
      if (frame < maxFrames) {
        animRef.current = requestAnimationFrame(simulate)
      }
    }

    simulate()

    return () => cancelAnimationFrame(animRef.current)
  }, [inputNodes, edges, width, height, hoveredNode])

  // Mouse hover detection
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top

    let found: GraphNode | null = null
    for (const node of nodesRef.current) {
      const dx = mx - node.x!
      const dy = my - node.y!
      if (dx * dx + dy * dy < 15 * 15) {
        found = node
        break
      }
    }
    setHoveredNode(found)
  }, [])

  if (inputNodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-sm" style={{ color: 'var(--text-tertiary)' }}>
        No graph data available
      </div>
    )
  }

  return (
    <div className="relative">
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{ width, height, cursor: hoveredNode ? 'pointer' : 'default' }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredNode(null)}
      />
      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-2 justify-center">
        {Object.entries(DEPT_COLORS).map(([dept, color]) => (
          <div key={dept} className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full" style={{ background: color }} />
            <span className="text-[9px] font-mono" style={{ color: 'var(--text-tertiary)' }}>{dept}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
