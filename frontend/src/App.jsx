import React, { useEffect, useRef } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import Lenis from 'lenis';
import { AnimatePresence, motion } from 'framer-motion';
import { AgentForgeProvider, useAgentForge } from './context/AgentForgeContext';
import Navbar from './components/Navbar';
import MergeGateModal from './components/MergeGateModal';

import OverviewPage from './pages/OverviewPage';
import PipelinePage from './pages/PipelinePage';
import DiffPage from './pages/DiffPage';
import AttestationPage from './pages/AttestationPage';
import TelemetryPage from './pages/TelemetryPage';

function PageWrapper({ children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
      animate={{
        opacity: 1,
        y: 0,
        filter: 'blur(0px)',
        transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] },
      }}
      exit={{
        opacity: 0,
        y: -10,
        filter: 'blur(2px)',
        transition: { duration: 0.2, ease: [0.7, 0, 0.84, 0] },
      }}
      className="w-full"
    >
      {children}
    </motion.div>
  );
}

function MainAppLayout() {
  const location = useLocation();
  const lenisRef = useRef(null);
  const {
    isMergeGateOpen,
    setIsMergeGateOpen,
    activeTaskId,
    proofData,
    approveMerge,
    approvedPrUrl,
  } = useAgentForge();

  // Initialize Lenis Inertia Smooth Scroll
  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.1,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
    });
    lenisRef.current = lenis;
    window.lenis = lenis;

    let rafId;
    function raf(time) {
      lenis.raf(time);
      rafId = requestAnimationFrame(raf);
    }
    rafId = requestAnimationFrame(raf);

    return () => {
      cancelAnimationFrame(rafId);
      lenis.destroy();
      window.lenis = null;
    };
  }, []);

  // Lenis Scroll Synchronization on route change
  useEffect(() => {
    const timer = setTimeout(() => {
      window.lenis?.scrollTo(0, { immediate: true });
    }, 50);
    return () => clearTimeout(timer);
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex flex-col selection:bg-sky-100 selection:text-sky-900">
      {/* Floating Centered Dock Navbar */}
      <Navbar />

      {/* Viewport Router Container with AnimatePresence */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 md:px-8 py-8 flex flex-col">
        <AnimatePresence mode="wait">
          <Routes key={location.pathname} location={location}>
            <Route
              path="/"
              element={
                <PageWrapper>
                  <OverviewPage />
                </PageWrapper>
              }
            />
            <Route
              path="/pipeline"
              element={
                <PageWrapper>
                  <PipelinePage />
                </PageWrapper>
              }
            />
            <Route
              path="/diff"
              element={
                <PageWrapper>
                  <DiffPage />
                </PageWrapper>
              }
            />
            <Route
              path="/attestation"
              element={
                <PageWrapper>
                  <AttestationPage />
                </PageWrapper>
              }
            />
            <Route
              path="/telemetry"
              element={
                <PageWrapper>
                  <TelemetryPage />
                </PageWrapper>
              }
            />
          </Routes>
        </AnimatePresence>
      </main>

      {/* Global Human Merge Gate Modal Mount (z-[100]) */}
      <MergeGateModal
        isOpen={isMergeGateOpen}
        onClose={() => setIsMergeGateOpen(false)}
        taskId={activeTaskId}
        confidenceScore={proofData?.confidence_score}
        onApprove={approveMerge}
        approvedPrUrl={approvedPrUrl}
      />
    </div>
  );
}

export default function App() {
  return (
    <AgentForgeProvider>
      <MainAppLayout />
    </AgentForgeProvider>
  );
}
