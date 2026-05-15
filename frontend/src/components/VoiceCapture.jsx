import { useState, useRef, useEffect } from 'react';
import { Mic, MicOff, Loader2 } from 'lucide-react';
import './VoiceCapture.css';

function VoiceCapture({ isRecording, setIsRecording, onRecordingComplete, generationStatus }) {
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
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm'
      });
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
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
    if (textInput.trim()) {
      // Create a mock audio blob for text input
      const textBlob = new Blob([textInput], { type: 'text/plain' });
      onRecordingComplete(textBlob);
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
    if (generationStatus === 'extracting') return 'Extracting intent...';
    if (generationStatus === 'generating') return 'Bob is working...';
    if (generationStatus === 'complete') return 'Complete!';
    if (isRecording) return 'Recording...';
    return 'Speak your feature idea';
  };

  const isProcessing = generationStatus !== 'idle' && generationStatus !== 'complete';

  return (
    <div className="voice-capture">
      <div className="mic-container">
        <button
          className={`mic-button ${isRecording ? 'recording' : ''} ${isProcessing ? 'processing' : ''}`}
          onClick={isRecording ? stopRecording : startRecording}
          disabled={!micAvailable || isProcessing}
        >
          {isProcessing ? (
            <Loader2 className="mic-icon spinning" size={64} />
          ) : isRecording ? (
            <Mic className="mic-icon" size={64} />
          ) : (
            <MicOff className="mic-icon" size={64} />
          )}
          
          {isRecording && (
            <div className="recording-pulse" />
          )}
        </button>

        <div className="status-text">
          {getStatusText()}
        </div>

        {isRecording && (
          <div className="recording-duration">
            {formatDuration(recordingDuration)}
          </div>
        )}
      </div>

      {!micAvailable && (
        <div className="text-input-fallback">
          <p className="fallback-message">Microphone not available. Type your request:</p>
          <form onSubmit={handleTextSubmit}>
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder="e.g., Add rate limiting - 100 requests per minute for free users"
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
