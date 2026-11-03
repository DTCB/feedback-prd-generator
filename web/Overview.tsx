import { ArrowRight, ArrowUpRight, CheckCheck, FileText, Layers3, MessageSquareText, ScanText, ShieldCheck, Sparkles, Target, TrendingUp } from 'lucide-react';
import { AiLabel, NeedStatus, PageHeading, SectionHeading, Tag, TextLink } from './components';
import { evidence, needScore, sentimentLabel, sortedNeeds, type Workspace } from './types';

export default function Overview({ workspace, onTour, onImport, onNeed, onFeedback, onContext }: {
  workspace: Workspace; onTour: () => void; onImport: () => void; onNeed: (id: string) => void;
  onFeedback: (id?: string) => void; onContext: () => void;
}) {
  const { feedback, needs } = workspace;
  const reviewed = feedback.filter(item => item.reviewed).length;
  const pending = needs.filter(item => item.status === 'pending').length;
  const focus = needs.find(need => need.title.includes('可追溯')) || sortedNeeds(workspace)[0];
  const focusFeedback = evidence(workspace, focus.id);
  const sentiments = (['negative', 'neutral', 'positive'] as const).map(key => ({ key, count: feedback.filter(item => item.sentiment === key).length }));
  const maxCount = Math.max(...needs.map(need => need.feedback_ids.length), 1);
  const themes = [...needs].sort((a, b) => b.feedback_ids.length - a.feedback_ids.length).slice(0, 5);
  return <>
    <PageHeading eyebrow="OVERVIEW / 洞察总览" title="让每个产品需求，都有用户证据。" description="从分散的用户声音出发，发现问题、校准判断，再形成可评审的产品方案。" actions={<><button className="button secondary" onClick={onTour}><span className="play-icon">▶</span>跟随案例体验</button><button className="button primary" onClick={onImport}><Sparkles size={15}/>分析我的反馈</button></>}/>
    <div className="case-ribbon"><div><span className="live-dot"/><strong>{workspace.is_sample ? 'AI 助手体验研究' : '我的反馈研究'}</strong><span className="ribbon-divider"/><span>{workspace.is_sample ? '演示样例 · 规则预分析＋人工分组' : '访客导入 · 当前会话'}</span></div><span className="ribbon-meta">{new Set(feedback.map(item => item.app_name)).size} 个产品 · {new Set(feedback.map(item => item.source)).size} 个来源</span></div>
    <div className="stats-grid">
      {[
        { label: '有效用户反馈', value: feedback.length, icon: MessageSquareText, foot: `${workspace.cleaning.original} 条原始记录`, tint: 'blue' },
        { label: '整理出的需求', value: needs.length, icon: Layers3, foot: '每个需求均关联原文', tint: 'purple' },
        { label: '等待人工确认', value: pending, icon: ScanText, foot: '从线索到可靠的判断', tint: 'amber' },
        { label: '已核验的反馈', value: reviewed, icon: CheckCheck, foot: `完成 ${Math.round(reviewed / feedback.length * 100)}% 的校准`, tint: 'green' },
      ].map(item => <div className="stat-card" key={item.label}><div className="stat-top"><span>{item.label}</span><span className={`stat-icon ${item.tint}`}><item.icon size={17}/></span></div><strong className="stat-number">{item.value}<small>项</small></strong><div className="stat-foot">{item.foot}</div></div>)}
    </div>
    <div className="overview-grid">
      <div className="overview-main">
        <section className="spotlight card">
          <div className="spotlight-top"><AiLabel>本次案例主线</AiLabel><Tag tone="purple">证据驱动的产品决策</Tag></div>
          <div className="spotlight-body"><div><h2>{focus.title}</h2><p>当用户需要反复核对 AI 输出，我们如何把“回答不可靠”拆解成一个可验证、可交付的产品需求？</p></div><span className="spotlight-art" aria-hidden="true"><ShieldCheck size={45} strokeWidth={1.3}/><span className="art-dot one"/><span className="art-dot two"/></span></div>
          <div className="quote-preview"><span className="quote-mark">“</span><p>{focusFeedback[0]?.text}</p><span className="quote-id">{focusFeedback[0]?.id}</span></div>
          <div className="spotlight-footer"><span><MessageSquareText size={14}/>{focusFeedback.length} 条关联反馈<span className="dot-separator">·</span>包含待核验线索</span><button className="button primary small-button" onClick={() => onFeedback(focus.id)}>查看问题与证据<ArrowRight size={14}/></button></div>
        </section>
        <section className="card priority-card">
          <SectionHeading title="值得进一步评估的需求" description="分数帮助讨论，最终取舍由你决定。" action={<TextLink onClick={() => onNeed(focus.id)}>查看需求池</TextLink>}/>
          <div className="priority-table"><div className="priority-table-head"><span>需求与反馈证据</span><span>RICE 分数</span><span>审核状态</span></div>
            {sortedNeeds(workspace).slice(0, 4).map((need, index) => <button className="priority-row" onClick={() => onNeed(need.id)} key={need.id}><span className="priority-info"><span className={`rank rank-${index}`}>{String(index + 1).padStart(2, '0')}</span><span><strong>{need.title}</strong><small>{need.feedback_ids.length} 条反馈<span className="dot-separator">·</span>{need.module}</small></span></span><span className="score-cell">{needScore(need).toFixed(2)}</span><NeedStatus need={need}/></button>)}
          </div>
          <div className="card-footnote"><Target size={13}/>Reach 使用样本代理值，初始评分仍需业务判断和人工校准。</div>
        </section>
        <section className="workflow-card"><div><span className="workflow-icon"><FileText size={20}/></span><div><h3>把洞察变成下一步行动</h3><p>核验证据、调整优先级，再生成一份可继续编辑的 PRD。</p></div></div><button className="icon-button" aria-label="进入需求决策" onClick={() => onNeed(focus.id)}><ArrowUpRight size={21}/></button></section>
      </div>
      <aside className="overview-aside">
        <section className="card theme-card"><SectionHeading title="用户在关注什么" action={<TrendingUp size={16} className="muted"/>}/><div className="theme-bars">{themes.map((need, index) => <button className="theme-item" key={need.id} onClick={() => onFeedback(need.id)}><span className="theme-label"><span>{need.title}</span><strong>{need.feedback_ids.length}</strong></span><span className="theme-track"><span className={`theme-fill fill-${index}`} style={{ width: `${need.feedback_ids.length / maxCount * 100}%` }}/></span></button>)}</div><p className="mini-note">点击主题，查看背后的原始反馈。</p></section>
        <section className="card sentiment-card"><SectionHeading title="反馈情绪分布"/><div className="sentiment-total"><strong>{feedback.length}</strong><span>条有效反馈</span><Tag tone="gray">规则／人工估计</Tag></div><div className="sentiment-track" role="img" aria-label={sentiments.map(item => `${sentimentLabel[item.key]} ${item.count} 条`).join('，')}>{sentiments.map(item => <span key={item.key} className={item.key} style={{ width: `${item.count / feedback.length * 100}%` }}/>)}</div><div className="sentiment-legend">{sentiments.map(item => <div key={item.key}><span><i className={item.key}/>{sentimentLabel[item.key]}</span><strong>{item.count}<small>{Math.round(item.count / feedback.length * 100)}%</small></strong></div>)}</div></section>
        <section className="context-preview"><div className="context-preview-title"><Target size={17}/><h3>让 AI 理解产品背景</h3></div><p>{workspace.context.goal}</p><TextLink onClick={onContext}>查看与编辑背景</TextLink></section>
      </aside>
    </div>
    <div className="page-footer"><span>每一条洞察，都可以回到用户原文。</span><span>反馈洞察 · Feedback Lens</span></div>
  </>;
}
