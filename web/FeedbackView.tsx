import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Check, CheckCheck, Filter, Link2, Search, Sparkles, X } from 'lucide-react';
import { AiLabel, Empty, PageHeading, Tag } from './components';
import { CATEGORIES, originLabel, refreshReach, sentimentLabel, sourceLabel, type ApiStatus, type Feedback, type Workspace } from './types';

export type Change = (action: string, detail: string, update: (draft: Workspace) => void, stale?: boolean) => void;

export default function FeedbackView({ workspace, focusNeed, selectedId, setSelectedId, clearFocus, change, notify, onNeed, onAnalyze, busy, aiStatus }: {
  workspace: Workspace; focusNeed: string; selectedId: string; setSelectedId: (id: string) => void; clearFocus: () => void;
  change: Change; notify: (text: string) => void; onNeed: (id: string) => void;
  onAnalyze: (ids: string[]) => void; busy: boolean; aiStatus: ApiStatus;
}) {
  const [search, setSearch] = useState(''), [category, setCategory] = useState(''), [review, setReview] = useState('');
  const [source, setSource] = useState(''), [sentiment, setSentiment] = useState('');
  const [checked, setChecked] = useState<string[]>([]), [editing, setEditing] = useState(false);
  const [editCategory, setEditCategory] = useState(''), [editNeed, setEditNeed] = useState(''), [reason, setReason] = useState('');
  const [newTitle, setNewTitle] = useState('');
  const [editSentiment, setEditSentiment] = useState<Feedback['sentiment']>('neutral');
  const filtered = useMemo(() => workspace.feedback.filter(item => (!focusNeed || item.need_id === focusNeed)
    && (!search || `${item.text} ${item.id} ${item.app_name}`.toLowerCase().includes(search.toLowerCase()))
    && (!category || item.category === category) && (!review || item.reviewed === (review === 'reviewed'))
    && (!source || item.source === source) && (!sentiment || item.sentiment === sentiment)), [workspace, focusNeed, search, category, review, source, sentiment]);
  const selected = filtered.find(item => item.id === selectedId) || filtered[0];
  useEffect(() => { setEditing(false); setReason(''); }, [selected?.id]);
  useEffect(() => { setChecked(previous => previous.filter(id => workspace.feedback.some(item => item.id === id))); }, [workspace.feedback]);
  const need = selected && workspace.needs.find(item => item.id === selected.need_id);
  const focus = workspace.needs.find(item => item.id === focusNeed);
  const updateReview = () => {
    if (!selected) return;
    change('确认反馈', selected.id, draft => { draft.feedback.find(item => item.id === selected.id)!.reviewed = true; }, false);
    notify('已确认该条分析，可通过右上角撤销。');
  };
  const saveEdit = () => {
    if (!selected || !reason.trim() || (editNeed === '__new__' && !newTitle.trim())) return;
    const independentId = `N-review-${crypto.randomUUID()}`;
    change('校准反馈', `${selected.id}：${reason}`, draft => {
      const item = draft.feedback.find(row => row.id === selected.id)!;
      const oldNeed = item.need_id;
      let nextNeed = editNeed;
      if (editNeed === '__new__') {
        nextNeed = independentId;
        const existing = draft.needs.find(value => value.id === oldNeed)!;
        draft.needs.push({ ...existing, id: nextNeed, title: newTitle.trim(), description: '人工核验后拆分出的独立需求，需继续确认业务边界。', feedback_ids: [], status: 'pending', category: editCategory });
        if (draft.feedback.filter(value => value.need_id === oldNeed).length === 1 && draft.documents[oldNeed]) {
          draft.documents[nextNeed] = { ...draft.documents[oldNeed], stale: true };
        }
      }
      Object.assign(item, { category: editCategory, sentiment: editSentiment, need_id: nextNeed, reason: reason.trim(), reviewed: true });
      if (oldNeed !== nextNeed) draft.needs = draft.needs.map(value => [oldNeed, nextNeed].includes(value.id) ? refreshReach(draft, value) : value);
    });
    setEditing(false); notify('校准已保存，关联需求与统计已更新。');
  };
  const startEdit = () => {
    if (!selected) return;
    setEditCategory(selected.category); setEditNeed(selected.need_id); setEditSentiment(selected.sentiment); setReason(''); setEditing(true);
    setNewTitle(`独立评估：${selected.module}相关诉求`);
  };
  return <>
    <PageHeading eyebrow="FEEDBACK / 反馈分析" title="回到原文，再做判断。" description="把用户表达、分析依据与产品诉求放在一起，逐条核验。" actions={<Tag tone="purple"><Sparkles size={12}/>{workspace.feedback.filter(item => item.origin === 'llm').length ? '包含真实 AI 分析' : '预分析结果待人工确认'}</Tag>}/>
    <div className="filter-toolbar card"><label className="search-input"><Search size={16}/><input aria-label="搜索反馈" placeholder="搜索反馈内容、产品或编号…" value={search} onChange={event => setSearch(event.target.value)}/>{search && <button aria-label="清除搜索" onClick={() => setSearch('')}><X size={13}/></button>}</label><div className="filter-selects"><Filter size={15}/><select aria-label="反馈类型" value={category} onChange={event => setCategory(event.target.value)}><option value="">全部类型</option>{CATEGORIES.map(item => <option key={item}>{item}</option>)}</select><select aria-label="反馈来源" value={source} onChange={event => setSource(event.target.value)}><option value="">全部来源</option>{[...new Set(workspace.feedback.map(item => item.source))].map(item => <option key={item} value={item}>{sourceLabel(item)}</option>)}</select><select aria-label="反馈情绪" value={sentiment} onChange={event => setSentiment(event.target.value)}><option value="">全部情绪</option>{Object.entries(sentimentLabel).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><select aria-label="审核状态" value={review} onChange={event => setReview(event.target.value)}><option value="">全部状态</option><option value="pending">待核验</option><option value="reviewed">已核验</option></select></div></div>
    {focus && <div className="focus-filter"><span>正在查看需求：<strong>{focus.title}</strong></span><button onClick={clearFocus}>查看全部反馈<X size={13}/></button></div>}
    <div className="feedback-workbench card">
      <section className="feedback-list"><div className="list-heading"><label className="checkbox-label"><input type="checkbox" aria-label="选择当前筛选反馈" checked={filtered.length > 0 && filtered.every(item => checked.includes(item.id))} onChange={event => setChecked(event.target.checked ? filtered.slice(0, 30).map(item => item.id) : [])}/><span>反馈列表 <b>{filtered.length}</b></span></label><span>{checked.length > 0 ? `已选 ${checked.length} 条` : '选择后可实时分析'}</span></div>
        <div className="feedback-scroll">{filtered.length ? filtered.map(item => <div className={`feedback-row ${selected?.id === item.id ? 'selected' : ''}`} key={item.id}><input type="checkbox" aria-label={`选择 ${item.id}`} checked={checked.includes(item.id)} onChange={event => setChecked(values => event.target.checked ? values.length < 30 ? [...values, item.id] : values : values.filter(id => id !== item.id))}/><button className="feedback-row-button" onClick={() => setSelectedId(item.id)}><span className="feedback-row-meta"><span className={`source-avatar ${item.app_name.toLowerCase().includes('notion') ? 'dark' : ''}`}>{item.app_name.slice(0, 1).toUpperCase()}</span><strong>{item.app_name}</strong><span>{item.id}</span>{item.reviewed && <CheckCheck size={14} className="green-text"/>}</span><p>{item.text}</p><span className="feedback-row-bottom"><Tag tone={item.sentiment === 'negative' ? 'rose' : item.sentiment === 'positive' ? 'green' : 'gray'}>{sentimentLabel[item.sentiment]}</Tag><span>{item.category}</span><time>{item.date || '日期未标注'}</time></span></button></div>) : <Empty/>}</div>
        <div className="list-footer"><span>每次最多选择 30 条</span><button className="button ai-button small-button" disabled={!checked.length || busy || !aiStatus.ai_available} title={aiStatus.message} onClick={() => onAnalyze(checked)}><Sparkles size={13}/>{busy ? '分析中…' : `AI 分析所选${checked.length ? ` (${checked.length})` : ''}`}</button></div>
        {!aiStatus.ai_available && <div className="list-ai-note">{aiStatus.message}</div>}
      </section>
      <section className="feedback-detail">{selected ? <><div className="detail-heading"><div><span className="eyebrow">原始反馈 / {selected.id}</span><h2>用户说了什么</h2></div><Tag tone={selected.reviewed ? 'green' : 'amber'} dot>{selected.reviewed ? '已人工核验' : '待人工核验'}</Tag></div><div className="detail-metadata"><span>{sourceLabel(selected.source)}</span><span>{selected.app_name}</span><span>{selected.rating == null ? '评分未提供' : `${selected.rating} / 5 分`}</span><span>{selected.user_type}</span></div>
        <blockquote className="original-quote"><p>{selected.text}</p><footer>{selected.date || '日期未标注'}<span>原文保留 · 不随分类修改</span></footer></blockquote>
        <div className="analysis-heading"><AiLabel>{originLabel[selected.origin]}</AiLabel><span>请检查依据与诉求是否准确</span></div>
        <div className="analysis-fields"><div><span>用户场景</span><p>{selected.scenario}</p></div><div><span>问题线索</span><p>{selected.problem}</p></div><div><span>产品诉求</span><p>{selected.request}</p></div></div>
        <div className="evidence-highlight"><span><Link2 size={13}/>依据原文</span><p><mark>{selected.quote || selected.text}</mark></p></div>
        <div className="classification-reason"><strong>判断依据</strong><p>{selected.reason}</p></div>
        {editing ? <div className="correction-form">
          <h3>校准分类与关联</h3>
          <div className="form-two-columns"><label>反馈类型<select value={editCategory} onChange={event => setEditCategory(event.target.value)}>{CATEGORIES.map(item => <option key={item}>{item}</option>)}</select></label><label>情绪<select value={editSentiment} onChange={event => setEditSentiment(event.target.value as Feedback['sentiment'])}>{Object.entries(sentimentLabel).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label></div>
          <label>关联需求<select aria-label="校准关联需求" value={editNeed} onChange={event => setEditNeed(event.target.value)}>{workspace.needs.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}<option value="__new__">不接受当前关联，创建独立需求</option></select></label>
          {editNeed === '__new__' && <label>独立需求标题<input aria-label="独立需求标题" value={newTitle} maxLength={300} onChange={event => setNewTitle(event.target.value)}/></label>}
          <label>修改依据<textarea aria-label="校准理由" placeholder="说明原分类或关联哪里不准确，以及本次修改的理由…" value={reason} maxLength={600} onChange={event => setReason(event.target.value)}/></label>
          <div className="form-actions"><button className="button secondary" onClick={() => setEditing(false)}>取消</button><button className="button primary" disabled={!reason.trim() || (editNeed === '__new__' && !newTitle.trim())} onClick={saveEdit}><Check size={14}/>保存校准</button></div>
        </div> : <>
          <button className="associated-need" onClick={() => need && onNeed(need.id)}><span><Link2 size={15}/><span><small>关联需求</small><strong>{need?.title}</strong></span></span><ArrowRight size={16}/></button>
          <button className="text-link reject-association" onClick={() => { startEdit(); setEditNeed('__new__'); }}>不接受当前关联建议</button>
          <div className="detail-actions"><button className="button secondary" onClick={startEdit}>校准分类与关联</button><button className="button primary" onClick={updateReview} disabled={selected.reviewed}><Check size={15}/>{selected.reviewed ? '已确认' : '确认该条分析'}</button></div>
        </>}
      </> : <Empty title="选择一条用户反馈" detail="在左侧列表中选择反馈，查看原文与分析依据。"/>}</section>
    </div>
  </>;
}
