import React, { useState } from 'react';
import { GitCompare, ShieldCheck, AlertTriangle, CheckCircle, FileCode, ArrowUpRight, Copy, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAgentForge } from '../context/AgentForgeContext';

export default function DiffPage() {
  const { diffText, reviewData } = useAgentForge();
  const [activeTab, setActiveTab] = useState('diff'); // 'diff' | 'review'
  const [copied, setCopied] = useState(false);

  const issues = reviewData?.issues || [];
  const status = reviewData?.approved ? 'Approved' : (issues.length > 0 ? 'Changes Requested' : 'Awaiting Review');

  // Stats calculation
  const lines = diffText ? diffText.split('\n') : [];
  const additions = lines.filter((l) => l.startsWith('+') && !l.startsWith('+++')).length;
  const deletions = lines.filter((l) => l.startsWith('-') && !l.startsWith('---')).length;
  const filesTouched = lines.filter((l) => l.startsWith('diff --git')).length || (diffText ? 1 : 0);

  const handleCopyDiff = () => {
    if (!diffText) return;
    navigator.clipboard.writeText(diffText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const renderDiffContent = () => {
    if (!diffText || !diffText.trim()) {
      return (
        <div className="text-slate-400 dark:text-slate-500 italic p-6 sm:p-12 text-center text-xs font-mono whitespace-normal break-words">
          No file modifications recorded in current session. Run a pipeline from Overview to generate diffs.
        </div>
      );
    }

    return lines.map((line, idx) => {
      let lineClass = 'text-slate-700 dark:text-slate-300 px-4 py-0.5 font-mono text-xs block';
      if (line.startsWith('+') && !line.startsWith('+++')) {
        lineClass = 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-950 dark:text-emerald-200 border-l-4 border-emerald-500 dark:border-emerald-500 font-mono text-xs px-4 py-0.5 block';
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        lineClass = 'bg-rose-50 dark:bg-rose-950/40 text-rose-950 dark:text-rose-200 border-l-4 border-rose-400 dark:border-rose-500 line-through opacity-80 font-mono text-xs px-4 py-0.5 block';
      } else if (line.startsWith('@@') || line.startsWith('diff --git')) {
        lineClass = 'bg-slate-100 dark:bg-white/[0.06] text-sky-800 dark:text-sky-300 font-mono text-xs font-semibold px-4 py-1 block border-y border-slate-200 dark:border-white/[0.08] mt-2 first:mt-0';
      }
      return (
        <span key={idx} className={lineClass}>
          {line || ' '}
        </span>
      );
    });
  };

  return (
    <motion.div 
      className="flex flex-col gap-6"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
    >
      {/* Header & Stats Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-[#0F172A] dark:text-[#F1F5F9] font-['Plus_Jakarta_Sans','Outfit']">
            Inspection & Code Diff Workspace
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            High-contrast daylight & carbon diff verified against zero-trust policy.
          </p>
        </div>

        {/* Telemetry Summary Bar */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-white/[0.06] border border-slate-200 dark:border-white/[0.08] font-mono text-xs">
            <span className="text-slate-500 dark:text-slate-400">Files:</span>
            <span className="font-bold text-slate-800 dark:text-slate-200">{filesTouched}</span>
            <span className="text-slate-300 dark:text-slate-600">|</span>
            <span className="text-emerald-700 dark:text-emerald-400 font-bold">+{additions}</span>
            <span className="text-rose-700 dark:text-rose-400 font-bold">-{deletions}</span>
          </div>

          <button
            onClick={handleCopyDiff}
            disabled={!diffText}
            className="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-white/[0.08] bg-white dark:bg-[#12141C] hover:bg-slate-50 dark:hover:bg-white/[0.04] text-xs font-medium text-slate-700 dark:text-slate-300 flex items-center gap-1.5 cursor-pointer disabled:opacity-50 transition-all"
          >
            {copied ? <Check size={13} className="text-emerald-600 dark:text-emerald-400" /> : <Copy size={13} />}
            <span>{copied ? 'Copied' : 'Copy Diff'}</span>
          </button>
        </div>
      </div>

      {/* Main Review Card */}
      <div className="bg-white dark:bg-[#12141C] border border-slate-200 dark:border-white/[0.08] rounded-3xl p-6 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] dark:shadow-none transition-colors">
        {/* Workspace Tab Switcher */}
        <div className="flex items-center justify-between mb-5 pb-4 border-b border-slate-100 dark:border-white/[0.06]">
          <div className="flex gap-2 p-1 rounded-xl bg-slate-100 dark:bg-white/[0.06] border border-slate-200 dark:border-white/[0.08]">
            <button
              onClick={() => setActiveTab('diff')}
              className={`text-xs px-4 py-1.5 rounded-lg transition-all cursor-pointer font-medium font-['Outfit'] ${
                activeTab === 'diff'
                  ? 'bg-white dark:bg-white/10 text-slate-900 dark:text-white shadow-sm font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              Unified Git Diff
            </button>
            <button
              onClick={() => setActiveTab('review')}
              className={`text-xs px-4 py-1.5 rounded-lg transition-all cursor-pointer font-medium font-['Outfit'] ${
                activeTab === 'review'
                  ? 'bg-white dark:bg-white/10 text-slate-900 dark:text-white shadow-sm font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              Quality Audit Findings ({issues.length})
            </button>
          </div>

          <div className="text-xs font-mono text-slate-500 dark:text-slate-400 hidden sm:block">
            Target Workspace: <span className="font-semibold text-slate-700 dark:text-slate-300">agentforge/tools/security.py</span>
          </div>
        </div>

        {/* Tab Content with data-lenis-prevent */}
        <div className="relative">
          <AnimatePresence mode="wait">
            {activeTab === 'diff' ? (
              <motion.div
                key="diff"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                data-lenis-prevent
                className="bg-slate-50/70 dark:bg-[#0F1118] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-3 max-h-[560px] overflow-y-auto overflow-x-auto whitespace-pre font-mono shadow-inner"
              >
                {renderDiffContent()}
              </motion.div>
            ) : (
              <motion.div 
                key="review"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
                className="flex flex-col gap-4"
              >
                <div
                  className={`flex items-center gap-3 p-5 rounded-2xl border ${
                    reviewData?.approved
                      ? 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800/40 text-emerald-950 dark:text-emerald-200'
                      : 'bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800/40 text-amber-950 dark:text-amber-200'
                  }`}
                >
                  {reviewData?.approved ? (
                    <CheckCircle size={22} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
                  ) : (
                    <AlertTriangle size={22} className="text-amber-600 dark:text-amber-400 shrink-0" />
                  )}
                  <div>
                    <h4 className="text-sm font-bold font-['Outfit']">
                      Independent Review Assessment: {status}
                    </h4>
                    <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                      {reviewData?.summary || 'No review remarks submitted yet.'}
                    </p>
                  </div>
                </div>

                {issues.length > 0 ? (
                  <div
                    data-lenis-prevent
                    className="flex flex-col gap-2.5 max-h-[420px] overflow-y-auto"
                  >
                    {issues.map((issue, i) => (
                      <div
                        key={i}
                        className="p-4 bg-slate-50 dark:bg-[#0F1118] border border-slate-200 dark:border-white/[0.08] rounded-xl text-xs"
                      >
                        <div className="flex justify-between items-center mb-1.5">
                          <span className="font-bold text-slate-800 dark:text-slate-200">
                            {issue.title || `Issue #${i + 1}`}
                          </span>
                          <span
                            className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase ${
                              issue.severity === 'critical'
                                ? 'bg-rose-100 dark:bg-rose-900/40 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800/50'
                                : 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800/50'
                            }`}
                          >
                            {issue.severity || 'warning'}
                          </span>
                        </div>
                        <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                          {issue.description || issue}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-8 text-center text-xs text-slate-400 dark:text-slate-500 font-mono italic">
                    Zero security vulnerabilities or test regressions found in workspace.
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
