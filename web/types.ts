export type Page = 'overview' | 'feedback' | 'needs' | 'prd' | 'about';
export type Origin = 'sample' | 'rule' | 'llm';
export interface ProductContext { product: string; audience: string; goal: string; capabilities: string; constraints: string }
export interface Feedback {
  id: string; text: string; date: string; source: string; app_name: string; rating: number | null;
  user_type: string; module: string; thumbs_up: number; category: string;
  sentiment: 'positive' | 'negative' | 'neutral'; severity: 'Low' | 'Medium' | 'High' | 'Critical';
  need_id: string; reviewed: boolean; origin: Origin; quote: string;
  scenario: string; problem: string; request: string; reason: string;
}
export interface Need {
  id: string; title: string; description: string; category: string; module: string;
  feedback_ids: string[]; reach: number; impact: number; confidence: number; effort: number;
  status: 'pending' | 'confirmed' | 'deferred'; origin: Origin; score_reason: string;
}
export interface PrdDocument {
  markdown: string; origin: 'template' | 'llm' | 'sample'; edited: boolean; stale: boolean; updated_at: string;
}
export interface Workspace {
  feedback: Feedback[]; needs: Need[]; context: ProductContext; documents: Record<string, PrdDocument>;
  history: { time: string; action: string; detail: string }[]; is_sample: boolean; version: number;
  cleaning: { original: number; valid: number; empty: number; duplicates: number };
}
export interface ApiStatus { ai_available: boolean; message: string }
export const CATEGORIES = ['Bug', '功能需求', '体验问题', '内容质量问题', '咨询/付费问题'];
export const sentimentLabel = { positive: '正向', negative: '负向', neutral: '中性' };
export const originLabel = { sample: '演示预分析', rule: '规则分析', llm: '真实 AI 分析' };
export const sourceLabel = (source: string) => ({ google_play: 'Google Play', app_store: 'App Store', manual: '手动输入' }[source] || source);
export const needScore = (need: Need) => Math.round(need.reach * need.impact * need.confidence / need.effort * 100) / 100;
export const sortedNeeds = (workspace: Workspace) => [...workspace.needs].sort((a, b) => needScore(b) - needScore(a));
export const evidence = (workspace: Workspace, id: string) => workspace.feedback.filter(item => item.need_id === id);

export function synchronize(workspace: Workspace): Workspace {
  const needIds = new Set(workspace.needs.map(need => need.id));
  workspace.feedback = workspace.feedback.filter(item => needIds.has(item.need_id));
  workspace.needs = workspace.needs.map(need => ({ ...need, feedback_ids: evidence(workspace, need.id).map(item => item.id) }))
    .filter(need => need.feedback_ids.length > 0);
  const remaining = new Set(workspace.needs.map(need => need.id));
  workspace.documents = Object.fromEntries(Object.entries(workspace.documents).filter(([id]) => remaining.has(id)));
  return workspace;
}

export function refreshReach(workspace: Workspace, need: Need): Need {
  const items = evidence(workspace, need.id);
  const count = items.length;
  const likes = items.reduce((total, item) => total + item.thumbs_up, 0);
  return { ...need, reach: Math.round(Math.min(10, Math.min(8, 1.5 + Math.log2(Math.max(1, count) + 1) * 1.8) + (likes > 0 ? Math.min(2, Math.log2(likes + 1) * 0.45) : 0)) * 100) / 100,
    score_reason: '关联反馈变化后按反馈数与点赞数重新估计 Reach；其他参数保留人工判断。' };
}

export function templatePrd(workspace: Workspace, need: Need): string {
  const items = evidence(workspace, need.id);
  return `# PRD：${need.title}

## 1. 背景与问题
本次从 ${items.length} 条关联反馈中整理出「${need.title}」的问题线索。样本数量不代表整体用户规模。

## 2. 产品背景
- 产品：${workspace.context.product}
- 目标用户：${workspace.context.audience}
- 业务目标：${workspace.context.goal}
- 已有能力：${workspace.context.capabilities}
- 资源约束：${workspace.context.constraints}

## 3. 用户场景与诉求
${items.slice(0, 3).map(item => `- ${item.scenario}：${item.request} [${item.id}](#evidence-${item.id})`).join('\n')}

## 4. 目标与功能范围
以下为待评审的产品建议。
- 目标：减少用户核验和返工的成本，改善任务完成质量。
- 本期范围：围绕当前证据定义最小方案，补充必要的提示、状态与异常处理。
- 范围外：缺乏反馈依据的全局重构、商业策略调整和全量功能升级。

## 5. 核心方案与规则
1. 梳理原始反馈，确认具体触发场景与问题边界。
2. 为目标场景提供可理解、可操作的解决路径。
3. 证据不足时显示待确认状态，保留用户自主判断。
4. 对异常情况提供明确提示、恢复入口与重试方式。

## 6. 验收标准
- 主流程：用户能够在目标场景完成任务，结果可检查。
- 异常流程：失败或缺少信息时保留已有内容，提供下一步操作。
- 证据核验：引用可回到原文；有引用不代表结论已经正确。
- 目标值：基线、目标改善幅度和观察周期待业务确认。

## 7. 反馈证据
${items.map(item => `- [${item.id}](#evidence-${item.id})：${item.text}`).join('\n')}

## 8. 优先级与取舍
- Reach：${need.reach}（样本代理值）
- Impact：${need.impact}
- Confidence：${Math.round(need.confidence * 100)}%
- Effort：${need.effort} 人周（估计）
- RICE：${needScore(need)}
- 评估依据：${need.score_reason}

## 9. 风险与待确认
- 事实：关联反馈内容与上述证据一致；数据性质为${workspace.is_sample ? '演示样例' : '访客导入反馈'}。
- 建议：本草稿中的方案、规则和验收标准需人工评审。
- 待确认：真实用户覆盖、成本估计、基线指标与上线目标值。
- 验证计划：小范围任务测试、反馈回访与失败案例复盘。
`;
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 110000);
  try {
    const response = await fetch(`/api/${path}`, {
      ...(body !== undefined ? { method: 'POST', headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' }, body: body instanceof FormData ? body : JSON.stringify(body) } : {}),
      signal: controller.signal,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(typeof error.detail === 'string' ? error.detail : '服务暂不可用，当前内容已保留。');
    }
    return await response.json();
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new Error('请求超时，当前内容已保留。可稍后重试。');
    if (error instanceof TypeError) throw new Error('暂时无法连接服务，当前内容已保留。');
    throw error;
  } finally { clearTimeout(timer); }
}

export function download(content: BlobPart, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
