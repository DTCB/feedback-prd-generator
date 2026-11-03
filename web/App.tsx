import { useEffect, useState } from 'react';
import { ArrowRight, ArrowUpRight, BookOpen, Check, CheckCircle2, ChevronDown, ChevronRight, CircleHelp, FileText, Info, LayoutDashboard, Layers3, Menu, MessageSquareText, Plus, RotateCcw, Settings2, Sparkles, Target, Undo2, X } from 'lucide-react';
import useWorkspace from './useWorkspace';
import { AiLabel, Brand, ErrorNotice, ExportButton, Modal, Spinner, Tag } from './components';
import Overview from './Overview';
import FeedbackView from './FeedbackView';
import NeedsView from './NeedsView';
import PrdView from './PrdView';
import AboutView from './AboutView';
import { ContextDialog, ImportDialog, MergeDialog } from './Dialogs';
import { api, download, evidence, refreshReach, sourceLabel, type ApiStatus, type Need, type Page, type Workspace } from './types';

const NAV = [
  { id: 'overview', name: '洞察总览', icon: LayoutDashboard },
  { id: 'feedback', name: '反馈分析', icon: MessageSquareText },
  { id: 'needs', name: '需求决策', icon: Layers3 },
  { id: 'prd', name: 'PRD 工作台', icon: FileText },
] as const;
const pageFromHash = (): Page => {
  const hash = window.location.hash.slice(1);
  return ['overview', 'feedback', 'needs', 'prd', 'about'].includes(hash) ? hash as Page : 'overview';
};
const TOUR = [
  { title: '先从一个值得探索的问题开始', text: '查看案例主线和反馈分布。这里所有数量都来自当前工作区，演示样例不代表整体用户情况。', page: 'overview' },
  { title: '点击反馈，核对原文与分析依据', text: '在列表中选择一条反馈，对照用户场景、问题和原文。你可以看到每条分析由什么证据支持。', page: 'feedback' },
  { title: '完成一次人工校准', text: '点击“确认该条分析”，或修正分类、情绪和关联需求。修改会同步到需求池，并可以撤销。', page: 'feedback' },
  { title: '调整假设，观察优先级如何变化', text: '点击“校准评分”，调整成本或影响程度并写下依据。分数辅助讨论，最终取舍由你决定。', page: 'needs' },
  { title: '把需求整理成可评审的草稿', text: '生成模板或真实 AI 草稿，先预览再应用。切换“编辑”补充内容，点击引用核验原文，最后下载 Markdown。', page: 'prd' },
] as const;

