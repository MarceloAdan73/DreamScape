import { useEffect, useState } from 'react'
import { motion } from 'motion/react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Kicker } from '@/components/ui/kicker'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import {
  CheckCircle2,
  Cloud,
  HardDrive,
  Loader2,
  ShieldCheck,
  TriangleAlert,
  Trash2,
  type LucideIcon,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { RuntimeSettingsRead } from '@/lib/types'
import { cn } from '@/lib/utils'

function Section({
  kicker,
  title,
  description,
  children,
}: {
  kicker: string
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <section className="grid gap-2.5">
      <header className="grid gap-0.5 px-1">
        <Kicker>{kicker}</Kicker>
        <h2 className="font-display text-lg font-semibold leading-snug">{title}</h2>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </header>
      {children}
    </section>
  )
}

function ProviderOption({
  active,
  icon: Icon,
  title,
  subtitle,
  onClick,
}: {
  active: boolean
  icon: LucideIcon
  title: string
  subtitle: string
  onClick: () => void
}) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.97 }}
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'relative grid gap-2.5 rounded-2xl border p-3.5 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/50',
        active
          ? 'border-primary/60 bg-primary/10 ring-1 ring-primary/30'
          : 'border-white/10 bg-white/[0.02] hover:border-white/20'
      )}
    >
      <div className="flex items-center justify-between">
        <div
          className={cn(
            'grid size-8 place-items-center rounded-xl transition-colors',
            active ? 'bg-primary/20 text-primary' : 'bg-white/5 text-muted-foreground'
          )}
        >
          <Icon className="size-4" />
        </div>
        {active && <CheckCircle2 className="size-4 text-primary" />}
      </div>
      <div>
        <p className="text-sm font-medium leading-tight">{title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
      </div>
    </motion.button>
  )
}

