import React, { useState, useRef, useEffect } from 'react';

export default function Timer() {
  const [seconds, setSeconds] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const intervalRef = useRef(null);

  const startTimer = () => {
    if (!isRunning) {
      setIsRunning(true);
      intervalRef.current = setInterval(() => {
        setSeconds((prev) => prev + 1);
      }, 1000);
    }
  };

  const pauseTimer = () => {
    setIsRunning(false);
    clearInterval(intervalRef.current);
  };

  const resetTimer = () => {
    setIsRunning(false);
    clearInterval(intervalRef.current);
    setSeconds(0);
  };

  // Clean up on unmount
  useEffect(() => {
    return () => clearInterval(intervalRef.current);
  }, []);

  const formatTime = (secs) => {
    const mins = Math.floor(secs / 60);
    const secsRem = secs % 60;
    return `${String(mins).padStart(2, '0')}:${String(secsRem).padStart(2, '0')}`;
  };

  return (
    <div className="timer" role="timer" aria-live="polite">
      <div className="timer-display" aria-label="Elapsed time">{formatTime(seconds)}</div>
      <div className="timer-controls">
        <button onClick={startTimer} disabled={isRunning} aria-label="Start timer">
          Start
        </button>
        <button onClick={pauseTimer} disabled={!isRunning} aria-label="Pause timer">
          Pause
        </button>
        <button onClick={resetTimer} aria-label="Reset timer">
          Reset
        </button>
      </div>
    </div>
  );
}