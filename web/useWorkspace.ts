import { useCallback, useEffect, useRef, useState } from 'react';
import { synchronize, type Workspace } from './types';

const KEY = 'feedback-lens-workspace-v1';
export default function useWorkspace() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [failure, setFailure] = useState('');
  const [storageWarning, setStorageWarning] = useState(false);
  const initial = useRef<Workspace | null>(null);
  const undo = useRef<Workspace[]>([]);
  const [undoCount, setUndoCount] = useState(0);
  useEffect(() => {
    let cancelled = false;
    fetch('/demo.json').then(response => { if (!response.ok) throw new Error(); return response.json(); }).then((demo: Workspace) => {
      if (cancelled) return;
      initial.current = demo;
      let restored: Workspace | null = null;
      try {
        const saved = JSON.parse(sessionStorage.getItem(KEY) || 'null');
        if (saved?.version === 1 && Array.isArray(saved.feedback) && saved.feedback.length && Array.isArray(saved.needs) && saved.needs.length && saved.context && saved.documents && Array.isArray(saved.history)) {
          const needIds = new Set(saved.needs.map((need: { id: string }) => need.id));
          if (saved.feedback.every((item: { id: string; need_id: string; text: string }) => typeof item.text === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(item.id) && needIds.has(item.need_id))) restored = saved;
        }
      } catch { /* Unavailable or outdated browser state: load the original case. */ }
      setWorkspace(restored || structuredClone(demo));
    }).catch(() => { if (!cancelled) setFailure('案例载入失败，请刷新页面重试。'); });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    if (!workspace) return;
    try { sessionStorage.setItem(KEY, JSON.stringify(workspace)); setStorageWarning(false); }
    catch { setStorageWarning(true); }
  }, [workspace]);
  const commit = useCallback((action: string, detail: string, update: (draft: Workspace) => void, stale = true) => {
    setWorkspace(previous => {
      if (!previous) return previous;
      // State setters must remain pure under React StrictMode. Push snapshots in
      // the event callback, using the current workspace captured below instead.
      const draft = structuredClone(previous);
      update(draft);
      synchronize(draft);
      if (stale) Object.values(draft.documents).forEach(document => { document.stale = true; });
      draft.history = [...draft.history, { time: new Date().toISOString(), action, detail }].slice(-100);
      return draft;
    });
  }, []);
  const change = useCallback((action: string, detail: string, update: (draft: Workspace) => void, stale = true) => {
    if (workspace) {
      undo.current = [...undo.current, structuredClone(workspace)].slice(-15);
      setUndoCount(undo.current.length);
    }
    commit(action, detail, update, stale);
  }, [workspace, commit]);
  const undoLast = () => {
    const previous = undo.current.pop();
    if (previous) setWorkspace(previous);
    setUndoCount(undo.current.length);
  };
  const reset = () => {
    if (initial.current) {
      undo.current = []; setUndoCount(0);
      setWorkspace(structuredClone(initial.current));
    }
  };
  const replace = (next: Workspace, action: string) => change(action, `${next.feedback.length} 条反馈`, draft => {
    const history = draft.history;
    Object.assign(draft, next, { history });
  });
  return { workspace, setWorkspace, change, undoLast, undoCount, reset, replace, failure, storageWarning };
}