export function SettingsView() {
  const [settings, setSettings] = useState<RuntimeSettingsRead | null>(null)
  const [status, setStatus] = useState<{ provider: string; ok: boolean; detail: string } | null>(null)
  const [models, setModels] = useState<{ chat: string[]; embed: string[] } | null>(null)
  const [detecting, setDetecting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirmText, setConfirmText] = useState('')
  const [clearing, setClearing] = useState(false)

  async function load() {
    try {
      const [cfg, providerStatus] = await Promise.all([api.getSettings(), api.providerStatus()])
      setSettings(cfg)
      setStatus({
        provider: providerStatus.provider,
        ok: providerStatus.ok === 'true',
        detail: providerStatus.detail,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar la configuración.')
    }
  }

  useEffect(() => {
    void load()
  }, [])

  function patch(field: keyof RuntimeSettingsRead, value: string) {
    setSettings((prev) => (prev ? { ...prev, [field]: value } : prev))
  }

  async function refreshModels() {
    try {
      const available = await api.listModels()
      setModels({ chat: available.chat, embed: available.embed })
      return available
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudieron listar los modelos.')
      return null
    }
  }

  async function handleDetect() {
    if (!settings || settings.provider !== 'ollama') return
    setDetecting(true)
    setError(null)
    setMessage(null)
    try {
      const [detected, available] = await Promise.all([api.detectSettings(), refreshModels()])
      setSettings(detected)
      const chat = available?.chat ?? [detected.ollama_chat_model]
      if (!chat.includes(detected.ollama_chat_model)) {
        setSettings((prev) => (prev ? { ...prev, ollama_chat_model: chat[0] } : prev))
      }
      setMessage('Modelos detectados y ajustados.')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo detectar.')
    } finally {
      setDetecting(false)
    }
  }

  async function handleSave() {
    if (!settings) return
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const payload: Record<string, string | undefined | null> = {
        provider: settings.provider,
        ollama_base_url: settings.ollama_base_url,
        openai_base_url: settings.openai_base_url,
      }
      if (settings.provider === 'ollama') {
        payload.ollama_chat_model = settings.ollama_chat_model
        payload.ollama_embed_model = settings.ollama_embed_model
        payload.openai_chat_model = null
        payload.openai_embed_model = null
      } else {
        payload.ollama_chat_model = null
        payload.ollama_embed_model = null
        payload.openai_chat_model = settings.openai_chat_model
        payload.openai_embed_model = settings.openai_embed_model
      }
      const updated = await api.updateSettings(payload as never)
      setSettings(updated)
      setMessage('Configuración guardada.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo guardar.')
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveKey(key: string) {
    setError(null)
    setMessage(null)
    try {
      const updated = await api.updateSettings({ provider: settings?.provider ?? 'openai', openai_api_key: key })
      setSettings(updated)
      setMessage('API key guardada (nunca se vuelve a mostrar).')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo guardar la key.')
    }
  }

  async function handleReset() {
    setError(null)
    setMessage(null)
    try {
      const reset = await api.resetSettings()
      setSettings(reset)
      setMessage('Volviste a la configuración por defecto.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo resetear.')
    }
  }

  async function handleDeleteAll() {
    if (confirmText !== 'BORRAR') return
    setClearing(true)
    setError(null)
    setMessage(null)
    try {
      await api.deleteAllDreams()
      window.location.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo reiniciar el diario.')
      setClearing(false)
    }
  }

  if (!settings) {
    return (
      <div className="grid place-items-center gap-3 py-20 text-muted-foreground">
        <Loader2 className="size-6 animate-spin text-dream-violet" />
        <p className="text-sm">Cargando configuración…</p>
      </div>
    )
  }

  const chatModels = models?.chat ?? []
  const embedModels = models?.embed ?? []
  const providerOk = status?.ok === true

  return (
    <div className="grid gap-7 pb-2 lg:mx-auto lg:max-w-2xl">
      <Section
        kicker="Motor de análisis"
        title="Tu IA"
        description="Elegí dónde y con qué modelos se analizan tus sueños."
      >
        <Card>
          <CardContent className="grid gap-5">
            <div className="grid grid-cols-2 gap-2">
              <ProviderOption
                active={settings.provider === 'ollama'}
                icon={HardDrive}
                title="Local"
                subtitle="Ollama · privacidad total"
                onClick={() => patch('provider', 'ollama')}
              />
              <ProviderOption
                active={settings.provider === 'openai'}
                icon={Cloud}
                title="Nube"
                subtitle="API compatible OpenAI"
                onClick={() => patch('provider', 'openai')}
              />
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {settings.provider === 'ollama'
                ? 'Local ejecuta todo en tu máquina: tus sueños nunca salen a internet.'
                : 'La nube envía tus sueños a una API externa para analizarlos — solo elegí nube si lo aceptás.'}
            </p>

            <Separator />

            {settings.provider === 'ollama' && (
              <>
                <div className="grid gap-1.5">
                  <Label htmlFor="ollama-url">Servidor de Ollama</Label>
                  <Input
                    id="ollama-url"
                    value={settings.ollama_base_url}
                    onChange={(event) => patch('ollama_base_url', event.target.value)}
                    placeholder="http://localhost:11434"
                  />
                </div>

                <div>
                  <Button
                    variant="outline"
                    disabled={detecting}
                    onClick={() => void handleDetect()}
                  >
                    {detecting ? (
                      <>
                        <Loader2 className="mr-2 size-4 animate-spin" />
                        Detectando…
                      </>
                    ) : (
                      'Detectar modelos automáticamente'
                    )}
                  </Button>
                </div>

                <Separator />

                <div className="grid gap-1.5">
                  <Label htmlFor="chat-model">Modelo de chat</Label>
                  <Input
                    id="chat-model"
                    list="chat-models"
                    value={settings.ollama_chat_model}
                    onChange={(event) => patch('ollama_chat_model', event.target.value)}
                    placeholder="qwen3.5:9b"
                  />
                  <datalist id="chat-models">
                    {chatModels.map((model) => (
                      <option key={model} value={model} />
                    ))}
                  </datalist>
                  <p className="text-xs text-muted-foreground">
                    {chatModels.length > 0
                      ? `Detectados en tu Ollama: ${chatModels.join(' · ')}`
                      : 'Escribí el nombre exacto de tu modelo (o usá Detectar).'}
                  </p>
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="embed-model">Modelo de embeddings</Label>
                  <Input
                    id="embed-model"
                    list="embed-models"
                    value={settings.ollama_embed_model}
                    onChange={(event) => patch('ollama_embed_model', event.target.value)}
                  />
                  <datalist id="embed-models">
                    {embedModels.map((model) => (
                      <option key={model} value={model} />
                    ))}
                  </datalist>
                </div>
              </>
            )}

            {settings.provider === 'openai' && (
              <>
                <div className="grid gap-1.5">
                  <Label htmlFor="openai-base">URL base de la API</Label>
                  <Input
                    id="openai-base"
                    value={settings.openai_base_url}
                    onChange={(event) => patch('openai_base_url', event.target.value)}
                    placeholder="https://api.openai.com/v1"
                  />
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="openai-key">API key</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      id="openai-key"
                      type="password"
                      placeholder={settings.openai_api_key_set ? '•••••••• (guardada)' : 'sk-…'}
                      onBlur={(event) => {
                        if (event.target.value.trim()) {
                          void handleSaveKey(event.target.value.trim())
                        }
                      }}
                    />
                    {settings.openai_api_key_set && (
                      <CheckCircle2 className="size-4 shrink-0 text-emerald-500" aria-label="Key guardada" />
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Se guarda solo en tu máquina y nunca se muestra de nuevo.
                  </p>
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="openai-chat">Modelo de chat</Label>
                  <Input
                    id="openai-chat"
                    value={settings.openai_chat_model}
                    onChange={(event) => patch('openai_chat_model', event.target.value)}
                    placeholder="gpt-4o-mini"
                  />
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="openai-embed">Modelo de embeddings</Label>
                  <Input
                    id="openai-embed"
                    value={settings.openai_embed_model}
                    onChange={(event) => patch('openai_embed_model', event.target.value)}
                    placeholder="text-embedding-3-small"
                  />
                </div>
              </>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}
            {message && (
              <p className="flex items-center gap-2 text-sm text-emerald-500">
                <CheckCircle2 className="size-4" />
                {message}
              </p>
            )}

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <Button className="w-full sm:w-auto" disabled={saving} onClick={() => void handleSave()}>
                {saving ? 'Guardando…' : 'Guardar configuración'}
              </Button>
              <Button variant="ghost" onClick={() => void handleReset()}>
                Restablecer
              </Button>
            </div>
          </CardContent>
        </Card>
      </Section>

      <Section
        kicker="Privacidad"
        title="Tus sueños, tus reglas"
        description="Estado de la conexión con el motor de análisis."
      >
        <Card>
          <CardContent className="flex items-start gap-3">
            <span className="relative mt-1 flex size-2.5 shrink-0">
              <span
                className={cn(
                  'absolute inline-flex size-full animate-ping rounded-full opacity-50',
                  providerOk ? 'bg-emerald-400' : 'bg-red-400'
                )}
              />
              <span
                className={cn(
                  'relative inline-flex size-2.5 rounded-full',
                  providerOk ? 'bg-emerald-400' : 'bg-red-400'
                )}
              />
            </span>
            <div className="grid gap-1">
              <p className="flex items-center gap-2 text-sm font-medium">
                {providerOk ? 'Motor respondiendo' : 'Sin conexión con el motor'}
                <span className="text-xs font-normal text-muted-foreground">
                  · {status?.provider ?? settings.provider}
                </span>
              </p>
              <p className="text-xs text-muted-foreground">{status?.detail}</p>
              <p className="mt-1 flex items-start gap-1.5 text-xs leading-relaxed text-muted-foreground">
                <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-emerald-500" />
                {settings.provider === 'ollama'
                  ? 'Todo el análisis corre en tu máquina con Ollama. Nada se sube a internet.'
                  : 'Estás usando la nube: tus sueños se envían a una API externa para su análisis.'}
              </p>
            </div>
          </CardContent>
        </Card>
      </Section>

      <Section
        kicker="Tus datos"
        title="Zona de riesgo"
        description="El borrado es irreversible: no hay papelera ni copia de seguridad."
      >
        <Card className="border border-destructive/25 ring-destructive/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <TriangleAlert className="size-4" />
              Borrar todos los sueños
            </CardTitle>
            <CardDescription>
              Se eliminan tus sueños, sus análisis y las conexiones entre ellos.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="confirm-reset">
                Escribí <span className="font-mono">BORRAR</span> para confirmar
              </Label>
              <Input
                id="confirm-reset"
                value={confirmText}
                onChange={(event) => setConfirmText(event.target.value)}
                placeholder="BORRAR"
                autoComplete="off"
              />
            </div>
            <div>
              <Button
                variant="destructive"
                disabled={confirmText !== 'BORRAR' || clearing}
                onClick={() => void handleDeleteAll()}
              >
                {clearing ? (
                  <>
                    <Loader2 className="mr-2 size-4 animate-spin" />
                    Borrando…
                  </>
                ) : (
                  <>
                    <Trash2 className="mr-2 size-4" />
                    Borrar todos los sueños
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      </Section>
    </div>
  )
}
