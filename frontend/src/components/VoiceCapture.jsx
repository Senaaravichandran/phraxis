import { useState, useRef, useEffect } from 'react';
import { ArrowRight, Mic, MicOff, Loader2 } from 'lucide-react';
import './VoiceCapture.css';

function VoiceCapture({ isRecording, setIsRecording, onRecordingComplete, generationStatus, onTextSubmit, inputMode }) {
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [textInput, setTextInput] = useState('');
  const [micAvailable, setMicAvailable] = useState(true);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);

  useEffect(() => {
    // Check if microphone is available
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setMicAvailable(false);
    }
  }, []);

  useEffect(() => {
    if (isRecording) {
      timerRef.current = setInterval(() => {
        setRecordingDuration(prev => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      setRecordingDuration(0);
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [isRecording]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const preferredMimeTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/ogg',
      ];
      const selectedMimeType = preferredMimeTypes.find((mimeType) => (
        typeof MediaRecorder.isTypeSupported === 'function'
          ? MediaRecorder.isTypeSupported(mimeType)
          : mimeType === 'audio/webm'
      ));

      const mediaRecorder = selectedMimeType
        ? new MediaRecorder(stream, { mimeType: selectedMimeType })
        : new MediaRecorder(stream);
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(
          audioChunksRef.current,
          { type: mediaRecorder.mimeType || selectedMimeType || 'audio/webm' }
        );
        onRecordingComplete(audioBlob);
        
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error('Error accessing microphone:', error);
      setMicAvailable(false);
      alert('Could not access microphone. Please check permissions.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleTextSubmit = (e) => {
    e.preventDefault();
    if (textInput.trim() && textInput.length <= 500) {
      // Call the text submit handler from parent
      if (onTextSubmit) {
        onTextSubmit(textInput.trim());
      }
      setTextInput('');
    }
  };

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getStatusText = () => {
    if (generationStatus === 'transcribing') return 'Transcribing...';
    if (generationStatus === 'extracting_intent') return 'Extracting intent...';
    if (generationStatus === 'quantum_optimizing') return 'Running quantum optimizer...';
    if (generationStatus === 'generating_code') return 'WatsonX is generating code...';
    if (generationStatus === 'opening_pr') return 'Opening pull request...';
    if (generationStatus === 'complete') return 'Complete!';
    if (isRecording) return 'Recording...';
    return 'Speak your feature idea';
  };

  const isProcessing = !['idle', 'recording', 'complete'].includes(generationStatus);
  const isChatMode = inputMode === 'chat';

  return (
    <div className="voice-capture">
      {!isChatMode ? (
        <div className="voice-shell">
          <div className="section-title">
            <span>Voice mode</span>
            <p>Capture spoken requests with IBM Watson Speech to Text.</p>
          </div>

          <div className="mic-container">
          <button
            className={`mic-button ${isRecording ? 'recording' : ''} ${isProcessing ? 'processing' : ''}`}
            onClick={isRecording ? stopRecording : startRecording}
            disabled={!micAvailable || isProcessing}
          >
            {isProcessing ? (
              <Loader2 className="mic-icon spinning" size={92} />
            ) : isRecording ? (
              <Mic className="mic-icon" size={92} />
            ) : (
              <MicOff className="mic-icon" size={92} />
            )}

            {isRecording && <div className="recording-pulse" />}
          </button>

          <div className="status-text">
            {getStatusText()}
          </div>

          {isRecording && (
            <div className="recording-duration">
              {formatDuration(recordingDuration)}
            </div>
          )}

          {!micAvailable && (
            <div className="text-input-fallback">
              <p className="fallback-message">Microphone not available. Type your request:</p>
              <form onSubmit={handleTextSubmit}>
                <input
                  type="text"
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  placeholder="e.g., Add authentication to the login endpoint"
                  className="text-input"
                  disabled={isProcessing}
                />
                <button
                  type="submit"
                  className="submit-button"
                  disabled={!textInput.trim() || isProcessing}
                >
                  Submit
                </button>
              </form>
            </div>
          )}
          </div>

          <div className="chat-under-voice">
            <div className="divider">
              <span className="divider-text">Type a command</span>
            </div>
            <form onSubmit={handleTextSubmit} className="text-form">
              <textarea
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Type the same request you would say aloud..."
                className="text-textarea"
                rows={4}
                maxLength={500}
                disabled={isProcessing}
              />
              <div className="text-form-footer">
                <span className="char-count">
                  {textInput.length}/500 characters
                </span>
                <button 
                  type="submit" 
                  className="submit-button-primary"
                  disabled={!textInput.trim() || isProcessing}
                >
                  Send Command
                  <ArrowRight size={16} />
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : (
        <div className="text-input-section chat-shell">
          <div className="section-title">
            <span>Chat mode</span>
            <p>Type the feature request and send it straight into WatsonX.</p>
          </div>

          <div className="divider">
            <span className="divider-text">chat input</span>
          </div>
          <form onSubmit={handleTextSubmit} className="text-form">
            <textarea
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder="Describe the feature you want to implement..."
              className="text-textarea"
              rows={4}
              maxLength={500}
              disabled={isProcessing}
            />
            <div className="text-form-footer">
              <span className="char-count">
                {textInput.length}/500 characters
              </span>
              <button 
                type="submit" 
                className="submit-button-primary"
                disabled={!textInput.trim() || isProcessing}
              >
                Send Chat Request
                <ArrowRight size={16} />
              </button>
            </div>
          </form>
        </div>
      )}

      {generationStatus === 'complete' && (
        <button
          className="reset-button"
          onClick={() => window.location.reload()}
        >
          Start New Request
        </button>
      )}
    </div>
  );
}

export default VoiceCapture;

// Made with Bob

