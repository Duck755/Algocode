export const siteCopy = {
  zh: {
    metadata: {
      title: 'Algocode — 可验证的算法优化 Agent',
      description:
        'Algocode 是面向 C++ / Python 的可验证算法优化 Agent，本地优先、证据驱动、可回滚。',
    },
    nav: {
      items: [
        { label: '能力', href: '#capabilities' },
        { label: '特性', href: '#features' },
        { label: '快速开始', href: '#quickstart' },
        { label: '架构', href: '#architecture' },
        { label: '使用形态', href: '#usage' },
      ],
      docsLabel: '文档',
      homeAria: 'Algocode 首页',
      mainAria: '主导航',
      install: '安装',
      themeToLight: '切换到浅色模式',
      themeToDark: '切换到深色模式',
      closeMenu: '关闭菜单',
      openMenu: '打开菜单',
    },
    terminal: {
      copy: '复制',
      copied: '已复制',
      copyAria: '复制命令',
    },
    hero: {
      kicker: '可验证的算法优化 Agent',
      lede: [
        '面向 C++ / Python 的可验证算法优化 Agent。',
        '先建立行为契约，再在隔离环境中尝试优化，最后用真实证据决定是否应用。',
      ],
      primary: '开始使用',
      github: '查看 GitHub',
      terminalTitle: 'algocode — 第一次优化',
      comments: ['# 检查配置', '# 配置模型', '# 建立契约', '# 开始优化'],
    },
    install: {
      eyebrow: '安装',
      title: '安装',
      description: '一行命令完成安装，随后配置模型、运行环境检查，就可以开始第一次优化。',
      docs: '阅读文档',
      star: '去 GitHub 上 Star',
    },
    capabilities: {
      eyebrow: '它做什么',
      title: '不是黑盒改代码，而是可验证地推进',
      description: '把可运行项目交给 Algocode，它会在有门控的阶段中完成分析、基线、候选生成、验证、基准测试与决策。',
      items: [
        {
          title: '行为契约优先',
          text: '优化前先锁定公开 API、输入输出、配置字段、错误语义与边界行为，性能不能以破坏语义为代价。',
        },
        {
          title: '隔离候选生成',
          text: 'CLI 在 Git Worktree 中试错，VS Code 在临时影子工作区中运行，原项目不会被直接修改。',
        },
        {
          title: '证据驱动决策',
          text: 'Correctness、Contract、Benchmark 三类结果全部持久化，接受或拒绝基于真实证据，而非模型自述。',
        },
        {
          title: '可回滚交付',
          text: 'Review、Accept、Apply 逐步分离。应用前看 Diff 与报告，应用后仍可通过 Manifest 回滚。',
        },
      ],
    },
    features: {
      eyebrow: '能力',
      title: '围绕证据建立的安全边界',
      description: 'Algocode 把优化拆成可观察、可验证、可回退的阶段，每一步都有明确的前置条件和产出。',
      items: [
        { title: '契约优先', text: '先确定行为语义，再进入优化阶段，避免“变快了但结果错了”。' },
        { title: '证据驱动', text: '正确性、契约、性能三类结果完整保存，决策有据可查。' },
        { title: '隔离候选', text: 'Git Worktree 与影子工作区让候选始终在独立副本中演进。' },
        { title: '人工可控', text: 'Diff、Review、Apply 分离，先看证据，再决定是否应用。' },
        { title: '全程可审计', text: '模型调用、工具调用、阶段结果与候选快照均被持久化。' },
        { title: '阶段进度可见', text: '终端实时显示阶段、序号、轮次、当前工具与耗时。' },
        { title: '失败可重试', text: '负收益、证据不足或阶段阻塞时，可基于历史重新规划方向。' },
        { title: '多模型 Provider', text: '支持 OpenAI、DeepSeek、Kimi、GLM、Claude 与任意 OpenAI-compatible 服务。' },
        { title: '本地优先', text: '默认本机执行，Docker / WSL2 仅作为可选隔离增强。' },
        { title: 'CLI + VS Code', text: '终端自动化与编辑器日常操作共享同一套验证与存储层。' },
      ],
    },
    quickStart: {
      eyebrow: '快速开始',
      title: '五分钟完成第一次优化',
      description: '安装后只需几条命令，就能从契约建立走到候选审阅与应用。',
      requirements: ['Python 3.11+', 'Git', 'C++ 编译器（优化 C++ 项目时）'],
      steps: [
        { title: '安装', text: '从 PyPI 安装 algocode-agent，或使用源码开发模式。' },
        { title: '配置模型', text: '选择 Provider、Base URL、模型 ID 与 API Key，凭据保存在本机。' },
        { title: '环境检查', text: '运行 doctor 确认 Git、Python、编译器与入口文件条件。' },
        { title: '发起优化', text: 'init 建立契约与基线，optimize 启动完整的候选优化流程。' },
        { title: '审阅与应用', text: '查看 review、diff 与 report，确认后再 apply，必要时 rollback。' },
      ],
      terminal: {
        title: '终端 — algocode',
        comments: [
          '# 1. 安装 Algocode',
          '# 2. 配置 Provider 并检查环境',
          '# 3. 建立契约并开始优化',
          '# 4. 审阅并应用',
        ],
        installOk: '[OK] 已成功安装 algocode-agent-0.1.2',
        providerOk: '[OK] provider: openai / API Key 已保存到本机',
        doctorOk: '[OK] Python 3.12 / Git / C++ 工具链就绪',
        contractOk: '[OK] 已创建 .algocode/contract.json，基线已就绪',
        optimizeStatus: '[ALGO] 状态：completed / Correctness：passed',
        benchmark: '[ALGO] 基线 0.7594s -> 候选 0.5357s',
        improvement: '[ALGO] 提升：29.46%',
        applyOk: '[OK] 候选已应用 / 可回滚',
      },
    },
    architecture: {
      eyebrow: '架构',
      title: '两个入口，一条可审计的请求路径',
      description: 'CLI 与 VS Code 最终调用同一套 Application Services、Agent Runtime、验证与存储层。',
      requestPath: '请求路径',
      flow: ['CLI / VS Code', 'Application', 'Agent Runtime', 'Tools', 'Storage'],
      note: 'Policy、Approval 与 Sandbox 在高风险动作发生时提供约束，Git Workspace 保证候选与原项目隔离。',
      layers: [
        { label: '入口层', items: ['CLI Commands', 'VS Code Extension'] },
        {
          label: '应用层',
          items: ['Application Services', 'Domain'],
        },
        {
          label: '运行时层',
          items: ['Agent Runtime', 'Model Providers', 'Python / C++ Adapters'],
        },
        {
          label: '支撑层',
          items: ['Policy / Approval / Sandbox', 'Git Workspace'],
        },
        {
          label: '持久层',
          items: ['SQLite Event Store + Projections', 'File Artifact Store'],
        },
      ],
    },
    usage: {
      eyebrow: '两种入口',
      title: '选择你习惯的工作方式',
      description: '同一个运行时，两种交互入口。终端适合自动化与脚本，编辑器适合日常查看与决策。',
      cards: [
        {
          tag: 'CLI',
          title: '完整命令行工作流',
          text: '适合终端自动化、批量任务与脚本调用。通过 Git Worktree 隔离候选，可执行 init、optimize、review、apply、rollback 等完整流程。',
          checklist: [],
        },
        {
          tag: 'VS Code',
          title: '编辑器内闭环体验',
          text: '在临时影子工作区中运行，右键即可优化。阶段进度、Diff、Review、Apply 与 Rollback 都在编辑器内完成。',
          checklist: ['实时阶段进度', 'Diff 与 Review', 'Apply / Rollback'],
        },
      ],
    },
    footer: {
      description: '面向 C++ / Python 的可验证算法优化 Agent。本地优先，证据驱动，可回滚。',
      resources: '资源',
      declarationTitle: '性能与结果声明',
      declaration:
        'Algocode 通过大模型分析源代码并生成候选优化。优化后的性能可能提升、没有明显变化，甚至下降；结果受源代码质量、项目结构、模型能力、输入规模、运行环境和系统负载等因素影响。Algocode 不承诺每次优化都带来正收益，也不替代人工代码审查。请以实际的 Correctness、Contract、Benchmark、Diff 和 Review 结果为准，在确认行为正确且收益满足预期后再 Apply。',
      contributors: '贡献者',
      license: 'MIT 许可证',
    },
  },
  en: {
    metadata: {
      title: 'Algocode — Verifiable Algorithm Optimization Agent',
      description:
        'Algocode is a local-first, evidence-driven, rollback-safe algorithm optimization agent for C++ and Python.',
    },
    nav: {
      items: [
        { label: 'Capabilities', href: '#capabilities' },
        { label: 'Features', href: '#features' },
        { label: 'Quick Start', href: '#quickstart' },
        { label: 'Architecture', href: '#architecture' },
        { label: 'Usage', href: '#usage' },
      ],
      docsLabel: 'Docs',
      homeAria: 'Algocode home',
      mainAria: 'Main navigation',
      install: 'Install',
      themeToLight: 'Switch to light mode',
      themeToDark: 'Switch to dark mode',
      closeMenu: 'Close menu',
      openMenu: 'Open menu',
    },
    terminal: {
      copy: 'Copy',
      copied: 'Copied',
      copyAria: 'Copy command',
    },
    hero: {
      kicker: 'Verifiable Algorithm Optimization Agent',
      lede: [
        'A verifiable algorithm optimization agent for C++ and Python.',
        'It establishes a behavioral contract first, explores optimizations in isolation, and uses real evidence to decide what to apply.',
      ],
      primary: 'Get Started',
      github: 'View GitHub',
      terminalTitle: 'algocode — first optimization',
      comments: ['# Check setup', '# Configure a model', '# Build the contract', '# Start optimizing'],
    },
    install: {
      eyebrow: 'Installation',
      title: 'Install',
      description:
        'Install with one command, configure a model, run the environment check, and start your first optimization.',
      docs: 'Read the Docs',
      star: 'Star on GitHub',
    },
    capabilities: {
      eyebrow: 'What it does',
      title: 'Not a black-box rewrite, but a verifiable process',
      description:
        'Point Algocode at a runnable project. It analyzes, captures a baseline, generates candidates, verifies behavior, benchmarks performance, and decides through gated phases.',
      items: [
        {
          title: 'Contract First',
          text: 'Before optimization, Algocode locks down public APIs, inputs and outputs, configuration semantics, errors, and boundary behavior. Speed cannot come at the cost of correctness.',
        },
        {
          title: 'Isolated Candidates',
          text: 'The CLI works in a Git worktree and the VS Code extension uses a temporary shadow workspace, so the original project is never modified directly.',
        },
        {
          title: 'Evidence-Driven Decisions',
          text: 'Correctness, Contract, and Benchmark results are persisted. Acceptance is based on real evidence, not the model’s own claims.',
        },
        {
          title: 'Rollback-Safe Delivery',
          text: 'Review, accept, and apply are separate steps. Inspect the diff and report before applying, and roll back through a manifest if needed.',
        },
      ],
    },
    features: {
      eyebrow: 'Capabilities',
      title: 'Safety boundaries built around evidence',
      description:
        'Algocode turns optimization into observable, verifiable, and reversible phases, each with explicit prerequisites and outputs.',
      items: [
        { title: 'Contract First', text: 'Behavior is defined before optimization begins, avoiding changes that are faster but wrong.' },
        { title: 'Evidence Driven', text: 'Correctness, contract, and performance results are all persisted for review.' },
        { title: 'Isolated Candidates', text: 'Git worktrees and shadow workspaces keep every candidate in an independent copy.' },
        { title: 'Human Controlled', text: 'Diff, review, and apply are separate so users can inspect evidence before accepting changes.' },
        { title: 'Fully Auditable', text: 'Model calls, tool calls, phase outcomes, and candidate snapshots are persisted.' },
        { title: 'Visible Progress', text: 'The terminal shows the phase, turn, active tool, and elapsed time in real time.' },
        { title: 'Retryable Failures', text: 'Failed directions, weak evidence, or blocked phases can be replanned from history.' },
        { title: 'Multiple Providers', text: 'Works with OpenAI, DeepSeek, Kimi, GLM, Claude, and any OpenAI-compatible service.' },
        { title: 'Local First', text: 'Runs locally by default, with Docker and WSL2 available as optional isolation layers.' },
        { title: 'CLI + VS Code', text: 'Terminal automation and editor workflows share the same verification and storage layers.' },
      ],
    },
    quickStart: {
      eyebrow: 'Quick Start',
      title: 'Complete your first optimization in five minutes',
      description:
        'After installation, a few commands take you from contract creation to candidate review and application.',
      requirements: ['Python 3.11+', 'Git', 'C++ compiler for C++ projects'],
      steps: [
        { title: 'Install', text: 'Install algocode-agent from PyPI or use an editable source checkout.' },
        { title: 'Configure a Model', text: 'Choose a provider, base URL, model ID, and API key. Credentials stay on your machine.' },
        { title: 'Check the Environment', text: 'Run doctor to verify Git, Python, compilers, and entrypoint requirements.' },
        { title: 'Start Optimizing', text: 'init creates the contract and baseline. optimize starts the full candidate workflow.' },
        { title: 'Review and Apply', text: 'Inspect review, diff, and report, then apply when satisfied and roll back if needed.' },
      ],
      terminal: {
        title: 'terminal — algocode',
        comments: [
          '# 1. Install Algocode',
          '# 2. Configure provider and verify environment',
          '# 3. Init contract and optimize',
          '# 4. Review and apply',
        ],
        installOk: '[OK] Successfully installed algocode-agent-0.1.2',
        providerOk: '[OK] provider: openai / API key stored locally',
        doctorOk: '[OK] Python 3.12 / Git / C++ toolchain ready',
        contractOk: '[OK] .algocode/contract.json created / baseline ready',
        optimizeStatus: '[ALGO] Status: completed / Correctness: passed',
        benchmark: '[ALGO] Baseline 0.7594s -> Candidate 0.5357s',
        improvement: '[ALGO] Improvement: 29.46%',
        applyOk: '[OK] candidate applied / rollback available',
      },
    },
    architecture: {
      eyebrow: 'Architecture',
      title: 'Two entry points, one auditable request path',
      description:
        'The CLI and VS Code extension ultimately use the same Application Services, Agent Runtime, verification, and storage layers.',
      requestPath: 'REQUEST PATH',
      flow: ['CLI / VS Code', 'Application', 'Agent Runtime', 'Tools', 'Storage'],
      note: 'Policy, Approval, and Sandbox constrain high-risk actions, while Git Workspace keeps candidates isolated from the original project.',
      layers: [
        { label: 'ENTRY', items: ['CLI Commands', 'VS Code Extension'] },
        { label: 'APPLICATION', items: ['Application Services', 'Domain'] },
        { label: 'RUNTIME', items: ['Agent Runtime', 'Model Providers', 'Python / C++ Adapters'] },
        { label: 'SUPPORT', items: ['Policy / Approval / Sandbox', 'Git Workspace'] },
        { label: 'PERSISTENCE', items: ['SQLite Event Store + Projections', 'File Artifact Store'] },
      ],
    },
    usage: {
      eyebrow: 'Two entry points',
      title: 'Choose the workflow that fits your habits',
      description:
        'One runtime, two interfaces. The terminal is built for automation and scripts; the editor is built for review and decisions.',
      cards: [
        {
          tag: 'CLI',
          title: 'Complete command-line workflow',
          text: 'Built for terminal automation, batch jobs, and scripts. Candidate isolation uses Git worktrees, with full init, optimize, review, apply, and rollback workflows.',
          checklist: [],
        },
        {
          tag: 'VS Code',
          title: 'An end-to-end editor workflow',
          text: 'Run inside a temporary shadow workspace and optimize from the context menu. Phase progress, diff, review, apply, and rollback all stay in the editor.',
          checklist: ['Live phase progress', 'Diff and review', 'Apply / rollback'],
        },
      ],
    },
    footer: {
      description:
        'A verifiable algorithm optimization agent for C++ and Python. Local first, evidence driven, and reversible.',
      resources: 'Resources',
      declarationTitle: 'Performance and Results Notice',
      declaration:
        'Algocode uses large language models to analyze source code and generate candidate optimizations. Performance may improve, remain unchanged, or regress. Results depend on source quality, project structure, model capability, input size, runtime environment, and system load. Algocode does not guarantee a positive result and does not replace human code review. Use the actual Correctness, Contract, Benchmark, Diff, and Review evidence, and apply only after verifying behavior and expected gains.',
      contributors: 'Contributors',
      license: 'MIT License',
    },
  },
}
