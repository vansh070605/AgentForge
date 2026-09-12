import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Layers, Play, Sun, Moon, Menu, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAgentForge } from '../context/AgentForgeContext';

export default function Navbar() {
  const location = useLocation();
  const { isConnected, runDemoSimulation, isRunning, theme, setTheme } = useAgentForge();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const navItems = [
    { path: '/', label: 'Overview' },
    { path: '/pipeline', label: 'Pipeline' },
    { path: '/diff', label: 'Code Diff' },
    { path: '/attestation', label: 'Proof Vault' },
    { path: '/telemetry', label: 'Telemetry' },
  ];

  const closeMenu = () => setIsMobileMenuOpen(false);

  return (
    <>
      <header className="sticky top-4 z-50 px-4 md:px-8 max-w-6xl mx-auto w-full">
        <div className="bg-white/85 dark:bg-[#0B0C10]/85 backdrop-blur-md border border-slate-200/80 dark:border-white/[0.08] shadow-[0_4px_24px_-4px_rgba(0,0,0,0.04)] dark:shadow-[0_4px_24px_-4px_rgba(0,0,0,0.5)] rounded-full px-4 py-2.5 flex items-center justify-between transition-all">
          {/* Left: Brand Lockup */}
          <Link to="/" className="flex items-center gap-2.5 group" onClick={closeMenu}>
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

          {/* Center: Tactile Route Navigation Pill (Desktop Only) */}
          <nav className="hidden md:flex items-center gap-1 bg-slate-50/80 dark:bg-white/[0.04] p-1 rounded-full border border-slate-200/60 dark:border-white/[0.08]">
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

          {/* Right: Actions and Mobile Menu Toggle */}
          <div className="flex items-center gap-2.5">
            {/* Segmented Tactile Theme Switcher */}
            <div className="flex items-center bg-slate-100 dark:bg-white/[0.06] p-0.5 rounded-full border border-slate-200/80 dark:border-white/[0.08]">
              <button
                onClick={() => setTheme('light')}
                className={`relative p-1.5 rounded-full text-xs transition-colors cursor-pointer ${
                  theme === 'light' ? 'text-amber-600' : 'text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                }`}
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

            <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-50 dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.08] text-xs font-medium text-slate-700 dark:text-slate-300">
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
              className="hidden sm:flex bg-sky-600 hover:bg-sky-500 text-white text-xs font-medium px-3.5 py-1.5 rounded-full items-center gap-1.5 shadow-sm hover:shadow-sky-200 dark:hover:shadow-sky-900/30 transition-all cursor-pointer disabled:opacity-50 disabled:pointer-events-none"
              onClick={runDemoSimulation}
              disabled={isRunning}
            >
              <Play size={12} className="fill-current" />
              <span>Demo</span>
            </motion.button>

          </div>
        </div>
      </header>

      {/* Floating Action Button (FAB) for Mobile Menu */}
      <div className="md:hidden fixed bottom-6 right-6 z-50">
        <button
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          className="relative group w-14 h-14 flex items-center justify-center rounded-full bg-gradient-to-br from-[#0284C7] to-[#8B5CF6] text-white shadow-[0_8px_32px_-8px_rgba(139,92,246,0.5)] transition-all hover:scale-105 active:scale-95"
          style={{
            /* Optional Honeycomb subtle pattern */
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='20' height='28' viewBox='0 0 20 28' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 14l5-8.66 10 0L20 14l-5 8.66-10 0z' fill='%23ffffff' fill-opacity='0.05' fill-rule='evenodd'/%3E%3C/svg%3E"), linear-gradient(to bottom right, #0284C7, #8B5CF6)`
          }}
        >
          <div className="absolute inset-0 rounded-full border border-white/20"></div>
          {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile Menu Dropdown */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95, transformOrigin: 'bottom right' }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="md:hidden fixed bottom-24 right-6 w-64 z-40 bg-white/95 dark:bg-[#0B0C10]/95 backdrop-blur-xl border border-slate-200 dark:border-white/[0.08] shadow-2xl rounded-2xl overflow-hidden"
          >
            <div className="flex flex-col p-2">
              {navItems.map((item) => {
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={closeMenu}
                    className={`px-4 py-3 rounded-xl text-sm font-['Outfit'] transition-colors ${
                      isActive 
                        ? 'bg-sky-50 dark:bg-sky-900/20 text-sky-700 dark:text-sky-300 font-semibold' 
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-white/5'
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
              
              <div className="mt-2 pt-2 border-t border-slate-100 dark:border-white/[0.06] px-2 flex justify-between items-center pb-2">
                <div className="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-300">
                  <span className={`inline-flex rounded-full h-2 w-2 ${isConnected ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
                  <span>{isConnected ? 'Online' : 'Offline'}</span>
                </div>
                <button
                  className="bg-sky-600 hover:bg-sky-500 text-white text-xs font-medium px-4 py-2 rounded-xl flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  onClick={() => { runDemoSimulation(); closeMenu(); }}
                  disabled={isRunning}
                >
                  <Play size={12} className="fill-current" />
                  Run Demo
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
