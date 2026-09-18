import * as childProcess from "child_process";
import * as crypto from "crypto";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as vscode from "vscode";

interface CliResult {
  stdout: string;
  stderr: string;
  code: number | null;
}

interface Envelope<T = unknown> {
  ok?: boolean;
  status?: string;
  data?: T;
  message?: string;
}

interface CandidateReview {
  candidate?: {
    id: string;
    workspace: string;
    changedFiles?: string[];
  };
}

interface ReviewInfo {
  task?: { status?: string; currentPhase?: string };
  candidate?: { id?: string; status?: string; changedFiles?: string[] };
  correctness?: { status?: string };
  benchmark?: {
    status?: string;
    comparison?: { improvement_percent?: number; valid?: boolean };
  };
  decision?: { outcome?: string; reason?: string };
}

interface FileBackup {
  path: string;
  existed: boolean;
  backupPath?: string;
}

interface LastRunRecord {
  projectRoot: string;
  shadow: string;
  taskId: string;
  candidateId?: string;
  candidateWorkspace?: string;
  changedFiles: string[];
  reportPath?: string;
  applied: boolean;
  backups: FileBackup[];
}

interface ActiveToolProgress {
  name?: string;
  elapsedSeconds?: number;
}

interface CompletedToolProgress {
  name?: string;
  status?: string;
  summary?: string;
}

interface TaskProgress {
  phase?: string;
  phaseElapsedSeconds?: number;
  turn?: number;
  toolCalls?: number;
  activeTool?: ActiveToolProgress;
  lastTool?: CompletedToolProgress;
  lastEvent?: string;
  lastEventSummary?: string;
}

interface TaskStatusData {
  currentPhase?: string;
  progress?: TaskProgress;
}

const OPTIMIZE_PHASES = [
  "analyze",
  "baseline",
  "plan",
  "generate_candidate",
  "implement",
  "verify",
  "benchmark",
  "compare",
  "decide",
  "report"
];

let output: vscode.OutputChannel | undefined;

class AlgocodeTerminal implements vscode.Pseudoterminal {
  private readonly writeEmitter = new vscode.EventEmitter<string>();
  private readonly closeEmitter = new vscode.EventEmitter<number>();
  private readonly pendingWrites: string[] = [];
  private opened = false;

  readonly onDidWrite = this.writeEmitter.event;
  readonly onDidClose = this.closeEmitter.event;

  open(): void {
    this.opened = true;
    for (const text of this.pendingWrites) {
      this.writeEmitter.fire(text);
    }
    this.pendingWrites.length = 0;
  }

  close(): void {
    this.closeEmitter.fire(0);
  }

  write(text: string): void {
    const normalized = text.replace(/\r?\n/g, "\r\n");
    if (this.opened) {
      this.writeEmitter.fire(normalized);
      return;
    }
    this.pendingWrites.push(normalized);
  }
}

let activeRunTerminal: vscode.Terminal | undefined;
let runTerminal: AlgocodeTerminal | undefined;
const pythonResolutionCache = new Map<string, string>();

function log(): vscode.OutputChannel {
  output ??= vscode.window.createOutputChannel("Algocode");
  return output;
}

function startRunTerminal(): void {
  activeRunTerminal?.dispose();
  runTerminal = new AlgocodeTerminal();
  activeRunTerminal = vscode.window.createTerminal({
    name: "Algocode",
    pty: runTerminal
  });
  activeRunTerminal.show(true);
}

function emitText(text: string): void {
  runTerminal?.write(text);
  log().append(text);
}

function emitLine(text = ""): void {
  emitText(`${text}\n`);
}

