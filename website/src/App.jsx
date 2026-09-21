import { Fragment, useEffect, useRef, useState } from 'react'
import {
  Activity,
  ArrowDown,
  ArrowRight,
  BadgeCheck,
  BookOpen,
  Boxes,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clipboard,
  Code2,
  Cpu,
  Database,
  Download,
  FileCheck2,
  FileDiff,
  Gauge,
  GitBranch,
  GitCompareArrows,
  Github,
  KeyRound,
  Layers3,
  LockKeyhole,
  Menu,
  Monitor,
  Moon,
  Network,
  Play,
  Repeat2,
  ScrollText,
  Search,
  Server,
  ShieldCheck,
  Sparkles,
  Star,
  Sun,
  Terminal,
  Undo2,
  Workflow,
  X,
  Zap,
} from 'lucide-react'
import DocsPage from './Docs'
import { siteCopy } from './siteCopy'

const GH_URL = 'https://github.com/acfoundry/Algocode'
const PYPI_URL = 'https://pypi.org/project/algocode-agent/'
const DEFAULT_DOC_PATH = 'getting-started/installation'
const LANGUAGE_STORAGE_KEY = 'algocode-site-language'

function getPreferredLanguage() {
  if (typeof window === 'undefined') return 'zh'
  const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY)
  if (stored === 'zh' || stored === 'en') return stored
  return window.navigator.language?.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

function languageFromHash(hash) {
  if (hash.startsWith('#/docs/en')) return 'en'
  if (hash.startsWith('#/docs/zh')) return 'zh'
  if (hash.startsWith('#/docs')) return 'zh'
  return null
}

function docsPathFromHash(hash) {
  const raw = String(hash || '')
    .replace(/^#\/docs\/(?:zh|en)\/?/, '')
    .replace(/^#\/docs\/?/, '')
    .split('?')[0]
    .replace(/\/+$/, '')
  return raw || DEFAULT_DOC_PATH
}

function docsPath(lang, path = DEFAULT_DOC_PATH) {
  return `#/docs/${lang}/${path}`
}

function Wordmark() {
  return <span className="wordmark">Algocode</span>
}

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash)

  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  return hash
}

function ParticleField() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined

    const ctx = canvas.getContext('2d')
    let width = 0
    let height = 0
    let dpr = 1
    let frame = 0
    let particles = []
    const pointer = { x: -9999, y: -9999 }
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = rect.width
      height = rect.height
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

      const count = Math.min(110, Math.max(38, Math.floor((width * height) / 21000)))
      particles = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.18,
        vy: (Math.random() - 0.5) * 0.18,
        r: Math.random() * 1.15 + 0.55,
        a: Math.random() * 0.35 + 0.14,
        color: Math.random() > 0.68 ? '91, 235, 220' : '130, 160, 190',
      }))
    }

    const onPointerMove = (event) => {
      const rect = canvas.getBoundingClientRect()
      pointer.x = event.clientX - rect.left
      pointer.y = event.clientY - rect.top
    }

    const onPointerLeave = () => {
      pointer.x = -9999
      pointer.y = -9999
    }

    const draw = () => {
      ctx.clearRect(0, 0, width, height)

      for (let i = 0; i < particles.length; i += 1) {
        const p = particles[i]
        p.x += p.vx
        p.y += p.vy

        if (p.x < -10) p.x = width + 10
        if (p.x > width + 10) p.x = -10
        if (p.y < -10) p.y = height + 10
        if (p.y > height + 10) p.y = -10

        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${p.color}, ${p.a})`
        ctx.fill()
      }

      for (let i = 0; i < particles.length; i += 1) {
        for (let j = i + 1; j < particles.length; j += 1) {
          const a = particles[i]
          const b = particles[j]
          const dx = a.x - b.x
          const dy = a.y - b.y
          const dist = Math.sqrt(dx * dx + dy * dy)

          if (dist < 118) {
            ctx.beginPath()
            ctx.moveTo(a.x, a.y)
            ctx.lineTo(b.x, b.y)
            ctx.strokeStyle = `rgba(90, 150, 176, ${(1 - dist / 118) * 0.085})`
            ctx.lineWidth = 1
            ctx.stroke()
          }
        }

        const p = particles[i]
        const pdx = p.x - pointer.x
        const pdy = p.y - pointer.y
        const pdist = Math.sqrt(pdx * pdx + pdy * pdy)

        if (pdist < 180) {
          ctx.beginPath()
          ctx.moveTo(p.x, p.y)
          ctx.lineTo(pointer.x, pointer.y)
          ctx.strokeStyle = `rgba(92, 222, 205, ${(1 - pdist / 180) * 0.16})`
          ctx.lineWidth = 1
          ctx.stroke()
        }
      }

      frame += 1
      if (!reduced) {
        window.requestAnimationFrame(draw)
      }
    }

    resize()
    draw()
    window.addEventListener('resize', resize)
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerleave', onPointerLeave)

    return () => {
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerleave', onPointerLeave)
      window.cancelAnimationFrame(frame)
    }
  }, [])

  return <canvas ref={canvasRef} className="particle-field" aria-hidden="true" />
}

function Reveal({ children, className = '', delay = 0 }) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const node = ref.current
    if (!node) return undefined

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      className={`reveal ${visible ? 'is-visible' : ''} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  )
}

