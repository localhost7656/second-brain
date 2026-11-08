// Data data, which the program gives to the plugin: snapshot .system/ui.json team-up (@@RESULT).

export interface ThrValue {
  value: number;
  source: "own" | "parent" | "global";
  from: string | null;
}

export interface ThrInfo {
  kind: "int" | "float";
  min: number;
  max: number;
  step: number;
  label: string;
  help: string;
  per_container: boolean;
}

export interface UiProduct {
  title: string;
  path: string;
  needs_review: boolean;
}

export interface UiBase {
  items: number;
  primary: number;
  excluded: number;
  built: string | null;
  conflicts: number;
}

export interface UiContainer {
  id: string;
  title: string;
  path: string;
  folder: string;
  type: string;
  type_ru: string;
  status: string;
  status_ru: string;
  color: string | null;
  parent_id: string | null;
  depth: number;
  description: string;
  last_modified: string;
  entities: number;
  shared: number;
  revalidate_count: number;
  products: UiProduct[];
  base: UiBase | null;
  dirty: boolean;
  dirty_reasons: string[];
  overrides: Record<string, number>;
  thresholds: Record<string, ThrValue>;
  style: string;
  style_effective: string;
  style_from: string | null;
  questions: number;
  views: { pool?: string; base?: string };
}

export interface UiQuestion {
  id: string;
  kind: string;
  title: string;
  text: string;
  created: string | null;
  options: { index: number; label: string }[];
  free_text: boolean;
  free_hint: string;
  note: string | null;
  container: string | null;
  entity: string | null;
  entity_path: string | null;
}

export interface UiStatus {
  containers: number;
  entities: number;
  products: number;
  stages: { done: number; quarantine: number; queue: number };
  files: Record<string, number>;
  questions: number;
  dirty: { id: string; title: string }[];
  structure_pending: boolean;
  approved_once: boolean;
  draft: string | null;
  webchat_pending: { req: string; ans: string; prompt: string }[];
  staging_new: number;
  pending_work: boolean;
  first_run: boolean;
}

// ---------- expense (section 14) ----------
export interface UsageTotals {
  calls: number;
  in: number;
  out: number;
  cached: number;
  cost: number;
  unpriced: number;
  sec: number;
  est: number;
}

export type Period = "today" | "month" | "prev_month" | "all";
export type UsagePeriods = Record<Period, UsageTotals>;

export interface Prices {
  input: number | null;
  cached_input: number | null;
  output: number | null;
}

export interface UsageProfile {
  key: string;
  id: string | null;
  name: string;
  ptype: string | null; // cloud | local | webchat | fake
  kind: string; // llm | emb
  model: string;
  exists: boolean;
  prices: Prices | null;
  priced: boolean | null;
  budget_month: number | null;
  budget_pct?: number;
  budget_state?: "ok" | "warn" | "over";
  active: boolean;
  steps: string[];
  totals: UsagePeriods;
  last: string | null;
}

export interface UsageDay {
  date: string;
  calls: number;
  in: number;
  out: number;
  cost: number;
  sec: number;
  unpriced: number;
}

export interface UsageRun extends UsageTotals {
  run: string;
  cmd: string | null;
  started: string;
  ended: string;
}

export interface UsageSummary {
  currency: string;
  today: string;
  month: string;
  prev_month: string;
  totals: UsagePeriods;
  profiles: UsageProfile[];
  steps: { name: string; totals: UsagePeriods }[];
  days: UsageDay[];
  runs: UsageRun[];
  budget: { monthly_usd: number | null; warn_pct: number; spent: number; pct: number | null; state: "ok" | "warn" | "over" | null; unpriced: number };
  current: { mode: string; key: string | null; name: string | null; ptype: string | null; totals: UsagePeriods | null };
}

/** Results of the current launch (liveline @@USAGE team-up). */
export interface RunUsage {
  calls: number;
  in: number;
  out: number;
  cached: number;
  cost: number;
  sec: number;
  unpriced: number;
  elapsed: number;
}

export interface UsageEvent {
  prompt: string;
  kind: string;
  profile: string | null;
  profile_name: string | null;
  ptype: string | null;
  model: string;
  in: number;
  out: number;
  cached: number;
  est: boolean;
  sec: number | null;
  cost: number | null;
  run: RunUsage;
}

export interface ProgressEvent {
  stage: string;
  n: number;
  total: number;
  item: string;
  level: number;
  t: number;
  unit?: string; // "%" — n its interest (modelling): «Downloading the model: 45% · 3,6 from 8,1 GB»
}

export interface AskEvent {
  id: string;
  title: string;
  text: string;
  lines: string[];
  options: string[];
}

export interface Estimate {
  title: string;
  calls: number;
  webchat: number;
  in: number;
  out: number;
  minutes: number;
  cost: number | null;
  unpriced: string[];
  basis: string;
  steps: Record<string, number>;
  lines: string[];
}

export interface UpdateInfo {
  repo: string;
  url: string;
  current: string;
  source?: "release" | "branch";
  version?: string;
  tag?: string;
  branch?: string;
  notes?: string;
  published?: string;
  asset?: string;
  newer: boolean;
}

export interface InstallInfo {
  version: string;
  updated: number;
  added: number;
  removed: string[];
  prompts_backed_up: string[];
  plugin: string | null;
  pip: boolean | null;
  notes: string[];
}

