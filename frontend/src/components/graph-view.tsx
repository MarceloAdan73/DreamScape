import { Canvas, useFrame } from '@react-three/fiber'
import { Billboard, Float, Line, OrbitControls, Sparkles, Stars, Text } from '@react-three/drei'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'

import { Badge } from '@/components/ui/badge'
import { DreamIllustration } from '@/components/dream-illustration'
import { Loader2, RefreshCw, Sparkles as SparklesIcon, X } from 'lucide-react'
import { api } from '@/lib/api'
import type { GraphNode, GraphPayload } from '@/lib/types'
import { cn, formatDreamDate } from '@/lib/utils'

const STATUS_META: Record<GraphNode['analysis_status'], { color: string; label: string }> = {
  completed: { color: '#7dd3fc', label: 'analizado' },
  failed: { color: '#f87171', label: 'falló' },
  processing: { color: '#a78bfa', label: 'analizando' },
  pending: { color: '#94a3b8', label: 'pendiente' },
}

/** Distribución tipo esfera de Fibonacci: pareja y onírica, sin colisiones. */
function computePositions(nodes: GraphNode[]): Map<number, THREE.Vector3> {
  const positions = new Map<number, THREE.Vector3>()
  const count = nodes.length
  if (count === 0) return positions
  if (count === 1) {
    positions.set(nodes[0].id, new THREE.Vector3(0, 0, 0))
    return positions
  }
  const radius = Math.min(2.9 + count * 0.4, 8)
  const golden = Math.PI * (3 - Math.sqrt(5))
  nodes.forEach((node, index) => {
    const y = 1 - (index / (count - 1)) * 2
    const ringRadius = Math.sqrt(1 - y * y)
    const theta = golden * index
    // Jitter onírico: que no quede como esfera matemática perfecta.
    const jitter = 0.18
    const x = Math.cos(theta) * ringRadius * radius + (Math.random() - 0.5) * jitter * radius
    const z = Math.sin(theta) * ringRadius * radius + (Math.random() - 0.5) * jitter * radius
    positions.set(node.id, new THREE.Vector3(x, y * radius, z))
  })
  return positions
}

let _glowTexture: THREE.CanvasTexture | null = null
function glowTexture(): THREE.CanvasTexture {
  if (_glowTexture) return _glowTexture
  const size = 128
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (ctx) {
    const gradient = ctx.createRadialGradient(
      size / 2,
      size / 2,
      0,
      size / 2,
      size / 2,
      size / 2,
    )
    gradient.addColorStop(0, 'rgba(255,255,255,1)')
    gradient.addColorStop(0.3, 'rgba(255,255,255,0.45)')
    gradient.addColorStop(1, 'rgba(255,255,255,0)')
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, size, size)
  }
  _glowTexture = new THREE.CanvasTexture(canvas)
  return _glowTexture
}

