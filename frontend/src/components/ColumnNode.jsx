import React from 'react';
import { Handle, Position } from 'reactflow';
import { Columns } from 'lucide-react';

export const ColumnNode = ({ data }) => {
  return (
    <div className={`px-3 py-1.5 rounded-full border shadow-sm flex items-center gap-2 bg-black/80 backdrop-blur-sm transition-all ${
      data.is_focal 
        ? 'border-cyan-400 text-cyan-200 shadow-[0_0_15px_rgba(34,211,238,0.3)]' 
        : 'border-white/20 text-gray-300 hover:border-cyan-500/50'
    }`}>
      <Handle type="target" position={Position.Left} className="w-1.5 h-1.5 bg-cyan-400 border-none" />
      <Columns size={12} className={data.is_focal ? 'text-cyan-400' : 'text-gray-500'} />
      <span className="font-mono text-[11px] font-medium tracking-wide">{data.name}</span>
      <Handle type="source" position={Position.Right} className="w-1.5 h-1.5 bg-cyan-400 border-none" />
    </div>
  );
};
