import { useState } from 'react';
import { ArrowRight, Check, FileSpreadsheet, GitMerge, UploadCloud } from 'lucide-react';
import { ErrorNotice, Modal, Spinner, Tag } from './components';
import { api, download, evidence, needScore, type Need, type ProductContext, type Workspace } from './types';

export function ImportDialog({ onClose, onApply }: { onClose: () => void; onApply: (workspace: Workspace) => void }) {
  const [tab, setTab] = useState<'file' | 'text'>('file'), [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [result, setResult] = useState<Workspace | null>(null);
  const inspect = async () => {
    setError(''); setResult(null);
    const content = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
    if (tab === 'file' && (!file || !/\.(csv|xlsx)$/i.test(file.name))) { setError('请选择 CSV 或 XLSX 文件。'); return; }
    if (file && tab === 'file' && file.size > 2 * 1024 * 1024) { setError('文件不能超过 2MB。'); return; }
    if (tab === 'text' && (!content.length || content.length > 500)) { setError('请提供 1–500 条反馈，每行一条。'); return; }
    const upload = tab === 'file' ? file! : new File(['feedback_text,source,app_name\n' + content.map(line => `"${line.replaceAll('"', '""')}",manual,我的产品`).join('\n')], 'feedback.csv', { type: 'text/csv' });
    const form = new FormData(); form.append('file', upload);
    setBusy(true);
    try { setResult(await api<Workspace>('import', form)); }
    catch (exception) { setError(exception instanceof Error ? exception.message : '导入失败，请检查文件。'); }
    finally { setBusy(false); }
  };
  return <Modal title="开始一次新的反馈研究" description="导入后先预览清洗结果，再决定是否替换当前工作区。" onClose={() => { if (!busy) onClose(); }}><div className="dialog-tabs"><button className={tab === 'file' ? 'active' : ''} onClick={() => { setTab('file'); setResult(null); }}>上传文件</button><button className={tab === 'text' ? 'active' : ''} onClick={() => { setTab('text'); setResult(null); }}>粘贴反馈</button></div>
    {tab === 'file' ? <><label className={`upload-zone ${file ? 'has-file' : ''}`}><UploadCloud size={29}/><strong>{file?.name || '点击选择，或拖入反馈文件'}</strong><span>CSV / XLSX · 最大 2MB · 最多 500 条</span><input aria-label="上传反馈文件" type="file" accept=".csv,.xlsx" onChange={event => { setFile(event.target.files?.[0] || null); setResult(null); setError(''); }} onDragOver={event => event.preventDefault()}/></label><div className="upload-template"><span>至少包含一列反馈文字，支持中英文字段名。</span><button className="text-link" onClick={() => download('\uFEFF反馈内容,来源,产品,评分\n"希望回答提供可核验的来源",手动输入,我的AI助手,3\n"导出后文档排版混乱",手动输入,我的AI助手,2', '反馈导入模板.csv', 'text/csv;charset=utf-8')}>下载模板<ArrowRight size={13}/></button></div></> : <label className="field-label">每行一条用户反馈<textarea className="paste-area" aria-label="粘贴反馈文本" maxLength={500000} value={text} onChange={event => { setText(event.target.value); setResult(null); }} placeholder={'希望 AI 的事实回答提供引用来源，方便我核验。\n导出文档后标题和列表的格式都乱了。'}/></label>}
    <ErrorNotice message={error}/>
    {result && <div className="import-result"><div><Check size={17}/><strong>已完成规则预分析</strong></div><div className="import-stats"><span><strong>{result.cleaning.original}</strong>原始记录</span><span><strong>{result.cleaning.valid}</strong>有效反馈</span><span><strong>{result.cleaning.duplicates}</strong>重复项</span><span><strong>{result.cleaning.empty}</strong>空文本</span></div><p>将创建 {result.needs.length} 个需求线索。应用后替换当前工作区，可通过撤销恢复。</p></div>}
    <div className="notice subtle import-privacy">文件仅用于本次解析，不持久化到服务器。实时 AI 仅在你主动发起时调用；请使用已脱敏内容。</div><div className="modal-actions"><button className="button secondary" onClick={onClose} disabled={busy}>取消</button>{result ? <button className="button primary" onClick={() => onApply(result)}><Check size={14}/>应用导入结果</button> : <button className="button primary" disabled={busy || (tab === 'file' ? !file : !text.trim())} onClick={inspect}>{busy ? <Spinner label="正在解析…"/> : <><FileSpreadsheet size={15}/>预览导入与分析</>}</button>}</div>
  </Modal>;
}

export function ContextDialog({ context, onClose, onSave }: { context: ProductContext; onClose: () => void; onSave: (context: ProductContext) => void }) {
  const [draft, setDraft] = useState(context);
  const fields: { key: keyof ProductContext; label: string; tip: string }[] = [
    { key: 'product', label: '产品定位', tip: '产品是什么，主要服务什么任务？' },
    { key: 'audience', label: '目标用户', tip: '谁会在什么场景使用它？' },
    { key: 'goal', label: '当前业务目标', tip: '这轮迭代希望改善什么？' },
    { key: 'capabilities', label: '已有产品能力', tip: '哪些功能已经存在？' },
    { key: 'constraints', label: '资源与范围约束', tip: '时间、成本和本期边界是什么？' },
  ];
  return <Modal title="产品背景" description="这些信息会随请求传给 AI，帮助它理解你的业务目标和方案边界。" onClose={onClose}><div className="context-form">{fields.map(field => <label key={field.key}>{field.label}<textarea maxLength={1500} aria-label={field.label} value={draft[field.key]} placeholder={field.tip} onChange={event => setDraft(previous => ({ ...previous, [field.key]: event.target.value }))}/></label>)}</div><div className="modal-actions"><button className="button secondary" onClick={onClose}>取消</button><button className="button primary" disabled={fields.some(field => !draft[field.key].trim())} onClick={() => onSave(draft)}><Check size={14}/>保存背景</button></div></Modal>;
}

export function MergeDialog({ workspace, need, onClose, onMerge }: { workspace: Workspace; need: Need; onClose: () => void; onMerge: (target: Need, title: string, reason: string) => void }) {
  const [targetId, setTargetId] = useState(workspace.needs.find(item => item.id !== need.id)?.id || '');
  const [title, setTitle] = useState(need.title), [reason, setReason] = useState('');
  const target = workspace.needs.find(item => item.id === targetId);
  const combinedLength = (workspace.documents[need.id]?.markdown.length || 0) + (workspace.documents[targetId]?.markdown.length || 0);
  return <Modal wide title="先比较诉求，再决定是否合并" description="相同关键词不一定意味着同一个问题。请核对用户场景和目标。" onClose={onClose}><label className="field-label">选择要合并的另一个需求<select aria-label="选择合并需求" value={targetId} onChange={event => setTargetId(event.target.value)}>{workspace.needs.filter(item => item.id !== need.id).map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label><div className="merge-comparison">{[need, target].filter(Boolean).map(item => item && <section key={item.id}><Tag tone="purple">{item.id === need.id ? '当前需求' : '待合并需求'}</Tag><h3>{item.title}</h3><p>{item.feedback_ids.length} 条反馈 · RICE {needScore(item).toFixed(2)}</p>{evidence(workspace, item.id).slice(0, 2).map(row => <blockquote key={row.id}><small>{row.id}</small>{row.text}</blockquote>)}</section>)}</div><div className="form-two-columns"><label>合并后的需求标题<input aria-label="合并后的需求标题" value={title} maxLength={300} onChange={event => setTitle(event.target.value)}/></label><label>合并依据<input aria-label="合并理由" value={reason} maxLength={600} placeholder="说明两者为什么属于同一需求" onChange={event => setReason(event.target.value)}/></label></div><p className="mini-note">原始反馈保留，Reach 重新估计，其余评分保留当前需求值；已有文档会合并保留并标记待复核。此操作可以撤销。</p>{combinedLength > 39000 && <ErrorNotice message="两个文档合计过长，请先导出并缩短文档后合并。"/>}<div className="modal-actions"><button className="button secondary" onClick={onClose}>保持独立</button><button className="button primary" disabled={!target || !reason.trim() || !title.trim() || combinedLength > 39000} onClick={() => target && onMerge(target, title.trim(), reason.trim())}><GitMerge size={15}/>确认合并</button></div></Modal>;
}