function SectionHeading({ eyebrow, title, description }) {
  return (
    <Reveal className="section-heading">
      <div className="eyebrow">
        <span className="eyebrow-mark" />
        {eyebrow}
      </div>
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
    </Reveal>
  )
}

function Navbar({ lang, copy, onLanguageChange }) {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [theme, setTheme] = useState('dark')
  const navItems = [...copy.nav.items, { label: copy.nav.docsLabel, href: docsPath(lang) }]

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 18)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  return (
    <header className={`site-nav ${scrolled ? 'is-scrolled' : ''}`}>
      <div className="container nav-inner">
        <a className="brand" href="#top" aria-label={copy.nav.homeAria}>
          <img src="./algocode_icon.png" alt="" width="30" height="30" />
          <span><Wordmark /></span>
        </a>

        <nav className={`nav-links ${menuOpen ? 'is-open' : ''}`} aria-label={copy.nav.mainAria}>
          {navItems.map((item) => (
            <a key={item.href} href={item.href} onClick={() => setMenuOpen(false)}>
              {item.label}
            </a>
          ))}
        </nav>

        <div className="nav-actions">
          <a
            className="icon-button nav-github"
            href={GH_URL}
            target="_blank"
            rel="noreferrer"
            aria-label="Algocode GitHub"
          >
            <Github size={18} strokeWidth={1.8} />
          </a>

          <div className="lang-switch" aria-label="Language">
            <button type="button" className={lang === 'zh' ? 'is-active' : ''} onClick={() => onLanguageChange('zh')}>中</button>
            <button type="button" className={lang === 'en' ? 'is-active' : ''} onClick={() => onLanguageChange('en')}>EN</button>
          </div>

          <button
            type="button"
            className="icon-button theme-toggle"
            aria-label={theme === 'dark' ? copy.nav.themeToLight : copy.nav.themeToDark}
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          <a className="button nav-install" href="#install">
            <Download size={16} />
            {copy.nav.install}
          </a>

          <button
            type="button"
            className="icon-button menu-button"
            aria-label={menuOpen ? copy.nav.closeMenu : copy.nav.openMenu}
            onClick={() => setMenuOpen((value) => !value)}
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>
    </header>
  )
}
function TerminalWindow({ title, copyText, children, className = '', labels }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(copyText)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className={`terminal-window ${className}`}>
      <div className="terminal-bar">
        <div className="window-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <div className="terminal-title">{title}</div>
        <button type="button" className="terminal-copy" onClick={copy} aria-label={labels?.copyAria || 'Copy command'}>
          {copied ? <Check size={14} /> : <Clipboard size={14} />}
          <span>{copied ? labels?.copied || 'Copied' : labels?.copy || 'Copy'}</span>
        </button>
      </div>
      <div className="terminal-content">{children}</div>
    </div>
  )
}

