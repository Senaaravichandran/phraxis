import { useState } from 'react';
import axios from 'axios';
import toast, { Toaster } from 'react-hot-toast';
import { Theme } from '@carbon/react';
import VoiceCapture from './components/VoiceCapture';
import TranscriptPanel from './components/TranscriptPanel';
import IntentPanel from './components/IntentPanel';
import QuantumPanel from './components/QuantumPanel';
import LiveCodePanel from './components/LiveCodePanel';
import PRStatus from './components/PRStatus';
import './App.css';

const API_BASE_URL = 'http://localhost:8000';
// Repo source URL is resolved by the backend from .env config — no hardcoding needed

const formatStatusLabel = (value, fallback) => {
  if (!value) {
    return fallback;
  }

  return value
    .split('_')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
};

function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [transcriptConfidence, setTranscriptConfidence] = useState(0);
  const [transcriptWords, setTranscriptWords] = useState([]);
  const [intent, setIntent] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState('idle');
  const [quantumStatus, setQuantumStatus] = useState('idle'); // idle, running, complete
  const [quantumResult, setQuantumResult] = useState(null);
  const [candidateChanges, setCandidateChanges] = useState([]);
  const [prUrl, setPrUrl] = useState('');
  const [prNumber, setPrNumber] = useState(null);
  const [filesChanged, setFilesChanged] = useState([]);
  const [liveProgress, setLiveProgress] = useState([]);
  const [startTime, setStartTime] = useState(null);
  const [endTime, setEndTime] = useState(null);
  const [intentDocId, setIntentDocId] = useState(null);
  const [isTextMode, setIsTextMode] = useState(false);
  const [inputMode, setInputMode] = useState('voice');

  // Calculate elapsed time
  const elapsedTime = startTime && endTime 
    ? ((endTime - startTime) / 1000).toFixed(1) 
    : null;

  const pipelineStatusLabel = formatStatusLabel(
    pipelineStatus === 'idle' ? null : pipelineStatus,
    'Ready'
  );
  const quantumStatusLabel = formatStatusLabel(quantumStatus, 'Standby');

  const handleRecordingStateChange = (recording) => {
    setIsRecording(recording);
    if (recording) {
      setInputMode('voice');
      setPipelineStatus('recording');
    } else if (pipelineStatus === 'recording') {
      setPipelineStatus('idle');
    }
  };

  // Handle voice recording complete
  const handleRecordingComplete = async (audioBlob) => {
    setStartTime(Date.now());
    setPipelineStatus('transcribing');
    setTranscript('');
    setIntent(null);
    setQuantumResult(null);
    setCandidateChanges([]);
    setQuantumStatus('idle');
    setLiveProgress([]);
    setPrUrl('');
    setIsTextMode(false);
    
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
      
      // Continue with intent extraction
      await extractAndGenerate(text);
      
    } catch (error) {
      console.error('Pipeline error:', error);
      toast.error(error.response?.data?.detail || 'An error occurred');
      setPipelineStatus('idle');
    }
  };

  // Handle text input submit
  const handleTextSubmit = async (text) => {
    setStartTime(Date.now());
    setPipelineStatus('extracting_intent');
    setTranscript(text);
    setTranscriptConfidence(1.0);
    setTranscriptWords([]);
    setIntent(null);
    setQuantumResult(null);
    setCandidateChanges([]);
    setQuantumStatus('idle');
    setLiveProgress([]);
    setPrUrl('');
    setIsTextMode(true);
    
    try {
      // Skip transcription, go directly to intent extraction
      await extractAndGenerate(text);
    } catch (error) {
      console.error('Pipeline error:', error);
      toast.error(error.response?.data?.detail || 'An error occurred');
      setPipelineStatus('idle');
    }
  };

  // Extract intent and generate code
  const extractAndGenerate = async (text) => {
    try {
      // Step 2: Extract intent
      setPipelineStatus('extracting_intent');
      toast.loading('Extracting intent...', { id: 'intent' });
      
      const intentResponse = await axios.post(
        `${API_BASE_URL}/api/intent/extract`,
        { transcript: text }
      );
      
      const extractedIntent = intentResponse.data;
      setIntent(extractedIntent);
      setIntentDocId(extractedIntent.intent_doc_id);
      
      toast.success('Intent extracted!', { id: 'intent' });
      
      // Step 3: Quantum optimization
      setPipelineStatus('quantum_optimizing');
      setQuantumStatus('running');
      toast.loading('Running quantum optimization...', { id: 'quantum' });
      
      // Generate mock candidate changes based on intent
      const candidateChanges = generateCandidateChanges(extractedIntent);
      const conflictMatrix = generateConflictMatrix(candidateChanges.length);
      setCandidateChanges(candidateChanges);
      
      const quantumResponse = await axios.post(
        `${API_BASE_URL}/api/quantum/optimize`,
        {
          doc_id: extractedIntent.intent_doc_id,
          candidate_changes: candidateChanges,
          conflict_matrix: conflictMatrix
        }
      );
      
      const quantumData = quantumResponse.data;
      setQuantumResult(quantumData);
      setQuantumStatus('complete');
      
      toast.success('Quantum optimization complete!', { id: 'quantum' });
      
      // Step 4: Generate code with SSE
      setPipelineStatus('generating_code');
      toast.loading('WatsonX is generating code...', { id: 'generate' });
      
      await streamCodeGeneration(extractedIntent.intent_doc_id);
      
    } catch (error) {
      console.error('Pipeline error:', error);
      toast.error(error.response?.data?.detail || 'An error occurred');
      setPipelineStatus('idle');
      setQuantumStatus('idle');
    }
  };

  // Generate mock candidate changes for quantum optimizer
  const generateCandidateChanges = (intent) => {
    const action = intent.action || 'add_feature';
    const module = intent.target_module || 'service';
    
    // Generate realistic candidate changes based on action
    const candidates = [
      { file_path: `${module}/main.py`, function_name: 'main', coverage_weight: 0.9 },
      { file_path: `${module}/__init__.py`, function_name: '__init__', coverage_weight: 0.3 },
      { file_path: `middleware/${action}.py`, function_name: action, coverage_weight: 1.0 },
      { file_path: 'app.py', function_name: 'configure_app', coverage_weight: 0.7 },
      { file_path: 'config.py', function_name: 'load_config', coverage_weight: 0.4 },
      { file_path: `routes/${module}_routes.py`, function_name: 'register_routes', coverage_weight: 0.8 },
      { file_path: `tests/test_${action}.py`, function_name: `test_${action}`, coverage_weight: 0.6 },
      { file_path: 'models.py', function_name: 'Base', coverage_weight: 0.5 },
    ];
    
    return candidates.slice(0, Math.min(12, candidates.length));
  };

  // Generate mock conflict matrix
  const generateConflictMatrix = (n) => {
    const matrix = Array(n).fill(0).map(() => Array(n).fill(0));
    
    // Add some realistic conflicts (files that touch the same functions)
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        // 20% chance of conflict
        if (Math.random() < 0.2) {
          matrix[i][j] = 1;
          matrix[j][i] = 1;
        }
      }
    }
    
    return matrix;
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
            setPipelineStatus('idle');
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
        setPipelineStatus('idle');
        reject(new Error('Connection lost'));
      };
    });
  };

  // Open pull request
  const openPullRequest = async (docId, generationResult) => {
    try {
      toast.loading('Opening pull request...', { id: 'pr' });
      setPipelineStatus('opening_pr');
      
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
      setPipelineStatus('complete');
      
      toast.success('Pull request opened!', { id: 'pr' });
    } catch (error) {
      console.error('PR error:', error);
      toast.error('Failed to open PR');
      setPipelineStatus('idle');
    }
  };

  return (
    <Theme theme="g10">
      <div className="app">
        <Toaster 
          position="top-right"
          toastOptions={{
            style: {
              background: 'var(--surface-strong)',
              color: 'var(--text)',
              border: '1px solid var(--border)'
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
            <div className="header-copy">
              <h1>PHRAXIS</h1>
              <p className="header-subtitle">Voice-to-code workspace</p>
            </div>
          </div>

          <div className="header-meta">
            <span className="meta-label">Live status</span>
            <span className="meta-value">{pipelineStatusLabel}</span>
          </div>
        </header>

        <div className="dashboard">
          <div className="panel voice-panel">
            <VoiceCapture
              isRecording={isRecording}
              setIsRecording={handleRecordingStateChange}
              onRecordingComplete={handleRecordingComplete}
              onTextSubmit={handleTextSubmit}
              generationStatus={pipelineStatus}
              inputMode={inputMode}
            />
          </div>

          <div className="panel transcript-panel">
            <TranscriptPanel
              transcript={transcript}
              confidence={transcriptConfidence}
              words={transcriptWords}
              isTextMode={isTextMode}
            />
            <IntentPanel intent={intent} />
          </div>

          <div className="panel quantum-panel-shell">
            <QuantumPanel
              quantumResult={quantumResult}
              quantumStatus={quantumStatus}
              numCandidates={candidateChanges.length || quantumResult?.num_qubits || 0}
            />
          </div>

          <div className="panel code-panel">
            <LiveCodePanel
              liveProgress={liveProgress}
              generationStatus={pipelineStatus}
            />
          </div>

          <div className="panel pr-panel">
            <PRStatus
              prUrl={prUrl}
              prNumber={prNumber}
              filesChanged={filesChanged}
              elapsedTime={elapsedTime}
              generationStatus={pipelineStatus}
            />
          </div>
        </div>
      </div>
    </Theme>
  );
}

export default App;

// Made with Bob
