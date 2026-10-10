import React from 'react';
import { Header } from '../features/Header';
import { Footer } from '../features/Footer';

export function DashboardLayout({ children, mode, cameraStatus, modelStatus, controls }) {
  return (
    <div className="min-h-screen flex flex-col relative" 
      style={{ background: `
        radial-gradient(circle at 18% 0%, rgba(255,145,77,0.14), transparent 28%), 
        radial-gradient(circle at 85% 8%, rgba(255,255,255,0.05), transparent 22%), 
        linear-gradient(180deg,#18181b,#121316 45%,#0d0e11)`}} >
      {/* Ambient glow — very subtle, warm */}
      <div className="fixed -top-32 left-1/4 w-[700px] h-[700px] rounded-full pointer-events-none"
      style={{
      background:'radial-gradient(circle, rgba(255,140,60,.12), transparent 70%)',
      filter:'blur(120px)'
      }}/>
      <div className="fixed bottom-[-180px] right-[-120px] w-[600px] h-[600px] rounded-full pointer-events-none"
      style={{
      background:'radial-gradient(circle, rgba(255,255,255,.05), transparent 70%)',
      filter:'blur(130px)'
      }}/>

      <Header mode={mode} cameraStatus={cameraStatus} modelStatus={modelStatus} controls={controls}/>

      <main className="flex-1 p-4 lg:p-5 overflow-auto">
        <div className="max-w-screen-2xl mx-auto h-full">
          {children}
        </div>
      </main>

      <Footer />
    </div>
  );
}