function Hero({ copy }) {
  const installText = [
    `algocode doctor  ${copy.hero.comments[0]}`,
    `algocode api  ${copy.hero.comments[1]}`,
    `algocode init  ${copy.hero.comments[2]}`,
    `algocode optimize  ${copy.hero.comments[3]}`,
    '',
    'Task: task_8f2a10',
    'Status: completed',
    'Correctness: passed',
    'Baseline median: 0.7594s',
    'Candidate median: 0.5357s',
    'Improvement: +29.46%',
  ].join('\n')

  return (
    <section className="hero" id="top">

      <div className="container hero-inner">
        <Reveal className="hero-copy">
          <div className="hero-kicker">
            <CircleDot size={14} />
            <span>{copy.hero.kicker}</span>
          </div>

          <h1 className="wordmark">Algocode</h1>
          <p className="hero-lede">
            {copy.hero.lede[0]}
            <br />
            {copy.hero.lede[1]}
          </p>

          <div className="hero-actions">
            <a className="button button-primary" href="#quickstart">
              {copy.hero.primary}
              <ArrowDown size={16} />
            </a>
            <a className="button button-ghost" href={GH_URL} target="_blank" rel="noreferrer">
              <Github size={17} />
              {copy.hero.github}
            </a>
          </div>

          <div className="hero-meta">
            <span>
              <BadgeCheck size={15} />
              Python 3.11+
            </span>
            <span>
              <BadgeCheck size={15} />
              C++ / Python
            </span>
            <span>
              <BadgeCheck size={15} />
              MIT License
            </span>
          </div>
        </Reveal>

        <Reveal delay={120} className="hero-terminal">
          <TerminalWindow title={copy.hero.terminalTitle} copyText={installText} labels={copy.terminal}>
            <div className="terminal-line">
              <span className="prompt">$</span>
              <span className="cmd">algocode doctor</span>
              <span className="comment">{copy.hero.comments[0]}</span>
            </div>
            <div className="terminal-line">
              <span className="prompt">$</span>
              <span className="cmd">algocode api</span>
              <span className="comment">{copy.hero.comments[1]}</span>
            </div>
            <div className="terminal-line">
              <span className="prompt">$</span>
              <span className="cmd">algocode init</span>
              <span className="comment">{copy.hero.comments[2]}</span>
            </div>
            <div className="terminal-line">
              <span className="prompt">$</span>
              <span className="cmd">algocode optimize</span>
              <span className="comment">{copy.hero.comments[3]}</span>
            </div>
            <div className="terminal-line terminal-line-spacer" />
            <div className="terminal-line">
              <span className="outline">Task: task_8f2a10</span>
            </div>
            <div className="terminal-line">
              <span className="outline">Status: </span>
              <span className="success">completed</span>
            </div>
            <div className="terminal-line">
              <span className="outline">Correctness: </span>
              <span className="success">passed</span>
            </div>
            <div className="terminal-line">
              <span className="outline">Baseline median: </span>
              <span className="metric">0.7594s</span>
            </div>
            <div className="terminal-line">
              <span className="outline">Candidate median: </span>
              <span className="metric">0.5357s</span>
            </div>
            <div className="terminal-line">
              <span className="outline">Improvement: </span>
              <span className="success">+29.46%</span>
            </div>
          </TerminalWindow>
        </Reveal>
      </div>
    </section>
  )
}

function Install({ copy, lang }) {
  const installText = 'pip install algocode-agent'

  return (
    <section className="section section-install" id="install">
      <div className="container">
        <div className="install-grid">
          <div className="install-copy">
            <div className="eyebrow">
              <span className="eyebrow-mark" />
              {copy.install.eyebrow}
            </div>
            <h2>{copy.install.title} <Wordmark /></h2>
            <p>{copy.install.description}</p>
            <div className="requirement-row">
              <span>Python 3.11+</span>
              <span>PyPI</span>
            </div>
          </div>

          <Reveal delay={90} className="install-action">
            <TerminalWindow title="pip install — algocode" copyText={installText} className="install-terminal" labels={copy.terminal}>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">pip install algocode-agent</span>
              </div>
            </TerminalWindow>

            <div className="install-buttons">
              <a className="button button-ghost" href={docsPath(lang)}>
                <BookOpen size={16} />
                {copy.install.docs}
              </a>
              <a className="button button-ghost" href={GH_URL} target="_blank" rel="noreferrer">
                <Star size={16} />
                {copy.install.star}
              </a>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  )
}

