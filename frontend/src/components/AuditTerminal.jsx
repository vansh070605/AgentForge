import React, { useRef, useEffect, useState } from 'react';
import { Terminal, Trash2, ArrowDown } from 'lucide-react';

export default function AuditTerminal({ logs, onClearLogs }) {
  const terminalEndRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const getActorTagClass = (actor) => {
    switch (actor) {
      case 'IDENTITY':
        return 'bg-violet-100 text-violet-800 border border-violet-200';
      case 'EXECUTION':
        return 'bg-amber-100 text-amber-900 border border-amber-200';
      case 'REVIEW':
        return 'bg-rose-100 text-rose-800 border border-rose-200';
      case 'PROOF':
        return 'bg-emerald-100 text-emerald-900 border border-emerald-200';
      case 'ORCHESTRATOR':
      default:
        return 'bg-slate-200 text-slate-800 border border-slate-300/60';
    }
  };

  return (
    <div className="bg-white border border-slate-200/80 rounded-3xl p-6 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-700 flex items-center justify-center">
              <Terminal size={16} />
            </div>
            <h3 className="font-['Outfit'] font-bold text-base text-[#0F172A]">
              Live Telemetry Stream
            </h3>
            <span className="text-xs text-slate-400 font-mono">
              ({logs.length} events)
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              className={`text-xs px-2.5 py-1 rounded-lg border font-mono transition-all cursor-pointer flex items-center gap-1 ${
                autoScroll
                  ? 'bg-sky-50 text-sky-700 border-sky-200 font-semibold'
                  : 'bg-slate-50 text-slate-500 border-slate-200'
              }`}
              onClick={() => setAutoScroll(!autoScroll)}
            >
              <ArrowDown size={11} />
              {autoScroll ? 'Lock Auto' : 'Scroll Free'}
            </button>
            <button
              className="p-1.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-500 hover:text-slate-800 transition-all cursor-pointer"
              onClick={onClearLogs}
              title="Clear telemetry stream"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>

        {/* Live Telemetry Paper Container */}
        <div
          data-lenis-prevent
          className="bg-[#F8FAFC] border border-slate-200 rounded-2xl p-4 font-mono text-xs text-slate-900 max-h-[360px] overflow-y-auto flex flex-col gap-2 shadow-inner"
        >
          {logs.length === 0 ? (
            <div className="text-slate-400 italic py-6 text-center">
              Telemetry paper ready. Awaiting multi-agent events...
            </div>
          ) : (
            logs.map((log, index) => {
              const actor = log.actor || 'ORCHESTRATOR';
              return (
                <div key={index} className="flex items-start gap-2.5 leading-relaxed">
                  <span className="text-slate-400 shrink-0 text-[11px]">
                    {log.time || '00:00:00'}
                  </span>
                  <span
                    className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md shrink-0 uppercase tracking-wide ${getActorTagClass(actor)}`}
                  >
                    {actor}
                  </span>
                  <span className="text-slate-700 break-words flex-1">
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
