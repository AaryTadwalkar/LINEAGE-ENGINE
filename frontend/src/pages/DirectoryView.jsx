import React, { useEffect, useState } from 'react';
import { getDatasets } from '../api/lineageApi';
import { Database, Search } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const DirectoryView = () => {
  const [datasets, setDatasets] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchDatasets = async () => {
      try {
        const data = await getDatasets();
        setDatasets(data || []);
      } catch (error) {
        console.error("Failed to load datasets:", error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchDatasets();
  }, []);

  const filteredSets = datasets.filter(d => 
    d.uri.toLowerCase().includes(filter.toLowerCase()) || 
    d.name.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="flex-1 h-full flex flex-col p-8 overflow-hidden">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white tracking-tight mb-2 flex items-center gap-3">
          <Database className="text-blue-400" /> Dataset Directory
        </h1>
        <p className="text-white/50">Browse all datasets currently tracked by the Lineage Engine.</p>
      </div>

      <div className="glass-panel flex-1 flex flex-col overflow-hidden relative">
        <div className="p-4 border-b border-white/10 flex items-center bg-white/5">
          <div className="relative w-96 flex-shrink-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40" size={18} />
            <input 
              type="text"
              placeholder="Filter by dataset name or URI..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="w-full bg-black/40 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white placeholder-white/30 focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
        </div>

        <div className="flex-1 overflow-auto overflow-x-hidden p-4">
          {isLoading ? (
            <div className="flex justify-center items-center h-full text-white/50">Loading directory...</div>
          ) : filteredSets.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredSets.map((ds, idx) => (
                <div 
                  key={idx} 
                  onClick={() => navigate(`/?uri=${encodeURIComponent(ds.uri)}`)}
                  className="bg-black/30 border border-white/5 rounded-lg p-5 cursor-pointer hover:bg-black/50 hover:border-blue-500/30 transition-all group"
                >
                  <div className="text-xs text-blue-400 mb-1">{ds.namespace}</div>
                  <div className="text-base text-white font-medium mb-3 truncate" title={ds.name}>{ds.name}</div>
                  <div className="text-xs text-white/40 break-all bg-white/5 p-2 rounded truncate" title={ds.uri}>
                    {ds.uri}
                  </div>
                  <div className="mt-4 pt-3 border-t border-white/5 text-xs text-white/50 group-hover:text-blue-300 flex justify-between items-center transition-colors">
                    Click to view details map &rarr;
                  </div>
                </div>
              ))}
            </div>
          ) : (
             <div className="flex flex-col items-center justify-center h-full text-white/40">
               <Database size={48} className="mb-4 opacity-30" />
               <p>No datasets found in the registry.</p>
             </div>
          )}
        </div>
      </div>
    </div>
  );
};
