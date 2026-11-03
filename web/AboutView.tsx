import { useEffect, useState } from 'react';
import { ArrowUpRight, Beaker, Code2, Fingerprint, GitBranch, Layers3, ShieldCheck, Target } from 'lucide-react';
import { PageHeading, Tag } from './components';

export default function AboutView() {
  const [evaluation, setEvaluation] = useState<{ mode: string; sample_count: number; category_correct: number; sentiment_correct: number } | null>(null);
  useEffect(() => { fetch('/evaluation.json').then(response => response.ok ? response.json() : null).then(setEvaluation).catch(() => {}); }, []);
  return <>
    <PageHeading eyebrow="BEHIND THE PRODUCT / 关于项目" title="让 AI 能力进入真实的产品工作流。" description="一个面向 AI 产品经理的个人作品：从理解用户，到形成有依据的产品方案。"/>
    <div className="about-hero card"><span className="about-icon"><Layers3 size={31}/></span><div><Tag tone="purple">个人项目 · 可交互 Demo</Tag><h2>反馈洞察 / Feedback Lens</h2><p>当反馈分散、判断缺乏依据、文档与洞察脱节，产品经理需要一条可追溯、可校准的工作流。这个项目把反馈清洗、分析、需求聚合、优先级与 PRD 串联起来，让 AI 的产出可以被核验和继续加工。</p></div></div>
    <div className="about-grid">{[
      { icon: Target, title: '问题与目标', text: '帮助产品经理把碎片化反馈整理为需求线索，再通过原文、业务背景和人工评估形成可讨论的决策。' },
      { icon: Fingerprint, title: '个人贡献', text: '问题定义、工作流与交互设计、证据关联、RICE 校准机制、AI 输出约束、失败处理、前后端实现与部署准备。' },
      { icon: ShieldCheck, title: '人机分工', text: 'AI 辅助提取场景、问题和诉求，提出关联建议并起草文档；人负责校准证据、判断业务价值、估计成本及确认最终方案。' },
      { icon: GitBranch, title: '关键产品取舍', text: '默认案例支持直接体验；真实调用由访客主动触发。保留规则与模板路径、人工修改和撤销，让任务在模型失败时仍能继续。' },
    ].map(item => <section className="card about-card" key={item.title}><item.icon size={21}/><h3>{item.title}</h3><p>{item.text}</p></section>)}</div>
    <section className="card about-evaluation"><div className="about-section-title"><Beaker size={21}/><div><h2>评测与能力边界</h2><p>把实现校验、模型效果和业务成效分开记录。</p></div></div><div className="evaluation-table"><div><strong>实现校验</strong><p>验证证据关联、RICE 计算、合并与撤销、会话恢复、文件导出及异常处理。自动化测试随项目提供。</p></div><div><strong>模型效果</strong><p>提供固定人工标注样本与评测脚本，对比规则和模型的分类、证据引用及输出完整性。尚未产生真实模型评测结果时，不展示准确率。</p></div><div><strong>业务成效</strong><p>尚未开展真实团队上线验证。节省时间、PRD 采纳率与需求交付改善均为待验证指标，不作为已取得成果展示。</p></div></div><div className="notice subtle">默认案例包含多个 AI 产品的演示样例，产品与渠道名称用于说明场景，不代表已核验的公开调研或整体用户结论。</div></section>
    {evaluation?.mode === 'rule' && <section className="card about-evaluation"><div className="about-section-title"><Beaker size={21}/><div><h2>规则基线：当前实测记录</h2><p>自建演示样本 · 单人参考标注 · {evaluation.sample_count} 条</p></div></div><div className="baseline-results"><div><strong>{evaluation.category_correct}<small> / {evaluation.sample_count}</small></strong><span>分类与参考标注一致</span></div><div><strong>{evaluation.sentiment_correct}<small> / {evaluation.sample_count}</small></strong><span>情绪与参考标注一致</span></div></div><p className="mini-note">以上仅反映当前规则在这组演示样本上的表现，不代表真实模型准确率或泛化能力。模型完整效果评测尚未完成，不展示推测结果。</p></section>}
    <section className="card about-tech"><div><Code2 size={21}/><h3>实现与参考</h3></div><p>React · TypeScript · Vite · Python · FastAPI · pandas · Vercel</p><div className="reference-links"><a href="https://www.productboard.com/product/insights/" target="_blank" rel="noreferrer">Productboard · 反馈与需求关联<ArrowUpRight size={14}/></a><a href="https://docs.dovetail.com/help/channels" target="_blank" rel="noreferrer">Dovetail · 洞察与证据<ArrowUpRight size={14}/></a><a href="https://canny.io/features/autopilot" target="_blank" rel="noreferrer">Canny · AI 建议与审核<ArrowUpRight size={14}/></a></div></section>
  </>;
}
