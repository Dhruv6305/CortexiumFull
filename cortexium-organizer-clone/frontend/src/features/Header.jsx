import React from 'react';
import { Brain, Clock } from 'lucide-react';

export function Header({ mode = 'Predict', cameraStatus = 'Disconnected', modelStatus = 'Ready', controls  }) {
  const [time, setTime] = React.useState(new Date());

  React.useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const isLearn    = mode === 'Learn';
  const isCamOn    = cameraStatus === 'Connected';
  const isTraining = modelStatus === 'Training';

  return (
    <header
      className="sticky top-0 z-50 flex flex-wrap md:flex-nowrap items-center justify-between px-4 md:px-6 py-2.5 md:py-3 gap-3"
      style={{
        background: "rgba(14, 19, 31, 0.90)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        borderBottom: "1px solid rgba(255, 255, 255, 0.08)"
      }}
    >
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-xl flex items-center justify-center shadow-md"
          style={{ background: 'linear-gradient(135deg, #10b981, #06b6d4)' }}>
          <Brain className="w-4 h-4 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-white tracking-tight leading-none">Cortexium XR</p>
          <p className="text-[10px] text-slate-300 leading-none mt-0.5">Adaptive AI Vision</p>
        </div>
      </div>

      {/*Controls*/}
      <div className="flex-1 flex justify-center">
        {controls}
      </div>

      {/* Clock */}
      <div className="flex items-center gap-2 text-gray-400">
        <Clock className="w-3.5 h-3.5" />
        <span className="text-xs font-mono tabular-nums text-slate-400">
          {time.toLocaleTimeString([], { hour12: false })}
        </span>
      </div>
    </header>
  );
}
