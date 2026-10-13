import React from 'react';
import ReactDOM from 'react-dom';

export default function Modal({ title, children, onClose }) {
  return ReactDOM.createPortal(
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="modal">
        <header>
          <h2 id="modal-title">{title}</h2>
          <button onClick={onClose} aria-label="Close modal" className="close-btn">✖</button>
        </header>
        <div className="modal-content">{children}</div>
      </div>
    </div>,
    document.body
  );
}