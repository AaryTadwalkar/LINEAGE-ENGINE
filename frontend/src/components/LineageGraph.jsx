import React, { useCallback, useEffect } from 'react';
import ReactFlow, { 
  Background, 
  Controls, 
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
import { nodeTypes } from './CustomNodes';
import { getLayoutedElements } from '../utils/graphLayout';

export const LineageGraph = ({ nodes, edges, onNodeClick }) => {
  const [rfNodes, setNodes, onNodesChange] = useNodesState([]);
  const [rfEdges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    const formattedNodes = nodes.map(n => ({
      id: String(n.id),
      type: n.label,    // 'Job' or 'Dataset'
      data: { ...n.properties, label: n.label },
      position: { x: 0, y: 0 },
    }));

    // Track seen edge keys to prevent duplicates caused by multi-path traversal
    const seenEdgeKeys = new Set();
    const formattedEdges = [];

    edges.forEach((e, idx) => {
      const baseKey = `${e.source_id}-${e.type}-${e.target_id}`;
      // If we've seen this exact relationship before, make the key unique with index
      const key = seenEdgeKeys.has(baseKey) ? `${baseKey}-${idx}` : baseKey;
      seenEdgeKeys.add(baseKey);

      const isProduces = e.type === 'PRODUCES';
      formattedEdges.push({
        id: key,
        source: String(e.source_id),
        target: String(e.target_id),
        type: 'smoothstep',
        animated: true,
        label: e.type,              // Shows PRODUCES or CONSUMES on the edge
        labelStyle: {
          fill: isProduces ? '#34d399' : '#fb923c',
          fontWeight: 600,
          fontSize: 10,
          fontFamily: 'Inter, sans-serif',
        },
        labelBgStyle: {
          fill: 'rgba(0,0,0,0.5)',
          rx: 4,
        },
        style: {
          stroke: isProduces ? 'rgba(52,211,153,0.5)' : 'rgba(251,146,60,0.5)',
          strokeWidth: 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isProduces ? '#34d399' : '#fb923c',
        },
      });
    });

    const layouted = getLayoutedElements(formattedNodes, formattedEdges);
    setNodes([...layouted.nodes]);
    setEdges([...layouted.edges]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges]);

  const handleNodeClick = useCallback((event, node) => {
    const originalNode = nodes.find(n => String(n.id) === node.id);
    if (originalNode && onNodeClick) {
      onNodeClick(originalNode);
    }
  }, [nodes, onNodeClick]);

  const handlePaneClick = useCallback(() => {
    if (onNodeClick) onNodeClick(null);
  }, [onNodeClick]);

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        attributionPosition="bottom-left"
        minZoom={0.05}
        maxZoom={1.5}
      >
        <Background gap={24} size={1.5} color="#ffffff" style={{ opacity: 0.04 }} />
        <Controls 
          className="bg-black/50 border border-white/10 rounded-lg overflow-hidden backdrop-blur" 
          showInteractive={false}
        />
        <MiniMap 
          nodeColor={(n) => n.type === 'Dataset' ? '#3B82F6' : '#F97316'}
          maskColor="rgba(0,0,0,0.8)"
          className="bg-black/50 border border-white/10 rounded-lg overflow-hidden backdrop-blur-md"
        />
      </ReactFlow>
    </div>
  );
};
