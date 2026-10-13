import React, { useState, useEffect } from 'react';
import Modal from './Modal.jsx';

export default function ShopForm({ visible, onClose, onSave, shop }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  useEffect(() => {
    if (shop) {
      setName(shop.name);
      setDescription(shop.description);
    } else {
      setName('');
      setDescription('');
    }
  }, [shop]);

  if (!visible) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSave({ id: shop?.id, name, description, ads: shop?.ads ?? [] });
    onClose();
  };

  return (
    <Modal title={shop ? 'Edit Shop' : 'Add Shop'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="form">
        <label>
          Name
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            aria-required="true"
          />
        </label>
        <label>
          Description
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <div className="form-actions">
          <button type="submit">{shop ? 'Save' : 'Add'}</button>
          <button type="button" onClick={onClose}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}