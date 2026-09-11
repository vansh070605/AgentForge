import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Layers, Play, Sun, Moon } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAgentForge } from '../context/AgentForgeContext';

export default function Navbar() {
  const location = useLocation();
  const { isConnected, runDemoSimulation, isRunning, theme, setTheme } = useAgentForge();

  const navItems = [
    { path: '/', label: 'Overview' },
    { path: '/pipeline', label: 'Pipeline' },
    { path: '/diff', label: 'Code Diff' },
    { path: '/attestation', label: 'Proof Vault' },
    { path: '/telemetry', label: 'Telemetry' },
  ];

  return (
    <header className="sticky top-4 z-50 px-4 md:px-8 max-w-6xl mx-auto w-full">
      <div className="bg-white/85 dark:bg-[#0B0C10]/85 backdrop-blur-md border border-slate-200/80 dark:border-white/[0.08] shadow-[0_4px_24px_-4px_rgba(0,0,0,0.04)] dark:shadow-[0_4px_24px_-4px_rgba(0,0,0,0.5)] rounded-full px-4 py-2.5 flex items-center justify-between transition-all">
        {/* Left: Brand Lockup */}
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#0284C7] to-[#8B5CF6] flex items-center justify-center text-white shadow-sm group-hover:scale-105 transition-transform">
            <Layers size={17} className="stroke-[2.2]" />
          </div>
          <div className="hidden sm:block">
            <div className="flex items-center gap-1.5">
              <span className="text-[15px] font-bold tracking-tight text-[#0F172A] dark:text-[#F1F5F9] font-['Outfit']">
                AgentForge
              </span>
              <span className="text-[9px] font-bold font-mono px-1.5 py-0.5 rounded-full bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300 border border-violet-200/60 dark:border-violet-700/40">
                STUDIO
              </span>
            </div>
          </div>
        </Link>

        {/* Center: Tactile Route Navigation Pill */}
        <nav className="flex items-center gap-1 bg-slate-50/80 dark:bg-white/[0.04] p-1 rounded-full border border-slate-200/60 dark:border-white/[0.08]">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`relative px-3 py-1.5 rounded-full text-xs transition-colors font-['Outfit'] select-none ${
                  isActive
                    ? 'text-slate-900 dark:text-white font-semibold'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white'
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="nav-pill-active"
                    className="absolute inset-0 bg-white dark:bg-white/10 rounded-full shadow-sm border border-slate-200/60 dark:border-white/10 z-0"
                    transition={{ type: 'spring', stiffness: 450, damping: 32 }}
                  />
                )}
                <span className="relative z-10">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Right: Theme Toggle, Engine Status & Simulator Action */}
        <div className="flex items-center gap-2.5">
          {/* Segmented Tactile Theme Switcher */}
          <div className="flex items-center bg-slate-100 dark:bg-white/[0.06] p-0.5 rounded-full border border-slate-200/80 dark:border-white/[0.08]">
            <button
              onClick={() => setTheme('light')}
              className={`relative p-1.5 rounded-full text-xs transition-colors cursor-pointer ${
                theme === 'light' ? 'text-amber-600' : 'text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
              }`}
              title="Light theme"
              aria-label="Switch to light theme"
            >
              {theme === 'light' && (
                <motion.div
                  layoutId="active-theme-pill"
                  className="absolute inset-0 bg-white rounded-full shadow-xs border border-slate-200/60 z-0"
                  transition={{ type: 'spring', stiffness: 450, damping: 30 }}
                />
              )}
              <Sun size={13} className="relative z-10" />
            </button>
            <button
              onClick={() => setTheme('dark')}
              className={`relative p-1.5 rounded-full text-xs transition-colors cursor-pointer ${
                theme === 'dark' ? 'text-sky-300' : 'text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
              }`}
              title="Dark theme"
              aria-label="Switch to dark theme"
            >
              {theme === 'dark' && (
                <motion.div
                  layoutId="active-theme-pill"
                  className="absolute inset-0 bg-white/15 rounded-full shadow-xs border border-white/10 z-0"
                  transition={{ type: 'spring', stiffness: 450, damping: 30 }}
                />
              )}
              <Moon size={13} className="relative z-10" />
            </button>
          </div>

          <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-50 dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.08] text-xs font-medium text-slate-700 dark:text-slate-300">
            <span className="relative flex h-2 w-2">
              {isConnected && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              )}
              <span className={`relative inline-flex rounded-full h-2 w-2 ${isConnected ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
            </span>
            <span className="font-mono text-[10px] font-semibold text-slate-600 dark:text-slate-300">
              {isConnected ? 'ENGINE :8000' : 'OFFLINE'}
            </span>
          </div>

          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            className="bg-sky-600 hover:bg-sky-500 text-white text-xs font-medium px-3.5 py-1.5 rounded-full flex items-center gap-1.5 shadow-sm hover:shadow-sky-200 dark:hover:shadow-sky-900/30 transition-all cursor-pointer disabled:opacity-50 disabled:pointer-events-none"
            onClick={runDemoSimulation}
            disabled={isRunning}
          >
            <Play size={12} className="fill-current" />
            <span className="hidden sm:inline">Demo Simulator</span>
            <span className="sm:hidden">Demo</span>
          </motion.button>
        </div>
      </div>
    </header>
  );
}
