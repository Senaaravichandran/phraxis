import { useEffect, useRef } from 'react';
import './LiveCodePanel.css';

function LiveCodePanel({ liveProgress, generationStatus }) {
  const architectRef = useRef(null);
  const planRef = useRef(null);
  const codeRef = useRef(null);

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    if (codeRef.current) {
      codeRef.current.scrollTop = codeRef.current.scrollHeight;
    }
  }, [liveProgress]);

  // Filter progress by type
  const architectEvents = liveProgress.filter(e => 
    e.type === 'architect_started' || e.type === 'architect_complete' || 
    (e.type === 'progress' && e.stage === 'architect')
  );
  
  const planEvents = liveProgress.filter(e => 
    e.type === 'plan_started' || e.type === 'plan_complete' ||
    (e.type === 'progress' && e.stage === 'plan')
  );
  
  const codeEvents = liveProgress.filter(e => 
    e.type === 'code_started' || e.type === 'code_step' || e.type === 'code_complete' ||
    (e.type === 'progress' && e.stage === 'code')
  );

  const isArchitectActive = architectEvents.length > 0 && !architectEvents.some(e => e.type === 'architect_complete');
  const isPlanActive = planEvents.length > 0 && !planEvents.some(e => e.type === 'plan_complete');
  const isCodeActive = codeEvents.length > 0 && !codeEvents.some(e => e.type === 'code_complete');

  if (generationStatus === 'idle' || generationStatus === 'transcribing' || generationStatus === 'extracting') {
    return (
      <div className="live-code-panel">
        <h3 className="panel-title">Bob's Workspace</h3>
        <div className="empty-state">
          <p>Waiting for code generation to start...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="live-code-panel">
      <h3 className="panel-title">Bob's Workspace</h3>

      {/* Architect Section */}
      <div className={`workspace-section ${isArchitectActive ? 'active' : ''}`}>
        <div className="section-header">
          <span className="section-icon">🏗️</span>
          <h4>Architect Mode</h4>
          {isArchitectActive && <span className="status-badge active">Active</span>}
          {architectEvents.some(e => e.type === 'architect_complete') && (
            <span className="status-badge complete">Complete</span>
          )}
        </div>
        <div className="section-content" ref={architectRef}>
          {architectEvents.length === 0 ? (
            <p className="waiting-text">Waiting...</p>
          ) : (
            architectEvents.map((event, index) => (
              <div key={index} className="progress-item animate-in">
                {event.type === 'architect_started' && (
                  <p className="info-text">📖 Reading repository structure...</p>
                )}
                {event.type === 'architect_complete' && event.result && (
                  <>
                    <p className="success-text">✓ Repository analysis complete</p>
                    {event.result.files_to_modify && (
                      <div className="file-list">
                        <p className="list-title">Files to modify:</p>
                        {event.result.files_to_modify.map((file, i) => (
                          <div key={i} className="file-item">{file}</div>
                        ))}
                      </div>
                    )}
                  </>
                )}
                {event.message && <p className="info-text">{event.message}</p>}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Plan Section */}
      <div className={`workspace-section ${isPlanActive ? 'active' : ''}`}>
        <div className="section-header">
          <span className="section-icon">📋</span>
          <h4>Plan Mode</h4>
          {isPlanActive && <span className="status-badge active">Active</span>}
          {planEvents.some(e => e.type === 'plan_complete') && (
            <span className="status-badge complete">Complete</span>
          )}
        </div>
        <div className="section-content" ref={planRef}>
          {planEvents.length === 0 ? (
            <p className="waiting-text">Waiting...</p>
          ) : (
            planEvents.map((event, index) => (
              <div key={index} className="progress-item animate-in">
                {event.type === 'plan_started' && (
                  <p className="info-text">🎯 Creating implementation plan...</p>
                )}
                {event.type === 'plan_complete' && event.result && (
                  <>
                    <p className="success-text">✓ Implementation plan ready</p>
                    {event.result.steps && (
                      <div className="plan-steps">
                        {event.result.steps.slice(0, 5).map((step, i) => (
                          <div key={i} className="plan-step">
                            <span className="step-number">{i + 1}</span>
                            <span className="step-description">{step.description || step}</span>
                          </div>
                        ))}
                        {event.result.steps.length > 5 && (
                          <p className="more-text">... and {event.result.steps.length - 5} more steps</p>
                        )}
                      </div>
                    )}
                  </>
                )}
                {event.message && <p className="info-text">{event.message}</p>}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Code Section */}
      <div className={`workspace-section ${isCodeActive ? 'active' : ''}`}>
        <div className="section-header">
          <span className="section-icon">💻</span>
          <h4>Code Mode</h4>
          {isCodeActive && <span className="status-badge active">Active</span>}
          {codeEvents.some(e => e.type === 'code_complete') && (
            <span className="status-badge complete">Complete</span>
          )}
        </div>
        <div className="section-content code-content" ref={codeRef}>
          {codeEvents.length === 0 ? (
            <p className="waiting-text">Waiting...</p>
          ) : (
            codeEvents.map((event, index) => (
              <div key={index} className="progress-item animate-in">
                {event.type === 'code_started' && (
                  <p className="info-text">⚡ Generating code...</p>
                )}
                {event.type === 'code_step' && (
                  <div className="code-step">
                    <p className="file-path">📄 {event.file || 'Working...'}</p>
                    {event.content && (
                      <pre className="code-block">
                        <code>{event.content}</code>
                        {isCodeActive && index === codeEvents.length - 1 && (
                          <span className="cursor-blink">█</span>
                        )}
                      </pre>
                    )}
                  </div>
                )}
                {event.type === 'code_complete' && (
                  <p className="success-text">✓ Code generation complete!</p>
                )}
                {event.message && !event.content && (
                  <p className="info-text">{event.message}</p>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default LiveCodePanel;

// Made with Bob
