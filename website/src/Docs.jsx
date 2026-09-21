import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import mermaid from 'mermaid'
import {
  BookOpen,
  Check,
  ChevronRight,
  Clipboard,
  ExternalLink,
  FileText,
  Menu,
  Search,
  Terminal,
  X,
} from 'lucide-react'
import './docs.css'

const docsNav = {
  zh: [
    { title: '快速上手', items: [
      { label: '安装', path: 'getting-started/installation' },
      { label: '快速开始', path: 'getting-started/quickstart' },
      { label: '配置', path: 'getting-started/configuration' },
      { label: '常见问题', path: 'getting-started/troubleshooting' },
    ] },
    { title: '命令手册', items: [{ label: '命令总览', path: 'commands/index' }] },
    { title: '用户指南', items: [
      { label: '简略工作流', path: 'user-guide/quick-workflow' },
      { label: '完整工作流', path: 'user-guide/workflow' },
    ] },
    { title: '核心概念', items: [
      { label: '架构概览', path: 'concepts/architecture' },
      { label: '证据模型', path: 'concepts/evidence-model' },
      { label: '候选生命周期', path: 'concepts/candidate-lifecycle' },
      { label: '存储与产物', path: 'concepts/storage-and-artifacts' },
      { label: '策略、审批与沙箱', path: 'concepts/policy-approval-sandbox' },
      { label: '模型 Provider', path: 'concepts/model-providers' },
    ] },
    { title: '参考文档', items: [
      { label: 'CLI 参考', path: 'reference/cli' },
      { label: '配置参考', path: 'reference/config' },
      { label: '项目目录', path: 'reference/project-layout' },
      { label: 'Correctness Schema', path: 'reference/correctness-spec' },
      { label: 'Benchmark Schema', path: 'reference/benchmark-spec' },
      { label: 'Contract Schema', path: 'reference/contract-schema' },
    ] },
    { title: '开发维护', items: [
      { label: '代码结构', path: 'development/code-structure' },
      { label: '测试', path: 'development/testing' },
      { label: '发布', path: 'development/release' },
    ] },
    { title: '更新日志', items: [
      { label: 'v0.1.2', path: 'changelog/v0.1.2' },
      { label: 'v0.1.1', path: 'changelog/v0.1.1' },
      { label: 'v0.1.0', path: 'changelog/v0.1.0' },
    ] },
  ],
  en: [
    { title: 'Getting Started', items: [
      { label: 'Installation', path: 'getting-started/installation' },
      { label: 'Quick Start', path: 'getting-started/quickstart' },
      { label: 'Configuration', path: 'getting-started/configuration' },
      { label: 'Troubleshooting', path: 'getting-started/troubleshooting' },
    ] },
    { title: 'Command Guide', items: [{ label: 'Command Overview', path: 'commands/index' }] },
    { title: 'User Guide', items: [
      { label: 'Quick Workflow', path: 'user-guide/quick-workflow' },
      { label: 'Complete Workflow', path: 'user-guide/workflow' },
    ] },
    { title: 'Core Concepts', items: [
      { label: 'Architecture', path: 'concepts/architecture' },
      { label: 'Evidence Model', path: 'concepts/evidence-model' },
      { label: 'Candidate Lifecycle', path: 'concepts/candidate-lifecycle' },
      { label: 'Storage and Artifacts', path: 'concepts/storage-and-artifacts' },
      { label: 'Policy, Approval, and Sandbox', path: 'concepts/policy-approval-sandbox' },
      { label: 'Model Providers', path: 'concepts/model-providers' },
    ] },
    { title: 'Reference', items: [
      { label: 'CLI Reference', path: 'reference/cli' },
      { label: 'Configuration Reference', path: 'reference/config' },
      { label: 'Project Layout', path: 'reference/project-layout' },
      { label: 'Correctness Schema', path: 'reference/correctness-spec' },
      { label: 'Benchmark Schema', path: 'reference/benchmark-spec' },
      { label: 'Contract Schema', path: 'reference/contract-schema' },
    ] },
    { title: 'Development', items: [
      { label: 'Code Structure', path: 'development/code-structure' },
      { label: 'Testing', path: 'development/testing' },
      { label: 'Release', path: 'development/release' },
    ] },
    { title: 'Changelog', items: [
      { label: 'v0.1.2', path: 'changelog/v0.1.2' },
      { label: 'v0.1.1', path: 'changelog/v0.1.1' },
      { label: 'v0.1.0', path: 'changelog/v0.1.0' },
    ] },
  ],
}

