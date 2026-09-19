import { useEffect, useRef, useState } from 'react'
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

const GH_URL = 'https://github.com/Duck755/Algocode'
const PYPI_URL = 'https://pypi.org/project/algocode-agent/'
const DOCS_PATH = '#/docs/getting-started/installation'

const navItems = [
  { label: '能力', href: '#capabilities' },
  { label: '特性', href: '#features' },
  { label: '快速开始', href: '#quickstart' },
  { label: '架构', href: '#architecture' },
  { label: '使用形态', href: '#usage' },
  { label: '文档', href: DOCS_PATH },
]

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

function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [lang, setLang] = useState('zh')
  const [theme, setTheme] = useState('dark')

  const navLabels = {
    zh: ['能力', '特性', '快速开始', '架构', '使用形态', '文档'],
    en: ['Capabilities', 'Features', 'Quick Start', 'Architecture', 'Usage', 'Docs'],
  }

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 18)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  useEffect(() => {
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en'
  }, [lang])

  const installLabel = lang === 'zh' ? '安装' : 'Install'

  return (
    <header className={`site-nav ${scrolled ? 'is-scrolled' : ''}`}>
      <div className="container nav-inner">
        <a className="brand" href="#top" aria-label="Algocode 首页">
          <img src="./algocode_icon.png" alt="" width="30" height="30" />
          <span><Wordmark /></span>
        </a>

        <nav className={`nav-links ${menuOpen ? 'is-open' : ''}`} aria-label={lang === 'zh' ? '主导航' : 'Main navigation'}>
          {navItems.map((item, index) => (
            <a key={item.href} href={item.href} onClick={() => setMenuOpen(false)}>
              {navLabels[lang][index]}
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
            <button type="button" className={lang === 'zh' ? 'is-active' : ''} onClick={() => setLang('zh')}>中</button>
            <button type="button" className={lang === 'en' ? 'is-active' : ''} onClick={() => setLang('en')}>EN</button>
          </div>

          <button
            type="button"
            className="icon-button theme-toggle"
            aria-label={theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'}
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          <a className="button nav-install" href="#install">
            <Download size={16} />
            {installLabel}
          </a>

          <button
            type="button"
            className="icon-button menu-button"
            aria-label={menuOpen ? '关闭菜单' : '打开菜单'}
            onClick={() => setMenuOpen((value) => !value)}
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>
    </header>
  )
}
function TerminalWindow({ title, copyText, children, className = '' }) {
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
        <button type="button" className="terminal-copy" onClick={copy} aria-label="复制命令">
          {copied ? <Check size={14} /> : <Clipboard size={14} />}
          <span>{copied ? '已复制' : '复制'}</span>
        </button>
      </div>
      <div className="terminal-content">{children}</div>
    </div>
  )
}

function Hero() {
  const installText = [
    'algocode doctor  # 检查配置',
    'algocode api  # 配置模型',
    'algocode init  # 建立契约',
    'algocode optimize  # 开始优化',
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
            <span>Verifiable Algorithm Optimization Agent</span>
          </div>

          <h1 className="wordmark">Algocode</h1>
          <p className="hero-lede">
            面向 C++ / Python 的可验证算法优化 Agent。
            <br />
            先建立行为契约，再在隔离环境中尝试优化，最后用真实证据决定是否应用。
          </p>

          <div className="hero-actions">
            <a className="button button-primary" href="#quickstart">
              开始使用
              <ArrowDown size={16} />
            </a>
            <a className="button button-ghost" href={GH_URL} target="_blank" rel="noreferrer">
              <Github size={17} />
              查看 GitHub
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
          <TerminalWindow title="algocode — first optimization" copyText={installText}>
            <div className="terminal-line">
              <span className="prompt">$</span>
              <span className="cmd">algocode doctor</span>
              <span className="comment"># 检查配置</span>
            </div>
            <div className="terminal-line">
              <span className="prompt">$</span>
              <span className="cmd">algocode api</span>
              <span className="comment"># 配置模型</span>
            </div>
            <div className="terminal-line">
              <span className="prompt">$</span>
              <span className="cmd">algocode init</span>
              <span className="comment"># 建立契约</span>
            </div>
            <div className="terminal-line">
              <span className="prompt">$</span>
              <span className="cmd">algocode optimize</span>
              <span className="comment"># 开始优化</span>
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

function Install() {
  const installText = 'pip install algocode-agent'

  return (
    <section className="section section-install" id="install">
      <div className="container">
        <div className="install-grid">
          <div className="install-copy">
            <div className="eyebrow">
              <span className="eyebrow-mark" />
              Installation
            </div>
            <h2>安装 <Wordmark /></h2>
            <p>一行命令完成安装，随后配置模型、运行环境检查，就可以开始第一次优化。</p>
            <div className="requirement-row">
              <span>Python 3.11+</span>
              <span>PyPI</span>
            </div>
          </div>

          <Reveal delay={90} className="install-action">
            <TerminalWindow title="pip install — algocode" copyText={installText} className="install-terminal">
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">pip install algocode-agent</span>
              </div>
            </TerminalWindow>

            <div className="install-buttons">
              <a className="button button-ghost" href={DOCS_PATH}>
                <BookOpen size={16} />
                阅读文档
              </a>
              <a className="button button-ghost" href={GH_URL} target="_blank" rel="noreferrer">
                <Star size={16} />
                去 GitHub 上 Star
              </a>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  )
}

const capabilities = [
  {
    icon: FileCheck2,
    index: '01',
    title: '行为契约优先',
    text: '优化前先锁定公开 API、输入输出、配置字段、错误语义与边界行为，性能不能以破坏语义为代价。',
  },
  {
    icon: GitBranch,
    index: '02',
    title: '隔离候选生成',
    text: 'CLI 在 Git Worktree 中试错，VS Code 在临时影子工作区中运行，原项目不会被直接修改。',
  },
  {
    icon: Gauge,
    index: '03',
    title: '证据驱动决策',
    text: 'Correctness、Contract、Benchmark 三类结果全部持久化，接受或拒绝基于真实证据，而非模型自述。',
  },
  {
    icon: Undo2,
    index: '04',
    title: '可回滚交付',
    text: 'Review、Accept、Apply 逐步分离。应用前看 Diff 与报告，应用后仍可通过 Manifest 回滚。',
  },
]

function Capabilities() {
  return (
    <section className="section section-capabilities" id="capabilities">
      <div className="container">
        <SectionHeading
          eyebrow="What it does"
          title="不是黑盒改代码，而是可验证地推进"
          description={<>把可运行项目交给 <Wordmark />，它会在有门控的阶段中完成分析、基线、候选生成、验证、基准测试与决策。</>}
        />
        <div className="capability-grid">
          {capabilities.map((item, index) => {
            const Icon = item.icon
            return (
              <Reveal key={item.title} delay={index * 70} className="capability-card">
                <div className="capability-topline">
                  <span className="capability-index">{item.index}</span>
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

const features = [
  {
    icon: ShieldCheck,
    title: '契约优先',
    text: '先确定行为语义，再进入优化阶段，避免“变快了但结果错了”。',
  },
  {
    icon: GitCompareArrows,
    title: '证据驱动',
    text: '正确性、契约、性能三类结果完整保存，决策有据可查。',
  },
  {
    icon: Boxes,
    title: '隔离候选',
    text: 'Git Worktree 与影子工作区让候选始终在独立副本中演进。',
  },
  {
    icon: LockKeyhole,
    title: '人工可控',
    text: 'Diff、Review、Apply 分离，先看证据，再决定是否应用。',
  },
  {
    icon: ScrollText,
    title: '全程可审计',
    text: '模型调用、工具调用、阶段结果与候选快照均被持久化。',
  },
  {
    icon: Activity,
    title: '阶段进度可见',
    text: '终端实时显示阶段、序号、轮次、当前工具与耗时。',
  },
  {
    icon: Repeat2,
    title: '失败可重试',
    text: '负收益、证据不足或阶段阻塞时，可基于历史重新规划方向。',
  },
  {
    icon: Network,
    title: '多模型 Provider',
    text: '支持 OpenAI、DeepSeek、Kimi、GLM、Claude 与任意 OpenAI-compatible 服务。',
  },
  {
    icon: Server,
    title: '本地优先',
    text: '默认本机执行，Docker / WSL2 仅作为可选隔离增强。',
  },
  {
    icon: Monitor,
    title: 'CLI + VS Code',
    text: '终端自动化与编辑器日常操作共享同一套验证与存储层。',
  },
]

function Features() {
  return (
    <section className="section section-features" id="features">
      <div className="container">
        <SectionHeading
          eyebrow="Capabilities"
          title="围绕证据建立的安全边界"
          description={<><Wordmark /> 把优化拆成可观察、可验证、可回退的阶段，每一步都有明确的前置条件和产出。</>}
        />
        <div className="feature-grid">
          {features.map((item, index) => {
            const Icon = item.icon
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

const quickStartSteps = [
  {
    icon: Play,
    title: '安装',
    text: '从 PyPI 安装 algocode-agent，或使用源码开发模式。',
  },
  {
    icon: KeyRound,
    title: '配置模型',
    text: '选择 Provider、Base URL、模型 ID 与 API Key，凭据保存在本机。',
  },
  {
    icon: Search,
    title: '环境检查',
    text: '运行 doctor 确认 Git、Python、编译器与入口文件条件。',
  },
  {
    icon: Sparkles,
    title: '发起优化',
    text: 'init 建立契约与基线，optimize 启动完整的候选优化流程。',
  },
  {
    icon: BadgeCheck,
    title: '审阅与应用',
    text: '查看 review、diff 与 report，确认后再 apply，必要时 rollback。',
  },
]

function QuickStart() {
  const copyText = [
    '# 1. Install Algocode',
    'pip install algocode-agent',
    '',
    '# 2. Configure provider and verify environment',
    'algocode api',
    'algocode doctor',
    '',
    '# 3. Init contract and optimize',
    'algocode init',
    'algocode optimize',
    '',
    '# 4. Review and apply',
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
              eyebrow="Quick start"
              title="五分钟完成第一次优化"
              description="安装后只需几条命令，就能从契约建立走到候选审阅与应用。"
            />
            <div className="step-list">
              {quickStartSteps.map((step, index) => {
                const Icon = step.icon
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
              <span>Python 3.11+</span>
              <span>Git</span>
              <span>C++ 编译器（优化 C++ 项目时）</span>
            </Reveal>
          </div>

          <Reveal delay={100} className="quickstart-terminal">
            <TerminalWindow title="terminal — algocode" copyText={copyText}>
              <div className="terminal-line">
                <span className="comment"># 1. Install Algocode</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">pip install algocode-agent</span>
              </div>
              <div className="terminal-line">
                <span className="success">[OK] Successfully installed algocode-agent-0.1.1</span>
              </div>
              <div className="terminal-line-spacer" />
              <div className="terminal-line">
                <span className="comment"># 2. Configure provider and verify environment</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">algocode api</span>
              </div>
              <div className="terminal-line">
                <span className="success">[OK] provider: openai / api key stored locally</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">algocode doctor</span>
              </div>
              <div className="terminal-line">
                <span className="success">[OK] python 3.12 / git / C++ toolchain ready</span>
              </div>
              <div className="terminal-line-spacer" />
              <div className="terminal-line">
                <span className="comment"># 3. Init contract and optimize</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">algocode init</span>
              </div>
              <div className="terminal-line">
                <span className="success">[OK] .algocode/contract.toml created - baseline ready</span>
              </div>
              <div className="terminal-line">
                <span className="prompt">$</span>
                <span className="cmd">algocode optimize</span>
              </div>
              <div className="terminal-line">
                <span className="metric">[ALGO] Status: completed / Correctness: passed</span>
              </div>
              <div className="terminal-line">
                <span className="metric">[ALGO] Baseline 0.7594s -&gt; Candidate 0.5357s</span>
              </div>
              <div className="terminal-line">
                <span className="metric">[ALGO] Improvement: 29.46%</span>
              </div>
              <div className="terminal-line-spacer" />
              <div className="terminal-line">
                <span className="comment"># 4. Review and apply</span>
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
                <span className="success">[OK] candidate applied / rollback available</span>
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
    label: '入口层',
    items: [
      { icon: Terminal, name: 'CLI Commands' },
      { icon: Monitor, name: 'VS Code Extension' },
    ],
  },
  {
    label: '应用层',
    items: [
      { icon: Layers3, name: 'Application Services' },
      { icon: Workflow, name: 'Domain' },
    ],
  },
  {
    label: '运行时层',
    items: [
      { icon: Cpu, name: 'Agent Runtime' },
      { icon: Network, name: 'Model Providers' },
      { icon: Code2, name: 'Python / C++ Adapters' },
    ],
  },
  {
    label: '支撑层',
    items: [
      { icon: ShieldCheck, name: 'Policy / Approval / Sandbox' },
      { icon: GitBranch, name: 'Git Workspace' },
    ],
  },
  {
    label: '持久层',
    items: [
      { icon: Database, name: 'SQLite Event Store + Projections' },
      { icon: ScrollText, name: 'File Artifact Store' },
    ],
  },
]

function Architecture() {
  return (
    <section className="section section-architecture" id="architecture">
      <div className="container architecture-layout">
        <div className="architecture-copy">
          <SectionHeading
            eyebrow="Architecture"
            title="两个入口，一条可审计的请求路径"
            description="CLI 与 VS Code 最终调用同一套 Application Services、Agent Runtime、验证与存储层。"
          />
          <Reveal className="request-path">
            <div className="request-path-label">REQUEST PATH</div>
            <div className="path-flow">
              <span>CLI / VS Code</span>
              <ChevronRight size={15} />
              <span>Application</span>
              <ChevronRight size={15} />
              <span>Agent Runtime</span>
              <ChevronRight size={15} />
              <span>Tools</span>
              <ChevronRight size={15} />
              <span>Storage</span>
            </div>
            <p>
              Policy、Approval 与 Sandbox 在高风险动作发生时提供约束，Git Workspace
              保证候选与原项目隔离。
            </p>
          </Reveal>
        </div>

        <Reveal delay={90} className="architecture-stack">
          {architectureLayers.map((layer, layerIndex) => (
            <div className="architecture-layer" key={layer.label}>
              <div className="architecture-layer-label">{layer.label}</div>
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

function Usage() {
  return (
    <section className="section section-usage" id="usage">
      <div className="container">
        <SectionHeading
          eyebrow="Two entry points"
          title="选择你习惯的工作方式"
          description="同一个运行时，两种交互入口。终端适合自动化与脚本，编辑器适合日常查看与决策。"
        />
        <div className="usage-grid">
          <Reveal className="usage-card">
            <div className="usage-card-head">
              <div className="usage-icon">
                <Terminal size={23} strokeWidth={1.6} />
              </div>
              <div>
                <span className="usage-tag">CLI</span>
                <h3>完整命令行工作流</h3>
              </div>
            </div>
            <p>
              适合终端自动化、批量任务与脚本调用。通过 Git Worktree 隔离候选，可执行
              init、optimize、review、apply、rollback 等完整流程。
            </p>
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
                <span className="usage-tag">VS Code</span>
                <h3>编辑器内闭环体验</h3>
              </div>
            </div>
            <p>
              在临时影子工作区中运行，右键即可优化。阶段进度、Diff、Review、Apply 与
              Rollback 都在编辑器内完成。
            </p>
            <div className="usage-checklist">
              <span>
                <CheckCircle2 size={15} />
                实时阶段进度
              </span>
              <span>
                <CheckCircle2 size={15} />
                Diff 与 Review
              </span>
              <span>
                <CheckCircle2 size={15} />
                Apply / Rollback
              </span>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="footer">
      <div className="container footer-grid">
        <div className="footer-brand">
          <div className="footer-logo">
            <img src="./algocode_icon.png" alt="" width="38" height="38" />
            <span><Wordmark /></span>
          </div>
          <p>面向 C++ / Python 的可验证算法优化 Agent。本地优先，证据驱动，可回滚。</p>
        </div>

        <div className="footer-column">
          <h3>资源</h3>
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
            <span>性能与结果声明</span>
          </div>
          <p>
            <Wordmark /> 通过大模型分析源代码并生成候选优化。优化后的性能可能提升、没有明显变化，甚至下降；
            结果受源代码质量、项目结构、模型能力、输入规模、运行环境和系统负载等因素影响。
            <Wordmark /> 不承诺每次优化都带来正收益，也不替代人工代码审查。请以实际的 Correctness、Contract、
            Benchmark、Diff 和 Review 结果为准，在确认行为正确且收益满足预期后再 Apply。
          </p>
        </div>
      </div>

      <div className="container footer-bottom">
        <span>© 2026 <Wordmark /> 贡献者</span>
        <span>MIT 许可证</span>
      </div>
    </footer>
  )
}

export default function App() {
  const hash = useHashRoute()
  const isDocs = hash.startsWith('#/docs')

  return (
    <>
      <div className="site-background" aria-hidden="true">
        <div className="site-grid" />
        <div className="site-light" />
        <ParticleField />
      </div>
      <Navbar />
      <main>
        {isDocs ? (
          <DocsPage route={hash} />
        ) : (
          <>
            <Hero />
            <Install />
            <Capabilities />
            <Features />
            <QuickStart />
            <Architecture />
            <Usage />
          </>
        )}
      </main>
      <Footer />
    </>
  )
}