export default function App() {
  const { workspace, setWorkspace, change, undoLast, undoCount, reset, replace, failure, storageWarning } = useWorkspace();
  const [page, setPage] = useState<Page>(pageFromHash), [mobileNav, setMobileNav] = useState(false);
  const [selectedNeed, setSelectedNeed] = useState(''), [focusNeed, setFocusNeed] = useState(''), [selectedFeedback, setSelectedFeedback] = useState('');
  const [dialog, setDialog] = useState<'import' | 'context' | 'merge' | 'reset' | null>(null);
  const [mergeId, setMergeId] = useState(''), [evidenceId, setEvidenceId] = useState('');
  const [toast, setToast] = useState<{ text: string; error?: boolean; id: number } | null>(null);
  const [aiStatus, setAiStatus] = useState<ApiStatus>({ ai_available: false, message: '实时 AI 尚未连接，完整案例和模板可以直接体验。' });
  const [exportBusy, setExportBusy] = useState(false), [analysisBusy, setAnalysisBusy] = useState(false);
  const [analysisPreview, setAnalysisPreview] = useState<{ workspace: Workspace; base: string } | null>(null);
  const [analysisError, setAnalysisError] = useState(''), [tour, setTour] = useState<number | null>(null);
  const notify = (text: string, error = false) => setToast({ text, error, id: Date.now() });
  useEffect(() => {
    const handle = () => setPage(pageFromHash()); window.addEventListener('hashchange', handle);
    api<ApiStatus>('status').then(setAiStatus).catch(() => {});
    return () => window.removeEventListener('hashchange', handle);
  }, []);
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(null), toast.error ? 12000 : 4500); return () => clearTimeout(timer); }, [toast]);
  useEffect(() => {
    if (workspace && !workspace.needs.some(need => need.id === selectedNeed)) setSelectedNeed((workspace.needs.find(need => need.title.includes('可追溯')) || workspace.needs[0]).id);
    if (workspace && focusNeed && !workspace.needs.some(need => need.id === focusNeed)) setFocusNeed('');
  }, [workspace, selectedNeed, focusNeed]);
  const go = (next: Page) => { setPage(next); window.location.hash = next; setMobileNav(false); window.scrollTo({ top: 0, behavior: 'instant' }); };
  if (!workspace) return <div className="app-loading"><Brand/><div>{failure ? <><ErrorNotice message={failure}/><button className="button primary" onClick={() => window.location.reload()}>重新载入</button></> : <Spinner label="正在整理演示案例…"/>}</div></div>;
  const need = workspace.needs.find(item => item.id === selectedNeed) || workspace.needs[0];
  const focus = workspace.needs.find(item => item.title.includes('可追溯')) || need;
  const visibleEvidence = workspace.feedback.find(item => item.id === evidenceId);
  const mergedNeed = workspace.needs.find(item => item.id === mergeId);
  const inspectFeedback = (needId?: string) => {
    setFocusNeed(needId || '');
    setSelectedFeedback(needId ? evidence(workspace, needId)[0]?.id || '' : ''); go('feedback');
  };
  const inspectNeed = (id: string) => { setSelectedNeed(id); go('needs'); };
  const inspectPrd = (id: string) => { setSelectedNeed(id); go('prd'); };
  const beginTour = () => { setTour(0); setSelectedNeed(focus.id); setFocusNeed(focus.id); setSelectedFeedback(evidence(workspace, focus.id)[0]?.id || ''); go('overview'); };
  const advanceTour = () => {
    if (tour == null) return;
    if (tour === TOUR.length - 1) { setTour(null); notify('已完成案例导览，你可以继续自由探索。'); return; }
    const next = tour + 1; setTour(next); setSelectedNeed(focus.id); go(TOUR[next].page);
  };
  const exportExcel = async () => {
    setExportBusy(true);
    try {
      const response = await fetch('/api/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(workspace), signal: AbortSignal.timeout(45000) });
      if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.detail || '导出服务暂不可用，请稍后重试。'); }
      download(await response.blob(), '反馈洞察-研究交付.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); notify('Excel 已下载，包含当前反馈、需求、文档和修改记录。');
    } catch (exception) { notify(exception instanceof Error ? exception.message : '导出失败，当前内容已保留。', true); }
    finally { setExportBusy(false); }
  };
  const analyzeSelected = async (ids: string[]) => {
    setAnalysisBusy(true); setAnalysisError(''); const base = JSON.stringify(workspace);
    try {
      const response = await api<{ workspace: Workspace }>('analyze', { workspace, mode: 'llm', selected_ids: ids });
      setAnalysisPreview({ workspace: response.workspace, base });
    } catch (exception) { notify(exception instanceof Error ? exception.message : '分析失败，当前内容已保留。', true); }
    finally { setAnalysisBusy(false); }
  };
  const applyMerge = (target: Need, title: string, reason: string) => {
    if (!mergedNeed) return;
    change('合并需求', `${mergedNeed.title}＋${target.title}：${reason}`, draft => {
      draft.feedback.forEach(item => { if (item.need_id === target.id) { item.need_id = mergedNeed.id; item.reviewed = false; } });
      draft.needs = draft.needs.filter(item => item.id !== target.id).map(item => item.id === mergedNeed.id ? refreshReach(draft, { ...item, title, status: 'pending' }) : item);
      const targetDoc = draft.documents[target.id], currentDoc = draft.documents[mergedNeed.id];
      if (targetDoc) draft.documents[mergedNeed.id] = { ...targetDoc, markdown: currentDoc ? currentDoc.markdown + `\n\n## 合并前文档：${target.title}\n\n` + targetDoc.markdown : targetDoc.markdown, stale: true, edited: true };
      delete draft.documents[target.id];
    });
    setSelectedNeed(mergedNeed.id); setDialog(null); notify('需求已合并，原始证据与文档已保留。');
  };
  const pageTitle = NAV.find(item => item.id === page)?.name || '关于项目';
  return <div className="app-shell">
    {mobileNav && <button className="sidebar-shade" aria-label="关闭导航" onClick={() => setMobileNav(false)}/>}
    <aside className={`sidebar ${mobileNav ? 'is-open' : ''}`}><button className="brand-button" onClick={() => go('overview')} aria-label="返回洞察总览"><Brand/></button><button className="workspace-switch" onClick={() => setDialog('context')}><span className="workspace-avatar"><Target size={18}/></span><span><strong>AI 产品研究空间</strong><small>个人作品 · 访客体验</small></span><ChevronDown size={14}/></button><div className="nav-section-label">工作台</div><nav aria-label="主导航">{NAV.map(item => <button key={item.id} className={`nav-item ${page === item.id ? 'active' : ''}`} aria-current={page === item.id ? 'page' : undefined} onClick={() => go(item.id)}><item.icon size={18}/><span>{item.name}</span>{item.id === 'feedback' && <small>{workspace.feedback.length}</small>}{item.id === 'needs' && <small>{workspace.needs.length}</small>}</button>)}</nav><div className="sidebar-separator"/><div className="nav-section-label">研究设置</div><button className="nav-item" onClick={() => setDialog('context')}><Settings2 size={18}/><span>产品背景</span></button><button className={`nav-item ${page === 'about' ? 'active' : ''}`} onClick={() => go('about')}><CircleHelp size={18}/><span>关于这个项目</span><ArrowUpRight size={14}/></button>
      <div className="sidebar-bottom"><div className="sidebar-guide"><span className="guide-icon"><Sparkles size={17}/></span><h3>第一次体验？</h3><p>跟随一个案例，走完从反馈到 PRD 的完整流程。</p><button onClick={beginTour}>开始案例导览<ArrowRight size={14}/></button></div><div className="session-status"><span className="user-avatar">访</span><span><strong>访客模式</strong><small>当前浏览器会话</small></span><span className="session-dot" title="免登录体验"/></div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div><button className="icon-button mobile-menu" aria-label="打开导航" aria-expanded={mobileNav} onClick={() => setMobileNav(!mobileNav)}><Menu size={20}/></button><span className="breadcrumb-root">研究工作台</span><ChevronRight size={13}/><strong>{pageTitle}</strong></div><div className="topbar-actions"><span className="session-save"><span className="live-dot"/>{storageWarning ? '会话存储不可用' : '会话自动保存'}</span><button className="icon-button undo-button" aria-label="撤销上次修改" title="撤销上次修改" disabled={!undoCount} onClick={() => { undoLast(); notify('已撤销上次修改。'); }}><Undo2 size={17}/></button><button className="icon-button" aria-label="重置演示案例" title="重置演示案例" onClick={() => setDialog('reset')}><RotateCcw size={16}/></button><ExportButton onClick={exportExcel} busy={exportBusy}/></div></header>
      <main className="main-content">
        {storageWarning && <div className="notice amber-notice"><Info size={15}/><span>浏览器无法保存当前会话。请及时下载结果，刷新可能丢失修改。</span></div>}
        {tour != null && <div className="tour-banner"><span className="tour-count">{tour + 1}<small>/ {TOUR.length}</small></span><div><strong>{TOUR[tour].title}</strong><p>{TOUR[tour].text}</p></div><div className="tour-actions"><button className="button small-button" onClick={advanceTour}>{tour === TOUR.length - 1 ? '完成导览' : '下一步'}<ArrowRight size={13}/></button><button className="icon-button" aria-label="退出案例导览" onClick={() => setTour(null)}><X size={16}/></button></div></div>}
        {page === 'overview' && <Overview workspace={workspace} onTour={beginTour} onImport={() => setDialog('import')} onNeed={inspectNeed} onFeedback={inspectFeedback} onContext={() => setDialog('context')}/>}
        {page === 'feedback' && <FeedbackView workspace={workspace} focusNeed={focusNeed} selectedId={selectedFeedback} setSelectedId={setSelectedFeedback} clearFocus={() => setFocusNeed('')} change={change} notify={notify} onNeed={inspectNeed} onAnalyze={analyzeSelected} busy={analysisBusy} aiStatus={aiStatus}/>}
        {page === 'needs' && <NeedsView workspace={workspace} selectedId={selectedNeed} onSelect={setSelectedNeed} change={change} notify={notify} onFeedback={inspectFeedback} onPrd={inspectPrd} onMerge={id => { setMergeId(id); setDialog('merge'); }}/ >}
        {page === 'prd' && <PrdView key={need.id} workspace={workspace} need={need} onSelect={setSelectedNeed} change={change} notify={notify} aiStatus={aiStatus} onEvidence={setEvidenceId} onEdit={(id, value) => setWorkspace(previous => previous ? { ...previous, documents: { ...previous.documents, [id]: { ...previous.documents[id], markdown: value, edited: true, updated_at: new Date().toISOString() } } } : previous)}/>}
        {page === 'about' && <AboutView/>}
      </main>
    </div>
    {toast && <div className={`toast ${toast.error ? 'toast-error' : ''}`} role={toast.error ? 'alert' : 'status'}>{toast.error ? <Info size={18}/> : <CheckCircle2 size={18}/>}<span>{toast.text}</span><button aria-label="关闭通知" onClick={() => setToast(null)}><X size={14}/></button></div>}
    {dialog === 'import' && <ImportDialog onClose={() => setDialog(null)} onApply={next => { next.context = workspace.context; replace(next, '导入反馈'); setDialog(null); setTour(null); setFocusNeed(''); go('feedback'); notify(`已导入 ${next.feedback.length} 条有效反馈。`); }}/ >}
    {dialog === 'context' && <ContextDialog context={workspace.context} onClose={() => setDialog(null)} onSave={context => { change('更新产品背景', context.product, draft => { draft.context = context; }); setDialog(null); notify('产品背景已保存，后续 AI 请求会使用新的上下文。'); }}/ >}
    {dialog === 'merge' && mergedNeed && <MergeDialog workspace={workspace} need={mergedNeed} onClose={() => setDialog(null)} onMerge={applyMerge}/ >}
    {dialog === 'reset' && <Modal title="重置为初始演示案例？" description="当前会话中的导入、校准和文档修改将被清除。需要保留的内容请先下载。" onClose={() => setDialog(null)}><div className="modal-actions"><button className="button secondary" onClick={() => setDialog(null)}>保留当前工作</button><button className="button primary" onClick={() => { reset(); setDialog(null); setTour(null); setFocusNeed(''); setSelectedNeed(''); go('overview'); notify('已恢复初始演示案例。'); }}>确认重置</button></div></Modal>}
    {visibleEvidence && <Modal title={`反馈证据 · ${visibleEvidence.id}`} description={`${visibleEvidence.app_name} · ${sourceLabel(visibleEvidence.source)} · ${visibleEvidence.date || '日期未提供'}`} onClose={() => setEvidenceId('')}><blockquote className="original-quote"><p>{visibleEvidence.text}</p></blockquote><div className="evidence-highlight"><span><LinkIcon/>引用片段</span><p><mark>{visibleEvidence.quote || visibleEvidence.text}</mark></p></div><p className="mini-note">{workspace.is_sample ? '此内容为演示样例，不代表已核验的公开用户调研。' : '此内容来自本次导入，判断时请结合来源与业务上下文。'}</p><div className="modal-actions"><button className="button secondary" onClick={() => setEvidenceId('')}>关闭</button><button className="button primary" onClick={() => { const item = visibleEvidence; setEvidenceId(''); setFocusNeed(item.need_id); setSelectedFeedback(item.id); go('feedback'); }}>在反馈分析中打开<ArrowRight size={14}/></button></div></Modal>}
    {analysisPreview && <Modal wide title="预览真实 AI 分析" description="应用后更新所选反馈及相关需求，其余反馈保留。" onClose={() => setAnalysisPreview(null)}><AiLabel>真实模型输出 · 已通过引用格式与原文校验</AiLabel><ErrorNotice message={analysisError}/><div className="analysis-preview-list">{analysisPreview.workspace.feedback.filter(item => item.origin === 'llm').map(item => <section key={item.id}><span><Tag>{item.id}</Tag><Tag tone="purple">{item.category}</Tag></span><p>{item.problem}</p><small>依据：“{item.quote}”</small></section>)}</div><div className="modal-actions"><button className="button secondary" onClick={() => setAnalysisPreview(null)}>保留当前分析</button><button className="button primary" onClick={() => { if (JSON.stringify(workspace) !== analysisPreview.base) { setAnalysisError('生成期间工作区已发生变化。为保留修改，请关闭预览并重新分析。'); return; } replace(analysisPreview.workspace, '应用 AI 分析'); setAnalysisPreview(null); notify('AI 分析已应用，请继续核验。'); }}><Check size={14}/>接受并应用分析</button></div></Modal>}
  </div>;
}

function LinkIcon() { return <BookOpen size={13}/>; }
