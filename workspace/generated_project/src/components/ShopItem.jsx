import React from 'react';

export default function ShopItem({ shop, onEdit, onDelete, onAddAd, onEditAd, onDeleteAd }) {
  return (
    <div className="shop-item">
      <div className="shop-header">
        <h2>{shop.name}</h2>
        <div className="shop-actions">
          <button onClick={onEdit} aria-label={"Edit " + shop.name} className="small-btn">✏️</button>
          <button onClick={onDelete} aria-label={"Delete " + shop.name} className="small-btn">🗑️</button>
        </div>
      </div>
      <p>{shop.description}</p>
      <div className="ads-section">
        <h3>Advertisements</h3>
        <button onClick={onAddAd} aria-label={"Add ad to " + shop.name} className="add-ad-btn">+ Add Ad</button>
        {shop.ads.length === 0 && <p>No ads yet.</p>}
        <ul className="ad-list">
          {shop.ads.map((ad) => (
            <li key={ad.id} className="ad-item">
              <span>{ad.title}</span>
              <div className="ad-actions">
                <button onClick={() => onEditAd(ad)} aria-label={"Edit ad " + ad.title} className="small-btn">✏️</button>
                <button onClick={() => onDeleteAd(ad.id)} aria-label={"Delete ad " + ad.title} className="small-btn">🗑️</button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}