import { useEffect, useRef, type ReactNode } from 'react';
import { ArrowDownToLine, ArrowUpRight, Check, ChevronRight, CircleHelp, MessageSquareText, Sparkles, X } from 'lucide-react';
import type { Need } from './types';

export function Brand({ small = false }: { small?: boolean }) {
  return <div className={`brand ${small ? 'small' : ''}`}><span className="brand-mark"><svg viewBox="0 0 28 28" aria-hidden="true"><path d="M6 6h16v4H10v4h10v4H10v5H6z" fill="currentColor"/><circle cx="21" cy="22" r="2.6" fill="currentColor" opacity=".55"/></svg></span>{!small && <span><strong>反馈洞察</strong><small>FEEDBACK LENS</small></span>}</div>;
}
export function Tag({ children, tone = '', dot = false }: { children: ReactNode; tone?: string; dot?: boolean }) {
  return <span className={`tag ${tone}`}>{dot && <span className="tag-dot" />}{children}</span>;
}
export function AiLabel({ children = 'AI 建议' }: { children?: ReactNode }) { return <span className="ai-label"><Sparkles size={12} />{children}</span>; }
export function Empty({ title = '暂无匹配结果', detail = '试试调整搜索或筛选条件。', action }: { title?: string; detail?: string; action?: ReactNode }) {
  return <div className="empty"><span className="empty-icon"><MessageSquareText size={25}/></span><h3>{title}</h3><p>{detail}</p>{action}</div>;
}
export function SectionHeading({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <div className="section-heading"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{action}</div>;
}
export function PageHeading({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{actions && <div className="heading-actions">{actions}</div>}</div>;
}
export function NeedStatus({ need }: { need: Need }) {
  return <Tag tone={need.status === 'confirmed' ? 'green' : need.status === 'deferred' ? 'gray' : 'amber'} dot>{({ pending: '待确认', confirmed: '已确认', deferred: '暂缓' })[need.status]}</Tag>;
}
export function Modal({ title, description, children, onClose, wide = false }: { title: string; description?: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose); closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const old = document.body.style.overflow; document.body.style.overflow = 'hidden';
    const panel = ref.current;
    const focusable = () => [...(panel?.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href],[tabindex="0"]') || [])];
    (focusable()[0] || panel)?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); closeRef.current(); }
      if (event.key === 'Tab') {
        const items = focusable(), first = items[0], last = items[items.length - 1];
        if (!first) { event.preventDefault(); panel?.focus(); }
        else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', handler);
    return () => { document.body.style.overflow = old; document.removeEventListener('keydown', handler); previous?.focus(); };
  }, []);
  return <div className="modal-overlay" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="modal-title" className={`modal ${wide ? 'wide' : ''}`}><div className="modal-heading"><div><h2 id="modal-title">{title}</h2>{description && <p>{description}</p>}</div><button className="icon-button" aria-label="关闭弹窗" onClick={onClose}><X size={19}/></button></div>{children}</div></div>;
}
export function Spinner({ label = '正在处理，请稍候…' }: { label?: string }) { return <span className="loading-inline"><span className="spinner"/>{label}</span>; }
export function ErrorNotice({ message }: { message: string }) { return message ? <div className="notice error" role="alert"><CircleHelp size={16}/><span>{message}</span></div> : null; }
export function ExportButton({ onClick, busy }: { onClick: () => void; busy: boolean }) {
  return <button className="button secondary" onClick={onClick} disabled={busy}><ArrowDownToLine size={15}/>{busy ? '正在导出' : '导出 Excel'}</button>;
}
export function TextLink({ children, onClick }: { children: ReactNode; onClick: () => void }) { return <button className="text-link" onClick={onClick}>{children}<ChevronRight size={14}/></button>; }
export function CheckLine({ children }: { children: ReactNode }) { return <div className="check-line"><Check size={14}/>{children}</div>; }
export function ExternalIcon() { return <ArrowUpRight size={13}/>; }
