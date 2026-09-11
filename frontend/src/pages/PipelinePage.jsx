import React, { useState } from 'react';
import { FileCode2, Terminal, ShieldCheck, Award, GitPullRequest, Check, Loader2, AlertTriangle, Clock, ChevronRight, FileText, Code, CheckCircle2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAgentForge } from '../context/AgentForgeContext';

export default function PipelinePage() {
  const { currentStage, iteration, maxIterations, globalStatus, proofData, reviewData, diffText, setIsMergeGateOpen } = useAgentForge();
  const [selectedStage, setSelectedStage] = useState('identity');

  const stages = [
    {
      id: 'identity',
      index: '01',
      title: 'Identity Agent',
      discipline: 'SPECIFY',
      tagline: 'AST Context Extraction & Requirement Contracts',
      wash: 'bg-violet-50/70 dark:bg-violet-950/20 border-violet-200 dark:border-violet-900/40 text-violet-950 dark:text-violet-200',
      icon: FileCode2,
      input: 'User prompt, repository workspace tree, target git ref.',
      output: 'TaskSpecification schema, scope boundary definitions, allowed tools whitelist.',
      astEntities: ['agentforge.agents.identity', 'TaskSpecification', 'ScopeContract'],
      statusDescription: 'Parses codebase symbol graphs to guarantee only explicitly scoped entities are modified.',
    },
    {
      id: 'execution',
      index: '02',
      title: 'Execution Agent',
      discipline: 'EXECUTE',
      tagline: 'Controlled Tool Invocation & Workspace Diff Generation',
      wash: 'bg-amber-50/70 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900/40 text-amber-950 dark:text-amber-200',
      icon: Terminal,
      input: 'TaskSpecification, filesystem sandbox, git branch manager.',
      output: 'Unified git diff, execution exit code 0, tool telemetry log.',
      astEntities: ['agentforge.tools.filesystem', 'agentforge.tools.git', 'WorkspaceManager'],
      statusDescription: 'Runs with least-privilege security restrictions, capturing all modifications as discrete diff blocks.',
    },
    {
      id: 'review',
      index: '03',
      title: 'Review Agent',
      discipline: 'INSPECT',
      tagline: 'Zero-Trust Verification & Adversarial AST Analysis',
      wash: 'bg-rose-50/70 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900/40 text-rose-950 dark:text-rose-200',
      icon: ShieldCheck,
      input: 'Execution diff, automated pytest suite results, AST static rules.',
      output: 'CodeReviewReport (approved: true/false, findings: list[Issue]).',
      astEntities: ['agentforge.agents.review', 'CodeReviewReport', 'PolicyValidator'],
      statusDescription: 'Independently executes test suites and checks for security regressions without trusting author state.',
    },
    {
      id: 'proof',
      index: '04',
      title: 'Proof-of-Work Agent',
      discipline: 'ATTEST',
      tagline: 'Cryptographic SHA-256 Attestation & Confidence Scoring',
      wash: 'bg-sky-50/70 dark:bg-sky-950/20 border-sky-200 dark:border-sky-900/40 text-sky-950 dark:text-sky-200',
      icon: Award,
      input: 'Specification hash, review report signature, AST diff seal.',
      output: 'ProofOfWorkCertificate (SHA-256 hash, confidence score: float).',
      astEntities: ['agentforge.agents.proof', 'ProofCertificate', 'Sha256Sealer'],
      statusDescription: 'Binds execution telemetry into an unforgeable cryptographic state seal verifying the solution.',
    },
    {
      id: 'merge',
      index: '05',
      title: 'Human Merge Gate',
      discipline: 'GATE',
      tagline: 'Mandatory Human Engineer Sign-Off & PR Clearance',
      wash: 'bg-emerald-50/70 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900/40 text-emerald-950 dark:text-emerald-200',
      icon: GitPullRequest,
      input: 'Verified diff, cryptographic proof of work certificate.',
      output: 'Authorized GitHub Pull Request bound to main branch.',
      astEntities: ['agentforge.api.MergeGate', 'GitHubIntegration'],
      statusDescription: 'Strict zero-trust threshold: code cannot merge autonomously without human clearance.',
    },
  ];

  const getStageStatus = (stageId, index) => {
    const stageOrder = ['identity', 'execution', 'review', 'proof', 'merge'];
    const currentIndex = stageOrder.indexOf(currentStage);

    if (currentStage === 'completed') return { label: 'Done', color: 'text-emerald-700 dark:text-emerald-300 bg-emerald-100 dark:bg-emerald-900/40', icon: Check };
    if (currentStage === 'failed') {
      if (index === currentIndex) return { label: 'Failed', color: 'text-rose-700 dark:text-rose-300 bg-rose-100 dark:bg-rose-900/40', icon: AlertTriangle };
      if (index < currentIndex) return { label: 'Done', color: 'text-emerald-700 dark:text-emerald-300 bg-emerald-100 dark:bg-emerald-900/40', icon: Check };
      return { label: 'Queued', color: 'text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-white/[0.06]', icon: Clock };
    }
    if (index < currentIndex) return { label: 'Passed', color: 'text-emerald-700 dark:text-emerald-300 bg-emerald-100 dark:bg-emerald-900/40', icon: Check };
    if (index === currentIndex) return { label: 'Active', color: 'text-sky-700 dark:text-sky-300 bg-sky-100 dark:bg-sky-900/40 font-semibold', icon: Loader2 };
    return { label: 'Idle', color: 'text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-white/[0.06]', icon: Clock };
  };

  const currentStageObj = stages.find((s) => s.id === selectedStage) || stages[0];

  return (
    <div className="flex flex-col gap-8">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-[#0F172A] dark:text-[#F1F5F9] font-['Plus_Jakarta_Sans','Outfit']">
            Verification Pipeline Studio
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Real-time inspection of the 5-stage zero-trust engineering lifecycle.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-mono font-semibold px-3 py-1 rounded-full bg-slate-100 dark:bg-white/[0.06] border border-slate-200 dark:border-white/[0.08] text-slate-700 dark:text-slate-300">
            Cycle {iteration} of {maxIterations}
          </span>
          <span className="text-xs font-mono px-3 py-1 rounded-full bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800/50 text-sky-700 dark:text-sky-300 font-semibold">
            {globalStatus}
          </span>
        </div>
      </div>

      {/* 5 Stage Horizontal Selector */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
        {stages.map((stage, idx) => {
          const { label, color, icon: StatusIcon } = getStageStatus(stage.id, idx);
          const Icon = stage.icon;
          const isSelected = selectedStage === stage.id;
          const isCurrentlyRunning = currentStage === stage.id;

          return (
            <button
              key={stage.id}
              onClick={() => setSelectedStage(stage.id)}
              className={`relative text-left p-4 rounded-2xl border transition-all cursor-pointer overflow-hidden ${
                isSelected
                  ? 'bg-white dark:bg-[#161924] border-slate-300 dark:border-white/20 shadow-md ring-2 ring-sky-500/30'
                  : 'bg-white/60 dark:bg-[#12141C]/60 border-slate-200/80 dark:border-white/[0.08] hover:bg-white dark:hover:bg-[#12141C] hover:border-slate-300 dark:hover:border-white/20'
              }`}
            >
              {/* Oversized Typographic Index */}
              <span className="absolute -right-2 -bottom-4 text-5xl font-extrabold text-slate-100 dark:text-white/[0.03] font-['Outfit'] select-none pointer-events-none">
                {stage.index}
              </span>

              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono font-bold text-slate-400 dark:text-slate-500">
                  {stage.discipline}
                </span>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full flex items-center gap-1 ${color}`}>
                  <StatusIcon size={10} className={isCurrentlyRunning ? 'animate-spin' : ''} />
                  {label}
                </span>
              </div>

              <div className="flex items-center gap-2 mb-1">
                <div className="w-6 h-6 rounded-lg bg-slate-100 dark:bg-white/[0.08] flex items-center justify-center text-slate-700 dark:text-slate-300">
                  <Icon size={14} />
                </div>
                <h4 className="font-['Outfit'] font-bold text-xs text-[#0F172A] dark:text-[#F1F5F9] truncate">
                  {stage.title}
                </h4>
              </div>
            </button>
          );
        })}
      </div>

      {/* Cinematic Stage Artifact & State Inspector */}
      <motion.div
        key={currentStageObj.id}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="bg-white dark:bg-[#12141C] border border-slate-200 dark:border-white/[0.08] rounded-3xl p-8 shadow-[0_8px_30px_-6px_rgba(0,0,0,0.04)] dark:shadow-none relative overflow-hidden transition-colors"
      >
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6 pb-6 border-b border-slate-100 dark:border-white/[0.06]">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-slate-100 dark:bg-white/[0.06] flex items-center justify-center text-slate-800 dark:text-slate-200 shadow-inner">
              <currentStageObj.icon size={24} />
            </div>
            <div>
              <div className="text-xs font-mono font-bold text-sky-700 dark:text-sky-400 uppercase tracking-wider">
                Stage {currentStageObj.index} &bull; {currentStageObj.discipline}
              </div>
              <h2 className="text-2xl font-bold text-[#0F172A] dark:text-[#F1F5F9] font-['Plus_Jakarta_Sans','Outfit']">
                {currentStageObj.title}
              </h2>
            </div>
          </div>

          {currentStageObj.id === 'merge' && currentStage === 'merge' && (
            <button
              onClick={() => setIsMergeGateOpen(true)}
              className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-2 rounded-xl shadow-sm cursor-pointer transition-all flex items-center gap-1.5"
            >
              <GitPullRequest size={14} />
              Open Clearance Modal
            </button>
          )}
        </div>

        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed mb-6 font-normal">
          {currentStageObj.statusDescription}
        </p>

        {/* Input/Output Artifact Contract Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-6">
          <div className="bg-slate-50/70 dark:bg-[#0F1118] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-5">
            <div className="text-xs font-mono font-bold text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">
              Input Invariants & Context
            </div>
            <p className="text-xs text-slate-800 dark:text-slate-200 font-mono leading-relaxed">
              {currentStageObj.input}
            </p>
          </div>

          <div className="bg-slate-50/70 dark:bg-[#0F1118] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-5">
            <div className="text-xs font-mono font-bold text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">
              Generated Attestation Artifacts
            </div>
            <p className="text-xs text-slate-800 dark:text-slate-200 font-mono leading-relaxed">
              {currentStageObj.output}
            </p>
          </div>
        </div>

        {/* Bound AST Entities */}
        <div>
          <span className="block text-xs font-mono font-semibold text-slate-500 dark:text-slate-400 mb-2">
            Target AST Entities & Classes:
          </span>
          <div className="flex flex-wrap gap-2">
            {currentStageObj.astEntities.map((ent, i) => (
              <span
                key={i}
                className="font-mono text-xs px-3 py-1 rounded-lg bg-slate-100 dark:bg-white/[0.06] border border-slate-200 dark:border-white/[0.08] text-slate-800 dark:text-slate-200 flex items-center gap-1.5"
              >
                <Code size={12} className="text-slate-400 dark:text-slate-500" />
                {ent}
              </span>
            ))}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
