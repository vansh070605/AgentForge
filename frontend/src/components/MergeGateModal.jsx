import React from 'react';
import { GitPullRequest, ShieldCheck, CheckCircle, X, ExternalLink } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function MergeGateModal({ isOpen, onClose, taskId, confidenceScore, onApprove, approvedPrUrl }) {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/30 dark:bg-black/60 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ type: 'spring', stiffness: 350, damping: 25 }}
          className="bg-white dark:bg-[#12141C] border border-slate-200 dark:border-white/[0.12] rounded-3xl p-7 max-w-lg w-full shadow-2xl flex flex-col gap-5 relative transition-colors"
        >
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 flex items-center justify-center">
                <GitPullRequest size={20} />
              </div>
              <div>
                <h3 className="font-['Outfit'] font-bold text-lg text-[#0F172A] dark:text-[#F1F5F9]">
                  Human Merge Gate Clearance
                </h3>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  Zero-Trust Verification Gate
                </span>
              </div>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-white/[0.08] text-slate-400 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-all cursor-pointer"
            >
              <X size={18} />
            </button>
          </div>

          {/* Modal Body */}
          {approvedPrUrl ? (
            <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/40 rounded-2xl p-5 flex flex-col gap-3">
              <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300 font-bold text-sm font-['Outfit']">
                <CheckCircle size={18} className="text-emerald-600 dark:text-emerald-400" />
                Pull Request Verified & Generated
              </div>
              <p className="text-xs text-emerald-950 dark:text-emerald-200 leading-relaxed">
                Cryptographic attestation and test verification have been formally bound to the GitHub Pull Request.
              </p>
              <a
                href={approvedPrUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 font-mono text-xs font-semibold text-sky-700 dark:text-sky-400 hover:text-sky-900 dark:hover:text-sky-300 underline"
              >
                {approvedPrUrl}
                <ExternalLink size={12} />
              </a>
            </div>
          ) : (
            <div className="flex flex-col gap-3 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              <p>
                The multi-agent pipeline has passed all verification stages with an{' '}
                <strong className="text-emerald-700 dark:text-emerald-400 font-bold">
                  {Math.round((confidenceScore || 0.96) * 100)}% Confidence Rating
                </strong>.
              </p>
              <p>
                Under AgentForge's Zero-Trust architecture, autonomous agent code cannot merge into <code className="bg-slate-100 dark:bg-white/[0.08] px-1 py-0.5 rounded text-slate-800 dark:text-slate-200 font-semibold font-mono">main</code> without explicit human engineer sign-off.
              </p>
              <div className="bg-slate-50 dark:bg-[#0F1118] border border-slate-200 dark:border-white/[0.08] rounded-xl p-3 font-mono text-[11px] text-slate-700 dark:text-slate-300">
                Target: <span className="text-sky-700 dark:text-sky-400 font-bold">agentforge/{taskId?.slice(0, 8) || 'task'}</span> &rarr; <span className="text-slate-900 dark:text-slate-100 font-bold">main</span>
              </div>
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-white/[0.06]">
            <button
              onClick={onClose}
              className="text-xs font-medium px-4 py-2 rounded-xl border border-slate-200 dark:border-white/[0.08] hover:bg-slate-50 dark:hover:bg-white/[0.04] text-slate-600 dark:text-slate-300 cursor-pointer transition-all"
            >
              {approvedPrUrl ? 'Done' : 'Dismiss'}
            </button>
            {!approvedPrUrl && (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={onApprove}
                className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-5 py-2 rounded-xl shadow-md shadow-emerald-600/20 flex items-center gap-1.5 cursor-pointer transition-all"
              >
                <ShieldCheck size={15} />
                Approve & Merge to Main
              </motion.button>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
