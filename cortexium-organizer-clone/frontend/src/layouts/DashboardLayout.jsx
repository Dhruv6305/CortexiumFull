import React from 'react';
import { Header } from '../features/Header';
import { Footer } from '../features/Footer';
import CollapsibleNavbar from '../components/CollapsibleNavbar';

export function DashboardLayout({ children, mode, cameraStatus, modelStatus, controls }) {
  return (
    <div className="h-screen w-screen flex overflow-hidden bg-[#0b0f17] text-slate-100">
      {/* ── Shared Collapsible Left Navbar ── */}
      <CollapsibleNavbar currentModule="organizer" />

      {/* ── Main Organizer Workspace ── */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-y-auto bg-[#0b0f17]">
        <Header mode={mode} cameraStatus={cameraStatus} modelStatus={modelStatus} controls={controls}/>

        <main className="flex-1 p-4 lg:p-5 overflow-auto">
          <div className="max-w-screen-2xl mx-auto h-full">
            {children}
          </div>
        </main>

        <Footer />
      </div>
    </div>
  );
}
