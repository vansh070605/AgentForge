import React from 'react';
import { FileCode2, Terminal, ShieldCheck, Award, GitPullRequest, Check, Loader2, AlertTriangle, Clock } from 'lucide-react';
import { motion } from 'framer-motion';

export default function PipelineVisualizer({ currentStage, iteration, maxIterations, globalStatus }) {
  const steps = [
    {
      id: 'identity',
      step: '01. SPECIFY',
      title: 'Identity Agent',
      desc: 'AST symbol & context parsing',
      icon: FileCode2,
      wash: 'bg-violet-50/70 dark:bg-violet-950/20 border-violet-200 dark:border-violet-900/40 text-violet-950 dark:text-violet-200',
      activeRing: 'ring-2 ring-violet-500 shadow-[0_12px_32px_-8px_rgba(139,92,246,0.22)]',
      iconBg: 'bg-violet-100 dark:bg-violet-900/50 text-violet-700 dark:text-violet-300',
    },
    {
      id: 'execution',
      step: '02. EXECUTE',
      title: 'Execution Agent',
      desc: 'Scoped runtime & diff generator',
      icon: Terminal,
      wash: 'bg-amber-50/70 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900/40 text-amber-950 dark:text-amber-200',
      activeRing: 'ring-2 ring-amber-500 shadow-[0_12px_32px_-8px_rgba(245,158,11,0.22)]',
      iconBg: 'bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300',
    },
    {
      id: 'review',
      step: '03. INSPECT',
      title: 'Review Agent',
      desc: 'Static analysis & test verification',
      icon: ShieldCheck,
      wash: 'bg-rose-50/70 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900/40 text-rose-950 dark:text-rose-200',
      activeRing: 'ring-2 ring-rose-500 shadow-[0_12px_32px_-8px_rgba(251,113,133,0.22)]',
      iconBg: 'bg-rose-100 dark:bg-rose-900/50 text-rose-700 dark:text-rose-300',
    },
    {
      id: 'proof',
      step: '04. ATTEST',
      title: 'Proof-of-Work',
      desc: 'Cryptographic SHA-256 certificate',
      icon: Award,
      wash: 'bg-sky-50/70 dark:bg-sky-950/20 border-sky-200 dark:border-sky-900/40 text-sky-950 dark:text-sky-200',
      activeRing: 'ring-2 ring-sky-500 shadow-[0_12px_32px_-8px_rgba(2,132,199,0.22)]',
      iconBg: 'bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300',
    },
    {
      id: 'merge',
      step: '05. GATE',
      title: 'Human Gate',
      desc: 'Mandatory engineer clearance',
      icon: GitPullRequest,
      wash: 'bg-emerald-50/70 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900/40 text-emerald-950 dark:text-emerald-200',
      activeRing: 'ring-2 ring-emerald-500 shadow-[0_12px_32px_-8px_rgba(16,185,129,0.22)]',
      iconBg: 'bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300',
    },
  ];

  const getStepStatus = (stepId, index) => {
    const stageOrder = ['identity', 'execution', 'review', 'proof', 'merge'];
    const currentIndex = stageOrder.indexOf(currentStage);

    if (currentStage === 'completed') {
      return { status: 'completed', label: 'Done', badgeClass: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/50', icon: Check };
    }
    if (currentStage === 'failed') {
      if (index === currentIndex) return { status: 'failed', label: 'Failed', badgeClass: 'bg-rose-100 dark:bg-rose-900/40 text-rose-800 dark:text-rose-300 border-rose-200 dark:border-rose-800/50', icon: AlertTriangle };
      if (index < currentIndex) return { status: 'completed', label: 'Done', badgeClass: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/50', icon: Check };
      return { status: 'idle', label: 'Queued', badgeClass: 'bg-slate-100 dark:bg-white/[0.06] text-slate-500 dark:text-slate-400 border-slate-200 dark:border-white/[0.08]', icon: Clock };
    }
    if (index < currentIndex) {
      return { status: 'completed', label: 'Passed', badgeClass: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/50', icon: Check };
    }
    if (index === currentIndex) {
      return { status: 'active', label: 'Active', badgeClass: 'bg-sky-100 dark:bg-sky-900/40 text-sky-800 dark:text-sky-300 border-sky-300 dark:border-sky-700/50 font-semibold', icon: Loader2 };
    }
    return { status: 'idle', label: 'Idle', badgeClass: 'bg-slate-100 dark:bg-white/[0.06] text-slate-500 dark:text-slate-400 border-slate-200 dark:border-white/[0.08]', icon: Clock };
  };

  return (
    <section className="bg-white dark:bg-[#12141C] border border-slate-200/80 dark:border-white/[0.08] rounded-3xl p-6 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] dark:shadow-none transition-colors">
      {/* Section Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-[#0F172A] dark:text-[#F1F5F9] font-['Outfit']">
            Multi-Agent Verification Pipeline
          </h2>
          <span className="text-xs font-mono font-semibold px-2.5 py-1 rounded-full bg-slate-100 dark:bg-white/[0.06] text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-white/[0.08]">
            Iteration {iteration} of {maxIterations}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-400 dark:text-slate-500">Current Phase:</span>
          <span className="font-semibold text-slate-800 dark:text-slate-200 bg-slate-50 dark:bg-[#0B0C10] px-2.5 py-1 rounded-md border border-slate-200 dark:border-white/[0.08]">
            {globalStatus}
          </span>
        </div>
      </div>

      {/* Responsive Horizontal Snap-Track / 5-Column Grid */}
      <div className="flex overflow-x-auto snap-x snap-mandatory gap-4 pb-3 scrollbar-none xl:grid xl:grid-cols-5 xl:pb-0">
        {steps.map((step, idx) => {
          const { status, label, badgeClass, icon: StatusIcon } = getStepStatus(step.id, idx);
          const IconComponent = step.icon;
          const isActive = status === 'active';

          return (
            <motion.div
              key={step.id}
              layout
              transition={{ type: 'spring', stiffness: 300, damping: 25 }}
              className={`relative min-w-[220px] xl:min-w-0 snap-start rounded-2xl p-5 border transition-all duration-300 flex flex-col justify-between ${step.wash} ${isActive ? `${step.activeRing} scale-[1.02] bg-white dark:bg-[#161924]` : 'hover:border-slate-300 dark:hover:border-white/20'}`}
            >
              {isActive && (
                <motion.div
                  layoutId="active-stage-indicator"
                  className="absolute inset-0 rounded-2xl border-2 border-[#0284C7] pointer-events-none"
                  transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                />
              )}

              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="font-mono text-[11px] font-bold tracking-wider opacity-60">
                    {step.step}
                  </span>
                  <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${step.iconBg} shadow-sm`}>
                    <IconComponent size={16} />
                  </div>
                </div>

                <h3 className="font-['Outfit'] font-bold text-sm text-[#0F172A] dark:text-[#F1F5F9] mb-1">
                  {step.title}
                </h3>
                <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed mb-4">
                  {step.desc}
                </p>
              </div>

              <div className="pt-2 border-t border-black/5 dark:border-white/[0.06] flex items-center justify-between">
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] border ${badgeClass}`}>
                  <StatusIcon size={12} className={isActive ? 'animate-spin' : ''} />
                  <span>{label}</span>
                </span>
              </div>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
