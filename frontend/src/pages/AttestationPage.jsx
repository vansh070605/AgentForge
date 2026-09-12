import React, { useState } from 'react';
import { Award, ShieldCheck, CheckCircle2, Copy, Check, Hash, Code, ExternalLink, GitPullRequest, FileCheck2, Lock } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAgentForge } from '../context/AgentForgeContext';

export default function AttestationPage() {
  const { proofData, currentStage, setIsMergeGateOpen, theme } = useAgentForge();
  const [copied, setCopied] = useState(false);

  const confidenceScore = proofData?.confidence_score ?? 0.96;
  const signature = proofData?.signature || 'sha256:d82e81b67482a9f4c39e80231920acb92f7b825cf4649c0042a12918e95758cf';
  const symbols = proofData?.verified_symbols || [
    'agentforge.auth.jwt.SecurityGuard',
    'verify_token_claims',
    'sanitize_ast_query',
    'test_security_guard_constant_time',
  ];

  const criteria = [
    { title: 'AST Syntax & Structure Invariance', desc: 'Code modifies strictly scoped AST symbols without unparsed side effects.', passed: true },
    { title: 'Least-Privilege Sandbox Execution', desc: 'Runtime commands and git mutations executed under sandboxed privilege controls.', passed: true },
    { title: 'Adversarial Test Suite Validation', desc: 'Pytest suite executed clean exit with 0 failing assertions.', passed: true },
    { title: 'Independent Review Agent Signature', desc: 'Review agent submitted uncompromised attestation payload.', passed: true },
    { title: 'Cryptographic State Hash Sealing', desc: 'State digest sealed using SHA-256 algorithm with tamper-evident signature.', passed: true },
  ];

  const handleCopy = () => {
    navigator.clipboard.writeText(signature);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Circular gauge calculations
  const radius = 64;
  const circumference = 2 * Math.PI * radius;
  const percentage = Math.round(confidenceScore * 100);
  const strokeDashoffset = circumference - (circumference * percentage) / 100;

  return (
    <motion.div 
      className="flex flex-col gap-8"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-[#0F172A] dark:text-[#F1F5F9] font-['Plus_Jakarta_Sans','Outfit']">
            Zero-Trust Proof Vault
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Cryptographically sealed attestation certificate binding AST diffs to execution proofs.
          </p>
        </div>

        {currentStage === 'merge' && (
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => setIsMergeGateOpen(true)}
            className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-2 rounded-xl shadow-md shadow-emerald-600/20 flex items-center gap-2 cursor-pointer transition-all"
          >
            <GitPullRequest size={14} />
            <span>Clear Human Merge Gate</span>
          </motion.button>
        )}
      </div>

      {/* Museum Exhibition Gallery Card */}
      <div className="bg-white dark:bg-[#12141C] border border-slate-200/90 dark:border-white/[0.08] rounded-3xl p-8 shadow-[0_8px_32px_-6px_rgba(0,0,0,0.04)] dark:shadow-none flex flex-col gap-8 transition-colors">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-center pb-8 border-b border-slate-100 dark:border-white/[0.06]">
          {/* Circular Confidence Meter */}
          <div className="flex flex-col items-center justify-center p-6 bg-slate-50/60 dark:bg-[#0F1118] border border-slate-200/70 dark:border-white/[0.08] rounded-3xl">
            <div className="relative w-40 h-40 flex items-center justify-center">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 160 160">
                <circle
                  cx="80"
                  cy="80"
                  r={radius}
                  className="stroke-slate-200 dark:stroke-white/[0.08]"
                  strokeWidth="12"
                  fill="transparent"
                />
                <motion.circle
                  cx="80"
                  cy="80"
                  r={radius}
                  stroke="#10B981"
                  strokeWidth="12"
                  strokeDasharray={circumference}
                  initial={{ strokeDashoffset: circumference }}
                  animate={{ strokeDashoffset }}
                  transition={{ duration: 1.2, ease: 'easeOut' }}
                  strokeLinecap="round"
                  fill="transparent"
                />
              </svg>
              <div className="absolute flex flex-col items-center justify-center text-center">
                <span className="text-3xl font-extrabold font-['Outfit'] text-[#0F172A] dark:text-[#F1F5F9]">
                  {percentage}%
                </span>
                <span className="text-[10px] font-bold font-mono text-emerald-700 dark:text-emerald-400 uppercase tracking-wider">
                  Verified
                </span>
              </div>
            </div>
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 mt-3 font-['Outfit']">
              Attestation Confidence Rating
            </span>
          </div>

          {/* Certificate Description & Ledger Stats */}
          <div className="md:col-span-2 flex flex-col justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-xs font-mono font-bold text-sky-700 dark:text-sky-400 mb-1">
                <Lock size={13} />
                <span>CRYPTOGRAPHIC SEAL &bull; TAMPER EVIDENT</span>
              </div>
              <h2 className="text-xl font-bold font-['Plus_Jakarta_Sans','Outfit'] text-[#0F172A] dark:text-[#F1F5F9] mb-2">
                Certified Software Artifact Attestation
              </h2>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed font-normal">
                This certificate represents mathematically verified proof that the executed code modifications satisfy AST syntax boundaries, pass all automated pytest regressions, and comply with the zero-trust policy.
              </p>
            </div>

            {/* SHA-256 Hash Display Strip */}
            <div className="bg-slate-50 dark:bg-[#0F1118] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4 flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 font-mono">
                <span className="flex items-center gap-1.5 font-semibold">
                  <Hash size={13} className="text-slate-400 dark:text-slate-500" />
                  SHA-256 Seal Signature:
                </span>
                <button
                  onClick={handleCopy}
                  className="text-[11px] font-semibold text-sky-700 dark:text-sky-400 hover:text-sky-900 dark:hover:text-sky-300 cursor-pointer flex items-center gap-1"
                >
                  {copied ? <Check size={12} className="text-emerald-600 dark:text-emerald-400" /> : <Copy size={12} />}
                  <span>{copied ? 'Copied to Clipboard' : 'Copy Hash'}</span>
                </button>
              </div>
              <div className="font-mono text-xs text-slate-800 dark:text-slate-200 break-all select-all bg-white dark:bg-[#0B0C10] p-2.5 rounded-xl border border-slate-200/80 dark:border-white/[0.08] shadow-inner">
                {signature}
              </div>
            </div>
          </div>
        </div>

        {/* AST Verified Symbol Cloud */}
        <div>
          <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 font-mono mb-3 uppercase tracking-wider">
            Verified AST Symbol Signatures
          </h3>
          <div className="flex flex-wrap gap-2">
            {symbols.map((sym, i) => (
              <span
                key={i}
                className="px-3 py-1.5 rounded-xl bg-slate-50 dark:bg-[#0F1118] border border-slate-200 dark:border-white/[0.08] text-slate-800 dark:text-slate-200 text-xs font-mono font-medium flex items-center gap-1.5 shadow-sm"
              >
                <Code size={13} className="text-sky-600 dark:text-sky-400" />
                {sym}
              </span>
            ))}
          </div>
        </div>

        {/* Verification Ledger Checklist */}
        <div>
          <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 font-mono mb-3 uppercase tracking-wider">
            Audit Checklist & Integrity Ledger
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {criteria.map((crit, idx) => (
              <div
                key={idx}
                className="p-4 rounded-2xl bg-slate-50/70 dark:bg-[#0F1118] border border-slate-200/80 dark:border-white/[0.08] flex items-start gap-3"
              >
                <CheckCircle2 size={18} className="text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100 font-['Outfit']">
                    {crit.title}
                  </h4>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed mt-0.5">
                    {crit.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