const docsUi = {
  zh: {
    title: '文档', search: '搜索文档', clearSearch: '清除搜索', navAria: '文档导航', notFound: '未找到匹配文档',
    toc: '本页目录', tocAria: '本页目录', copyCode: '复制代码', copied: '已复制', copy: '复制', copyHeading: '复制标题链接',
    previous: '上一页', next: '下一页', breadcrumb: '文档', openNav: '打开文档导航', closeNav: '关闭文档导航',
    mermaidError: '图表渲染失败', mermaidLoading: '正在渲染图表…', notFoundBody: '当前文档路径', notFoundHint: '请从左侧导航选择其他文档。',
  },
  en: {
    title: 'Documentation', search: 'Search docs', clearSearch: 'Clear search', navAria: 'Documentation navigation', notFound: 'No matching documentation',
    toc: 'On this page', tocAria: 'On this page', copyCode: 'Copy code', copied: 'Copied', copy: 'Copy', copyHeading: 'Copy heading link',
    previous: 'Previous', next: 'Next', breadcrumb: 'Docs', openNav: 'Open documentation navigation', closeNav: 'Close documentation navigation',
    mermaidError: 'Diagram rendering failed', mermaidLoading: 'Rendering diagram…', notFoundBody: 'Current documentation path', notFoundHint: 'Choose another page from the navigation.',
  },
}

const rawDocFiles = import.meta.glob('../../docs/**/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
})

const rawImageFiles = import.meta.glob('../../docs/**/*.{png,jpg,jpeg,gif,webp,svg}', {
  query: '?url',
  import: 'default',
  eager: true,
})

const defaultDocPath = 'getting-started/installation'

function stripDocsPrefix(key) {
  return key.replaceAll('\\', '/').replace(/^.*\/docs\//, '')
}

function getDocsRoute(route) {
  const raw = String(route || '')
    .replace(/^#\/docs\/?/, '')
    .split('?')[0]
    .replace(/\/+$/, '')
  const [locale, ...rest] = raw.split('/')
  if (locale === 'en' || locale === 'zh') {
    return { lang: locale, path: rest.join('/') || defaultDocPath }
  }
  return { lang: 'zh', path: raw || defaultDocPath }
}

function docsHref(lang, path) {
  return `#/docs/${lang}/${path}`
}

function getDocContent(lang, path) {
  if (lang === 'en') return docsContent[`en/${path}.md`]
  return docsContent[`${path}.md`]
}

function resolveRelativePath(baseDir, target) {
  if (/^(?:[a-z]+:)?\//i.test(target)) return target

  const parts = baseDir
    ? baseDir.split('/').filter(Boolean)
    : []

  for (const part of target.split('/')) {
    if (!part || part === '.') continue
    if (part === '..') parts.pop()
    else parts.push(part)
  }

  return parts.join('/')
}

function slugify(value) {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/<[^>]+>/g, '')
    .replace(/[`*_~]/g, '')
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '') || 'section'
}

function excerpt(text) {
  return text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/[#>*`_~[\]()]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 96)
}

const docsContent = Object.fromEntries(
  Object.entries(rawDocFiles).map(([key, value]) => [stripDocsPrefix(key), value]),
)

const imageUrls = Object.fromEntries(
  Object.entries(rawImageFiles).map(([key, value]) => [stripDocsPrefix(key), value]),
)

function resolveImage(src, docPath) {
  if (!src || /^(https?:|data:|mailto:)/i.test(src)) return src

  const baseDir = docPath.includes('/')
    ? docPath.slice(0, docPath.lastIndexOf('/'))
    : ''
  const resolved = resolveRelativePath(baseDir, src)

  return imageUrls[resolved] || imageUrls[stripDocsPrefix(resolved)] || src
}

let mermaidSequence = 0

function useDocsTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'dark')

  useEffect(() => {
    const updateTheme = () => setTheme(document.documentElement.dataset.theme || 'dark')
    const observer = new MutationObserver(updateTheme)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })
    return () => observer.disconnect()
  }, [])

  return theme
}

function MermaidBlock({ code, ui }) {
  const [svg, setSvg] = useState('')
  const [error, setError] = useState('')
  const theme = useDocsTheme()

  useEffect(() => {
    let cancelled = false
    const id = `docs-mermaid-${mermaidSequence += 1}`
    const isDark = theme === 'dark'

    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      theme: isDark ? 'dark' : 'neutral',
      themeVariables: isDark
        ? {
            background: '#080b10',
            primaryColor: '#101821',
            primaryTextColor: '#d7e2ec',
            primaryBorderColor: '#33465c',
            lineColor: '#5f7c96',
            secondaryColor: '#131e28',
            tertiaryColor: '#0d141c',
            fontSize: '14px',
          }
        : {
            background: '#f4f7f9',
            primaryColor: '#ffffff',
            primaryTextColor: '#24303b',
            primaryBorderColor: '#c9d5df',
            lineColor: '#71869a',
            secondaryColor: '#f8fafb',
            tertiaryColor: '#eef3f6',
            fontSize: '14px',
          },
    })

    mermaid.render(id, code)
      .then(({ svg: renderedSvg }) => {
        if (!cancelled) {
          setSvg(renderedSvg)
          setError('')
        }
      })
      .catch((renderError) => {
        if (!cancelled) {
          setSvg('')
          setError(renderError instanceof Error ? renderError.message : String(renderError))
        }
      })

    return () => {
      cancelled = true
    }
  }, [code, theme])

  return (
    <div className={`docs-mermaid ${error ? 'has-error' : ''}`}>
      {svg ? (
        <div className="docs-mermaid-canvas" dangerouslySetInnerHTML={{ __html: svg }} />
      ) : (
        <div className="docs-mermaid-loading">
          {error ? `${ui.mermaidError}: ${error}` : ui.mermaidLoading}
        </div>
      )}
    </div>
  )
}