const capabilityIcons = [FileCheck2, GitBranch, Gauge, Undo2]

function Capabilities({ copy }) {
  return (
    <section className="section section-capabilities" id="capabilities">
      <div className="container">
        <SectionHeading
          eyebrow={copy.capabilities.eyebrow}
          title={copy.capabilities.title}
          description={<>{copy.capabilities.description}</>}
        />
        <div className="capability-grid">
          {copy.capabilities.items.map((item, index) => {
            const Icon = capabilityIcons[index]
            return (
              <Reveal key={item.title} delay={index * 70} className="capability-card">
                <div className="capability-topline">
                  <span className="capability-index">{String(index + 1).padStart(2, '0')}</span>
                  <Icon size={25} strokeWidth={1.45} />
                </div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </Reveal>
            )
          })}
        </div>
      </div>
    </section>
  )
}

const featureIcons = [ShieldCheck, GitCompareArrows, Boxes, LockKeyhole, ScrollText, Activity, Repeat2, Network, Server, Monitor]

function Features({ copy }) {
  return (
    <section className="section section-features" id="features">
      <div className="container">
        <SectionHeading
          eyebrow={copy.features.eyebrow}
          title={copy.features.title}
          description={<>{copy.features.description}</>}
        />
        <div className="feature-grid">
          {copy.features.items.map((item, index) => {
            const Icon = featureIcons[index]
            return (
              <Reveal key={item.title} delay={(index % 5) * 55} className="feature-card">
                <Icon size={21} strokeWidth={1.5} />
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </Reveal>
            )
          })}
        </div>
      </div>
    </section>
  )
}

const quickStartIcons = [Play, KeyRound, Search, Sparkles, BadgeCheck]

function QuickStart({ copy }) {
  const copyText = [
    copy.quickStart.terminal.comments[0],
    'pip install algocode-agent',
    '',
    copy.quickStart.terminal.comments[1],
    'algocode api',
    'algocode doctor',
    '',
    copy.quickStart.terminal.comments[2],
    'algocode init',
    'algocode optimize',
    '',
    copy.quickStart.terminal.comments[3],
    'algocode review',
    'algocode diff',
    'algocode apply <task-id> <candidate-id>',
  ].join('\n')

  return (
    <section className="section section-quickstart" id="quickstart">
      <div className="container">
        <div className="quickstart-grid">
          <div className="quickstart-copy">
            <SectionHeading
              eyebrow={copy.quickStart.eyebrow}
              title={copy.quickStart.title}
              description={copy.quickStart.description}
            />
            <div className="step-list">
              {copy.quickStart.steps.map((step, index) => {
                const Icon = quickStartIcons[index]
                return (
                  <Reveal key={step.title} delay={index * 60} className="step-item">
                    <div className="step-icon">
                      <Icon size={19} strokeWidth={1.7} />
                    </div>
                    <div className="step-content">
                      <div className="step-number">{String(index + 1).padStart(2, '0')}</div>
                      <h3>{step.title}</h3>
                      <p>{step.text}</p>
                    </div>
                  </Reveal>
                )
              })}
            </div>
            <Reveal className="requirement-row">
              {copy.quickStart.requirements.map((requirement) => (
                <span key={requirement}>{requirement}</span>
              ))}
            </Reveal>
          </div>

          <Reveal delay={100} className="quickstart-terminal">
            <TerminalWindow title={copy.quickStart.terminal.title} copyText={copyText} labels={copy.terminal}>
              <div className="terminal-line">
                <span className="comment">{copy.quickStart.terminal.comments[0]}</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">pip install algocode-agent</span>
              </div>
              <div className="terminal-line">
                <span className="success">{copy.quickStart.terminal.installOk}</span>
              </div>
              <div className="terminal-line-spacer" />
              <div className="terminal-line">
                <span className="comment">{copy.quickStart.terminal.comments[1]}</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">algocode api</span>
              </div>
              <div className="terminal-line">
                <span className="success">{copy.quickStart.terminal.providerOk}</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">algocode doctor</span>
              </div>
              <div className="terminal-line">
                <span className="success">{copy.quickStart.terminal.doctorOk}</span>
              </div>
              <div className="terminal-line-spacer" />
              <div className="terminal-line">
                <span className="comment">{copy.quickStart.terminal.comments[2]}</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">algocode init</span>
              </div>
              <div className="terminal-line">
                <span className="success">{copy.quickStart.terminal.contractOk}</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">algocode optimize</span>
              </div>
              <div className="terminal-line">
                <span className="metric">{copy.quickStart.terminal.optimizeStatus}</span>
              </div>
              <div className="terminal-line">
                <span className="metric">{copy.quickStart.terminal.benchmark}</span>
              </div>
              <div className="terminal-line">
                <span className="metric">{copy.quickStart.terminal.improvement}</span>
              </div>
              <div className="terminal-line-spacer" />
              <div className="terminal-line">
                <span className="comment">{copy.quickStart.terminal.comments[3]}</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">algocode review</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">algocode diff</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">algocode apply &lt;task-id&gt; &lt;candidate-id&gt;</span>
              </div>
              <div className="terminal-line">
                <span className="success">{copy.quickStart.terminal.applyOk}</span>
              </div>
            </TerminalWindow>
          </Reveal>
        </div>
      </div>
    </section>
  )
}

