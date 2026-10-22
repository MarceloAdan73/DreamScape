import { cn } from 'cn'

type DreamIllustrationProps = {
  variant?: 'dreamer' | 'constellation'
  className?: string
}

/**
 * Ilustración propia de DreamScape para estados vacíos.
 * `dreamer`: luna dormida entre la niebla. `constellation`: constelación en espera.
 */
export function DreamIllustration({ variant = 'dreamer', className }: DreamIllustrationProps) {
  return (
    <svg
      viewBox="0 0 200 200"
      fill="none"
      aria-hidden="true"
      className={cn('select-none', className)}
    >
      <defs>
        <radialGradient id="ds-halo" cx="0.5" cy="0.44" r="0.55">
          <stop offset="0" stopColor="var(--dream-violet)" stopOpacity="0.45" />
          <stop offset="0.55" stopColor="var(--dream-cyan)" stopOpacity="0.12" />
          <stop offset="1" stopColor="var(--dream-cyan)" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ds-moon" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#c4b5fd" />
          <stop offset="0.55" stopColor="#a78bfa" />
          <stop offset="1" stopColor="#7dd3fc" />
        </linearGradient>
        <linearGradient id="ds-mist" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.12" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
        <radialGradient id="ds-node" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#e9d5ff" />
          <stop offset="1" stopColor="#8b5cf6" />
        </radialGradient>
        <path
          id="ds-spark"
          d="M0 -7 C0.9 -1.5 1.5 -0.9 7 0 C1.5 0.9 0.9 1.5 0 7 C-0.9 1.5 -1.5 0.9 -7 0 C-1.5 -0.9 -0.9 -1.5 0 -7 Z"
          fill="#e9d5ff"
        />
      </defs>

      {variant === 'dreamer' ? (
        <>
          <circle cx="100" cy="88" r="84" fill="url(#ds-halo)" />

          <g className="ds-twinkle">
            <use href="#ds-spark" transform="translate(40 54) scale(0.75)" />
          </g>
          <g className="ds-twinkle ds-twinkle-delay-1">
            <use href="#ds-spark" transform="translate(160 46) scale(1)" />
          </g>
          <g className="ds-twinkle ds-twinkle-delay-2">
            <use href="#ds-spark" transform="translate(170 104) scale(0.55)" />
          </g>
          <g className="ds-twinkle ds-twinkle-delay-3">
            <use href="#ds-spark" transform="translate(34 112) scale(0.5)" />
          </g>
          <circle cx="62" cy="34" r="1.6" fill="#e9d5ff" opacity="0.5" />
          <circle cx="142" cy="130" r="1.6" fill="#e9d5ff" opacity="0.4" />

          <g className="ds-floaty">
            <circle cx="100" cy="88" r="40" fill="url(#ds-moon)" />
            <path
              d="M84 86 q5 5 10 0"
              stroke="#312e81"
              strokeWidth="2.6"
              strokeLinecap="round"
            />
            <path
              d="M106 86 q5 5 10 0"
              stroke="#312e81"
              strokeWidth="2.6"
              strokeLinecap="round"
            />
            <path
              d="M94 102 q6 5 12 0"
              stroke="#312e81"
              strokeWidth="2.6"
              strokeLinecap="round"
            />
            <circle cx="80" cy="98" r="5" fill="#f9a8d4" opacity="0.32" />
            <circle cx="120" cy="98" r="5" fill="#f9a8d4" opacity="0.32" />
          </g>

          <path
            d="M6 158 C 38 138, 76 168, 110 152 S 174 138, 194 152 L 194 200 L 6 200 Z"
            fill="url(#ds-mist)"
          />
          <path
            d="M0 172 C 48 158, 94 186, 138 170 S 186 160, 200 168 L 200 200 L 0 200 Z"
            fill="url(#ds-mist)"
          />
        </>
      ) : (
        <>
          <circle cx="100" cy="96" r="84" fill="url(#ds-halo)" />

          <g className="ds-twinkle">
            <use href="#ds-spark" transform="translate(150 46) scale(0.85)" />
          </g>
          <g className="ds-twinkle ds-twinkle-delay-1">
            <use href="#ds-spark" transform="translate(44 66) scale(0.6)" />
          </g>
          <g className="ds-twinkle ds-twinkle-delay-2">
            <use href="#ds-spark" transform="translate(168 132) scale(0.7)" />
          </g>
          <circle cx="118" cy="38" r="1.6" fill="#e9d5ff" opacity="0.5" />
          <circle cx="58" cy="146" r="1.6" fill="#e9d5ff" opacity="0.4" />

          <path
            d="M46 128 L78 88 L106 114 L134 72 L162 102"
            stroke="#a78bfa"
            strokeOpacity="0.4"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          <circle cx="78" cy="88" r="3" fill="#c4b5fd" opacity="0.9" />
          <circle cx="134" cy="72" r="3" fill="#c4b5fd" opacity="0.9" />
          <circle cx="162" cy="102" r="3" fill="#c4b5fd" opacity="0.75" />
          <circle cx="46" cy="128" r="3" fill="#c4b5fd" opacity="0.75" />

          <g className="ds-floaty">
            <circle cx="106" cy="114" r="14" fill="url(#ds-halo)" />
            <circle cx="106" cy="114" r="5.5" fill="url(#ds-node)" />
          </g>
        </>
      )}
    </svg>
  )
}
