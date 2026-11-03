import { useEffect, useState } from 'react';
import { ArrowDown, ArrowRight, ArrowUp, Check, ChevronRight, FileText, GitMerge, Info, MessageSquareText, PencilLine, Search } from 'lucide-react';
import { Empty, NeedStatus, PageHeading, Tag } from './components';
import { evidence, needScore, sortedNeeds, type Need, type Workspace } from './types';
import type { Change } from './FeedbackView';

export default function NeedsView({ workspace, selectedId, onSelect, change, notify, onFeedback, onPrd, onMerge }: {
  workspace: Workspace; selectedId: string; onSelect: (id: string) => void; change: Change;
  notify: (message: string) => void; onFeedback: (id: string) => void; onPrd: (id: string) => void; onMerge: (id: string) => void;
}) {
  const [search, setSearch] = useState(''), [statusFilter, setStatusFilter] = useState('');
  const [editing, setEditing] = useState(false), [reason, setReason] = useState('');
  const all = sortedNeeds(workspace);
  const filtered = all.filter(need => (!search || need.title.includes(search)) && (!statusFilter || need.status === statusFilter));
  const need = workspace.needs.find(item => item.id === selectedId) || all[0];
  const [values, setValues] = useState({ reach: 1, impact: 1, confidence: 0.5, effort: 1 });
  useEffect(() => { setEditing(false); setReason(''); }, [need.id, need.feedback_ids.join(',')]);
  const related = evidence(workspace, need.id);
  const score = needScore(need), previewScore = needScore({ ...need, ...values });
  const previousRank = all.findIndex(item => item.id === need.id) + 1;
  const previewRank = [...all.filter(item => item.id !== need.id), { ...need, ...values }].sort((a, b) => needScore(b) - needScore(a)).findIndex(item => item.id === need.id) + 1;
  const startEdit = () => { setValues({ reach: need.reach, impact: need.impact, confidence: need.confidence, effort: need.effort }); setReason(''); setEditing(true); };
  const saveRice = () => {
    if (!reason.trim()) return;
    change('调整 RICE', `${need.title}：${reason}`, draft => { Object.assign(draft.needs.find(item => item.id === need.id)!, values, { score_reason: reason.trim() }); });
    setEditing(false); notify('评分已更新，需求已重新排序。');
  };
  const setStatus = (status: Need['status']) => {
    change('更新需求状态', `${need.title} → ${status === 'confirmed' ? '已确认' : '暂缓'}`, draft => { draft.needs.find(item => item.id === need.id)!.status = status; }, false);
    notify(status === 'confirmed' ? '需求已确认，可以继续形成 PRD。' : '需求已暂缓，证据与评估结果已保留。');
  };
  return <>
    <PageHeading eyebrow="DECISIONS / 需求决策" title="用证据和取舍，决定下一步。" description="查看需求依据，调整评估假设，让每一次排序都能解释。" actions={<button className="button primary" onClick={() => onPrd(need.id)}><FileText size={15}/>为所选需求生成 PRD</button>}/>
    <div className="notice subtle"><Info size={16}/><span>RICE = Reach × Impact × Confidence ÷ Effort。当前 Reach 是样本代理值；影响、信心与成本均为估计，不等同于已验证业务结果。</span></div>
    <div className="needs-grid">
      <section className="card needs-list"><div className="needs-toolbar"><label className="search-input"><Search size={15}/><input aria-label="搜索需求" placeholder="搜索需求…" value={search} onChange={event => setSearch(event.target.value)}/></label><select aria-label="需求审核状态" value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="">全部状态</option><option value="pending">待确认</option><option value="confirmed">已确认</option><option value="deferred">暂缓</option></select></div><div className="needs-table-heading"><span>需求 · 按 RICE 排序</span><span>分数</span></div>
        {filtered.length ? filtered.map(item => <button key={item.id} className={`need-list-row ${item.id === need.id ? 'active' : ''}`} onClick={() => onSelect(item.id)}><span className="need-list-title"><span className="need-rank">{String(all.findIndex(value => value.id === item.id) + 1).padStart(2, '0')}</span><span><strong>{item.title}</strong><small><MessageSquareText size={12}/>{item.feedback_ids.length} 条证据<span className="dot-separator">·</span><NeedStatus need={item}/></small></span></span><span className="need-list-score">{needScore(item).toFixed(2)}<ChevronRight size={14}/></span></button>) : <Empty/>}
        <div className="card-footnote">共 {filtered.length} 个需求 · 分数随评估参数更新</div>
      </section>
      <section className="card need-detail"><div className="detail-heading"><span className="eyebrow">需求详情 / {need.id}</span><NeedStatus need={need}/></div><h2>{need.title}</h2><p className="need-description">{need.description}</p><div className="need-attributes"><Tag>{need.module}</Tag><Tag>{need.category}</Tag><span>{related.filter(item => item.reviewed).length}/{related.length} 条证据已核验</span></div>
        <div className="rice-card"><div className="rice-title"><h3>RICE 优先级评估</h3>{!editing && <button className="text-link" onClick={startEdit}><PencilLine size={13}/>校准评分</button>}</div>
          <div className="rice-score"><strong>{editing ? previewScore.toFixed(2) : score.toFixed(2)}</strong><span>当前得分<small>第 {editing ? previewRank : previousRank} 位 / 共 {all.length} 个需求</small></span></div>
          {editing ? <><div className="rice-input-grid">{[
            { key: 'reach', label: 'Reach · 样本代理值', min: 0, max: 10000, step: 0.1 },
            { key: 'impact', label: 'Impact · 影响程度', min: 0, max: 10, step: 0.5 },
            { key: 'confidence', label: 'Confidence · 信心 (0–1)', min: 0, max: 1, step: 0.05 },
            { key: 'effort', label: 'Effort · 成本人周', min: 0.1, max: 1000, step: 0.5 },
          ].map(field => <label key={field.key}>{field.label}<input aria-label={field.label} type="number" min={field.min} max={field.max} step={field.step} value={values[field.key as keyof typeof values]} onChange={event => {
            const value = Number(event.target.value); if (Number.isFinite(value)) setValues(previous => ({ ...previous, [field.key]: Math.max(field.min, Math.min(field.max, value)) }));
          }}/></label>)}</div><div className="rank-preview">{previewRank < previousRank ? <ArrowUp size={14}/> : <ArrowDown size={14}/>}预计排名：{previousRank} → {previewRank}<span>实时预览，保存后生效</span></div><label className="field-label">本次调整的依据<textarea aria-label="RICE 调整依据" maxLength={600} value={reason} onChange={event => setReason(event.target.value)} placeholder="例如：方案缩小到引用展示与失效提示，预估工作量从 3 人周降到 2 人周。"/></label><div className="form-actions"><button className="button secondary" onClick={() => setEditing(false)}>取消</button><button className="button primary" disabled={!reason.trim()} onClick={saveRice}>应用评分并重新排序</button></div></> : <><div className="rice-values">{[['R', 'Reach', need.reach], ['I', 'Impact', need.impact], ['C', 'Confidence', `${Math.round(need.confidence * 100)}%`], ['E', 'Effort', need.effort]].map(([letter, label, value]) => <div key={label}><span>{letter}<small>{label}</small></span><strong>{value}</strong></div>)}</div><p className="rice-reason">{need.score_reason}</p></>}
        </div>
        <div className="evidence-section-heading"><h3>支撑这个需求的用户声音</h3><button className="text-link" onClick={() => onFeedback(need.id)}>查看全部 {related.length} 条<ArrowRight size={13}/></button></div>
        <div className="need-evidence-list">{related.slice(0, 3).map(item => <button className="need-evidence" key={item.id} onClick={() => onFeedback(need.id)}><span><strong>{item.id}</strong><small>{item.app_name}</small>{item.reviewed && <Check size={12} className="green-text"/>}</span><p>“{item.text}”</p></button>)}</div>
        <div className="decision-actions"><button className="button secondary" onClick={() => onMerge(need.id)} disabled={workspace.needs.length < 2}><GitMerge size={14}/>对比与合并</button><button className="button secondary" onClick={() => setStatus('deferred')} disabled={need.status === 'deferred'}>暂缓</button><button className="button primary" onClick={() => setStatus('confirmed')} disabled={need.status === 'confirmed'}><Check size={14}/>{need.status === 'confirmed' ? '已确认需求' : '确认需求'}</button></div>
      </section>
    </div>
  </>;
}
