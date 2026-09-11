import React, { useState } from 'react';
import { GitCompare, ShieldAlert, CheckCircle, AlertTriangle, FileCode } from 'lucide-react';

export default function CodeReviewDiff({ reviewData, diffText }) {
  const [activeTab, setActiveTab] = useState('diff'); // 'diff' | 'review'

  const issues = reviewData?.issues || [];
  const status = reviewData?.approved ? 'Approved' : (issues.length > 0 ? 'Changes Requested' : 'Awaiting Review');

  const renderDiffLines = () => {
    if (!diffText || !diffText.trim()) {
      return (
        <div className="text-slate-400 italic p-6 text-xs text-center font-mono">
          No file modifications recorded yet. Launch the pipeline to generate real-time diffs.
        </div>
      );
    }

    const lines = diffText.split('\n');
    return lines.map((line, idx) => {
      let lineClass = 'text-slate-700 px-3 py-0.5 font-mono text-xs block';
      if (line.startsWith('+') && !line.startsWith('+++')) {
        lineClass = 'bg-emerald-50 text-emerald-950 border-l-4 border-emerald-500 font-mono text-xs px-3 py-0.5 block';
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        lineClass = 'bg-rose-50 text-rose-950 border-l-4 border-rose-400 line-through opacity-80 font-mono text-xs px-3 py-0.5 block';
      } else if (line.startsWith('@@') || line.startsWith('diff --git')) {
        lineClass = 'bg-slate-100 text-sky-800 font-mono text-xs font-semibold px-3 py-0.5 block border-y border-slate-200';
      }
      return (
        <span key={idx} className={lineClass}>
          {line || ' '}
        </span>
      );
    });
  };

  return (
    <div className="bg-white border border-slate-200/80 rounded-3xl p-6 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-sky-100 text-sky-700 flex items-center justify-center">
              <GitCompare size={16} />
            </div>
            <h3 className="font-['Outfit'] font-bold text-base text-[#0F172A]">
              Execution Inspection & Diff
            </h3>
          </div>

          <div className="flex gap-1.5 p-1 rounded-xl bg-slate-100 border border-slate-200">
            <button
              className={`text-xs font-medium px-3 py-1 rounded-lg transition-all cursor-pointer ${
                activeTab === 'diff'
                  ? 'bg-white text-[#0F172A] shadow-sm font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
              onClick={() => setActiveTab('diff')}
            >
              Unified Diff
            </button>
            <button
              className={`text-xs font-medium px-3 py-1 rounded-lg transition-all cursor-pointer ${
                activeTab === 'review'
                  ? 'bg-white text-[#0F172A] shadow-sm font-semibold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
              onClick={() => setActiveTab('review')}
            >
              Review Report ({issues.length})
            </button>
          </div>
        </div>

        {activeTab === 'diff' ? (
          <div
            data-lenis-prevent
            className="bg-slate-50/70 border border-slate-200 rounded-2xl p-2 max-h-[360px] overflow-y-auto whitespace-pre font-mono"
          >
            {renderDiffLines()}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div
              className={`flex items-center gap-3 p-4 rounded-2xl border ${
                reviewData?.approved
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-950'
                  : 'bg-amber-50 border-amber-200 text-amber-950'
              }`}
            >
              {reviewData?.approved ? (
                <CheckCircle size={20} className="text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle size={20} className="text-amber-600 shrink-0" />
              )}
              <div>
                <div className="text-xs font-bold font-['Outfit']">
                  Verification Status: {status}
                </div>
                <div className="text-xs text-slate-600 mt-0.5">
                  {reviewData?.summary || 'No review remarks submitted yet.'}
                </div>
              </div>
            </div>

            {issues.length > 0 ? (
              <div
                data-lenis-prevent
                className="flex flex-col gap-2 max-h-[260px] overflow-y-auto"
              >
                {issues.map((issue, i) => (
                  <div
                    key={i}
                    className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs"
                  >
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-semibold text-slate-800">
                        {issue.title || `Issue #${i + 1}`}
                      </span>
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase ${
                          issue.severity === 'critical'
                            ? 'bg-rose-100 text-rose-700 border border-rose-200'
                            : 'bg-amber-100 text-amber-700 border border-amber-200'
                        }`}
                      >
                        {issue.severity || 'warning'}
                      </span>
                    </div>
                    <p className="text-slate-600">{issue.description || issue}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-400 italic text-center p-6 font-mono">
                No policy violations identified. Zero-trust review approved.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
