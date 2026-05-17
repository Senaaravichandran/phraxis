import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import './IntentPanel.css';

function IntentPanel({ intent }) {
  const svgRef = useRef(null);
  const palette = {
    surface: '#1a1a1d',
    surfaceAlt: '#232326',
    line: '#d7d7d7',
    muted: '#bdbdbd',
    text: '#0b0b0c',
    textOnSurface: '#f5f5f5',
  };

  useEffect(() => {
    if (!intent || !svgRef.current) return;

    // Clear previous visualization
    d3.select(svgRef.current).selectAll('*').remove();

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    // Create nodes data
    const centerNode = {
      id: 'action',
      label: intent.action,
      type: 'action',
      x: width / 2,
      y: height / 2,
      confidence: intent.confidence
    };

    const parameterNodes = Object.entries(intent.parameters || {}).map(([key, value], index) => ({
      id: `param-${key}`,
      label: `${key}: ${value}`,
      type: 'parameter',
      confidence: intent.confidence * 0.9
    }));

    const constraintNodes = (intent.constraints || []).map((constraint, index) => ({
      id: `constraint-${index}`,
      label: constraint,
      type: 'constraint',
      confidence: intent.confidence * 0.85
    }));

    const nodes = [centerNode, ...parameterNodes, ...constraintNodes];

    // Create links
    const links = [
      ...parameterNodes.map(node => ({
        source: 'action',
        target: node.id,
        type: 'solid'
      })),
      ...constraintNodes.map(node => ({
        source: 'action',
        target: node.id,
        type: 'dashed'
      }))
    ];

    // Create force simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(60));

    // Create links
    const link = svg.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', d => d.type === 'dashed' ? palette.muted : palette.line)
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', d => d.type === 'dashed' ? '5,5' : 'none')
      .attr('opacity', 0)
      .transition()
      .duration(800)
      .attr('opacity', 0.6);

    // Create node groups
    const node = svg.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .attr('opacity', 0)
      .attr('transform', `translate(${width / 2}, ${height / 2})`);

    // Add circles to nodes
    node.append('circle')
      .attr('r', d => d.type === 'action' ? 50 : 40)
      .attr('fill', d => {
        if (d.type === 'action') return palette.textOnSurface;
        if (d.type === 'parameter') return '#cfcfcf';
        return '#9f9f9f';
      })
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 2);

    // Add labels to nodes
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.3em')
      .attr('fill', palette.text)
      .attr('font-size', d => d.type === 'action' ? '14px' : '11px')
      .attr('font-weight', d => d.type === 'action' ? 'bold' : 'normal')
      .each(function(d) {
        const text = d3.select(this);
        const words = d.label.split(/[\s_]+/);
        const maxWidth = d.type === 'action' ? 80 : 70;
        
        let line = [];
        let lineNumber = 0;
        const lineHeight = 1.1;
        const y = 0;
        
        words.forEach(word => {
          line.push(word);
          text.text(line.join(' '));
          
          if (text.node().getComputedTextLength() > maxWidth && line.length > 1) {
            line.pop();
            text.text(line.join(' '));
            
            const tspan = text.append('tspan')
              .attr('x', 0)
              .attr('y', y)
              .attr('dy', `${lineNumber * lineHeight}em`)
              .text(line.join(' '));
            
            line = [word];
            lineNumber++;
          }
        });
        
        if (line.length > 0) {
          text.append('tspan')
            .attr('x', 0)
            .attr('y', y)
            .attr('dy', `${lineNumber * lineHeight}em`)
            .text(line.join(' '));
        }
        
        text.text('');
      });

    // Add tooltip on hover
    node.on('mouseover', function(event, d) {
      d3.select(this).select('circle')
        .transition()
        .duration(200)
        .attr('r', d.type === 'action' ? 55 : 45)
        .attr('stroke-width', 3);

      // Show confidence tooltip
      const tooltip = svg.append('g')
        .attr('class', 'tooltip')
        .attr('transform', `translate(${d.x}, ${d.y - 70})`);

      tooltip.append('rect')
        .attr('x', -60)
        .attr('y', -25)
        .attr('width', 120)
        .attr('height', 30)
        .attr('fill', palette.surfaceAlt)
        .attr('stroke', palette.line)
        .attr('stroke-width', 2)
        .attr('rx', 5);

      tooltip.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '-0.5em')
        .attr('fill', palette.textOnSurface)
        .attr('font-size', '12px')
        .text(`Confidence: ${(d.confidence * 100).toFixed(1)}%`);
    })
    .on('mouseout', function(event, d) {
      d3.select(this).select('circle')
        .transition()
        .duration(200)
        .attr('r', d.type === 'action' ? 50 : 40)
        .attr('stroke-width', 2);

      svg.selectAll('.tooltip').remove();
    });

    // Animate nodes appearing
    node.transition()
      .duration(800)
      .delay((d, i) => i * 100)
      .attr('opacity', 1);

    // Update positions on simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node.attr('transform', d => `translate(${d.x}, ${d.y})`);
    });

    // Cleanup
    return () => {
      simulation.stop();
    };
  }, [intent]);

  if (!intent) {
    return (
      <div className="intent-panel-content">
        <h3 className="panel-title">Intent Structure</h3>
        <p className="panel-subtitle">IBM Watson Natural Language Understanding extracts action, module, and constraints.</p>
        <div className="empty-state">
          <p>Waiting for intent extraction...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="intent-panel-content">
      <h3 className="panel-title">Intent Structure</h3>
      <p className="panel-subtitle">IBM NLU maps your request into action, module, and confidence data.</p>
      <div className="intent-metadata">
        <div className="metadata-item">
          <span className="metadata-label">Action:</span>
          <span className="metadata-value">{intent.action}</span>
        </div>
        <div className="metadata-item">
          <span className="metadata-label">Module:</span>
          <span className="metadata-value">{intent.target_module}</span>
        </div>
        <div className="metadata-item">
          <span className="metadata-label">Confidence:</span>
          <span className="metadata-value">{(intent.confidence * 100).toFixed(1)}%</span>
        </div>
      </div>
      <svg ref={svgRef} className="intent-graph"></svg>
    </div>
  );
}

export default IntentPanel;

// Made with Bob