const architectureLayers = [
  {
    items: [
      { icon: Terminal, name: 'CLI Commands' },
      { icon: Monitor, name: 'VS Code Extension' },
    ],
  },
  {
    items: [
      { icon: Layers3, name: 'Application Services' },
      { icon: Workflow, name: 'Domain' },
    ],
  },
  {
    items: [
      { icon: Cpu, name: 'Agent Runtime' },
      { icon: Network, name: 'Model Providers' },
      { icon: Code2, name: 'Python / C++ Adapters' },
    ],
  },
  {
    items: [
      { icon: ShieldCheck, name: 'Policy / Approval / Sandbox' },
      { icon: GitBranch, name: 'Git Workspace' },
    ],
  },
  {
    items: [
      { icon: Database, name: 'SQLite Event Store + Projections' },
      { icon: ScrollText, name: 'File Artifact Store' },
    ],
  },
]

function Architecture({ copy }) {
  return (
    <section className="section section-architecture" id="architecture">
      <div className="container architecture-layout">
        <div className="architecture-copy">
          <SectionHeading
            eyebrow={copy.architecture.eyebrow}
            title={copy.architecture.title}
            description={copy.architecture.description}
          />
          <Reveal className="request-path">
            <div className="request-path-label">{copy.architecture.requestPath}</div>
            <div className="path-flow">
              {copy.architecture.flow.map((item, index) => (
                <Fragment key={item}>
                  <span>{item}</span>
                  {index < copy.architecture.flow.length - 1 ? <ChevronRight size={15} /> : null}
                </Fragment>
              ))}
            </div>
            <p>{copy.architecture.note}</p>
          </Reveal>
        </div>

        <Reveal delay={90} className="architecture-stack">
          {architectureLayers.map((layer, layerIndex) => (
            <div className="architecture-layer" key={copy.architecture.layers[layerIndex].label}>
              <div className="architecture-layer-label">{copy.architecture.layers[layerIndex].label}</div>
              <div className="architecture-layer-items">
                {layer.items.map((item, itemIndex) => {
                  const Icon = item.icon
                  return (
                    <div
                      className="architecture-node"
                      key={item.name}
                      style={{ animationDelay: `${layerIndex * 60 + itemIndex * 40}ms` }}
                    >
                      <Icon size={16} strokeWidth={1.7} />
                      <span>{item.name}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </Reveal>
      </div>
    </section>
  )
}

function Usage({ copy }) {
  return (
    <section className="section section-usage" id="usage">
      <div className="container">
        <SectionHeading
          eyebrow={copy.usage.eyebrow}
          title={copy.usage.title}
          description={copy.usage.description}
        />
        <div className="usage-grid">
          <Reveal className="usage-card">
            <div className="usage-card-head">
              <div className="usage-icon">
                <Terminal size={23} strokeWidth={1.6} />
              </div>
              <div>
                <span className="usage-tag">{copy.usage.cards[0].tag}</span>
                <h3>{copy.usage.cards[0].title}</h3>
              </div>
            </div>
            <p>{copy.usage.cards[0].text}</p>
            <div className="usage-commands">
              <code>algocode init</code>
              <code>algocode optimize</code>
              <code>algocode review</code>
              <code>algocode apply</code>
              <code>algocode rollback</code>
            </div>
          </Reveal>

          <Reveal delay={90} className="usage-card">
            <div className="usage-card-head">
              <div className="usage-icon">
                <Monitor size={23} strokeWidth={1.6} />
              </div>
              <div>
                <span className="usage-tag">{copy.usage.cards[1].tag}</span>
                <h3>{copy.usage.cards[1].title}</h3>
              </div>
            </div>
            <p>{copy.usage.cards[1].text}</p>
            <div className="usage-checklist">
              {copy.usage.cards[1].checklist.map((item) => (
                <span key={item}>
                  <CheckCircle2 size={15} />
                  {item}
                </span>
              ))}
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  )
}

function Footer({ copy }) {
  return (
    <footer className="footer">
      <div className="container footer-grid">
        <div className="footer-brand">
          <div className="footer-logo">
            <img src="./algocode_icon.png" alt="" width="38" height="38" />
            <span><Wordmark /></span>
          </div>
          <p>{copy.footer.description}</p>
        </div>

        <div className="footer-column">
          <h3>{copy.footer.resources}</h3>
          <a href={GH_URL} target="_blank" rel="noreferrer">
            GitHub
            <ArrowRight size={13} />
          </a>
          <a href={PYPI_URL} target="_blank" rel="noreferrer">
            PyPI
            <ArrowRight size={13} />
          </a>
          <a href={`${GH_URL}/issues`} target="_blank" rel="noreferrer">
            Issues
            <ArrowRight size={13} />
          </a>
        </div>

        <div className="footer-declaration">
          <div className="footer-declaration-mark">
            <Zap size={16} />
            <span>{copy.footer.declarationTitle}</span>
          </div>
          <p>{copy.footer.declaration}</p>
        </div>
      </div>

      <div className="container footer-bottom">
        <span>© 2026 <Wordmark /> {copy.footer.contributors}</span>
        <span>{copy.footer.license}</span>
      </div>
    </footer>
  )
}

export default function App() {
  const hash = useHashRoute()
  const isDocs = hash.startsWith('#/docs')
  const routeLanguage = languageFromHash(hash)
  const [lang, setLang] = useState(() => routeLanguage || getPreferredLanguage())
  const copy = siteCopy[lang]

  useEffect(() => {
    if (routeLanguage && routeLanguage !== lang) {
      setLang(routeLanguage)
    }
  }, [routeLanguage, lang])

  useEffect(() => {
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en'
    document.title = copy.metadata.title
    document.querySelector('meta[name="description"]')?.setAttribute('content', copy.metadata.description)
  }, [lang, copy.metadata.description, copy.metadata.title])

  const changeLanguage = (nextLanguage) => {
    setLang(nextLanguage)
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage)
    if (isDocs) {
      window.location.hash = docsPath(nextLanguage, docsPathFromHash(hash))
    }
  }

  return (
    <>
      <div className="site-background" aria-hidden="true">
        <div className="site-grid" />
        <div className="site-light" />
        <ParticleField />
      </div>
      <Navbar lang={lang} copy={copy} onLanguageChange={changeLanguage} />
      <main>
        {isDocs ? (
          <DocsPage route={hash} lang={lang} />
        ) : (
          <>
            <Hero copy={copy} />
            <Install copy={copy} lang={lang} />
            <Capabilities copy={copy} />
            <Features copy={copy} />
            <QuickStart copy={copy} />
            <Architecture copy={copy} />
            <Usage copy={copy} />
          </>
        )}
      </main>
      <Footer copy={copy} />
    </>
  )
}