function CodeBlock({ language, code, ui }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="docs-codeblock">
      <div className="docs-codebar">
        <span>
          <Terminal size={13} />
          {language || 'text'}
        </span>
        <button type="button" onClick={copy} aria-label={ui.copyCode}>
          {copied ? <Check size={14} /> : <Clipboard size={14} />}
          {copied ? ui.copied : ui.copy}
        </button>
      </div>
      <pre>
        <code>{code}</code>
      </pre>
    </div>
  )
}

function MarkdownRenderer({ content, docPath, lang, onNavigate, ui }) {
  const components = useMemo(() => {
    const makeHeading = (Tag) => {
      return function Heading({ children }) {
        const text = Array.isArray(children)
          ? children.join('')
          : String(children)
        const id = slugify(text)

        return (
          <Tag id={id}>
            {children}
            <a className="docs-heading-anchor" href={`#${id}`} aria-label={ui.copyHeading}>
              #
            </a>
          </Tag>
        )
      }
    }

    return {
      h1: ({ children }) => <h1 className="docs-title">{children}</h1>,
      h2: makeHeading('h2'),
      h3: makeHeading('h3'),
      h4: makeHeading('h4'),
      pre: ({ children }) => <>{children}</>,
      code: ({ className, children }) => {
        const text = String(children).replace(/\n$/, '')
        const match = /language-(\w+)/.exec(className || '')
        const isBlock = Boolean(className) || text.includes('\n')
        const language = match?.[1]?.toLowerCase()

        if (language === 'mermaid') {
          return <MermaidBlock code={text} ui={ui} />
        }

        if (isBlock) {
          return <CodeBlock language={language} code={text} ui={ui} />
        }

        return <code className="docs-inline-code">{children}</code>
      },
      img: ({ src, alt }) => (
        <img src={resolveImage(src, docPath)} alt={alt || ''} loading="lazy" />
      ),
      a: ({ href, children }) => {
        if (!href) return <a>{children}</a>

        if (href.startsWith('#')) {
          return (
            <a
              href={href}
              onClick={(event) => {
                event.preventDefault()
                const id = href.slice(1)
                document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
              }}
            >
              {children}
            </a>
          )
        }

        if (href.endsWith('.md')) {
          const baseDir = docPath.includes('/')
            ? docPath.slice(0, docPath.lastIndexOf('/'))
            : ''
          const target = resolveRelativePath(baseDir, href.replace(/\.md$/, ''))

          return (
            <a
              href={docsHref(lang, target)}
              onClick={(event) => {
                event.preventDefault()
                onNavigate(target)
              }}
            >
              {children}
            </a>
          )
        }

        return (
          <a href={href} target="_blank" rel="noreferrer">
            {children}
            <ExternalLink size={12} />
          </a>
        )
      },
    }
  }, [docPath, lang, onNavigate, ui])

  return (
    <div className="docs-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

function TableOfContents({ headings, ui }) {
  if (!headings.length) return null

  return (
    <aside className="docs-toc">
      <div className="docs-toc-title">{ui.toc}</div>
      <nav aria-label={ui.tocAria}>
        {headings.map((heading) => (
          <a
            key={`${heading.id}-${heading.level}`}
            href={`#${heading.id}`}
            className={`docs-toc-link level-${heading.level}`}
            onClick={(event) => {
              event.preventDefault()
              document.getElementById(heading.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
            }}
          >
            {heading.text}
          </a>
        ))}
      </nav>
    </aside>
  )
}

export default function DocsPage({ route, lang: preferredLang }) {
  const [query, setQuery] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const routeInfo = getDocsRoute(route)
  const lang = routeInfo.lang || preferredLang || 'zh'
  const docPath = routeInfo.path
  const ui = docsUi[lang]
  const nav = docsNav[lang]
  const content = getDocContent(lang, docPath)
    || `# ${ui.notFound}\n\n${ui.notFoundBody}: \`${docPath}\`\n\n${ui.notFoundHint}`

  const flatItems = useMemo(
    () => nav.flatMap((section) => section.items.map((item) => ({
      ...item,
      section: section.title,
    }))),
    [nav],
  )

  const currentIndex = flatItems.findIndex((item) => item.path === docPath)
  const previous = currentIndex > 0 ? flatItems[currentIndex - 1] : null
  const next = currentIndex >= 0 && currentIndex < flatItems.length - 1
    ? flatItems[currentIndex + 1]
    : null
  const currentItem = flatItems[currentIndex]

  const headings = useMemo(() => {
    const result = []
    const regex = /^(#{1,4})\s+(.+?)\s*#*\s*$/gm
    let match

    while ((match = regex.exec(content))) {
      result.push({
        level: match[1].length,
        text: match[2].replace(/[`*_~]/g, '').trim(),
        id: slugify(match[2]),
      })
    }

    return result
  }, [content])

  const searchResults = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    if (!keyword) return []

    return flatItems.filter((item) => {
      const source = getDocContent(lang, item.path) || ''
      return item.label.toLowerCase().includes(keyword)
        || source.toLowerCase().includes(keyword)
    })
  }, [query, flatItems, lang])

  const navigate = (path) => {
    setSidebarOpen(false)
    window.location.hash = docsHref(lang, path)
  }

  useEffect(() => {
    setQuery('')
    setSidebarOpen(false)
    window.scrollTo(0, 0)
  }, [docPath, lang])

  return (
    <div className="docs-page">
      <aside className={`docs-sidebar ${sidebarOpen ? 'is-open' : ''}`}>
        <div className="docs-sidebar-top">
          <div className="docs-sidebar-title">
            <BookOpen size={17} />
            <span>{ui.title}</span>
          </div>

          <label className="docs-search">
            <Search size={15} />
            <input
              type="search"
              value={query}
              placeholder={ui.search}
              onChange={(event) => setQuery(event.target.value)}
            />
            {query ? (
              <button type="button" onClick={() => setQuery('')} aria-label={ui.clearSearch}>
                <X size={14} />
              </button>
            ) : null}
          </label>
        </div>

        <nav className="docs-nav" aria-label={ui.navAria}>
          {query ? (
            <div className="docs-search-results">
              {searchResults.length ? (
                searchResults.map((item) => (
                  <button
                    type="button"
                    className="docs-search-result"
                    key={item.path}
                    onClick={() => navigate(item.path)}
                  >
                    <span className="docs-search-result-title">{item.label}</span>
                    <span className="docs-search-result-section">{item.section}</span>
                  </button>
                ))
              ) : (
                <div className="docs-search-empty">{ui.notFound}</div>
              )}
            </div>
          ) : (
            nav.map((section) => (
              <div className="docs-nav-section" key={section.title}>
                <div className="docs-nav-section-title">{section.title}</div>
                {section.items.map((item) => (
                  <a
                    key={item.path}
                    href={docsHref(lang, item.path)}
                    className={`docs-nav-link ${docPath === item.path ? 'is-active' : ''}`}
                    onClick={(event) => {
                      event.preventDefault()
                      navigate(item.path)
                    }}
                  >
                    <FileText size={14} />
                    <span>{item.label}</span>
                  </a>
                ))}
              </div>
            ))
          )}
        </nav>
      </aside>

      {sidebarOpen ? (
        <button
          type="button"
          className="docs-sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
          aria-label={ui.closeNav}
        />
      ) : null}

      <div className="docs-content">
        <button
          type="button"
          className="docs-sidebar-toggle"
          onClick={() => setSidebarOpen((value) => !value)}
          aria-label={ui.openNav}
        >
          <Menu size={18} />
        </button>

        <div className="docs-content-inner">
          <main className="docs-main">
            <div className="docs-breadcrumb">
              {ui.breadcrumb}
              {currentItem ? (
                <>
                  <ChevronRight size={14} />
                  <span>{currentItem.section}</span>
                  <ChevronRight size={14} />
                  <span>{currentItem.label}</span>
                </>
              ) : null}
            </div>

            <MarkdownRenderer content={content} docPath={docPath} lang={lang} onNavigate={navigate} ui={ui} />

            <div className="docs-pager">
              {previous ? (
                <button type="button" onClick={() => navigate(previous.path)}>
                  <span>{ui.previous}</span>
                  <strong>{previous.label}</strong>
                </button>
              ) : <span />}

              {next ? (
                <button type="button" className="is-next" onClick={() => navigate(next.path)}>
                  <span>{ui.next}</span>
                  <strong>{next.label}</strong>
                </button>
              ) : <span />}
            </div>
          </main>

          <TableOfContents headings={headings} ui={ui} />
        </div>
      </div>
    </div>
  )
}
