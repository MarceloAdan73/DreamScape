import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion } from 'motion/react'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { DreamIllustration } from '@/components/dream-illustration'
import { useShell } from '@/lib/shell-context'
import { Loader2, Plus, RotateCw, Sparkles, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { DreamRead, ProviderStatus } from '@/lib/types'
import { formatDreamDate } from '@/lib/utils'

const STATUS_LABEL: Record<DreamRead['analysis_status'], string> = {
  pending: 'pendiente',
  processing: 'analizando',
  completed: 'analizado',
  failed: 'falló',
}

const STATUS_VARIANT: Record<DreamRead['analysis_status'], 'default' | 'secondary' | 'destructive'> = {
  pending: 'secondary',
  processing: 'secondary',
  completed: 'default',
  failed: 'destructive',
}

const ACTIVE_STATUSES: DreamRead['analysis_status'][] = ['pending', 'processing']

export function DreamsView() {
  const { container, floating } = useShell()
  const [dreams, setDreams] = useState<DreamRead[]>([])
  const [provider, setProvider] = useState<ProviderStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [text, setText] = useState('')
  const [mood, setMood] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<DreamRead | null>(null)
  const [deleting, setDeleting] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  async function refresh() {
    try {
      const [list, status] = await Promise.all([api.listDreams(), api.providerStatus()])
      setDreams(list.items)
      setProvider(status)
    } finally {
      setLoading(false)
    }
  }

  function stopPolling() {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  function refreshAndPoll() {
    void refresh()
    stopPolling()
    // Mientras quede algún sueño sin terminar, seguimos actualizando solo.
    pollRef.current = setInterval(() => {
      void refresh()
    }, 4000)
  }

  useEffect(() => {
    void refresh()
    return stopPolling
  }, [])

  // Detiene el polling cuando ya no hay sueños en asimilación.
  useEffect(() => {
    if (pollRef.current !== null && !dreams.some((d) => ACTIVE_STATUSES.includes(d.analysis_status))) {
      stopPolling()
    }
  }, [dreams])

  function openSheet() {
    setError(null)
    setSheetOpen(true)
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || saving) return
    setSaving(true)
    setError(null)
    try {
      await api.createDream({ text: trimmed, mood_on_wake: mood.trim() || null })
      setText('')
      setMood('')
      setSheetOpen(false)
      refreshAndPoll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo guardar el sueño.')
    } finally {
      setSaving(false)
    }
  }

  async function handleReanalyze(id: number) {
    try {
      await api.reanalyze(id)
      refreshAndPoll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo reanalizar.')
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    setError(null)
    try {
      await api.deleteDream(deleteTarget.id)
      setDeleteTarget(null)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo eliminar el sueño.')
      setDeleteTarget(null)
    } finally {
      setDeleting(false)
    }
  }

  const analyzing = dreams.some((d) => ACTIVE_STATUSES.includes(d.analysis_status))
  const providerOk = provider?.ok === 'true'

  return (
    <div className="grid gap-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          {dreams.length} {dreams.length === 1 ? 'sueño' : 'sueños'}
          {analyzing && (
            <span className="flex items-center gap-1.5 text-xs">
              <Loader2 className="size-3.5 animate-spin" />
              asimilando…
            </span>
          )}
        </h2>
        {provider && (
          <Badge variant={providerOk ? 'outline' : 'destructive'}>
            {provider.provider}
            {providerOk ? ' · ok' : ' · caído'}
          </Badge>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && dreams.length === 0 && (
        <p className="py-8 text-center text-sm text-muted-foreground">Cargando tus sueños…</p>
      )}

      {!loading && dreams.length === 0 && (
        <div className="mt-4 grid place-items-center gap-3 rounded-3xl border border-dashed border-white/10 px-6 py-10 text-center">
          <DreamIllustration className="w-44" />
          <p className="text-sm text-muted-foreground">
            Todavía no registraste sueños.
            <br />
            Tocá <span className="font-medium text-foreground">+</span> para anotar el primero.
          </p>
          <Button onClick={openSheet}>Registrar mi primer sueño</Button>
        </div>
      )}

      {dreams.length > 0 && (
        <div className="grid gap-3 lg:grid-cols-2">
          {dreams.map((dream) => (
            <article
              key={dream.id}
              className="glass group rounded-2xl border border-white/10 p-4 transition-colors hover:border-white/20"
            >
              <div className="flex items-center justify-between gap-2">
                <Badge variant={STATUS_VARIANT[dream.analysis_status]}>
                  {STATUS_LABEL[dream.analysis_status]}
                </Badge>
                <time
                  dateTime={dream.dreamed_at ?? dream.created_at}
                  className="text-xs text-muted-foreground"
                >
                  {formatDreamDate(dream.dreamed_at, dream.created_at)}
                </time>
              </div>

              <h3 className="mt-2 font-display text-base font-semibold leading-snug">
                {dream.title ??
                  (ACTIVE_STATUSES.includes(dream.analysis_status)
                    ? 'Analizando sueño…'
                    : 'Sueño sin título')}
              </h3>

              <p className="mt-1 line-clamp-4 whitespace-pre-wrap text-sm text-foreground/80">
                {dream.text}
              </p>

              {dream.one_line_insight && (
                <p className="mt-2 flex items-start gap-1.5 text-sm italic text-dream-cyan">
                  <Sparkles className="mt-0.5 size-3.5 shrink-0" />
                  <span>{dream.one_line_insight}</span>
                </p>
              )}

              {dream.analysis_error && (
                <p className="mt-2 text-xs text-destructive">{dream.analysis_error}</p>
              )}

              <div className="mt-3 flex justify-end gap-1">
                {dream.analysis_status === 'failed' && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => void handleReanalyze(dream.id)}
                  >
                    <RotateCw className="size-3.5" />
                    Reanalizar
                  </Button>
                )}
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-label="Eliminar sueño"
                  className="text-muted-foreground hover:text-destructive"
                  onClick={() => setDeleteTarget(dream)}
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}

      {floating &&
        createPortal(
          <motion.button
            type="button"
            onClick={openSheet}
            aria-label="Registrar sueño"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            whileTap={{ scale: 0.9 }}
            transition={{ type: 'spring', stiffness: 400, damping: 24, delay: 0.1 }}
            className="pointer-events-auto absolute bottom-24 right-5 grid size-14 place-items-center rounded-full bg-gradient-to-br from-dream-violet to-dream-pink text-white shadow-xl shadow-dream-violet/40 ring-1 ring-white/20 outline-none focus-visible:ring-2 focus-visible:ring-white/50"
          >
            <Plus className="size-6" />
          </motion.button>,
          floating
        )}

      <Drawer open={sheetOpen} onOpenChange={setSheetOpen} container={container}>
        <DrawerContent>
          <form onSubmit={handleSubmit} className="flex min-h-0 flex-col">
            <DrawerHeader>
              <DrawerTitle>Nuevo sueño</DrawerTitle>
              <DrawerDescription>
                Contá lo que recordás. La IA lo analiza en tu máquina, sin salir de acá.
              </DrawerDescription>
            </DrawerHeader>
            <div className="grid gap-4 overflow-y-auto px-5 py-2">
              <div className="grid gap-1.5">
                <Label htmlFor="dream-text">Relato del sueño</Label>
                <Textarea
                  id="dream-text"
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder="Anoche soñé que…"
                  rows={5}
                  maxLength={20000}
                  autoFocus
                  required
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="dream-mood">Ánimo al despertar</Label>
                <Input
                  id="dream-mood"
                  value={mood}
                  onChange={(event) => setMood(event.target.value)}
                  placeholder="sereno, angustia…"
                  maxLength={32}
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
            </div>
            <DrawerFooter>
              <Button
                type="submit"
                disabled={saving || !text.trim()}
                className="h-11 w-full text-base"
              >
                {saving ? 'Guardando…' : 'Registrar sueño'}
              </Button>
            </DrawerFooter>
          </form>
        </DrawerContent>
      </Drawer>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) setDeleteTarget(null)
        }}
      >
        <AlertDialogContent container={container}>
          <AlertDialogHeader>
            <div className="grid size-11 place-items-center rounded-2xl bg-destructive/15 text-destructive ring-1 ring-destructive/25">
              <Trash2 className="size-5" />
            </div>
            <AlertDialogTitle>¿Eliminar este sueño?</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="text-foreground/90">{deleteTarget?.title ?? 'Este sueño'}</span> va
              a desaparecer del diario, del grafo y de los patrones. Esta acción no se puede
              deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleting}
              onClick={(event) => {
                event.preventDefault()
                void confirmDelete()
              }}
            >
              {deleting ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  Eliminando…
                </>
              ) : (
                'Eliminar'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
