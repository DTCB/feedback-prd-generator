import { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowDownToLine, BookOpen, Check, FilePlus2, FileText, Link2, PencilLine, Sparkles } from 'lucide-react';
import { AiLabel, Empty, ErrorNotice, Modal, PageHeading, Spinner, Tag } from './components';
import { api, download, evidence, templatePrd, type ApiStatus, type Need, type PrdDocument, type Workspace } from './types';
import type { Change } from './FeedbackView';

export function Markdown({ text, onEvidence }: { text: string; onEvidence?: (id: string) => void }) {
  return <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{
    a: ({ href, children }) => href?.startsWith('#evidence-') ? <button className="citation" onClick={() => onEvidence?.(href.slice(10))}>{children}<Link2 size={10}/></button> : <a href={href} target="_blank" rel="noreferrer">{children}</a>,
    h2: ({ children }) => <h2 id={`section-${String(children).replace(/\s+/g, '-')}`}>{children}</h2>,
  }}>{text}</ReactMarkdown></div>;
}

type Preview = { markdown: string; origin: PrdDocument['origin']; base: string; needId: string; section: string; signature: string };

const generationSignature = (workspace: Workspace, needId: string) => JSON.stringify({
  context: workspace.context, need: workspace.needs.find(item => item.id === needId), feedback: evidence(workspace, needId),
});

