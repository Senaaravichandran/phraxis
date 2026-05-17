import { useEffect, useState } from 'react';
import { CheckCircle2, ExternalLink, GitPullRequest, Clock } from 'lucide-react';
import './PRStatus.css';

function PRStatus({ prUrl, prNumber, filesChanged, elapsedTime, generationStatus }) {
  const [showCheckmark, setShowCheckmark] = useState(false);

  useEffect(() => {
    if (prUrl) {
      // Trigger checkmark animation
      setTimeout(() => setShowCheckmark(true), 100);
    }
  }, [prUrl]);

  if (
    generationStatus === 'idle' ||
    generationStatus === 'recording' ||
    generationStatus === 'transcribing' ||
    generationStatus === 'extracting_intent' ||
    generationStatus === 'quantum_optimizing'
  ) {
    return (
      <div className="pr-status">
        <h3 className="panel-title">Pull Request Status</h3>
        <p className="panel-subtitle">IBM watsonx.ai code output is packaged into a GitHub pull request.</p>
        <div className="empty-state">
          <GitPullRequest size={48} className="empty-icon" />
          <p>Waiting for code generation...</p>
        </div>
      </div>
    );
  }

  if (generationStatus === 'generating_code') {
    return (
      <div className="pr-status">
        <h3 className="panel-title">Pull Request Status</h3>
        <p className="panel-subtitle">IBM watsonx.ai is still generating the code before PR creation.</p>
        <div className="generating-state">
          <div className="spinner"></div>
          <p>WatsonX is generating code...</p>
          <p className="sub-text">PR will be created automatically when complete</p>
        </div>
      </div>
    );
  }

  if (!prUrl) {
    return (
      <div className="pr-status">
        <h3 className="panel-title">Pull Request Status</h3>
        <p className="panel-subtitle">IBM watsonx.ai will hand off the finished changes to GitHub.</p>
        <div className="empty-state">
          <p>Waiting for pull request creation...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="pr-status">
      <h3 className="panel-title">Pull Request Status</h3>
      <p className="panel-subtitle">WatsonX-generated code is turned into a PR with tracked files and timing.</p>

      {/* Success Animation */}
      <div className={`success-animation ${showCheckmark ? 'show' : ''}`}>
        <CheckCircle2 size={80} className="checkmark" />
        <h2 className="success-title">Pull Request Created!</h2>
      </div>

      {/* PR Details */}
      <div className="pr-details">
        <div className="pr-header">
          <GitPullRequest size={24} className="pr-icon" />
          <div className="pr-info">
            <h4 className="pr-title">PR #{prNumber}</h4>
            <a 
              href={prUrl} 
              target="_blank" 
              rel="noopener noreferrer"
              className="pr-link"
            >
              View on GitHub <ExternalLink size={16} />
            </a>
          </div>
        </div>

        {/* Files Changed */}
        {filesChanged && filesChanged.length > 0 && (
          <div className="files-changed">
            <h5 className="section-subtitle">Files Changed ({filesChanged.length})</h5>
            <div className="file-list">
              {filesChanged.map((file, index) => (
                <div key={index} className="file-change">
                  <span className="file-name">{file.filename || file}</span>
                  <div className="file-stats">
                    {file.additions !== undefined && (
                      <span className="additions">+{file.additions}</span>
                    )}
                    {file.deletions !== undefined && (
                      <span className="deletions">-{file.deletions}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Time Comparison */}
        {elapsedTime && (
          <div className="time-comparison">
            <div className="time-stat">
              <Clock size={20} />
              <div className="time-info">
                <span className="time-label">PHRAXIS Time</span>
                <span className="time-value phraxis">{elapsedTime}s</span>
              </div>
            </div>
            <div className="vs-divider">vs</div>
            <div className="time-stat">
              <Clock size={20} />
              <div className="time-info">
                <span className="time-label">Traditional Approach</span>
                <span className="time-value traditional">~2 weeks</span>
              </div>
            </div>
          </div>
        )}

        {/* Impact Statement */}
        <div className="impact-statement">
          <div className="impact-metric">
            <span className="metric-value">
              {elapsedTime ? Math.round((2 * 7 * 24 * 60 * 60) / parseFloat(elapsedTime)) : '10,000'}x
            </span>
            <span className="metric-label">Faster</span>
          </div>
          <div className="impact-description">
            <p>From voice to production-ready code in under {elapsedTime || '4'} seconds</p>
            <p className="powered-by">Powered by IBM WatsonX + Watson AI</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PRStatus;

// Made with Bob
