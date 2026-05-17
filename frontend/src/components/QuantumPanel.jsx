import { CheckCircle, Zap } from 'lucide-react';
import './QuantumPanel.css';

function QuantumPanel({ quantumResult, quantumStatus, numCandidates }) {
  const palette = {
    line: '#d7d7d7',
    gate: '#f4f4f4',
    muted: '#bdbdbd',
    text: '#f5f5f5',
  };

  const formatBackendLabel = (backend) => {
    if (!backend || backend === 'unknown') {
      return 'Unknown';
    }

    if (backend === 'classical_fallback') {
      return 'Classical fallback';
    }

    return backend
      .split('_')
      .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
      .join(' ');
  };

  if (quantumStatus === 'idle') {
    return (
      <div className="quantum-panel idle">
        <h3 className="panel-title">
          <Zap size={20} />
          Quantum Optimizer
        </h3>
        <p className="panel-subtitle panel-subtitle-light">Code optimization with Qiskit and IBM Quantum ranks the best file-change set.</p>
        <div className="quantum-idle">
          <Zap size={56} className="quantum-icon-large" />
          <p className="status-text">Quantum optimizer standing by</p>
        </div>
      </div>
    );
  }

  if (quantumStatus === 'running') {
    const combinations = numCandidates ? Math.pow(2, numCandidates) : 0;

    return (
      <div className="quantum-panel running">
        <h3 className="panel-title">
          <Zap size={20} className="pulse" />
          Quantum Optimizer
        </h3>
        <p className="panel-subtitle panel-subtitle-light">Code optimization with Qiskit builds the QAOA circuit while IBM Quantum evaluates it.</p>
        <div className="quantum-running">
          <div className="quantum-circuit">
            <svg width="100%" height="200" viewBox="0 0 400 200" role="img" aria-label="Animated quantum circuit">
              {[0, 1, 2, 3, 4].map((qubit) => (
                <g key={qubit}>
                  <line
                    x1="20"
                    y1={40 + qubit * 35}
                    x2="380"
                    y2={40 + qubit * 35}
                    stroke={palette.line}
                    strokeWidth="2"
                  />
                  <text x="5" y={45 + qubit * 35} fill={palette.muted} fontSize="12">
                    q{qubit}
                  </text>
                  <rect
                    className="quantum-gate"
                    x="20"
                    y={40 + qubit * 35 - 12}
                    width="24"
                    height="24"
                    rx="4"
                    style={{ animationDelay: `${qubit * 0.18}s` }}
                  />
                </g>
              ))}
            </svg>
          </div>

          <div className="quantum-status">
            <div className="pulse-indicator" />
            <p className="status-text-large">QAOA running on IBM Quantum</p>
            <p className="status-subtext">
              Evaluating {combinations.toLocaleString()} combinations simultaneously
            </p>
            <p className="status-detail">{numCandidates} qubits | QAOA circuit depth: 3</p>
          </div>
        </div>
      </div>
    );
  }

  if (quantumStatus === 'complete' && quantumResult) {
    const {
      selected_files = [],
      conflict_risk = 0,
      quantum_backend = 'unknown',
    } = quantumResult;

    return (
      <div className="quantum-panel complete">
        <h3 className="panel-title">
          <CheckCircle size={20} className="success-icon" />
          Quantum Optimizer
        </h3>
        <p className="panel-subtitle panel-subtitle-light">IBM Quantum code optimization selected the safest high-value files to change.</p>
        <div className="quantum-complete">
          <div className="result-header">
            <CheckCircle size={48} className="result-icon" />
            <div className="result-text">
              <h4 className="result-title">
                {selected_files.length} optimal file{selected_files.length !== 1 ? 's' : ''} selected
              </h4>
              <p className="result-subtitle">
                Conflict risk: {conflict_risk} | Backend: {formatBackendLabel(quantum_backend)}
              </p>
            </div>
          </div>

          <div className="selected-files">
            {selected_files.map((file, index) => (
              <div key={index} className="file-item">
                <CheckCircle size={16} className="file-check" />
                <span className="file-path">{file}</span>
              </div>
            ))}
          </div>

          <div className="complexity-comparison">
            <p className="complexity-line">
              Classical complexity: O(2^N) | Quantum: O(N^2)
            </p>
          </div>

          {quantum_backend !== 'classical_fallback' && (
            <div className="quantum-badge">
              <Zap size={14} />
              <span>Optimized with IBM Quantum QAOA</span>
            </div>
          )}
        </div>
      </div>
    );
  }

  return null;
}

export default QuantumPanel;
