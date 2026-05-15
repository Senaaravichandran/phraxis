import { useState, useEffect } from 'react';
import './TranscriptPanel.css';

function TranscriptPanel({ transcript, confidence, words }) {
  const [displayedText, setDisplayedText] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);

  // Typewriter effect for transcript
  useEffect(() => {
    if (transcript && currentIndex < transcript.length) {
      const timer = setTimeout(() => {
        setDisplayedText(transcript.slice(0, currentIndex + 1));
        setCurrentIndex(currentIndex + 1);
      }, 30);
      return () => clearTimeout(timer);
    } else if (transcript && currentIndex >= transcript.length) {
      setDisplayedText(transcript);
    }
  }, [transcript, currentIndex]);

  // Reset when new transcript arrives
  useEffect(() => {
    setCurrentIndex(0);
    setDisplayedText('');
  }, [transcript]);

  // Extract keywords from words with high confidence
  const keywords = words
    .filter(word => word.confidence > 0.8)
    .map(word => word.word.toLowerCase());

  // Highlight keywords in transcript
  const highlightKeywords = (text) => {
    if (!text || keywords.length === 0) return text;

    const words = text.split(' ');
    return words.map((word, index) => {
      const cleanWord = word.toLowerCase().replace(/[.,!?;:]/, '');
      const isKeyword = keywords.includes(cleanWord);
      
      return (
        <span
          key={index}
          className={isKeyword ? 'keyword' : ''}
        >
          {word}{' '}
        </span>
      );
    });
  };

  if (!transcript) {
    return (
      <div className="transcript-panel-content">
        <h3 className="panel-title">Transcript</h3>
        <div className="empty-state">
          <p>Waiting for voice input...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="transcript-panel-content">
      <h3 className="panel-title">Transcript</h3>
      
      <div className="transcript-text">
        {highlightKeywords(displayedText)}
        {currentIndex < transcript.length && (
          <span className="cursor-blink">|</span>
        )}
      </div>

      <div className="confidence-section">
        <div className="confidence-label">
          <span>IBM Watson Confidence</span>
          <span className="confidence-value">{(confidence * 100).toFixed(1)}%</span>
        </div>
        <div className="confidence-bar">
          <div 
            className="confidence-fill"
            style={{ 
              width: `${confidence * 100}%`,
              background: confidence > 0.8 
                ? 'linear-gradient(90deg, #22c55e, #16a34a)'
                : confidence > 0.6
                ? 'linear-gradient(90deg, #f59e0b, #d97706)'
                : 'linear-gradient(90deg, #ef4444, #dc2626)'
            }}
          />
        </div>
      </div>

      {words.length > 0 && (
        <div className="keywords-section">
          <p className="keywords-label">Detected Keywords:</p>
          <div className="keywords-list">
            {keywords.slice(0, 8).map((keyword, index) => (
              <span key={index} className="keyword-tag">
                {keyword}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default TranscriptPanel;

// Made with Bob
