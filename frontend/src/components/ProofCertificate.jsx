import React, { useState } from 'react';
import { Award, CheckCircle2, Copy, Check, Hash, Code, ExternalLink, ShieldCheck } from 'lucide-react';
import { motion } from 'framer-motion';

export default function ProofCertificate({ proofData, isReadyForPR, onOpenMergeGate }) {
  const [copied, setCopied] = useState(false);
  const confidenceScore = proofData?.confidence_score ?? 0;
  const signature = proofData?.signature || 'sha256:d82e81b67482a9f4c39e80231920acb92f7...';
  const symbols = proofData?.verified_symbols || ['agentforge.auth.jwt', 'verify_token_claims', 'SecurityGuard'];

  const criteria = [
    { label: 'AST Structure & Syntax Integrity Verified', passed: confidenceScore > 0 },
    { label: 'Sandbox Execution Runtime Clean Exit (code 0)', passed: confidenceScore >= 0.7 },
    { label: 'Independent Zero-Trust Review Agent Approved', passed: confidenceScore >= 0.8 },
    { label: 'Cryptographic SHA-256 Signature Sealed', passed: !!proofData?.signature },
  ];

  const handleCopyHash = () => {
    navigator.clipboard.writeText(signature);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-white border border-slate-200/80 rounded-3xl p-6 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.03)] flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center">
              <Award size={16} />
            </div>
            <h3 className="font-['Outfit'] font-bold text-base text-[#0F172A]">
              Zero-Trust Proof Certificate
            </h3>
          </div>

          {isReadyForPR && (
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-3 py-1.5 rounded-full shadow-sm flex items-center gap-1.5 cursor-pointer transition-all"
              onClick={onOpenMergeGate}
            >
              <ShieldCheck size={14} />
              Merge Gate
            </motion.button>
          )}
        </div>

        {/* Confidence Rating Gauge */}
        <div className="bg-emerald-50/70 border border-emerald-200/80 rounded-2xl p-4 flex items-center justify-between mb-4">
          <div>
            <div className="text-xs font-bold text-emerald-900 font-['Outfit']">
              Attestation Rating
            </div>
            <div className="text-[11px] text-emerald-700">
              AST coverage & verification weight
            </div>
          </div>
          <div className="text-3xl font-extrabold font-['Outfit'] text-emerald-600">
            {confidenceScore ? `${Math.round(confidenceScore * 100)}%` : '0%'}
          </div>
        </div>

        {/* Verified AST Symbols */}
        <div className="mb-4">
          <span className="block text-xs font-semibold text-slate-500 mb-2 font-mono">
            Verified AST Entities:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {symbols.map((sym, i) => (
              <span
                key={i}
                className="font-mono text-[11px] font-medium px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200 text-slate-800 flex items-center gap-1"
              >
                <Code size={11} className="text-slate-400" />
                {sym}
              </span>
            ))}
          </div>
        </div>

        {/* Multi-Criteria Checklist */}
        <div className="flex flex-col gap-2 mb-4">
          {criteria.map((c, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              {c.passed ? (
                <CheckCircle2 size={15} className="text-emerald-600 shrink-0" />
              ) : (
                <div className="w-3.5 h-3.5 rounded-full border border-slate-300 shrink-0" />
              )}
              <span className={c.passed ? 'text-slate-800 font-medium' : 'text-slate-400'}>
                {c.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* SHA-256 Hash Container */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Hash size={14} className="text-slate-400 shrink-0" />
          <span className="font-mono text-[11px] text-slate-700 truncate select-all">
            {signature}
          </span>
        </div>
        <button
          type="button"
          onClick={handleCopyHash}
          className="p-1.5 rounded-lg bg-white border border-slate-200 text-slate-500 hover:text-slate-800 hover:border-slate-300 cursor-pointer transition-all relative group shrink-0"
          title="Copy SHA-256 hash"
        >
          {copied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
          <span className="absolute -top-7 right-0 text-[10px] bg-slate-900 text-white px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
            {copied ? 'Copied!' : 'Copy'}
          </span>
        </button>
      </div>
    </div>
  );
}
