import { useEffect, useState } from 'react'
import { motion } from 'motion/react'

import { Button } from '@/components/ui/button'
import { DreamIllustration } from '@/components/dream-illustration'
import { Kicker } from '@/components/ui/kicker'
import { BookOpen, Loader2, Sparkles } from 'lucide-react'
import { api } from '@/lib/api'
import type { EntityType, Pattern } from '@/lib/types'

const TYPE_META: Record<EntityType, { label: string; color: string }> = {
  symbol: { label: 'símbolos', color: 'var(--dream-violet)' },
  emotion: { label: 'emociones', color: 'var(--dream-pink)' },
  person: { label: 'personas', color: 'var(--dream-cyan)' },
  place: { label: 'lugares', color: 'oklch(0.72 0.13 160)' },
}

function paragraphsOf(reading: string): string[] {
  return reading
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
}

export function PatternsView() {
  const [patterns, setPatterns] = useState<Pattern[]>([])
  const [analyzed, setAnalyzed] = useState(0)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [reading, setReading] = useState<string | null>(null)
  const [readingDetail, setReadingDetail] = useState<string | null>(null)

  async function refresh() {
    setLoading(true)
    try {
      const response = await api.patterns()
      setPatterns(response.patterns)
      setAnalyzed(response.dreams_analyzed)
      setReading(null)
      setReadingDetail(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function generateReading() {
    setGenerating(true)
    setReading(null)
    setReadingDetail(null)
    try {
      const response = await api.patternsReading()
      setReading(response.reading)
      setReadingDetail(response.detail)
    } catch (error) {
      setReadingDetail(error instanceof Error ? error.message : 'No se pudo generar la lectura.')
    } finally {
      setGenerating(false)
    }
  }

  const sorted = [...patterns].sort((a, b) => b.dream_count - a.dream_count)
  const maxCount = Math.max(2, ...sorted.map((pattern) => pattern.dream_count))
  const presentTypes = Array.from(new Set(sorted.map((pattern) => pattern.type)))
  const paragraphs = reading ? paragraphsOf(reading) : []

  if (loading) {
    return (
      <div className="grid gap-4">
        <div className="grid place-items-center gap-3 py-20 text-muted-foreground">
          <Loader2 className="size-6 animate-spin text-dream-violet" />
          <p className="text-sm">Buscando lo que se repite…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-6">
      <section className="relative overflow-hidden rounded-3xl border border-white/10 bg-card/70">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-24 left-1/2 h-48 w-80 -translate-x-1/2 rounded-full bg-dream-violet/25 blur-3xl"
        />
        <div className="relative grid gap-4 p-5 lg:max-w-[72ch]">
          <div className="flex items-start gap-3">
            <div className="grid size-10 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-dream-violet/30 to-dream-cyan/20 text-dream-violet ring-1 ring-white/10">
              <BookOpen className="size-5" />
            </div>
            <div>
              <Kicker className="text-dream-cyan">Lectura del subconsciente</Kicker>
              <h2 className="mt-1 font-display text-lg font-semibold leading-snug">
                El hilo que une tus sueños
              </h2>
            </div>
          </div>

          {generating && (
            <div className="grid place-items-center gap-3 py-6 text-muted-foreground">
              <Loader2 className="size-5 animate-spin text-dream-violet" />
              <p className="text-sm">La IA está leyendo tus sueños…</p>
            </div>
          )}

          {!generating && paragraphs.length > 0 && (
            <div className="grid gap-3 lg:max-w-[68ch]">
              {paragraphs.map((paragraph, index) => (
                <p
                  key={index}
                  className={
                    index === 0
                      ? 'text-[0.95rem] leading-relaxed text-foreground/90'
                      : 'text-sm leading-relaxed text-muted-foreground'
                  }
                >
                  {paragraph}
                </p>
              ))}
            </div>
          )}

          {!generating && paragraphs.length === 0 && (
            <p className="text-sm leading-relaxed text-muted-foreground">
              {readingDetail ??
                'Generá una lectura y la IA va a conectar los sueños que comparten símbolos, emociones y personas para mostrar qué tema se repite en tu subconsciente.'}
            </p>
          )}

          <Button
            size="lg"
            className="h-11 w-full gap-2 text-base lg:justify-self-start lg:w-auto lg:px-8"
            onClick={() => void generateReading()}
            disabled={generating || patterns.length === 0}
          >
            {generating ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Tejiendo la lectura…
              </>
            ) : (
              <>
                <Sparkles className="size-4" />
                {reading ? 'Regenerar lectura' : 'Generar lectura'}
              </>
            )}
          </Button>

          {patterns.length === 0 && (
            <p className="text-center text-xs text-muted-foreground">
              La lectura se activa con al menos 2 sueños analizados que compartan un tema.
            </p>
          )}
        </div>
      </section>

      {sorted.length === 0 ? (
        <section className="grid justify-items-center gap-3 rounded-3xl border border-dashed border-white/10 px-6 py-10 text-center">
          <DreamIllustration variant="constellation" className="w-36" />
          <div>
            <p className="font-display text-base font-semibold">
              {analyzed > 0 ? 'Aún no hay temas repetidos' : 'Todavía no hay sueños analizados'}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {analyzed > 0
                ? 'Seguí registrando sueños: cuando dos compartan un símbolo o una emoción, va a aparecer acá.'
                : 'Registrá sueños y la IA va a extraer sus símbolos, emociones, personas y lugares.'}
            </p>
          </div>
        </section>
      ) : (
        <section className="grid gap-3">
          <header className="flex items-end justify-between gap-2 px-1">
            <div>
              <Kicker className="text-dream-pink">Temas que se repiten</Kicker>
              <h2 className="mt-1 font-display text-lg font-semibold leading-snug">
                Tu vocabulario onírico
              </h2>
            </div>
            <p className="shrink-0 text-xs text-muted-foreground">
              {analyzed} {analyzed === 1 ? 'sueño' : 'sueños'} analizados
            </p>
          </header>

          <div className="flex flex-wrap items-baseline gap-2">
            {sorted.map((pattern, index) => {
              const meta = TYPE_META[pattern.type]
              const size = 0.78 + (pattern.dream_count / maxCount) * 0.42
              return (
                <motion.span
                  key={`${pattern.type}-${pattern.name}`}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: Math.min(index * 0.025, 0.5), duration: 0.22 }}
                  title={`${meta.label} · aparece en ${pattern.dream_count} ${
                    pattern.dream_count === 1 ? 'sueño' : 'sueños'
                  }`}
                  className="inline-flex cursor-default items-baseline gap-1.5 rounded-full border px-3 py-1 leading-none"
                  style={{
                    fontSize: `${size}rem`,
                    borderColor: `color-mix(in oklch, ${meta.color} 45%, transparent)`,
                    backgroundColor: `color-mix(in oklch, ${meta.color} 12%, transparent)`,
                  }}
                >
                  <span>{pattern.name}</span>
                  <span className="text-[0.7em] opacity-70" style={{ color: meta.color }}>
                    ×{pattern.dream_count}
                  </span>
                </motion.span>
              )
            })}
          </div>

          <div className="flex flex-wrap gap-x-3 gap-y-1 px-1 text-[0.68rem] text-muted-foreground">
            {presentTypes.map((type) => (
              <span key={type} className="flex items-center gap-1.5">
                <span
                  className="size-1.5 rounded-full"
                  style={{ backgroundColor: TYPE_META[type].color }}
                />
                {TYPE_META[type].label}
              </span>
            ))}
            <span className="opacity-60">el tamaño indica cuánto se repite</span>
          </div>
        </section>
      )}
    </div>
  )
}
