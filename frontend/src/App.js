import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [isListening, setIsListening] = useState(false);
  const [language, setLanguage] = useState('de');
  const [transcript, setTranscript] = useState('');
  const [insights, setInsights] = useState([]);
  const socket = useRef(null);

  useEffect(() => {
    // Cleanup on component unmount
    return () => {
      if (socket.current) {
        socket.current.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    // Ensure existing socket is closed before opening a new one
    if (socket.current) {
      socket.current.close();
    }

    // Use ws:// for local development, wss:// for production
    socket.current = new WebSocket('ws://localhost:8000/ws');

    socket.current.onopen = () => {
      console.log('WebSocket connected');
      // Send start message to the backend
      socket.current.send(JSON.stringify({ action: 'start', language: language }));
      setIsListening(true);
    };

    socket.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('Received message from WebSocket:', message); // Add this line
      if (message.type === 'transcript') {
        setTranscript(message.data);
      } else if (message.type === 'insight') {
        setInsights(prevInsights => [...prevInsights, message.data]);
      }
    };

    socket.current.onclose = () => {
      console.log('WebSocket disconnected');
      setIsListening(false);
    };

    socket.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsListening(false);
    };
  };

  const handleStartListening = () => {
    setTranscript('');
    setInsights([]);
    connectWebSocket();
  };

  const handleStopListening = () => {
    if (socket.current) {
      socket.current.close();
      socket.current = null;
    }
    setIsListening(false);
  };

  const handleLanguageChange = (e) => {
    setLanguage(e.target.value);
    if (isListening) {
      handleStopListening();
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🎙️ KuBe Co-Pilot</h1>
        <div className="controls">
          <div className="language-selector">
            <label>
              <input type="radio" value="de" checked={language === 'de'} onChange={handleLanguageChange} />
              DE
            </label>
            <label>
              <input type="radio" value="en" checked={language === 'en'} onChange={handleLanguageChange} />
              EN
            </label>
          </div>
          <button onClick={isListening ? handleStopListening : handleStartListening} className="listen-button">
            {isListening ? 'Stop Listening' : 'Start Listening'}
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
