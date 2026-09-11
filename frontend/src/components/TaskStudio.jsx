import React, { useState } from 'react';
import { Send, Sparkles, RefreshCw, Sliders } from 'lucide-react';
import { motion } from 'framer-motion';

const PRESETS = [
  {
    label: 'JWT Auth Guard',
    color: 'hover:bg-sky-50 dark:hover:bg-sky-950/30 hover:border-sky-300 dark:hover:border-sky-700/50 hover:text-sky-700 dark:hover:text-sky-300',
    prompt: 'Implement a zero-trust JWT authentication dependency for protected API routes, verifying tokens and extracting claims.',
  },
  {
    label: 'Health & Metrics Route',
    color: 'hover:bg-emerald-50 dark:hover:bg-emerald-950/30 hover:border-emerald-300 dark:hover:border-emerald-700/50 hover:text-emerald-700 dark:hover:text-emerald-300',
    prompt: 'Add a /health and /metrics endpoint to the FastAPI app reporting uptime, memory usage, and git branch status.',
  },
  {
    label: 'AST Input Sanitizer',
    color: 'hover:bg-violet-50 dark:hover:bg-violet-950/30 hover:border-violet-300 dark:hover:border-violet-700/50 hover:text-violet-700 dark:hover:text-violet-300',
    prompt: 'Create an AST-based input sanitizer utility in agentforge/tools to detect and neutralize command injection patterns.',
  },
];

export default function TaskStudio({ onLaunchTask, isRunning }) {
  const [prompt, setPrompt] = useState(PRESETS[0].prompt);
  const [maxIterations, setMaxIterations] = useState(2);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!prompt.trim() || isRunning) return;
    onLaunchTask({ user_prompt: prompt, max_iterations: maxIterations });
  };

  return (
    <div className="bg-white dark:bg-[#12141C] border border-slate-200/80 dark:border-white/[0.08] rounded-3xl p-6 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] dark:shadow-none transition-colors flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-sky-100 dark:bg-sky-900/40 text-sky-700 dark:text-sky-300 flex items-center justify-center">
              <Sparkles size={16} />
            </div>
            <h3 className="font-['Outfit'] font-bold text-base text-[#0F172A] dark:text-[#F1F5F9]">
              Task Mission Studio
            </h3>
          </div>
          <span className="text-xs text-slate-400 dark:text-slate-500 font-mono">AST Directed</span>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1.5 uppercase tracking-wider font-mono">
              Engineering Directive / Prompt
            </label>
            <textarea
              className="w-full min-h-[120px] text-slate-900 dark:text-slate-100 bg-slate-50/70 dark:bg-[#0F1118] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4 font-mono text-xs leading-relaxed focus:bg-white dark:focus:bg-[#0B0C10] focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 outline-none transition-all resize-none"
              placeholder="Describe your engineering requirement, bugfix, or refactor objective..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={isRunning}
            />
          </div>

          <div>
            <span className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2 font-mono">
              Quick Presets:
            </span>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  className={`text-xs px-3 py-1.5 rounded-full border border-slate-200 dark:border-white/[0.08] bg-slate-50 dark:bg-[#0F1118] text-slate-700 dark:text-slate-300 transition-all cursor-pointer font-medium ${p.color}`}
                  onClick={() => setPrompt(p.prompt)}
                  disabled={isRunning}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100 dark:border-white/[0.06]">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-400">
              <Sliders size={14} className="text-slate-400" />
              <span>Feedback Cycles:</span>
              <select
                className="bg-slate-50 dark:bg-[#0F1118] border border-slate-200 dark:border-white/[0.08] rounded-lg px-2.5 py-1 text-xs font-mono font-semibold text-slate-800 dark:text-slate-200 outline-none focus:border-sky-500"
                value={maxIterations}
                onChange={(e) => setMaxIterations(Number(e.target.value))}
                disabled={isRunning}
              >
                <option value={1}>1 (Fast)</option>
                <option value={2}>2 (Standard - Recommend)</option>
                <option value={3}>3 (Thorough)</option>
              </select>
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="submit"
              className="bg-gradient-to-r from-sky-600 via-indigo-600 to-violet-600 hover:opacity-95 text-white text-xs font-semibold px-5 py-2.5 rounded-xl shadow-md shadow-sky-600/20 flex items-center gap-2 cursor-pointer transition-all disabled:opacity-50 disabled:pointer-events-none"
              disabled={isRunning || !prompt.trim()}
            >
              {isRunning ? (
                <>
                  <RefreshCw size={14} className="animate-spin" />
                  <span>Pipeline Dispatching...</span>
                </>
              ) : (
                <>
                  <Send size={14} />
                  <span>Launch Multi-Agent Pipeline</span>
                </>
              )}
            </motion.button>
          </div>
        </form>
      </div>
    </div>
  );
}
