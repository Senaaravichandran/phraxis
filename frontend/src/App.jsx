import { useState, useEffect } from 'react';
import axios from 'axios';
import toast, { Toaster } from 'react-hot-toast';
import VoiceCapture from './components/VoiceCapture';
import TranscriptPanel from './components/TranscriptPanel';
import IntentPanel from './components/IntentPanel';
import LiveCodePanel from './components/LiveCodePanel';
import PRStatus from './components/PRStatus';
import './App.css';

const API_BASE_URL = 'http://localhost:8000';
// Repo source URL is resolved by the backend from .env config — no hardcoding needed

function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [transcriptConfidence, setTranscriptConfidence] = useState(0);
  const [transcriptWords, setTranscriptWords] = useState([]);
  const [intent, setIntent] = useState(null);
  const [generationStatus, setGenerationStatus] = useState('idle'); // idle, transcribing, extracting, generating, complete
  const [prUrl, setPrUrl] = useState('');
  const [prNumber, setPrNumber] = useState(null);
  const [filesChanged, setFilesChanged] = useState([]);
  const [liveProgress, setLiveProgress] = useState([]);
  const [startTime, setStartTime] = useState(null);
  const [endTime, setEndTime] = useState(null);
  const [intentDocId, setIntentDocId] = useState(null);

  // Calculate elapsed time
  const elapsedTime = startTime && endTime 
    ? ((endTime - startTime) / 1000).toFixed(1) 
    : null;

  // Handle voice recording complete
  const handleRecordingComplete = async (audioBlob) => {
    setStartTime(Date.now());
    setGenerationStatus('transcribing');
    setTranscript('');
    setIntent(null);
    setLiveProgress([]);
    setPrUrl('');
    
    try {
      // Step 1: Transcribe audio
      toast.loading('Transcribing audio...', { id: 'transcribe' });
      
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');
      
      const transcribeResponse = await axios.post(
        `${API_BASE_URL}/api/voice/transcribe`,
        formData,
        {
          headers: { 'Content-Type': 'multipart/form-data' }
        }
      );
      
      const { transcript: text, confidence, words } = transcribeResponse.data;
      setTranscript(text);
      setTranscriptConfidence(confidence);
      setTranscriptWords(words || []);
      
      toast.success('Transcription complete!', { id: 'transcribe' });
      
      // Step 2: Extract intent
      setGenerationStatus('extracting');
      toast.loading('Extracting intent...', { id: 'intent' });
      
      const intentResponse = await axios.post(
        `${API_BASE_URL}/api/intent/extract`,
        { transcript: text }
      );
      
      const extractedIntent = intentResponse.data;
      setIntent(extractedIntent);
      setIntentDocId(extractedIntent.intent_doc_id);
      
      toast.success('Intent extracted!', { id: 'intent' });
      
      // Step 3: Generate code with SSE
      setGenerationStatus('generating');
      toast.loading('WatsonX is generating code...', { id: 'generate' });
      
      await streamCodeGeneration(extractedIntent.intent_doc_id);
      
    } catch (error) {
      console.error('Pipeline error:', error);
      toast.error(error.response?.data?.detail || 'An error occurred');
      setGenerationStatus('idle');
    }
  };

  // Stream code generation progress
  const streamCodeGeneration = async (docId) => {
    return new Promise((resolve, reject) => {
      const eventSource = new EventSource(
        `${API_BASE_URL}/api/generate/code?intent_doc_id=${docId}`
      );

      let settled = false;

      const handleStructuredEvent = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const normalizedEvent = {
            ...payload,
            type: payload.type || payload.event || event.type,
          };

          setLiveProgress(prev => [...prev, normalizedEvent]);

          if (normalizedEvent.type === 'complete') {
            settled = true;
            eventSource.close();
            toast.success('Code generation complete!', { id: 'generate' });

            openPullRequest(docId, normalizedEvent.result || normalizedEvent.data || {});
            resolve();
          } else if (normalizedEvent.type === 'error') {
            settled = true;
            eventSource.close();
            toast.error(normalizedEvent.message || 'Code generation failed', { id: 'generate' });
            setGenerationStatus('idle');
            reject(new Error(normalizedEvent.message || 'Code generation failed'));
          }
        } catch (error) {
          console.error('Error parsing SSE data:', error);
        }
      };

      const eventTypes = [
        'started',
        'architect_started',
        'architect_complete',
        'plan_started',
        'plan_complete',
        'code_started',
        'code_step',
        'code_step_error',
        'code_complete',
        'complete',
        'error',
      ];

      eventTypes.forEach((type) => {
        eventSource.addEventListener(type, handleStructuredEvent);
      });

      eventSource.onmessage = handleStructuredEvent;

      eventSource.onerror = (error) => {
        if (settled) {
          return;
        }

        console.error('SSE error:', error);
        eventSource.close();
        toast.error('Connection lost', { id: 'generate' });
        setGenerationStatus('idle');
        reject(new Error('Connection lost'));
      };
    });
  };

  // Open pull request
  const openPullRequest = async (docId, generationResult) => {
    try {
      toast.loading('Opening pull request...', { id: 'pr' });
      
      const prResponse = await axios.post(
        `${API_BASE_URL}/api/pr/open`,
        {
          intent_doc_id: docId,
          files_changed: generationResult.code_changes || generationResult.files_changed || {}
        }
      );
      
      const { pr_url, pr_number, files_committed, files_changed } = prResponse.data;
      setPrUrl(pr_url);
      setPrNumber(pr_number);
      setFilesChanged(files_committed || files_changed || []);
      setEndTime(Date.now());
      setGenerationStatus('complete');
      
      toast.success('Pull request opened!', { id: 'pr' });
    } catch (error) {
      console.error('PR error:', error);
      toast.error('Failed to open PR');
      setGenerationStatus('idle');
    }
  };

  return (
    <div className="app">
      <Toaster 
        position="top-right"
        toastOptions={{
          style: {
            background: '#1a1f3a',
            color: '#fff',
            border: '1px solid #2563eb'
          }
        }}
      />
      
      <header className="app-header">
        <div className="logo">
          <span className="logo-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 14C13.66 14 15 12.66 15 11V5C15 3.34 13.66 2 12 2C10.34 2 9 3.34 9 5V11C9 12.66 10.34 14 12 14Z" fill="currentColor"/>
              <path d="M17 11C17 13.76 14.76 16 12 16C9.24 16 7 13.76 7 11H5C5 14.53 7.61 17.43 11 17.92V21H13V17.92C16.39 17.43 19 14.53 19 11H17Z" fill="currentColor"/>
            </svg>
          </span>
          <h1>PHRAXIS</h1>
        </div>
        <p className="tagline">Voice to Impact • Powered by IBM WatsonX</p>
      </header>

      <div className="dashboard">
        <div className="panel voice-panel">
          <VoiceCapture
            isRecording={isRecording}
            setIsRecording={setIsRecording}
            onRecordingComplete={handleRecordingComplete}
            generationStatus={generationStatus}
          />
        </div>

        <div className="panel transcript-panel">
          <TranscriptPanel
            transcript={transcript}
            confidence={transcriptConfidence}
            words={transcriptWords}
          />
          <IntentPanel intent={intent} />
        </div>

        <div className="panel code-panel">
          <LiveCodePanel
            liveProgress={liveProgress}
            generationStatus={generationStatus}
          />
        </div>

        <div className="panel pr-panel">
          <PRStatus
            prUrl={prUrl}
            prNumber={prNumber}
            filesChanged={filesChanged}
            elapsedTime={elapsedTime}
            generationStatus={generationStatus}
          />
        </div>
      </div>
    </div>
  );
}

export default App;

// Made with Bob
