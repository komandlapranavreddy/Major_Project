import type { ReactNode } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence, MotionConfig, motion } from 'framer-motion';
import { LandingPage } from './pages/LandingPage';
import { AppPage } from './pages/AppPage';
import { HistoryPage } from './pages/HistoryPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { ResearchPage } from './pages/ResearchPage';

// Opacity only: a transform or filter here would re-anchor the landing
// page's position:fixed navbar to this wrapper.
function PageFade({ children }: { children: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1, transition: { duration: 0.3, ease: 'easeOut' } }}
      exit={{ opacity: 0, transition: { duration: 0.15, ease: 'easeIn' } }}
    >
      {children}
    </motion.div>
  );
}

function App() {
  const location = useLocation();

  return (
    <MotionConfig reducedMotion="user">
      <AnimatePresence mode="wait" initial={false}>
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<PageFade><LandingPage /></PageFade>} />
          <Route path="/app" element={<PageFade><AppPage /></PageFade>} />
          <Route path="/history" element={<PageFade><HistoryPage /></PageFade>} />
          <Route path="/analytics" element={<PageFade><AnalyticsPage /></PageFade>} />
          <Route path="/research" element={<PageFade><ResearchPage /></PageFade>} />
        </Routes>
      </AnimatePresence>
    </MotionConfig>
  );
}

export default App;
