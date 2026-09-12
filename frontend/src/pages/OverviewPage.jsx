import React from 'react';
import { ArrowRight, Sparkles, ShieldCheck, Cpu, Code2, Layers } from 'lucide-react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAgentForge } from '../context/AgentForgeContext';
import PipelineVisualizer from '../components/PipelineVisualizer';
import TaskStudio from '../components/TaskStudio';

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.15,
      delayChildren: 0.1,
    }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring', stiffness: 300, damping: 24 }
  }
};

export default function OverviewPage() {
  const { currentStage, iteration, maxIterations, globalStatus, launchPipeline, isRunning, proofData } = useAgentForge();

  return (
    <motion.div 
      className="flex flex-col gap-10"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Editorial Hero Lockup */}
      <motion.section variants={itemVariants} className="pt-6 pb-2">
        <div className="flex flex-col gap-3 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-100/70 dark:bg-violet-900/30 text-violet-800 dark:text-violet-300 border border-violet-200 dark:border-violet-800/40 text-xs font-semibold w-fit font-mono">
            <Sparkles size={13} className="text-violet-600 dark:text-violet-400" />
            <span>Multi-Agent Software Engineering Runtime</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-[#0F172A] dark:text-[#F1F5F9] font-['Plus_Jakarta_Sans','Outfit'] leading-[1.15]">
            Accountable software generation with <span className="bg-gradient-to-r from-[#0284C7] via-[#6366F1] to-[#8B5CF6] bg-clip-text text-transparent">zero-trust attestation.</span>
          </h1>

          <p className="text-base text-slate-600 dark:text-[#94A3B8] leading-relaxed max-w-2xl font-normal">
            AgentForge orchestrates four specialized agents through a rigorous AST-verified lifecycle: from requirement contracts to sandboxed execution, adversarial code review, and SHA-256 cryptographic attestation.
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <Link
              to="/pipeline"
              className="inline-flex items-center gap-2 text-xs font-semibold text-sky-700 dark:text-sky-400 hover:text-sky-900 dark:hover:text-sky-300 group"
            >
              <span>Explore live 5-stage verification track</span>
              <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
            </Link>
            <span className="text-slate-300 dark:text-slate-700">&bull;</span>
            <Link
              to="/attestation"
              className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
            >
              <span>Zero-Trust Proof Vault</span>
            </Link>
          </div>
        </div>
      </motion.section>

      {/* Expanded Interactive Stage Track */}
      <motion.section variants={itemVariants}>
        <PipelineVisualizer
          currentStage={currentStage}
          iteration={iteration}
          maxIterations={maxIterations}
          globalStatus={globalStatus}
        />
      </motion.section>

      {/* Spacious Mission Studio */}
      <motion.section variants={itemVariants}>
        <TaskStudio
          onLaunchTask={launchPipeline}
          isRunning={isRunning}
        />
      </motion.section>

      {/* Quick Access Discipline Cards */}
      <motion.section variants={itemVariants} className="grid grid-cols-1 md:grid-cols-3 gap-5 pb-6">
        <Link
          to="/diff"
          className="bg-white dark:bg-[#12141C] border border-slate-200/80 dark:border-white/[0.08] rounded-2xl p-5 hover:border-sky-300 dark:hover:border-sky-500/40 hover:shadow-md transition-all group"
        >
          <div className="w-8 h-8 rounded-xl bg-sky-50 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300 flex items-center justify-center mb-3">
            <Code2 size={18} />
          </div>
          <h3 className="font-bold text-sm text-[#0F172A] dark:text-[#F1F5F9] font-['Outfit'] mb-1 group-hover:text-sky-700 dark:group-hover:text-sky-400 transition-colors">
            Daylight Code Diff
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            Inspect line-by-line syntax modifications and review agent feedback.
          </p>
        </Link>

        <Link
          to="/attestation"
          className="bg-white dark:bg-[#12141C] border border-slate-200/80 dark:border-white/[0.08] rounded-2xl p-5 hover:border-emerald-300 dark:hover:border-emerald-500/40 hover:shadow-md transition-all group"
        >
          <div className="w-8 h-8 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 flex items-center justify-center mb-3">
            <ShieldCheck size={18} />
          </div>
          <h3 className="font-bold text-sm text-[#0F172A] dark:text-[#F1F5F9] font-['Outfit'] mb-1 group-hover:text-emerald-700 dark:group-hover:text-emerald-400 transition-colors">
            Proof Vault ({proofData ? `${Math.round(proofData.confidence_score * 100)}%` : 'Active'})
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            View cryptographic SHA-256 state seal and verified AST symbol clouds.
          </p>
        </Link>

        <Link
          to="/telemetry"
          className="bg-white dark:bg-[#12141C] border border-slate-200/80 dark:border-white/[0.08] rounded-2xl p-5 hover:border-violet-300 dark:hover:border-violet-500/40 hover:shadow-md transition-all group"
        >
          <div className="w-8 h-8 rounded-xl bg-violet-50 dark:bg-violet-950/40 text-violet-700 dark:text-violet-300 flex items-center justify-center mb-3">
            <Cpu size={18} />
          </div>
          <h3 className="font-bold text-sm text-[#0F172A] dark:text-[#F1F5F9] font-['Outfit'] mb-1 group-hover:text-violet-700 dark:group-hover:text-violet-400 transition-colors">
            Live Telemetry Paper
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            Filter, search, and export multi-agent event logs and audit streams.
          </p>
        </Link>
      </motion.section>
    </motion.div>
  );
}