export interface UiSnapshot {
  version: number;
  program: string;
  generated: string;
  vault: string;
  status: UiStatus;
  containers: UiContainer[];
  questions: UiQuestion[];
  thresholds: Record<string, number>;
  threshold_info: Record<string, ThrInfo>;
  threshold_aliases: Record<string, string>;
  types: Record<string, string>;
  statuses: Record<string, string>;
  sources: { name: string; color: string }[];
  usage?: UsageSummary;
  updates?: { repo: string; check_on_start: boolean };
  logs: { changes?: string; reasoning?: string; archive?: string; errors?: string };
  warnings: string[];
  notices: string[];
}

export interface AdviceRec {
  name: string;
  label: string;
  current: number;
  source: string;
  from: string | null;
  value: number;
  reasoning: string;
  help: string;
  kind: string;
  min: number;
  max: number;
  step: number;
}

export interface Advice {
  container: { id: string; title: string; type: string; type_ru: string };
  summary: string;
  recommendations: AdviceRec[];
  brief: string[];
  ref: string;
}

export interface CheckItem {
  name: string;
  ok: boolean;
  text: string;
}

export interface SchemaField {
  key: string;
  type: string;
  label: string;
  help: string;
  min?: number;
  max?: number;
  step?: number;
  choices?: Record<string, string>;
  placeholder?: string;
  target?: string;
  prompts?: string[];
  prompt_help?: Record<string, string>;
  /** stepping-step, which have a long material divided into parts by «limit» */
  split_prompts?: string[];
  /** slider */
  slider?: boolean;
  /** field, If the other field has a value, */
  show_if?: Record<string, string[]>;
  /** What profiles does the field have? (field) */
  kinds?: string[];
  group?: string;
}

export interface SchemaSection {
  id: string;
  tab?: string;
  title: string;
  advanced?: boolean;
  help?: string;
  fields: SchemaField[];
}

export interface SettingsInfo {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  values: any;
  schema: SchemaSection[];
  keys: { llm: boolean; embeddings: boolean; profiles: Record<string, boolean> };
  path: string;
  program_dir: string;
  prompts_dir: string;
  prompts: string[];
  version: string;
  tabs: Record<string, string>;
  profile_fields: SchemaField[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  profile_defaults: Record<string, any>;
  modes: Record<string, string>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  defaults: any;
  /** repository reference for updates — UPDATE_REPO into brain/__init__.py (empty — non-inscribed) */
  update_repo?: string;
}

/** Parameters of launching your embedding model (embeddings.server) */
export interface LlamaParams {
  device: "cpu" | "gpu";
  build: "auto" | "cpu" | "vulkan" | "cuda";
  gpu_layers: "auto" | "all" | number;
  ctx: number;
  kv_cache: string;
  threads: number;
  port: number;
  sleep_min: number;
  autostart: boolean;
  models_dir: string;
}

export interface LlamaGpu {
  name: string;
  vram_gb?: number | null;
  vendor?: string;
}

export interface LlamaHardware {
  ram_gb: number | null;
  ram_free_gb: number | null;
  cores: number | null;
  threads: number | null;
  cpu: string;
  gpus: LlamaGpu[];
  nvidia: boolean;
  os: string;
  arch: string;
}

export interface LlamaPlanItem {
  what: string;
  title: string;
  size: number;
  note: string;
}

export interface LlamaServer {
  running: boolean;
  pid?: number;
  port?: number;
  url?: string;
  build?: string;
  tag?: string;
  params?: LlamaParams;
  devices?: string[];
  started?: string;
  dim?: number | null;
  load_sec?: number | null;
  health?: "ok" | "loading" | "error" | null;
  already?: boolean;
  foreign?: boolean;
}

export interface LlamaStatus {
  model: {
    file: string; title: string; alias: string; path: string; dir: string; exists: boolean; size: number; partial: number;
    layers: number; dim: number; ctx_max: number; free: number | null;
  };
  builds: Record<string, { build: string; exe: string; tag: string; dir: string }>;
  system: string | null;
  server: LlamaServer;
  params: LlamaParams;
  defaults: LlamaParams;
  configured: boolean;
  default_models_dir: string;
  log: string;
  home: string;
  approx_mb: Record<string, number>;
  min_ram_gb: number;
  vram_gb: number;
  ctx_choices: number[];
  need_gb?: Record<string, number>; // How much memory does a model with that context take?, GB
  kv_types: string[];
  os: string;
  arch: string;
  vcredist_missing: boolean;
  hardware?: LlamaHardware;
  plan?: { build: string; exe: string | null; download: LlamaPlanItem[]; download_size: number } | null;
}

export interface RunResult {
  cmd?: string;
  ok: boolean;
  code?: number;
  title?: string;
  stats?: Record<string, number>;
  calls?: Record<string, number>;
  notices?: string[];
  warnings?: string[];
  questions?: number;
  messages?: string[];
  error?: string;
  stopped?: boolean;
  webchat?: boolean;
  unchanged?: boolean;
  count?: number;
  container?: string | null;
  advice?: Advice;
  settings?: SettingsInfo;
  check?: CheckItem[];
  accepted?: boolean;
  note?: string | null;
  qid?: string;
  path?: string;
  // v2.5
  estimate?: Estimate;
  over?: boolean;
  run_usage?: RunUsage;
  elapsed?: number;
  run_id?: string;
  cancelled?: boolean;
  budget_stop?: boolean;
  usage?: UsageSummary;
  repriced?: number;
  update?: UpdateInfo;
  installed?: InstallInfo;
  restart?: boolean;
  // v2.7
  llama?: LlamaStatus;
  server?: LlamaServer;
}