export default function PrdView({ workspace, need, onSelect, change, onEdit, notify, aiStatus, onEvidence }: {
  workspace: Workspace; need: Need; onSelect: (id: string) => void; change: Change;
  onEdit: (id: string, value: string) => void; notify: (message: string) => void;
  aiStatus: ApiStatus; onEvidence: (id: string) => void;
}) {
  const doc = workspace.documents[need.id];
  const [editing, setEditing] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null), [sectionTitle, setSectionTitle] = useState('');
  const [instruction, setInstruction] = useState('补充可检查的验收标准，并明确异常场景与待确认信息。');
  const related = evidence(workspace, need.id);
  const sections = useMemo(() => (doc?.markdown || '').split(/(?=^## )/m).filter(item => item.startsWith('## ')).map(content => ({ title: content.split('\n')[0].replace(/^## /, ''), content })), [doc?.markdown]);
  const currentSection = sections.find(item => item.title === sectionTitle) || sections.find(item => item.title.includes('验收')) || sections[0];
  const generate = async (useLlm: boolean, revise = false) => {
    setError('');
    const base = doc?.markdown || '';
    const signature = generationSignature(workspace, need.id);
    if (!useLlm) {
      setPreview({ markdown: templatePrd(workspace, need), origin: 'template', base, needId: need.id, section: '', signature });
      return;
    }
    setBusy(true);
    try {
      const result = await api<{ markdown: string; origin: PrdDocument['origin'] }>('prd', {
        workspace, need_id: need.id, use_llm: true, action: revise ? 'revise' : 'generate',
        draft: revise ? currentSection?.content || '' : base.slice(0, 16000), instruction: revise ? instruction : '',
      });
      setPreview({ markdown: result.markdown, origin: result.origin, base, needId: need.id, section: revise ? currentSection?.content || '' : '', signature });
    } catch (exception) { setError(exception instanceof Error ? exception.message : '生成失败，当前文档已保留。'); }
    finally { setBusy(false); }
  };
  const accept = () => {
    if (!preview) return;
    const current = workspace.documents[preview.needId]?.markdown || '';
    if (current !== preview.base || generationSignature(workspace, preview.needId) !== preview.signature) { setError('预览生成后，文档、证据或产品背景已发生变化。为保留修改，请关闭预览并重新生成。'); return; }
    const content = preview.section ? current.replace(preview.section, preview.markdown.trim() + '\n\n') : preview.markdown;
    change('接受 PRD 草稿', preview.section ? '接受章节改写' : need.title, draft => {
      draft.documents[preview.needId] = { markdown: content, origin: preview.origin, edited: Boolean(preview.section), stale: false, updated_at: new Date().toISOString() };
    }, false);
    setPreview(null); setEditing(false); notify('草稿已应用，可以继续编辑与下载。');
  };
  const selectNeed = (id: string) => { onSelect(id); setEditing(false); setError(''); setSectionTitle(''); };
  return <>
    <PageHeading eyebrow="DOCUMENTS / PRD 工作台" title="把产品判断，写成可执行的方案。" description="基于当前需求与证据生成草稿，人工校准后再用于评审。" actions={<button className="button secondary" disabled={!doc} onClick={() => { if (doc) { download(doc.markdown, `PRD-${need.title.replace(/[\\/:*?"<>|]/g, '-')}.md`, 'text/markdown;charset=utf-8'); notify('Markdown 已下载。'); } }}><ArrowDownToLine size={15}/>下载 Markdown</button>}/>
    <div className="prd-selection card"><div><span className="label-icon"><FileText size={17}/></span><label>当前需求<select aria-label="选择 PRD 需求" value={need.id} onChange={event => selectNeed(event.target.value)}>{workspace.needs.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label></div><span>{related.length} 条反馈证据<Tag tone={need.status === 'confirmed' ? 'green' : 'amber'}>{need.status === 'confirmed' ? '已确认需求' : '需求待确认'}</Tag></span></div>
    <ErrorNotice message={error}/>
    {doc?.stale && <div className="notice amber-notice"><BookOpen size={16}/><span>证据、评分或产品背景已更新。当前文档已保留，建议生成新预览后核对变化。</span></div>}
    <div className="prd-grid"><section className="card document-panel"><div className="document-toolbar"><div><Tag tone={doc?.origin === 'llm' ? 'purple' : 'gray'}>{doc?.origin === 'llm' ? '真实 AI 草稿' : doc ? '模板草稿' : '待生成'}</Tag>{doc?.edited && <Tag tone="green">含人工修改</Tag>}</div>{doc && <div className="segmented"><button className={!editing ? 'active' : ''} onClick={() => setEditing(false)}><BookOpen size={13}/>阅读</button><button className={editing ? 'active' : ''} disabled={busy} onClick={() => { change('编辑 PRD', need.title, () => {}, false); setEditing(true); }}><PencilLine size={13}/>编辑</button></div>}</div>
      {doc ? editing ? <div className="editor-wrap"><div className="editor-note"><span><span className="live-dot"/>修改自动保存在当前浏览器会话</span><button className="text-link" onClick={() => { setEditing(false); notify('修改已保存在当前会话。'); }}><Check size={13}/>完成编辑</button></div><textarea aria-label="PRD Markdown 编辑器" className="markdown-editor" value={doc.markdown} maxLength={40000} disabled={busy} onChange={event => onEdit(need.id, event.target.value)}/></div> : <div className="document-content"><Markdown text={doc.markdown} onEvidence={onEvidence}/></div> : <Empty title="从一个有证据的需求开始" detail="选择生成方式，先预览，再决定是否应用。" action={<button className="button primary" onClick={() => generate(false)}><FilePlus2 size={15}/>生成模板草稿</button>}/>}
      {doc && <div className="document-footer"><span>{doc.markdown.length.toLocaleString()} 字符 · {doc.updated_at ? '已保存到当前会话' : '默认案例模板'}</span><span>引用可点击查看原文</span></div>}
    </section><aside className="prd-aside">
      {sections.length > 0 && <section className="card toc-card"><h3><BookOpen size={14}/>文档目录</h3><nav aria-label="PRD 文档目录">{sections.map(section => <button key={section.title} onClick={() => document.getElementById(`section-${section.title.replace(/\s+/g, '-')}`)?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' })}>{section.title}</button>)}</nav></section>}
      <section className="card generation-card"><AiLabel>AI 产品写作助手</AiLabel><h3>从证据出发，形成初稿</h3><p>模型会结合产品背景、当前需求和关联反馈，保留引用与待确认事项。</p><button className="button ai-button full-width" disabled={busy || !aiStatus.ai_available} onClick={() => generate(true)}>{busy ? <Spinner label="正在生成…"/> : <><Sparkles size={15}/>AI 生成完整 PRD</>}</button><button className="button secondary full-width" disabled={busy} onClick={() => generate(false)}><FileText size={14}/>{doc ? '按当前证据更新模板' : '使用模板生成'}</button><p className="mini-note">{aiStatus.message}</p></section>
      {doc && <section className="card chapter-card"><h3>针对一个章节继续完善</h3><label>选择章节<select aria-label="改写章节" value={currentSection?.title || ''} onChange={event => setSectionTitle(event.target.value)}>{sections.map(item => <option key={item.title}>{item.title}</option>)}</select></label><label>修改要求<textarea aria-label="章节修改要求" maxLength={600} value={instruction} onChange={event => setInstruction(event.target.value)}/></label><button className="button ai-button full-width" disabled={busy || !instruction.trim() || !currentSection || !aiStatus.ai_available} onClick={() => generate(true, true)}><Sparkles size={14}/>预览章节改写</button><p className="mini-note">接受前不会替换当前内容。</p></section>}
      <section className="card prd-evidence-card"><h3><Link2 size={15}/>关联证据 <span>{related.length}</span></h3>{related.slice(0, 4).map(item => <button key={item.id} onClick={() => onEvidence(item.id)}><span>{item.id}<small>{item.app_name}</small></span><p>{item.text}</p></button>)}</section>
    </aside></div>
    {preview && <Modal wide title={preview.section ? '预览章节改写' : '预览 PRD 草稿'} description="对照当前内容，确认后再应用。取消会保留原文。" onClose={() => setPreview(null)}><ErrorNotice message={error}/><div className="comparison-grid"><section><h3>当前内容</h3><div className="comparison-scroll"><Markdown text={preview.section || preview.base || '当前还没有文档。'} onEvidence={onEvidence}/></div></section><section><h3>{preview.origin === 'llm' ? '真实 AI 建议' : '模板建议'}</h3><div className="comparison-scroll"><Markdown text={preview.markdown} onEvidence={onEvidence}/></div></section></div><div className="modal-actions"><button className="button secondary" onClick={() => setPreview(null)}>保留原文</button><button className="button primary" onClick={accept}><Check size={14}/>接受并应用</button></div></Modal>}
  </>;
}
