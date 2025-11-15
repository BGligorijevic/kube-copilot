import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [appStatus, setAppStatus] = useState('idle'); // 'idle', 'initializing', 'listening', 'stopping', 'disconnected'
  const [language, setLanguage] = useState('de');
  const [userId, setUserId] = useState('');
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

    // Use the window's hostname to dynamically connect to the backend.
    // This works for both localhost and local network access.
    // For production, you might use wss:// and a different logic.
    const backendHost = window.location.hostname;
    socket.current = new WebSocket(`ws://${backendHost}:8000/ws`);

    socket.current.onopen = () => {
      console.log('WebSocket connected');
      setAppStatus('initializing');
      // Send start message to the backend
      socket.current.send(JSON.stringify({ action: 'start', language: language, user_id: userId }));
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
      } else if (message.type === 'status' && message.data === 'stopped') {
        // Backend confirms graceful shutdown. Now we can close.
        socket.current.close();
      }
      if (message.type === 'transcript') {
        setTranscript(message.data);
      } else if (message.type === 'insight') {
        // Add the new insight only if it's different from the most recent one.
        setInsights(prevInsights => {
          if (prevInsights.length > 0 && prevInsights[0] === message.data) {
            return prevInsights; // It's a duplicate, do not update.
          }
          return [message.data, ...prevInsights]; // It's new, prepend it.
        });
      }
    };

    socket.current.onclose = () => {
      console.log('WebSocket disconnected');
      stopHealthCheck();
      if (intentionalClose.current) {
        setAppStatus('idle'); // Graceful stop, return to idle.
      } else {
        setAppStatus('disconnected');
        // Don't nullify the socket here, so reconnect can be attempted.
      }
    };

    socket.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setAppStatus('disconnected');
    };
  };

  const handleStartListening = () => {
    setAppStatus('initializing');
    setTranscript('');
    setInsights([]);
    connectWebSocket();
  };

  const handleStopListening = () => {
    if (socket.current && socket.current.readyState === WebSocket.OPEN) {
      intentionalClose.current = true; // Mark the close as intentional
      setAppStatus('stopping');
      // Request a graceful shutdown from the backend.
      socket.current.send(JSON.stringify({ action: 'stop' }));
      // The backend will now send final data and then close the connection.
    }
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
        return 'Initialisierung...';
      case 'stopping':
        return 'Wird gestoppt...';
      case 'listening':
        return 'Flüsterer stoppen';
      case 'disconnected':
        return 'Wiederverbinden';
      case 'idle':
      default:
        return 'Flüsterer aktivieren';
    }
  };


  return (
    <div className="App">
      <header className="App-header">
        <h1 style={{ marginBottom: "20px"}}>KuBe Flüsterer</h1>
        <img src="kube_whisperer.png" className="App-logo" alt="logo" width={"150px"} height={'150px'} />
        {appStatus === 'disconnected' && (
          <div className="error-message">
            Die Verbindung zum Server wurde unterbrochen. Bitte stellen Sie sicher, dass das Backend ausgeführt wird.
          </div>
        )}
        <div className="controls-container">
          <div className="language-controls">
            <div className="controls">
              <span className="language-label">Besprechungssprache</span>
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
            </div>
            <div className="controls">
              <span className="language-label">Kunde ID</span>
              <input
                type="text"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                className="customer-id-input"
                disabled={appStatus !== 'idle'}
              />
            </div>
          </div>
          <div className="button-container">
            <button
              onClick={(appStatus === 'listening') ? handleStopListening : handleStartListening}
              className={`listen-button ${appStatus === 'disconnected' ? 'reconnect-button' : ''}`}
              disabled={appStatus === 'initializing' || appStatus === 'stopping'}>
              {getButtonText()}
            </button>
          </div>
        </div>
      </header>
      <main className="App-main">
        <div className="column transcript-column">
          <h2>Transkript</h2>
          <textarea
            className="display-area"
            value={transcript}
            readOnly
          />
        </div>
        <div className="column fluesterer-column">
          <h2>Der Flüsterer</h2>
          <div className="display-area insights-display">
            {insights.map((insight, index) => (
              <div key={index} className="insight-item">
                {insight.split('\n').map((line, i) => <p key={i}>{line}</p>)}
              </div>
            ))}
            {(appStatus === 'listening' || appStatus === 'stopping') && (
              <div className="insight-item thinking">
                <p>Der Flüsterer hört aktiv zu und denkt mit...</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
