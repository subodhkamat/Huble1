import { useEffect, useRef } from 'react';

export default function VideoPlayer({ video, onClose }) {
  const containerRef = useRef(null);

  useEffect(() => {
    const handleEsc = e => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  return (
    <div className="video-player" ref={containerRef} aria-label="Video player">
      <button className="close-btn" onClick={onClose} aria-label="Close video player">✕</button>
      <video src={video.videoUrl} controls autoPlay />
    </div>
  );
}