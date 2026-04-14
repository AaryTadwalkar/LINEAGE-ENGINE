import React, { useEffect, useState } from 'react';
import { getGlobalRuns } from '../api/lineageApi';
import { Activity, Clock, CheckCircle2, XCircle } from 'lucide-react';
import { format } from 'date-fns';

export const SystemRunsView = () => {
  const [runs, setRuns] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchRuns = async () => {
      try {
        const data = await getGlobalRuns(100);
        setRuns(data || []);
      } catch (error) {
        console.error("Failed to load global runs:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchRuns();
    
    // Poll every 5 seconds since the pipeline is live!
    const interval = setInterval(fetchRuns, 5000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (isoString) => {
    if (!isoString) return '-';
    // Remove the trailing 'Z' or timezone bits if necessary or just format
    try {
      return format(new Date(isoString), 'MMM d, HH:mm:ss');
    } catch {
      return isoString;
    }
  };

  return (
    <div className="flex-1 h-full flex flex-col p-8 overflow-hidden">
      <div className="mb-8 flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight mb-2 flex items-center gap-3">
            <Activity className="text-purple-400" /> Global Pipeline Logs
          </h1>
          <p className="text-white/50">Real-time audit log of all jobs executed across the orchestrators.</p>
        </div>
        <div className="text-xs text-white/40 flex items-center gap-2 bg-white/5 px-3 py-1.5 rounded-full border border-white/10">
          <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span> Auto-refreshing
        </div>
      </div>

      <div className="glass-panel flex-1 flex flex-col overflow-hidden">
        <div className="overflow-auto flex-1 p-2">
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-darkspace/90 backdrop-blur-md z-10 shadow-sm text-xs uppercase tracking-wider text-white/50">
              <tr>
                <th className="p-4 font-semibold w-12">Status</th>
                <th className="p-4 font-semibold">Job Name</th>
                <th className="p-4 font-semibold">Run ID</th>
                <th className="p-4 font-semibold">Started At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {runs.map((run) => (
                <tr key={run.run_id} className="hover:bg-white/5 transition-colors group">
                  <td className="p-4">
                    {run.status === 'COMPLETE' ? (
                      <CheckCircle2 className="text-green-500/80" size={18} />
                    ) : run.status === 'FAIL' ? (
                      <XCircle className="text-red-500/80" size={18} />
                    ) : (
                      <Activity className="text-blue-500/80" size={18} />
                    )}
                  </td>
                  <td className="p-4 font-medium text-white/90">
                    <span className="bg-white/5 px-2 py-0.5 rounded text-sm group-hover:bg-blue-500/20 group-hover:text-blue-200 transition-colors">
                      {run.job_name}
                    </span>
                  </td>
                  <td className="p-4 font-mono text-xs text-white/40">{run.run_id}</td>
                  <td className="p-4 text-sm text-white/60 flex items-center gap-2">
                    <Clock size={14} className="opacity-50" />
                    {formatTime(run.start_time)}
                  </td>
                </tr>
              ))}
              {runs.length === 0 && !isLoading && (
                <tr>
                  <td colSpan={4} className="text-center p-8 text-white/40">No pipeline runs have been recorded yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
