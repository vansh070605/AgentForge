import React, { useState, useRef, useEffect } from 'react';
import { Terminal, Trash2, ArrowDown, Search, Download, Filter, FileSpreadsheet } from 'lucide-react';
import { useAgentForge } from '../context/AgentForgeContext';

export default function TelemetryPage() {
  const { logs, clearLogs } = useAgentForge();
  const [filterActor, setFilterActor] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const terminalEndRef = useRef(null);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const actors = ['ALL', 'ORCHESTRATOR', 'IDENTITY', 'EXECUTION', 'REVIEW', 'PROOF'];

  const getActorBadge = (actor) => {
    switch (actor) {
      case 'IDENTITY':
        return 'bg-violet-100 dark:bg-violet-900/40 text-violet-800 dark:text-violet-300 border-violet-200 dark:border-violet-800/50';
      case 'EXECUTION':
        return 'bg-amber-100 dark:bg-amber-900/40 text-amber-900 dark:text-amber-300 border-amber-200 dark:border-amber-800/50';
      case 'REVIEW':
        return 'bg-rose-100 dark:bg-rose-900/40 text-rose-800 dark:text-rose-300 border-rose-200 dark:border-rose-800/50';
      case 'PROOF':
        return 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-900 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/50';
      case 'ORCHESTRATOR':
      default:
        return 'bg-slate-200 dark:bg-white/[0.08] text-slate-800 dark:text-slate-300 border-slate-300 dark:border-white/[0.08]';
    }
  };

  const filteredLogs = logs.filter((log) => {
    const matchesActor = filterActor === 'ALL' || log.actor === filterActor;
    const matchesQuery =
      !searchQuery.trim() ||
      log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.actor.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesActor && matchesQuery;
  });

  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(logs, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `agentforge-telemetry-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportCSV = () => {
    const headers = 'Time,Actor,Message\n';
    const rows = logs
      .map((l) => `"${l.time}","${l.actor}","${l.message.replace(/"/g, '""')}"`)
      .join('\n');
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `agentforge-telemetry-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-[#0F172A] dark:text-[#F1F5F9] font-['Plus_Jakarta_Sans','Outfit']">
            Live Telemetry Console
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Real-time event paper recording state mutations and multi-agent communications.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={exportJSON}
            disabled={logs.length === 0}
            className="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-white/[0.08] bg-white dark:bg-[#12141C] hover:bg-slate-50 dark:hover:bg-white/[0.04] text-xs font-medium text-slate-700 dark:text-slate-300 flex items-center gap-1.5 cursor-pointer disabled:opacity-50 transition-all"
          >
            <Download size={13} />
            <span>JSON</span>
          </button>
          <button
            onClick={exportCSV}
            disabled={logs.length === 0}
            className="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-white/[0.08] bg-white dark:bg-[#12141C] hover:bg-slate-50 dark:hover:bg-white/[0.04] text-xs font-medium text-slate-700 dark:text-slate-300 flex items-center gap-1.5 cursor-pointer disabled:opacity-50 transition-all"
          >
            <FileSpreadsheet size={13} />
            <span>CSV</span>
          </button>
          <button
            onClick={clearLogs}
            disabled={logs.length === 0}
            className="p-1.5 rounded-xl border border-slate-200 dark:border-white/[0.08] bg-white dark:bg-[#12141C] hover:bg-slate-50 dark:hover:bg-white/[0.04] text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 cursor-pointer disabled:opacity-50 transition-all"
            title="Clear logs"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white dark:bg-[#12141C] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4 shadow-sm flex flex-wrap items-center justify-between gap-4 transition-colors">
        {/* Agent Filter Chips */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs font-mono font-semibold text-slate-400 dark:text-slate-500 mr-1 flex items-center gap-1">
            <Filter size={12} />
            Filter:
          </span>
          {actors.map((act) => (
            <button
              key={act}
              onClick={() => setFilterActor(act)}
              className={`text-[11px] font-mono font-bold px-2.5 py-1 rounded-lg border transition-all cursor-pointer ${
                filterActor === act
                  ? 'bg-slate-900 dark:bg-white text-white dark:text-slate-900 border-slate-900 dark:border-white shadow-sm'
                  : 'bg-slate-50 dark:bg-white/[0.04] text-slate-600 dark:text-slate-300 border-slate-200 dark:border-white/[0.08] hover:bg-slate-100 dark:hover:bg-white/[0.08]'
              }`}
            >
              [{act}]
            </button>
          ))}
        </div>

        {/* Search Input & Auto-Scroll Toggle */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
            <input
              type="text"
              placeholder="Search event messages..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-slate-50 dark:bg-[#0F1118] border border-slate-200 dark:border-white/[0.08] rounded-xl pl-8 pr-3 py-1.5 text-xs font-mono text-slate-800 dark:text-slate-200 outline-none focus:bg-white dark:focus:bg-[#0B0C10] focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 w-48 sm:w-64 transition-all"
            />
          </div>

          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`text-xs px-3 py-1.5 rounded-xl border font-mono transition-all cursor-pointer flex items-center gap-1.5 ${
              autoScroll
                ? 'bg-sky-50 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800/50 font-semibold'
                : 'bg-slate-50 dark:bg-white/[0.04] text-slate-500 dark:text-slate-400 border-slate-200 dark:border-white/[0.08]'
            }`}
          >
            <ArrowDown size={12} />
            <span>{autoScroll ? 'Auto-Lock' : 'Scroll Free'}</span>
          </button>
        </div>
      </div>

      {/* Live Telemetry Paper Container */}
      <div className="bg-white dark:bg-[#12141C] border border-slate-200 dark:border-white/[0.08] rounded-3xl p-6 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] dark:shadow-none transition-colors">
        <div
          data-lenis-prevent
          className="bg-[#F8FAFC] dark:bg-[#0F1118] border border-slate-200/90 dark:border-white/[0.08] rounded-2xl p-5 font-mono text-xs text-slate-900 dark:text-slate-200 max-h-[580px] overflow-y-auto flex flex-col gap-2.5 shadow-inner"
        >
          {filteredLogs.length === 0 ? (
            <div className="text-slate-400 dark:text-slate-500 italic py-16 text-center">
              {logs.length === 0
                ? 'Telemetry paper ready. Run a pipeline from the Overview tab to stream events.'
                : 'No telemetry events match your active filters.'}
            </div>
          ) : (
            filteredLogs.map((log, index) => {
              const actor = log.actor || 'ORCHESTRATOR';
              return (
                <div key={index} className="flex items-start gap-3 leading-relaxed">
                  <span className="text-slate-400 dark:text-slate-500 shrink-0 text-[11px] select-none">
                    {log.time || '00:00:00'}
                  </span>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-md border shrink-0 uppercase tracking-wide ${getActorBadge(actor)}`}
                  >
                    [{actor}]
                  </span>
                  <span className="text-slate-800 dark:text-slate-200 break-words flex-1 selection:bg-sky-100 dark:selection:bg-sky-900">
                    {log.message}
                  </span>
                </div>
              );
            })
          )}
          <div ref={terminalEndRef} />
        </div>
      </div>
    </div>
  );
}