function workspaceRoot(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function isWithin(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function projectRootForFile(filePath: string, workspace: string): string {
  const markers = [
    ".algocode",
    ".algocode.yaml",
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "CMakeLists.txt",
    "Cargo.toml",
    "go.mod"
  ];
  const fileDirectory = path.dirname(filePath);
  let current = fileDirectory;

  while (isWithin(workspace, current)) {
    if (markers.some((marker) => fs.existsSync(path.join(current, marker)))) {
      return current;
    }
    if (path.resolve(current) === path.resolve(workspace)) {
      break;
    }
    const parent = path.dirname(current);
    if (parent === current) {
      break;
    }
    current = parent;
  }

  return fileDirectory;
}

function canImportAlgocode(executable: string): boolean {
  const result = childProcess.spawnSync(executable, ["-c", "import algocode"], {
    windowsHide: true,
    encoding: "utf8",
    timeout: 5000
  });
  return result.status === 0;
}

function resolvePython(cwd: string, configured: string): string {
  if (configured) {
    return configured;
  }

  const cached = pythonResolutionCache.get(cwd);
  if (cached) {
    return cached;
  }

  const roots = [workspaceRoot(), cwd].filter((value): value is string => Boolean(value));
  const venvCandidates = roots.flatMap((root) => [
    path.join(root, ".venv", "Scripts", "python.exe"),
    path.join(root, ".venv", "bin", "python")
  ]);

  for (const candidate of venvCandidates.filter((item) => fs.existsSync(item))) {
    if (canImportAlgocode(candidate)) {
      pythonResolutionCache.set(cwd, candidate);
      return candidate;
    }
  }

  for (const candidate of ["python", "py"]) {
    if (canImportAlgocode(candidate)) {
      pythonResolutionCache.set(cwd, candidate);
      return candidate;
    }
  }

  const fallback = venvCandidates.find((candidate) => fs.existsSync(candidate)) ?? "python";
  pythonResolutionCache.set(cwd, fallback);
  return fallback;
}

function cliCommand(cwd: string): { executable: string; prefix: string[] } {
  const config = vscode.workspace.getConfiguration("algocode");
  const usePythonModule = config.get<boolean>("usePythonModule", true);
  if (usePythonModule) {
    const configured = config.get<string>("pythonPath", "").trim();
    return {
      executable: resolvePython(cwd, configured),
      prefix: ["-m", "algocode"]
    };
  }
  return { executable: config.get<string>("command", "algocode"), prefix: [] };
}

function runCli(args: string[], cwd: string, mirrorToTerminal = false): Promise<CliResult> {
  const { executable, prefix } = cliCommand(cwd);
  return new Promise((resolve, reject) => {
    const child = childProcess.spawn(executable, [...prefix, ...args], {
      cwd,
      windowsHide: true,
      env: process.env
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk: Buffer) => {
      const text = chunk.toString("utf8");
      stdout += text;
      if (mirrorToTerminal) {
        emitText(text);
      } else {
        log().append(text);
      }
    });
    child.stderr.on("data", (chunk: Buffer) => {
      const text = chunk.toString("utf8");
      stderr += text;
      if (mirrorToTerminal) {
        emitText(text);
      } else {
        log().append(text);
      }
    });
    child.on("error", (error) => {
      if (mirrorToTerminal) {
        emitLine(`[algocode] failed to start ${executable}: ${String(error)}`);
      }
      reject(error);
    });
    child.on("close", (code) => resolve({ stdout, stderr, code }));
  });
}

function parseEnvelope<T>(result: CliResult): Envelope<T> {
  const text = result.stdout.trim();
  if (!text) {
    throw new Error(result.stderr.trim() || "Algocode returned no output");
  }
  try {
    return JSON.parse(text) as Envelope<T>;
  } catch (error) {
    throw new Error(`Unable to parse Algocode JSON output: ${String(error)}\n${text}`);
  }
}

function runInTerminal(command: string, cwd: string): void {
  const terminal = vscode.window.createTerminal({ name: "Algocode", cwd });
  terminal.show();
  terminal.sendText(command, true);
}

function shellQuote(value: string): string {
  return `"${value.replace(/"/g, '\\"')}"`;
}

function commandString(args: string[], cwd: string): string {
  const { executable, prefix } = cliCommand(cwd);
  return [executable, ...prefix, ...args].map(shellQuote).join(" ");
}

async function assertWorkspace(): Promise<string> {
  const root = workspaceRoot();
  if (!root) {
    throw new Error("Open a workspace folder before using Algocode.");
  }
  return root;
}

async function copyWorkspace(source: string, target: string): Promise<void> {
  const ignored = new Set([
    ".git",
    ".algocode",
    ".venv",
    "venv",
    "node_modules",
    "build",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache"
  ]);
  await fs.promises.cp(source, target, {
    recursive: true,
    force: true,
    filter: (item) => !ignored.has(path.basename(item))
  });
}

function shadowRoot(source: string): string {
  const digest = crypto.createHash("sha256").update(source).digest("hex").slice(0, 16);
  const runId = `${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
  return path.join(os.tmpdir(), "algocode-vscode", digest, runId);
}

function runKey(root: string): string {
  return path.resolve(root).toLowerCase();
}

function lastRunsPath(context: vscode.ExtensionContext): string {
  return path.join(context.globalStorageUri.fsPath, "last-runs.json");
}

async function readLastRuns(
  context: vscode.ExtensionContext
): Promise<Record<string, LastRunRecord>> {
  const file = lastRunsPath(context);
  try {
    const parsed = JSON.parse(await fs.promises.readFile(file, "utf8")) as unknown;
    return parsed && typeof parsed === "object"
      ? (parsed as Record<string, LastRunRecord>)
      : {};
  } catch {
    return {};
  }
}

async function writeLastRuns(
  context: vscode.ExtensionContext,
  records: Record<string, LastRunRecord>
): Promise<void> {
  const file = lastRunsPath(context);
  await fs.promises.mkdir(path.dirname(file), { recursive: true });
  await fs.promises.writeFile(file, JSON.stringify(records, null, 2), "utf8");
}

async function saveLastRun(
  context: vscode.ExtensionContext,
  record: LastRunRecord
): Promise<void> {
  const records = await readLastRuns(context);
  records[runKey(record.projectRoot)] = record;
  await writeLastRuns(context, records);
}

async function loadLastRun(
  context: vscode.ExtensionContext,
  projectRoot: string
): Promise<LastRunRecord | undefined> {
  return (await readLastRuns(context))[runKey(projectRoot)];
}

function assertSafeRelativePath(relative: string): void {
  const parsed = path.parse(relative);
  if (path.isAbsolute(relative) || parsed.root || relative.split(/[\\/]+/).includes("..")) {
    throw new Error(`Unsafe candidate path: ${relative}`);
  }
}

function backupRoot(context: vscode.ExtensionContext, taskId: string): string {
  return path.join(context.globalStorageUri.fsPath, "backups", taskId);
}

function formatDuration(value?: number): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "";
  }
  const total = Math.max(0, Math.floor(value));
  if (total < 60) {
    return `${total}s`;
  }
  const minutes = Math.floor(total / 60);
  return `${minutes}m${String(total % 60).padStart(2, "0")}s`;
}

function progressKey(progress: TaskProgress | undefined, phase: string): string {
  return JSON.stringify([
    phase,
    progress?.turn,
    progress?.toolCalls,
    progress?.activeTool?.name,
    progress?.lastTool?.name,
    progress?.lastTool?.status,
    progress?.lastTool?.summary,
    progress?.lastEventSummary
  ]);
}

function formatProgress(progress: TaskProgress | undefined, fallbackPhase: string): string {
  const phase = progress?.phase || fallbackPhase || "unknown";
  const parts = [phase];
  const phaseIndex = OPTIMIZE_PHASES.indexOf(phase);
  if (phaseIndex >= 0) {
    parts.push(`${phaseIndex + 1}/${OPTIMIZE_PHASES.length}`);
  }
  if (typeof progress?.turn === "number") {
    parts.push(`turn ${progress.turn}`);
  }
  if (progress?.activeTool?.name) {
    const elapsed = formatDuration(progress.activeTool.elapsedSeconds);
    parts.push(`running ${progress.activeTool.name}${elapsed ? ` (${elapsed})` : ""}`);
  } else if (progress?.lastTool?.name) {
    const status = progress.lastTool.status ? ` ${progress.lastTool.status}` : "";
    const summary = progress.lastTool.summary ? `: ${progress.lastTool.summary}` : "";
    parts.push(`${progress.lastTool.name}${status}${summary}`);
  } else if (progress?.lastEventSummary) {
    parts.push(progress.lastEventSummary);
  }
  if (typeof progress?.toolCalls === "number" && progress.toolCalls > 0) {
    parts.push(`tools ${progress.toolCalls}`);
  }
  const elapsed = formatDuration(progress?.phaseElapsedSeconds);
  if (elapsed) {
    parts.push(elapsed);
  }
  return `[algocode] ${parts.join(" | ")}`;
}

async function pollStatus(taskId: string, cwd: string, stop: { value: boolean }): Promise<void> {
  let lastProgressKey = "";
  let lastProgressAt = 0;
  while (!stop.value) {
    try {
      const result = await runCli(["status", taskId, "--json"], cwd);
      if (result.code === 0) {
        const envelope = parseEnvelope<TaskStatusData>(result);
        const data = envelope.data;
        const phase = data?.currentPhase ?? data?.progress?.phase ?? "";
        const key = progressKey(data?.progress, phase);
        const now = Date.now();
        if (phase && (key !== lastProgressKey || now - lastProgressAt >= 10_000)) {
          lastProgressKey = key;
          lastProgressAt = now;
          emitLine(formatProgress(data?.progress, phase));
        }
      }
    } catch {
      // Status polling is best effort while optimize is running.
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
}

async function resolveLastRun(
  context: vscode.ExtensionContext,
  uri?: vscode.Uri
): Promise<LastRunRecord> {
  const workspace = await assertWorkspace();
  const target = uri ?? vscode.window.activeTextEditor?.document.uri;
  const projectRoot =
    target && target.scheme === "file"
      ? projectRootForFile(target.fsPath, workspace)
      : workspace;
  const record = await loadLastRun(context, projectRoot);
  if (!record) {
    throw new Error("No Algocode run found for this project. Run Optimize first.");
  }
  return record;
}

async function openRunDiff(record: LastRunRecord, uri?: vscode.Uri): Promise<void> {
  if (!record.candidateWorkspace || record.changedFiles.length === 0) {
    vscode.window.showWarningMessage("The last Algocode run has no changed files.");
    return;
  }
  const relativeFromSelection = uri && uri.scheme === "file" ? path.relative(record.projectRoot, uri.fsPath) : "";
  const relative = record.changedFiles.includes(relativeFromSelection)
    ? relativeFromSelection
    : record.changedFiles[0];
  const originalUri = vscode.Uri.file(path.join(record.projectRoot, relative));
  const candidateUri = vscode.Uri.file(path.join(record.candidateWorkspace, relative));
  await vscode.commands.executeCommand(
    "vscode.diff",
    originalUri,
    candidateUri,
    `${relative} (Algocode Candidate)`
  );
}

async function applyRun(context: vscode.ExtensionContext, record: LastRunRecord): Promise<void> {
  if (!record.candidateWorkspace || record.changedFiles.length === 0) {
    vscode.window.showWarningMessage("The last Algocode run has no candidate changes to apply.");
    return;
  }
  if (record.applied) {
    vscode.window.showInformationMessage("The last Algocode run is already applied.");
    return;
  }

  const backups: FileBackup[] = [];
  for (const relative of record.changedFiles) {
    assertSafeRelativePath(relative);
    const source = path.join(record.candidateWorkspace, relative);
    const target = path.join(record.projectRoot, relative);
    let backupPath: string | undefined;
    const targetExists = fs.existsSync(target);
    const sourceExists = fs.existsSync(source);
    if (targetExists) {
      backupPath = path.join(backupRoot(context, record.taskId), relative);
      await fs.promises.mkdir(path.dirname(backupPath), { recursive: true });
      await fs.promises.copyFile(target, backupPath);
    }
    if (!sourceExists) {
      if (targetExists) {
        await fs.promises.rm(target, { force: true });
      }
      backups.push({ path: relative, existed: targetExists, backupPath });
      continue;
    }
    await fs.promises.mkdir(path.dirname(target), { recursive: true });
    await fs.promises.copyFile(source, target);
    backups.push({ path: relative, existed: targetExists, backupPath });
  }

  record.applied = true;
  record.backups = backups;
  await saveLastRun(context, record);
  vscode.window.showInformationMessage("Algocode changes applied.");
}

async function rollbackRun(context: vscode.ExtensionContext, record: LastRunRecord): Promise<void> {
  if (!record.applied) {
    vscode.window.showWarningMessage("The last Algocode run is not applied.");
    return;
  }
  for (const backup of record.backups) {
    assertSafeRelativePath(backup.path);
    const target = path.join(record.projectRoot, backup.path);
    if (backup.existed && backup.backupPath && fs.existsSync(backup.backupPath)) {
      await fs.promises.mkdir(path.dirname(target), { recursive: true });
      await fs.promises.copyFile(backup.backupPath, target);
    } else if (fs.existsSync(target)) {
      await fs.promises.rm(target, { force: true });
    }
  }
  record.applied = false;
  record.backups = [];
  await saveLastRun(context, record);
  vscode.window.showInformationMessage("Algocode changes rolled back.");
}

async function reviewRun(record: LastRunRecord): Promise<void> {
  const result = await runCli(["review", record.taskId, "--json"], record.shadow);
  const envelope = parseEnvelope<ReviewInfo>(result);
  const info = envelope.data;
  const comparison = info?.benchmark?.comparison;
  const changed = info?.candidate?.changedFiles ?? record.changedFiles;
  const lines = [
    `Candidate: ${info?.candidate?.status ?? "unknown"}`,
    `Changed files: ${changed.length}`,
    `Correctness: ${info?.correctness?.status ?? "unknown"}`,
    `Benchmark: ${info?.benchmark?.status ?? "unknown"}`,
    `Improvement: ${comparison?.improvement_percent ?? "not available"}%`,
    `Decision: ${info?.decision?.outcome ?? "not made"}`
  ];
  const actions = ["Open Diff"];
  if (record.reportPath && fs.existsSync(record.reportPath)) {
    actions.push("Open Report");
  }
  const choice = await vscode.window.showInformationMessage(lines.join("\n"), ...actions);
  if (choice === "Open Diff") {
    await openRunDiff(record);
  } else if (choice === "Open Report" && record.reportPath) {
    await vscode.commands.executeCommand("markdown.showPreview", vscode.Uri.file(record.reportPath));
  }
}

async function runFileOptimize(context: vscode.ExtensionContext, fileUri: vscode.Uri): Promise<void> {
  const workspace = await assertWorkspace();
  const sourceRoot = projectRootForFile(fileUri.fsPath, workspace);
  const relativeFile = path.relative(sourceRoot, fileUri.fsPath);
  if (relativeFile.startsWith("..")) {
    throw new Error("The selected file must be inside the current workspace.");
  }

  startRunTerminal();
  emitLine(`[algocode] project root: ${sourceRoot}`);
  emitLine("[algocode] starting file optimization");
  emitLine(`[algocode] target file: ${relativeFile}`);

  const shadow = shadowRoot(sourceRoot);
  await fs.promises.mkdir(path.dirname(shadow), { recursive: true });
  emitLine(`[algocode] shadow workspace: ${shadow}`);
  await copyWorkspace(sourceRoot, shadow);

  emitLine("[algocode] initializing project contract and baseline...");

  const initResult = await runCli(["init", "--path", shadow, "--json"], shadow);
  const initEnvelope = parseEnvelope<{ task: { id: string } }>(initResult);
  const taskId = initEnvelope.data?.task.id;
  if (!taskId) {
    throw new Error("Algocode init did not return a task id.");
  }

  emitLine(`[algocode] task: ${taskId}`);
  emitLine("[algocode] optimizing...");
  const stop = { value: false };
  const polling = pollStatus(taskId, shadow, stop);
  const optimizeResult = await runCli(["optimize", taskId, "--json"], shadow);
  stop.value = true;
  await polling;
  const optimizeEnvelope = parseEnvelope(optimizeResult);
  if (optimizeResult.code !== 0 || optimizeEnvelope.status !== "completed") {
    throw new Error(optimizeEnvelope.message || "Algocode optimize did not complete.");
  }

  emitLine("[algocode] optimize completed; loading candidate diff...");

  const reviewResult = await runCli(["review", taskId, "--json"], shadow);
  const reviewEnvelope = parseEnvelope<CandidateReview>(reviewResult);
  const candidate = reviewEnvelope.data?.candidate;
  const changedFiles = candidate?.changedFiles ?? [];
  const record: LastRunRecord = {
    projectRoot: sourceRoot,
    shadow,
    taskId,
    candidateId: candidate?.id,
    candidateWorkspace: candidate?.workspace,
    changedFiles,
    reportPath: path.join(shadow, "report.md"),
    applied: false,
    backups: []
  };
  await saveLastRun(context, record);
  emitLine(`[algocode] changed files: ${changedFiles.length}`);
  changedFiles.forEach((file) => emitLine(`  - ${file}`));

  if (candidate && changedFiles.length > 0) {
    const candidateFile = changedFiles.includes(relativeFile) ? relativeFile : changedFiles[0];
    const originalUri = vscode.Uri.file(path.join(sourceRoot, candidateFile));
    const candidateUri = vscode.Uri.file(path.join(candidate.workspace, candidateFile));
    emitLine(`[algocode] opening diff: ${candidateFile}`);
    await vscode.commands.executeCommand(
      "vscode.diff",
      originalUri,
      candidateUri,
      `${candidateFile} (Algocode Candidate)`
    );

    const choice = await vscode.window.showInformationMessage(
      `Algocode completed. ${changedFiles.length} file(s) changed.`,
      "Apply All",
      "Open Report",
      "Discard"
    );
    if (choice === "Apply All") {
      await applyRun(context, record);
    } else if (choice === "Open Report") {
      const report = path.join(shadow, "report.md");
      if (fs.existsSync(report)) {
        await vscode.commands.executeCommand("markdown.showPreview", vscode.Uri.file(report));
      }
    }
  } else {
    vscode.window.showInformationMessage("Algocode completed with no changed files.");
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const register = (command: string, callback: (...args: any[]) => unknown) =>
    context.subscriptions.push(vscode.commands.registerCommand(command, callback));

  register("algocode.api", async () => {
    const root = await assertWorkspace();
    runInTerminal(commandString(["api"], root), root);
  });
  register("algocode.test", async () => {
    const root = await assertWorkspace();
    runInTerminal(commandString(["test"], root), root);
  });
  register("algocode.model", async () => {
    const root = await assertWorkspace();
    runInTerminal(commandString(["model"], root), root);
  });
  register("algocode.init", async () => {
    const root = await assertWorkspace();
    runInTerminal(commandString(["init"], root), root);
  });
  register("algocode.optimize", async () => {
    const root = await assertWorkspace();
    runInTerminal(commandString(["optimize"], root), root);
  });
  register("algocode.status", async () => {
    const root = await assertWorkspace();
    runInTerminal(commandString(["status"], root), root);
  });
  register("algocode.report", async () => {
    const root = await assertWorkspace();
    const report = path.join(root, "report.md");
    if (!fs.existsSync(report)) {
      vscode.window.showWarningMessage("report.md does not exist. Run Algocode Report first.");
      return;
    }
    await vscode.commands.executeCommand("markdown.showPreview", vscode.Uri.file(report));
  });
  register("algocode.apply", async (uri?: vscode.Uri) => {
    try {
      const record = await resolveLastRun(context, uri);
      await applyRun(context, record);
    } catch (error) {
      vscode.window.showErrorMessage(`Algocode apply failed: ${String(error)}`);
    }
  });
  register("algocode.rollback", async (uri?: vscode.Uri) => {
    try {
      const record = await resolveLastRun(context, uri);
      await rollbackRun(context, record);
    } catch (error) {
      vscode.window.showErrorMessage(`Algocode rollback failed: ${String(error)}`);
    }
  });
  register("algocode.diff", async (uri?: vscode.Uri) => {
    try {
      const record = await resolveLastRun(context, uri);
      await openRunDiff(record, uri);
    } catch (error) {
      vscode.window.showErrorMessage(`Algocode diff failed: ${String(error)}`);
    }
  });
  register("algocode.review", async (uri?: vscode.Uri) => {
    try {
      const record = await resolveLastRun(context, uri);
      await reviewRun(record);
    } catch (error) {
      vscode.window.showErrorMessage(`Algocode review failed: ${String(error)}`);
    }
  });
  register("algocode.optimizeFile", async (uri?: vscode.Uri) => {
    const target = uri ?? vscode.window.activeTextEditor?.document.uri;
    if (!target || target.scheme !== "file") {
      vscode.window.showWarningMessage("Select a Python or C++ file first.");
      return;
    }
    try {
      await runFileOptimize(context, target);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      emitLine(`[algocode] ERROR: ${detail}`);
      log().appendLine(detail);
      vscode.window.showErrorMessage(`Algocode failed: ${detail}`);
    }
  });
}

export function deactivate(): void {}
