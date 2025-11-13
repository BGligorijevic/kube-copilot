import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [appStatus, setAppStatus] = useState('idle'); // 'idle', 'initializing', 'listening', 'disconnected'
  const [language, setLanguage] = useState('de');
  const [transcript, setTranscript] = useState('');
  const [insights, setInsights] = useState([]);
  const socket = useRef(null);
  const intentionalClose = useRef(false);
  const healthCheckInterval = useRef(null);
  const pongTimeout = useRef(null);

  useEffect(() => {
    // Cleanup on component unmount
    return () => {
      if (socket.current) {
        socket.current.close();
        clearTimeout(pongTimeout.current);
      }
    };
  }, []);

  const connectWebSocket = () => {
    // Ensure existing socket is closed before opening a new one
    if (socket.current) {
      socket.current.close();
    }

    // Reset the flag on each new connection attempt
    intentionalClose.current = false;

    const startHealthCheck = () => {
      healthCheckInterval.current = setInterval(() => {
        if (socket.current && socket.current.readyState === WebSocket.OPEN) {
          socket.current.send(JSON.stringify({ action: 'ping' }));
          // Expect a pong back within 2 seconds. If not, consider it disconnected.
          pongTimeout.current = setTimeout(() => {
            console.error("Pong not received, connection is likely dead.");
            setAppStatus('disconnected');
            socket.current.close();
          }, 2000);
        }
      }, 5000); // Send a ping every 5 seconds
    };

    const stopHealthCheck = () => {
      clearInterval(healthCheckInterval.current);
      clearTimeout(pongTimeout.current);
    };

    // Use ws:// for local development, wss:// for production
    socket.current = new WebSocket('ws://localhost:8000/ws');

    socket.current.onopen = () => {
      console.log('WebSocket connected');
      setAppStatus('initializing');
      // Send start message to the backend
      socket.current.send(JSON.stringify({ action: 'start', language: language }));
      startHealthCheck();
    };

    socket.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('Received message from WebSocket:', message);

      if (message.type === 'pong') {
        clearTimeout(pongTimeout.current); // Pong received, connection is healthy.
        return;
      } else if (message.type === 'status' && message.data === 'listening') {
        setAppStatus('listening');
      }
      if (message.type === 'transcript') {
        setTranscript(message.data);
      } else if (message.type === 'insight') {
        setInsights(prevInsights => [...prevInsights, message.data]);
      }
    };

    socket.current.onclose = () => {
      console.log('WebSocket disconnected');
      stopHealthCheck();
      // Only show disconnected error if it wasn't a manual stop.
      if (!intentionalClose.current) {
        setAppStatus('disconnected');
      }
    };

    socket.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setAppStatus('disconnected');
    };
  };

  const handleStartListening = () => {
    setTranscript('');
    setInsights([]);
    connectWebSocket();
  };

  const handleStopListening = () => {
    intentionalClose.current = true; // Mark the close as intentional
    if (socket.current) {
      socket.current.close();
      socket.current = null;
    }
    setAppStatus('idle');
  };

  const handleLanguageChange = (e) => {
    setLanguage(e.target.value);
    if (appStatus !== 'idle') {
      handleStopListening();
    }
  };

  const getButtonText = () => {
    switch (appStatus) {
      case 'initializing':
        return 'Initializing...';
      case 'listening':
        return 'Stop Listening';
      case 'disconnected':
        return 'Reconnect';
      case 'idle':
      default:
        return 'Start Listening';
    }
  };


  return (
    <div className="App">
      <header className="App-header">
        <h1>🎙️ KuBe Co-Pilot</h1>
        {appStatus === 'disconnected' && (
          <div className="error-message">
            Connection to the server was lost. Please ensure the backend is running.
          </div>
        )}
        <div className="controls">
          <div className="language-selector">
            <label>
              <input type="radio" value="de" checked={language === 'de'} onChange={handleLanguageChange} disabled={appStatus !== 'idle'} />
              DE
            </label>
            <label>
              <input type="radio" value="en" checked={language === 'en'} onChange={handleLanguageChange} disabled={appStatus !== 'idle'} />
              EN
            </label>
          </div>
          <button
            onClick={(appStatus === 'listening' || appStatus === 'disconnected') ? handleStopListening : handleStartListening}
            className={`listen-button ${appStatus === 'disconnected' ? 'reconnect-button' : ''}`}
            disabled={appStatus === 'initializing'}>
            {getButtonText()}
          </button>
        </div>
      </header>
      <main className="App-main">
        <div className="column">
          <h2>Transcript</h2>
          <textarea
            className="display-area"
            value={transcript}
            readOnly
          />
        </div>
        <div className="column">
          <h2>Co-Pilot Insights</h2>
          <div className="display-area insights-display">
            {insights.map((insight, index) => (
              <div key={index} className="insight-item">
                {insight.split('\n').map((line, i) => <p key={i}>{line}</p>)}
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
