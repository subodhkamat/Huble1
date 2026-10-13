import React, { useState, useEffect } from 'react';
import Modal from './Modal.jsx';

export default function AdForm({ visible, onClose, onSave, ad }) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');

  useEffect(() => {
    if (ad) {
      setTitle(ad.title);
      setContent(ad.content);
    } else {
      setTitle('');
      setContent('');
    }
  }, [ad]);

  if (!visible) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    onSave({ id: ad?.id, title, content });
    onClose();
  };

  return (
    <Modal title={ad ? 'Edit Ad' : 'Add Ad'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="form">
        <label>
          Title
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            aria-required="true"
          />
        </label>
        <label>
          Content
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        </label>
        <div className="form-actions">
          <button type="submit">{ad ? 'Save' : 'Add'}</button>
          <button type="button" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}