function NodeDream({
  node,
  position,
  selected,
  dimmed,
  onSelect,
}: {
  node: GraphNode
  position: THREE.Vector3
  selected: boolean
  dimmed: boolean
  onSelect: (node: GraphNode) => void
}) {
  const groupRef = useRef<THREE.Group>(null)
  const materialRef = useRef<THREE.MeshStandardMaterial>(null)
  const glowRef = useRef<THREE.Sprite>(null)
  const ringRef = useRef<THREE.Sprite>(null)
  const [hovered, setHovered] = useState(false)
  const hue = STATUS_META[node.analysis_status].color

  const glow = useMemo(() => {
    const material = new THREE.SpriteMaterial({
      map: glowTexture(),
      color: hue,
      transparent: true,
      opacity: 0.8,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    const sprite = new THREE.Sprite(material)
    sprite.scale.setScalar(2.2)
    return sprite
  }, [hue])

  /** Halo extra que aparece al seleccionar, como una estrella que se enciende. */
  const ring = useMemo(() => {
    const material = new THREE.SpriteMaterial({
      map: glowTexture(),
      color: '#e9d5ff',
      transparent: true,
      opacity: 0,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    const sprite = new THREE.Sprite(material)
    sprite.scale.setScalar(4.4)
    return sprite
  }, [])

  useEffect(() => {
    document.body.style.cursor = hovered ? 'pointer' : 'auto'
    return () => {
      document.body.style.cursor = 'auto'
    }
  }, [hovered])

  useFrame((state, delta) => {
    const t = state.clock.getElapsedTime()
    const active = selected || hovered
    const targetScale = selected ? 1.5 : hovered ? 1.22 : 1
    if (groupRef.current) {
      const next = THREE.MathUtils.damp(groupRef.current.scale.x, targetScale, 7, delta)
      groupRef.current.scale.setScalar(next)
    }
    if (materialRef.current) {
      const pulse = Math.sin(t * 1.7 + node.id * 0.9) * 0.45
      const target = (active ? 3.1 : 2.3) + pulse
      materialRef.current.emissiveIntensity = THREE.MathUtils.damp(
        materialRef.current.emissiveIntensity,
        target,
        6,
        delta,
      )
    }
    const glowMaterial = glowRef.current?.material as THREE.SpriteMaterial | undefined
    if (glowMaterial) {
      const target = dimmed ? 0.1 : active ? 0.95 : 0.75
      glowMaterial.opacity = THREE.MathUtils.damp(glowMaterial.opacity, target, 6, delta)
    }
    const ringMaterial = ringRef.current?.material as THREE.SpriteMaterial | undefined
    if (ringMaterial) {
      ringMaterial.opacity = THREE.MathUtils.damp(ringMaterial.opacity, selected ? 0.5 : 0, 6, delta)
    }
  })

  const source = node.title?.trim() || node.preview
  const label = source.length > 42 ? `${source.slice(0, 42)}…` : source

  return (
    <Float speed={1.4} rotationIntensity={0.08} floatIntensity={1.1}>
      <group
        position={position}
        onClick={(event) => {
          event.stopPropagation()
          onSelect(node)
        }}
        onPointerOver={(event) => {
          event.stopPropagation()
          setHovered(true)
        }}
        onPointerOut={() => setHovered(false)}
      >
        <group ref={groupRef}>
          <primitive ref={ringRef} object={ring} />
          <primitive ref={glowRef} object={glow} />
          <mesh>
            <sphereGeometry args={[0.3, 32, 32]} />
            <meshStandardMaterial
              ref={materialRef}
              color={hue}
              emissive={hue}
              emissiveIntensity={2.3}
              roughness={0.25}
              transparent
              opacity={dimmed ? 0.45 : 1}
            />
          </mesh>
        </group>
        <Billboard position={[0, 0.62, 0]}>
          <Text
            fontSize={0.24}
            color="#cbd5e1"
            anchorX="center"
            anchorY="bottom"
            maxWidth={5}
            outlineColor="#050816"
            outlineWidth={0.02}
            fillOpacity={dimmed ? 0.25 : 1}
          >
            {label}
          </Text>
        </Billboard>
      </group>
    </Float>
  )
}

function EdgeArc({
  start,
  end,
  similarity,
}: {
  start: THREE.Vector3
  end: THREE.Vector3
  similarity: number
}) {
  const curve = useMemo(() => {
    const mid = start.clone().add(end).multiplyScalar(0.5)
    const direction = end.clone().sub(start).normalize()
    // Curva en 3D: desvío perpendicular para arcos suaves, alzada aleatoria por gracia.
    const perpendicular = new THREE.Vector3(
      -direction.y,
      direction.x,
      direction.z,
    ).normalize()
    // Elevación determinística por geometría (estable entre renders).
    const seed = (start.x + start.y + start.z + end.x + end.y + end.z) * 7919
    const lift = 0.35 + (seed - Math.floor(seed)) * 0.45
    const control = mid.clone().add(perpendicular.multiplyScalar(lift))
    return new THREE.CatmullRomCurve3([start, control, end])
  }, [start, end])

  const points = useMemo(() => curve.getPoints(24), [curve])
  const opacity = Math.max(0.2, Math.min(0.9, similarity))
  return (
    <group>
      {/* Halo ancho y suave, y por encima la línea fina brillante. */}
      <Line
        points={points}
        color="#60a5fa"
        lineWidth={4}
        transparent
        opacity={opacity * 0.28}
      />
      <Line
        points={points}
        color="#93c5fd"
        lineWidth={1.2}
        transparent
        opacity={opacity}
      />
    </group>
  )
}

/** Nebulosa central: da profundidad al fondo sin competir con los nodos. */
function Nebula() {
  const sprite = useMemo(() => {
    const material = new THREE.SpriteMaterial({
      map: glowTexture(),
      color: '#6d28d9',
      transparent: true,
      opacity: 0.18,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    const node = new THREE.Sprite(material)
    node.scale.setScalar(30)
    return node
  }, [])
  return <primitive object={sprite} position={[0, -2, -6]} />
}

function GraphScene({
  payload,
  selectedId,
  onSelect,
}: {
  payload: GraphPayload
  selectedId: number | null
  onSelect: (node: GraphNode) => void
}) {
  const positions = useMemo(() => computePositions(payload.nodes), [payload.nodes])

  const edges = payload.edges
    .map((edge) => {
      const start = positions.get(edge.source)
      const end = positions.get(edge.target)
      if (!start || !end) return null
      return (
        <EdgeArc
          key={`${edge.source}-${edge.target}`}
          start={start}
          end={end}
          similarity={edge.similarity}
        />
      )
    })
    .filter(Boolean)

  return (
    <>
      <color attach="background" args={['#050816']} />
      <fog attach="fog" args={['#050816', 16, 42]} />
      <ambientLight intensity={0.35} />
      <directionalLight position={[6, 8, 4]} intensity={1.1} />
      <pointLight position={[0, 0, 0]} intensity={0.4} color="#7dd3fc" />

      <Nebula />
      <Stars radius={85} depth={55} count={4500} factor={4.2} saturation={0.4} fade speed={0.6} />
      <Sparkles count={130} scale={14} size={2.2} speed={0.35} opacity={0.5} color="#c4b5fd" />

      {payload.nodes.map((node) => {
        const position = positions.get(node.id)
        if (!position) return null
        return (
          <NodeDream
            key={node.id}
            node={node}
            position={position}
            selected={selectedId === node.id}
            dimmed={selectedId !== null && selectedId !== node.id}
            onSelect={onSelect}
          />
        )
      })}
      {edges}

      <OrbitControls
        enablePan
        autoRotate={selectedId === null}
        autoRotateSpeed={0.6}
        enableDamping
        dampingFactor={0.08}
      />
    </>
  )
}

export function GraphView() {
  const [payload, setPayload] = useState<GraphPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<GraphNode | null>(null)

  async function refresh() {
    setLoading(true)
    try {
      const next = await api.graph()
      setPayload(next)
      setSelected(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const nodes = payload?.nodes ?? []
  const edges = payload?.edges ?? []
  const statuses = Array.from(new Set(nodes.map((node) => node.analysis_status)))
  const meta = selected ? STATUS_META[selected.analysis_status] : null

  return (
    <div className="relative h-full w-full overflow-hidden bg-[#050816]">
      {nodes.length > 0 && (
        <Canvas camera={{ position: [0, 3, 13], fov: 55 }} onPointerMissed={() => setSelected(null)}>
          <GraphScene
            payload={payload as GraphPayload}
            selectedId={selected?.id ?? null}
            onSelect={setSelected}
          />
        </Canvas>
      )}

      {loading && nodes.length === 0 && (
        <div className="absolute inset-0 grid place-items-center">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <Loader2 className="size-6 animate-spin text-dream-violet" />
            <p className="text-sm">Tejiendo el mapa de tus sueños…</p>
          </div>
        </div>
      )}

      {!loading && nodes.length === 0 && (
        <div className="absolute inset-0 grid place-items-center px-8">
          <div className="grid justify-items-center gap-3 text-center">
            <DreamIllustration variant="constellation" className="w-40" />
            <div>
              <p className="font-display text-base font-semibold">Tu constelación está vacía</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Registrá sueños y acá aparecerán como estrellas conectadas por lo que comparten.
              </p>
            </div>
          </div>
        </div>
      )}

      {nodes.length > 0 && (
        <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between gap-2 p-4">
          <span className="glass rounded-full border border-white/10 px-3 py-1.5 text-xs text-muted-foreground">
            {nodes.length} {nodes.length === 1 ? 'sueño' : 'sueños'} · {edges.length}{' '}
            {edges.length === 1 ? 'conexión' : 'conexiones'}
          </span>
          <button
            type="button"
            onClick={() => void refresh()}
            aria-label="Actualizar grafo"
            className="glass pointer-events-auto grid size-9 shrink-0 place-items-center rounded-full border border-white/10 text-muted-foreground transition-colors hover:text-foreground"
          >
            <RefreshCw className={cn('size-4', loading && 'animate-spin')} />
          </button>
        </div>
      )}

      <AnimatePresence mode="wait">
        {selected && meta ? (
          <motion.div
            key="node-detail"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 24 }}
            transition={{ type: 'spring', stiffness: 420, damping: 34 }}
            className="absolute inset-x-3 bottom-3"
          >
            <div className="glass-strong rounded-3xl border border-white/10 p-4 shadow-2xl shadow-black/50">
              <div className="flex items-center justify-between gap-2">
                <Badge variant="outline" className="gap-1.5 border-white/15 text-[0.68rem]">
                  <span
                    className="size-1.5 rounded-full"
                    style={{ backgroundColor: meta.color }}
                  />
                  {meta.label}
                </Badge>
                <div className="flex items-center gap-2">
                  <time className="text-xs text-muted-foreground">
                    {formatDreamDate(selected.dreamed_at, selected.created_at)}
                  </time>
                  <button
                    type="button"
                    onClick={() => setSelected(null)}
                    aria-label="Cerrar detalle"
                    className="grid size-7 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground"
                  >
                    <X className="size-4" />
                  </button>
                </div>
              </div>
              <h2 className="mt-2.5 font-display text-base font-semibold leading-snug">
                {selected.title ?? 'Sueño sin título'}
              </h2>
              {selected.mood_on_wake && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Ánimo al despertar:{' '}
                  <span className="text-foreground/80">{selected.mood_on_wake}</span>
                </p>
              )}
              {selected.insight && (
                <p className="mt-2 flex items-start gap-1.5 text-sm italic text-dream-cyan">
                  <SparklesIcon className="mt-0.5 size-3.5 shrink-0" />
                  <span>{selected.insight}</span>
                </p>
              )}
              <p className="mt-2 line-clamp-3 text-sm text-foreground/75">{selected.preview}</p>
            </div>
          </motion.div>
        ) : nodes.length > 0 ? (
          <motion.div
            key="legend"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            transition={{ duration: 0.18 }}
            className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col items-center gap-2 p-4"
          >
            <div className="glass flex flex-wrap items-center justify-center gap-x-3 gap-y-1 rounded-full border border-white/10 px-3.5 py-2 text-[0.68rem] text-muted-foreground">
              {statuses.map((status) => (
                <span key={status} className="flex items-center gap-1.5">
                  <span
                    className="size-1.5 rounded-full"
                    style={{ backgroundColor: STATUS_META[status].color }}
                  />
                  {STATUS_META[status].label}
                </span>
              ))}
            </div>
            <p className="text-[0.65rem] text-muted-foreground/60">
              Arrastrá para girar · Pellizcá para acercar · Tocá una estrella
            </p>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
