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
      setIntentDocId(extractedIntent.doc_id);
      
      toast.success('Intent extracted!', { id: 'intent' });
      
      // Step 3: Generate code with SSE
      setGenerationStatus('generating');
      toast.loading('Bob is generating code...', { id: 'generate' });
      
      await streamCodeGeneration(extractedIntent.doc_id);
      
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
        `${API_BASE_URL}/api/generate/code?intent_doc_id=${docId}&repo_path=../demo_repo`
      );
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          setLiveProgress(prev => [...prev, data]);
          
          if (data.type === 'complete') {
            eventSource.close();
            toast.success('Code generation complete!', { id: 'generate' });
            
            // Step 4: Open PR
            openPullRequest(docId, data.result);
            resolve();
          } else if (data.type === 'error') {
            eventSource.close();
            toast.error('Code generation failed', { id: 'generate' });
            setGenerationStatus('idle');
            reject(new Error(data.message));
          }
        } catch (error) {
          console.error('Error parsing SSE data:', error);
        }
      };
      
      eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        eventSource.close();
        toast.error('Connection lost', { id: 'generate' });
        setGenerationStatus('idle');
        reject(error);
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
          files_changed: generationResult.files_generated || {}
        }
      );
      
      const { pr_url, pr_number, files_changed } = prResponse.data;
      setPrUrl(pr_url);
      setPrNumber(pr_number);
      setFilesChanged(files_changed || []);
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
          <span className="logo-icon">🎤</span>
          <h1>PHRAXIS</h1>
        </div>
        <p className="tagline">Voice to Impact • Powered by IBM Bob</p>
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
