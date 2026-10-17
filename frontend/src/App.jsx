import { useState, useEffect, useRef, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Search, Network, Database, Activity, Code, GitMerge, X,
  Zap, Maximize, Cpu, RefreshCw, Layout, Braces, FileText,
  CheckCircle2, Circle, ChevronDown, Plus, GitBranch, Layers,
  Terminal, Box, ArrowRight
} from 'lucide-react';
import './App.css';

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

/* ── Graph Colors (shared) ────────────────────────────────── */
const COLORS = {
  function: '#4ade80',
  class: '#f472b6',
  file: '#9ca3af',
  link: 'rgba(255,255,255,0.1)',
};

/* ─────────────────────────────────────────────────────────────
   GRAPH EXPLORER — do not touch
───────────────────────────────────────────────────────────── */
function GraphExplorer({ initialRepo, initialType }) {
  const [repo]                             = useState(initialRepo);
  const [type, setType]                    = useState(initialType);
  const [data, setData]                    = useState({ nodes: [], links: [] });
  const [loading, setLoading]              = useState(true);
  const [inspectedNode, setInspectedNode]  = useState(null);
  const graphRef                           = useRef(null);
  const connectedRef                       = useRef(null); // { nodeId, incoming: Set, outgoing: Set }
  const [dim, setDim]                      = useState({ w: window.innerWidth, h: window.innerHeight });

  useEffect(() => {
    const h = () => setDim({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener('resize', h);
    return () => window.removeEventListener('resize', h);
  }, []);

  useEffect(() => {
    setLoading(true); setData({ nodes: [], links: [] });
    const go = async () => {
      if (type === 'query') {
        const cached = localStorage.getItem('AXON_QUERY_GRAPH');
        if (cached) { try { setData(JSON.parse(cached)); } catch(e) {} }
      } else {
        try {
          const res = await fetch(`${API_BASE_URL}/api/repos/${repo}/graph`);
          const d   = await res.json();
          if (d.nodes && d.links) setData(d);
        } catch(e) { console.error(e); }
      }
      setLoading(false);
    };
    go();
  }, [repo, type]);

  useEffect(() => {
    const g = graphRef.current;
    if (!g || !g.d3Force) return;
    try {
      g.d3Force('charge')?.strength(-600);
      g.d3Force('link')?.distance(type === 'repo' ? 120 : 150);
    } catch(e) {}
  }, [data, type]);

  /* Rebuild connected set whenever selected node changes */
  useEffect(() => {
    if (!inspectedNode) { connectedRef.current = null; return; }
    const incoming = new Set();
    const outgoing = new Set();
    data.links.forEach(l => {
      const src = typeof l.source === 'object' ? l.source.id : l.source;
      const tgt = typeof l.target === 'object' ? l.target.id : l.target;
      if (src === inspectedNode.id) outgoing.add(tgt);
      if (tgt === inspectedNode.id) incoming.add(src);
    });
    connectedRef.current = { nodeId: inspectedNode.id, incoming, outgoing };
  }, [inspectedNode, data.links]);

  /* ── paintNode — dim non-connected, enlarge selected —————— */
  const paintNode = useCallback((node, ctx, scale) => {
    try {
      const conn       = connectedRef.current;
      const isSelected = conn && node.id === conn.nodeId;
      const isIn       = conn && conn.incoming.has(node.id);
      const isOut      = conn && conn.outgoing.has(node.id);
      const dimmed     = conn && !isSelected && !isIn && !isOut;

      const label  = node.label || node.id || '?';
      const fs     = Math.min(Math.max(13 / scale, 10 / scale), 24);
      ctx.font     = `600 ${fs}px Inter,sans-serif`;
      const r      = isSelected ? 11 : 7;
      const tw     = ctx.measureText(label).width;
      const lw     = tw + 8; const lh = fs + 6; const yo = r + fs * 1.6;

      ctx.globalAlpha = dimmed ? 0.15 : 1;

      /* Node circle */
      ctx.beginPath(); ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = isSelected
        ? '#fff'
        : isIn  ? '#4ade80'
        : isOut ? '#f472b6'
        : COLORS[node.type] || '#fff';
      ctx.fill();

      /* Glow ring for selected */
      if (isSelected) {
        ctx.shadowColor  = '#fff';
        ctx.shadowBlur   = 20;
        ctx.strokeStyle  = 'rgba(255,255,255,0.6)';
        ctx.lineWidth    = 2;
        ctx.stroke();
        ctx.shadowBlur   = 0;
      } else if (isIn || isOut) {
        ctx.strokeStyle = isIn ? '#4ade80' : '#f472b6';
        ctx.lineWidth   = 1.5;
        ctx.stroke();
      } else {
        ctx.strokeStyle = 'rgba(0,0,0,0.5)';
        ctx.lineWidth   = 1;
        ctx.stroke();
      }

      /* Label */
      if (scale > 0.35) {
        ctx.fillStyle = dimmed ? 'rgba(8,8,12,0.4)' : 'rgba(8,8,12,0.88)';
        ctx.beginPath();
        ctx.roundRect?.(node.x - lw / 2, node.y + yo - lh / 2, lw, lh, 4);
        ctx.fill();
        ctx.textAlign    = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle    = dimmed ? 'rgba(243,244,246,0.3)' : '#f3f4f6';
        ctx.fillText(label, node.x, node.y + yo);
      }

      ctx.globalAlpha      = 1;
      node.__bckgDimensions = [lw, lh, yo];
    } catch(e) {}
  }, [inspectedNode]);

  /* ── Link helpers ————————————————————————————— */
  const getLinkSrcTgt = l => ({
    src: typeof l.source === 'object' ? l.source.id : l.source,
    tgt: typeof l.target === 'object' ? l.target.id : l.target,
  });

  const linkColor = useCallback(l => {
    const conn = connectedRef.current;
    if (!conn) return 'rgba(255,255,255,0.10)';
    const { src, tgt } = getLinkSrcTgt(l);
    if (src === conn.nodeId) return 'rgba(244,114,182,0.85)';
    if (tgt === conn.nodeId) return 'rgba(74,222,128,0.85)';
    return 'rgba(255,255,255,0.03)';
  }, [inspectedNode]);

  const linkWidth = useCallback(l => {
    const conn = connectedRef.current;
    if (!conn) return 0.8;
    const { src, tgt } = getLinkSrcTgt(l);
    return (src === conn.nodeId || tgt === conn.nodeId) ? 2 : 0.25;
  }, [inspectedNode]);

  /* NEVER return 0 — it permanently kills that edge's particle animation.
     Keep all particles alive; use transparent color to hide unrelated ones. */
  const linkParticles = useCallback(_l => {
    return type === 'query' ? 4 : 2;
  }, [type]);

  const linkParticleWidth = useCallback(l => {
    const conn = connectedRef.current;
    if (!conn) return 2;
    const { src, tgt } = getLinkSrcTgt(l);
    return (src === conn.nodeId || tgt === conn.nodeId) ? 4 : 1.5;
  }, [inspectedNode]);

  /* Hide unrelated particles via transparent color, not zero count */
  const linkParticleColor = useCallback(l => {
    const conn = connectedRef.current;
    if (!conn) return 'rgba(255,255,255,0.55)';
    const { src, tgt } = getLinkSrcTgt(l);
    if (src === conn.nodeId) return '#f472b6';
    if (tgt === conn.nodeId) return '#4ade80';
    return 'rgba(0,0,0,0)';
  }, [inspectedNode]);

  const handleNodeClick = n => {
    /* Clicking same node deselects */
    setInspectedNode(prev => prev?.id === n.id ? null : n);
  };

  const inDeg  = n => data.links.filter(l => (typeof l.target === 'object' ? l.target.id : l.target) === n.id).length;
  const outDeg = n => data.links.filter(l => (typeof l.source === 'object' ? l.source.id : l.source) === n.id).length;

  return (
    <div style={{ background:'#0a0a0c', color:'#fff', width:'100vw', height:'100vh', overflow:'hidden', position:'relative', fontFamily:'Inter,sans-serif' }}>
      <div className="ge-topbar">
        <div className="ge-brand">
          <div className="ge-brand-icon"><Network size={20}/></div>
          <div>
            <div className="ge-brand-title">{repo?.toUpperCase()} ARCHITECTURE</div>
            <div className="ge-brand-sub">Visualizing {type === 'repo' ? 'Entire Repository' : 'Targeted Query Path'} · {data.nodes.length} nodes · {data.links.length} edges</div>
          </div>
        </div>
        <div className="ge-toggle-group">
          <button className={`ge-toggle-btn ${type === 'query' ? 'active' : ''}`} onClick={() => setType('query')}><Search size={14}/> Query Graph</button>
          <button className={`ge-toggle-btn ${type === 'repo'  ? 'active' : ''}`} onClick={() => setType('repo')}><Network size={14}/> Full Repo</button>
        </div>
        <button className="ge-close-btn" onClick={() => window.close()}><X size={16}/> Close</button>
      </div>

      {loading && (
        <div className="ge-loading-overlay">
          <RefreshCw className="spinning" size={52} style={{ color: 'var(--primary)' }}/>
          <h2 style={{ marginTop: '1.5rem', letterSpacing: '1px', fontSize: '1.3rem' }}>RECONSTRUCTING TOPOLOGY…</h2>
          <p style={{ color: '#6b7280', marginTop: '0.5rem', fontSize: '0.85rem' }}>Traversing AST relationships and call graphs.</p>
        </div>
      )}

      <div className="ge-legend">
        <div className="ge-legend-title">NODE SCHEMA</div>
        {[['#4ade80', 'Function / Entity'], ['#f472b6', 'Object / Class'], ['#9ca3af', 'Source File']].map(([color, label]) => (
          <div key={label} className="ge-legend-item"><span className="ge-legend-dot" style={{ background: color }}/>{label}</div>
        ))}
        <div className="ge-legend-tip">Click node to focus paths · Click again to deselect</div>
        {inspectedNode && (
          <div className="ge-legend-focus">
            <span style={{ color:'#4ade80' }}>●</span> Incoming
            <span style={{ color:'#f472b6' }}>●</span> Outgoing
          </div>
        )}
      </div>

      <ForceGraph2D
        ref={graphRef} width={dim.w} height={dim.h} graphData={data}
        nodeCanvasObject={paintNode}
        nodePointerAreaPaint={(n, color, ctx) => {
          const d = n.__bckgDimensions; if (!d) return;
          ctx.fillStyle = color;
          ctx.beginPath(); ctx.arc(n.x, n.y, 11, 0, 2 * Math.PI); ctx.fill();
          ctx.fillRect(n.x - d[0] / 2, n.y + d[2] - d[1] / 2, d[0], d[1]);
        }}
        linkColor={linkColor}
        linkWidth={linkWidth}
        linkDirectionalParticles={linkParticles}
        linkDirectionalParticleSpeed={0.006}
        linkDirectionalParticleWidth={linkParticleWidth}
        linkDirectionalParticleColor={linkParticleColor}
        onNodeClick={handleNodeClick}
        backgroundColor="#0a0a0c"
      />

      <AnimatePresence>
        {inspectedNode && (
          <motion.div key="inspector" initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 40 }} className="ge-inspector">
            <div className="ge-inspector-header">
              <div>
                <div className="ge-inspector-name">{inspectedNode.label || inspectedNode.id}</div>
                <div className="ge-inspector-type" style={{ color: COLORS[inspectedNode.type] || '#fff' }}>{(inspectedNode.type || 'UNKNOWN').toUpperCase()} ELEMENT</div>
              </div>
              <button className="ge-inspector-close" onClick={() => setInspectedNode(null)}><X size={18}/></button>
            </div>
            <div className="ge-inspector-stats">
              <div className="ge-stat"><div className="ge-stat-label">INCOMING</div><div className="ge-stat-val" style={{ color: '#4ade80' }}>{inDeg(inspectedNode)}</div></div>
              <div className="ge-stat"><div className="ge-stat-label">OUTGOING</div><div className="ge-stat-val" style={{ color: '#f472b6' }}>{outDeg(inspectedNode)}</div></div>
              <div className="ge-stat"><div className="ge-stat-label">TOTAL</div><div className="ge-stat-val">{inDeg(inspectedNode) + outDeg(inspectedNode)}</div></div>
            </div>
            <div className="ge-inspector-field"><div className="ge-field-label">SOURCE FILE</div><div className="ge-field-val">{inspectedNode.file || '— External Symbol —'}</div></div>
            <div className="ge-inspector-field"><div className="ge-field-label">IDENTIFIER</div><div className="ge-field-val" style={{ fontFamily: 'monospace', fontSize: '0.75rem', opacity: 0.6 }}>{inspectedNode.id}</div></div>
            {outDeg(inspectedNode) > 0 && (
              <div className="ge-inspector-field">
                <div className="ge-field-label">CALLS</div>
                {data.links.filter(l => (typeof l.source === 'object' ? l.source.id : l.source) === inspectedNode.id).slice(0, 5).map((l, i) => (
                  <div key={i} className="ge-conn-item" style={{ color: '#f472b6' }}>→ {typeof l.target === 'object' ? l.target.label || l.target.id : l.target}</div>
                ))}
              </div>
            )}
            {inDeg(inspectedNode) > 0 && (
              <div className="ge-inspector-field">
                <div className="ge-field-label">CALLED BY</div>
                {data.links.filter(l => (typeof l.target === 'object' ? l.target.id : l.target) === inspectedNode.id).slice(0, 5).map((l, i) => (
                  <div key={i} className="ge-conn-item" style={{ color: '#4ade80' }}>← {typeof l.source === 'object' ? l.source.label || l.source.id : l.source}</div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   PIPELINE STEPS CONFIG
───────────────────────────────────────────────────────────── */
const STEPS = [
  { id: 1, icon: Search,   label: 'Query Router',     desc: 'Extracting topological targets' },
  { id: 2, icon: GitMerge, label: 'Graph Traversal',  desc: 'Tracing symbolic call paths' },
  { id: 3, icon: Database, label: 'Vector Retrieval', desc: 'Fetching semantic embeddings' },
  { id: 4, icon: Cpu,      label: 'Fusion Engine',    desc: 'Synthesizing final response' },
];

/* ── Markdown component overrides
   Rule: fn-token (green) applied ONLY to inline backtick tokens
   that look like a snake_case function name and have no spaces.
   Block code fences always render as <pre>. ─────────────────── */
const makeMdComponents = () => ({
  /* Never apply fn-token to bold — LLMs bold whole sentences */
  strong: ({ children }) => <strong>{children}</strong>,

  code: ({ className, children }) => {
    /* A fenced code block always receives a language-* className
       OR contains newlines in its content. Anything else is inline. */
    const raw       = String(children ?? '').replace(/\n$/, '');
    const isBlock   = !!(className?.startsWith('language-') || raw.includes('\n'));

    if (isBlock) {
      return (
        <pre className="code-block">
          <code className={className}>{raw}</code>
        </pre>
      );
    }

    /* Inline token — highlight green only for snake_case fn names */
    const isFn = !raw.includes(' ') && raw.length < 60 &&
      (raw.endsWith('(') || raw.includes('(') || /^[a-z_][a-z0-9_]*$/.test(raw));

    return isFn
      ? <code className="fn-token">{raw}</code>
      : <code className="inline-code">{raw}</code>;
  },

  h1:         ({ children }) => <h1 className="md-h1">{children}</h1>,
  h2:         ({ children }) => <h2 className="md-h2">{children}</h2>,
  h3:         ({ children }) => <h3 className="md-h3">{children}</h3>,
  p:          ({ children }) => <p  className="md-p">{children}</p>,
  ul:         ({ children }) => <ul className="md-ul">{children}</ul>,
  ol:         ({ children }) => <ol className="md-ol">{children}</ol>,
  li:         ({ children }) => <li className="md-li">{children}</li>,
  blockquote: ({ children }) => <blockquote className="md-quote">{children}</blockquote>,
});
const MD_COMPONENTS = makeMdComponents();

/* ─────────────────────────────────────────────────────────────
   MAIN APP
───────────────────────────────────────────────────────────── */
function App() {
  const [params] = useState(() => new URLSearchParams(window.location.search));
  if (params.get('graph')) {
    return <GraphExplorer initialRepo={params.get('repo')} initialType={params.get('graph')} />;
  }

  // ── State ──────────────────────────────────────────────────
  const [query,        setQuery]        = useState('');
  const [mode,         setMode]         = useState('hybrid');
  const [repos,        setRepos]        = useState([]);
  const [activeRepo,   setActiveRepo]   = useState('');
  const [cloneUrl,     setCloneUrl]     = useState('');
  const [loading,      setLoading]      = useState(false);
  const [cloning,      setCloning]      = useState(false);
  const [error,        setError]        = useState(null);
  const [answer,       setAnswer]       = useState(null);
  const [pipelineData, setPipelineData] = useState(null);
  const [traceStep,    setTraceStep]    = useState(0);
  const [activeTab,    setActiveTab]    = useState('insight');
  const [showClone,    setShowClone]    = useState(false);
  const queryRef                        = useRef(null);

  // ── Load repos ─────────────────────────────────────────────
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/repos`)
      .then(r => r.json())
      .then(d => { if (d.repos?.length) { setRepos(d.repos); setActiveRepo(d.repos[0]); } });
  }, []);

  // ── Search ─────────────────────────────────────────────────
  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;
    setLoading(true); setError(null); setAnswer(null); setPipelineData(null); setTraceStep(1);
    const iv = setInterval(() => setTraceStep(p => p < 3 ? p + 1 : p), 2200);
    try {
      const res  = await fetch(`${API_BASE_URL}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, mode, repo: activeRepo }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Query failed');
      clearInterval(iv); setTraceStep(4);
      setAnswer(data.answer); setPipelineData(data.pipeline_data);
      if (data.pipeline_data?.graph_json) {
        const nodes = data.pipeline_data.graph_json.nodes || [];
        const links = (data.pipeline_data.graph_json.edges || []).map(e => ({ source: e.source, target: e.target }));
        localStorage.setItem('AXON_QUERY_GRAPH', JSON.stringify({ nodes, links }));
      }
    } catch (err) { clearInterval(iv); setTraceStep(0); setError(err.message); }
    finally { setLoading(false); }
  };

  // ── Clone ──────────────────────────────────────────────────
  const handleClone = async () => {
    if (!cloneUrl.trim()) return;
    setCloning(true); setError(null);
    try {
      const res  = await fetch(`${API_BASE_URL}/api/repos/clone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: cloneUrl }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Clone failed');
      setCloneUrl(''); setShowClone(false);
      const updated = await fetch(`${API_BASE_URL}/api/repos`).then(r => r.json());
      if (updated.repos?.length) { setRepos(updated.repos); setActiveRepo(data.repo); }
    } catch (err) { setError(err.message); }
    finally { setCloning(false); }
  };

  const handleExplore = () => window.open(`/?graph=query&repo=${activeRepo}`, '_blank');
  const handleNewQuery = () => { setAnswer(null); setPipelineData(null); setTraceStep(0); setError(null); queryRef.current?.focus(); };

  // ── Render ─────────────────────────────────────────────────
  return (
    <div className="shell">

      {/* ══════════════════════════════════════════════════════
          TOP NAVIGATION BAR
      ══════════════════════════════════════════════════════ */}
      <header className="topnav">
        <div className="topnav-brand">
          <div className="topnav-logo"><Zap size={18}/></div>
          <span className="topnav-name">AXON</span>
          <span className="topnav-tagline">Codebase Intelligence Engine</span>
        </div>

        <div className="topnav-controls">
          {/* Repo selector */}
          <div className="nav-control-group">
            <GitBranch size={13} className="nav-control-icon"/>
            <select className="nav-select" value={activeRepo} onChange={e => setActiveRepo(e.target.value)}>
              {repos.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
            <ChevronDown size={12} className="nav-control-icon"/>
          </div>

          {/* Mode selector */}
          <div className="nav-control-group">
            <Layers size={13} className="nav-control-icon"/>
            <select className="nav-select" value={mode} onChange={e => setMode(e.target.value)}>
              <option value="hybrid">Fusion Mode</option>
              <option value="graph">Graph Mode</option>
              <option value="vector">Semantic Mode</option>
            </select>
            <ChevronDown size={12} className="nav-control-icon"/>
          </div>

          {/* Add repo button */}
          <button className="nav-add-btn" onClick={() => setShowClone(v => !v)}>
            <Plus size={14}/> Add Repo
          </button>
        </div>
      </header>

      {/* ── Clone drawer ─────────────────────────────────── */}
      <AnimatePresence>
        {showClone && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="clone-drawer">
            <div className="clone-drawer-inner">
              <div className="clone-drawer-label">
                <GitBranch size={14}/> Index a new GitHub repository
              </div>
              <div className="clone-drawer-row">
                <input
                  className="clone-url-input" placeholder="https://github.com/owner/repo"
                  value={cloneUrl} onChange={e => setCloneUrl(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleClone()}
                />
                <button className="clone-submit-btn" onClick={handleClone} disabled={cloning}>
                  {cloning ? <RefreshCw size={14} className="spinning"/> : <><Plus size={14}/> Clone & Index</>}
                </button>
                <button className="clone-cancel-btn" onClick={() => setShowClone(false)}><X size={14}/></button>
              </div>
              {cloning && <div className="clone-progress-label">Cloning repository and generating embeddings…</div>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ══════════════════════════════════════════════════════
          MAIN BODY
      ══════════════════════════════════════════════════════ */}
      <div className="body-split">

        {/* ── LEFT PANEL ──────────────────────────────────── */}
        <aside className="left-panel">

          {/* Query form */}
          <div className="query-section">
            <div className="section-label"><Terminal size={12}/> QUERY CONSOLE</div>
            <form onSubmit={handleSearch}>
              <div className="query-input-wrap">
                <Search size={16} className="query-search-icon"/>
                <textarea
                  ref={queryRef}
                  className="query-textarea"
                  placeholder="How does this codebase handle authentication?"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSearch(); }
                  }}
                  disabled={loading}
                  rows={3}
                />
              </div>
              {error && <div className="query-error"><X size={12}/> {error}</div>}
              <button type="submit" className="query-run-btn" disabled={loading || !query.trim()}>
                {loading
                  ? <><RefreshCw size={15} className="spinning"/> Analyzing…</>
                  : <><ArrowRight size={15}/> Run Analysis</>
                }
              </button>
            </form>
          </div>

          {/* Repos list */}
          <div className="repos-section">
            <div className="section-label"><Box size={12}/> INDEXED REPOS</div>
            <div className="repo-list">
              {repos.map(r => (
                <button
                  key={r}
                  className={`repo-item ${r === activeRepo ? 'active' : ''}`}
                  onClick={() => setActiveRepo(r)}
                >
                  <GitBranch size={12}/>
                  <span>{r}</span>
                  {r === activeRepo && <div className="repo-active-dot"/>}
                </button>
              ))}
            </div>
          </div>

          {/* Pipeline trace */}
          <div className="pipeline-section">
            <div className="section-label"><Activity size={12}/> PIPELINE STATUS</div>
            <div className="pipeline-steps">
              {STEPS.map(s => {
                const done    = traceStep > s.id;
                const active  = traceStep === s.id && (loading || traceStep === 4);
                const current = traceStep === s.id;
                const Icon    = s.icon;
                return (
                  <div key={s.id} className={`pipeline-step ${done ? 'done' : current ? 'current' : 'idle'}`}>
                    <div className="pipeline-step-icon">
                      {done    ? <CheckCircle2 size={14}/>
                               : current ? <Icon size={14}/>
                               : <Circle size={14}/>}
                    </div>
                    <div className="pipeline-step-text">
                      <span className="pipeline-step-label">{s.label}</span>
                      {(current || done) && (
                        <span className="pipeline-step-desc">
                          {done ? '✓ done' : s.desc}
                        </span>
                      )}
                    </div>
                    {s.id < 4 && <div className="pipeline-connector"/>}
                  </div>
                );
              })}
            </div>
          </div>

        </aside>

        {/* ── MAIN OUTPUT AREA ────────────────────────────── */}
        <main className="output-area">

          {/* Empty state */}
          {!answer && !loading && !error && (
            <div className="idle-screen">
              <motion.div animate={{ scale: [1, 1.04, 1] }} transition={{ repeat: Infinity, duration: 4, ease: 'easeInOut' }}>
                <div className="idle-icon"><Network size={56}/></div>
              </motion.div>
              <h2 className="idle-title">AXON Engine Ready</h2>
              <p className="idle-sub">Select a repository, write a query, and let the engine traverse your codebase's AST structure and semantic space.</p>
              <div className="idle-hints">
                <div className="idle-hint"><Code size={14}/> "How is routing implemented?"</div>
                <div className="idle-hint"><GitMerge size={14}/> "What calls the auth middleware?"</div>
                <div className="idle-hint"><Database size={14}/> "Explain the database schema."</div>
              </div>
            </div>
          )}

          {/* Loading state */}
          {loading && !answer && (
            <div className="idle-screen">
              <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 2, ease: 'linear' }}>
                <div className="idle-icon" style={{ color: 'var(--primary)' }}><RefreshCw size={56}/></div>
              </motion.div>
              <h2 className="idle-title">Synthesizing Response</h2>
              <p className="idle-sub">
                {STEPS.find(s => s.id === traceStep)?.desc || 'Initializing pipeline…'}
              </p>
              {/* Mini progress */}
              <div className="loading-progress">
                {STEPS.map(s => (
                  <div key={s.id} className={`progress-pip ${traceStep >= s.id ? 'lit' : ''}`}/>
                ))}
              </div>
            </div>
          )}

          {/* Answer */}
          <AnimatePresence>
            {answer && (
              <motion.div
                key="answer"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className="answer-pane"
              >
                {/* Answer header bar */}
                <div className="answer-topbar">
                  <div className="answer-topbar-left">
                    <div className="answer-repo-chip">
                      <GitBranch size={12}/> {activeRepo}
                    </div>
                    <div className="answer-mode-chip">{mode.toUpperCase()}</div>
                  </div>

                  <div className="answer-tabs">
                    <button className={`answer-tab ${activeTab === 'insight' ? 'on' : ''}`} onClick={() => setActiveTab('insight')}>
                      <Layout size={13}/> AI Insight
                    </button>
                    <button className={`answer-tab ${activeTab === 'sources' ? 'on' : ''}`} onClick={() => setActiveTab('sources')}>
                      <Braces size={13}/> Sources ({(pipelineData?.semantic_nodes?.length || 0) + (pipelineData?.graph_context && pipelineData.graph_context !== "No structural graph data found for this query." ? 1 : 0)})
                    </button>
                  </div>

                  <div className="answer-topbar-actions">
                    <button className="action-btn secondary" onClick={handleNewQuery}>
                      <Search size={13}/> New Query
                    </button>
                    <button className="action-btn primary" onClick={handleExplore}>
                      <Maximize size={13}/> Explore Graph
                    </button>
                  </div>
                </div>

                {/* Answer body */}
                <div className="answer-scroll">
                  {activeTab === 'insight' ? (
                    <div className="answer-prose">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                        {answer}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <div className="sources-list">
                      {pipelineData?.graph_context && pipelineData.graph_context !== "No structural graph data found for this query." && (
                        <div className="source-card" style={{ borderLeft: '3px solid #f472b6' }}>
                          <div className="source-card-header">
                            <div className="source-card-file"><Network size={13}/> Structural Call Path (AST)</div>
                            <div className="source-card-line">Architectural Trace</div>
                          </div>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{`\`\`\`text\n${pipelineData.graph_context}\n\`\`\``}</ReactMarkdown>
                        </div>
                      )}
                      
                      {pipelineData?.semantic_nodes?.length ? pipelineData.semantic_nodes.map((node, i) => (
                        <div key={i} className="source-card">
                          <div className="source-card-header">
                            <div className="source-card-file"><FileText size={13}/> {node.file}</div>
                            <div className="source-card-line">Line {node.line}</div>
                          </div>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{`\`\`\`python\n${node.content}\n\`\`\``}</ReactMarkdown>
                        </div>
                      )) : (
                        (!pipelineData?.graph_context || pipelineData.graph_context === "No structural graph data found for this query.") && (
                          <div className="sources-empty">No source chunks retrieved for this query.</div>
                        )
                      )}
                    </div>
                  )}
                </div>

                {/* Answer footer */}
                <div className="answer-footer">
                  <div className="fn-legend"><span className="fn-token" style={{ fontSize: '0.7rem' }}>fn_name</span> = function identifier</div>
                  <span className="answer-footer-tag">AXON · {mode} · {activeRepo}</span>
                </div>

              </motion.div>
            )}
          </AnimatePresence>

        </main>

      </div>
    </div>
  );
}

export default App;
