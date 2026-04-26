import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { GraphView } from './pages/GraphView';
import { DirectoryView } from './pages/DirectoryView';
import { SystemRunsView } from './pages/SystemRunsView';
import { ColumnGraphView } from './pages/ColumnGraphView';

function App() {
  return (
    <BrowserRouter>
      <div className="w-screen h-screen flex bg-darkspace overflow-hidden">
        {/* Navigation Sidebar */}
        <Sidebar />
        
        {/* Main Content Pane */}
        <main className="flex-1 h-full relative">
          <Routes>
            <Route path="/" element={<GraphView />} />
            <Route path="/directory" element={<DirectoryView />} />
            <Route path="/system-runs" element={<SystemRunsView />} />
            <Route path="/column-graph" element={<ColumnGraphView />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
