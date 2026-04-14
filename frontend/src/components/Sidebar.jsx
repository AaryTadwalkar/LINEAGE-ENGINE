import React from 'react';
import { NavLink } from 'react-router-dom';
import { Network, Database, Activity, Hexagon } from 'lucide-react';
import { clsx } from 'clsx';

export const Sidebar = () => {
  const links = [
    { to: '/', label: 'Lineage Map', icon: Network },
    { to: '/directory', label: 'Dataset Directory', icon: Database },
    { to: '/system-runs', label: 'Global Pipeline Runs', icon: Activity },
  ];

  return (
    <aside className="w-64 h-full bg-darkglass backdrop-blur-xl border-r border-white/10 flex flex-col z-50">
      <div className="p-6 flex items-center gap-3 border-b border-white/10">
        <div className="w-10 h-10 rounded-lg shadow-lg bg-blue-600/20 border border-blue-500/50 flex items-center justify-center">
          <Hexagon className="text-blue-400" size={24} />
        </div>
        <h1 className="text-xl font-bold tracking-tight text-white/90">Lineage</h1>
      </div>

      <nav className="flex-1 p-4 flex flex-col gap-2">
        {links.map((link) => {
          const Icon = link.icon;
          return (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) => clsx(
                "flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-300",
                isActive 
                  ? "bg-blue-600/20 text-blue-400 border border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.15)]" 
                  : "text-white/60 hover:text-white/90 hover:bg-white/5 border border-transparent"
              )}
            >
              <Icon size={20} />
              <span className="font-medium text-sm">{link.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="p-4 border-t border-white/10">
        <div className="px-4 py-3 bg-white/5 rounded-lg border border-white/5">
          <p className="text-xs text-white/40 uppercase tracking-widest mb-1">Status</p>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>
            <span className="text-sm font-medium text-green-400">Live Streaming</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
