import React from 'react';
import ShopItem from './ShopItem.jsx';

export default function ShopList({ shops, onEditShop, onDeleteShop, onAddAd, onEditAd, onDeleteAd }) {
  return (
    <div className="shop-list">
      {shops.map((shop) => (
        <ShopItem
          key={shop.id}
          shop={shop}
          onEdit={() => onEditShop(shop)}
          onDelete={() => onDeleteShop(shop.id)}
          onAddAd={() => onAddAd(shop.id)}
          onEditAd={(ad) => onEditAd(shop.id, ad)}
          onDeleteAd={(adId) => onDeleteAd(shop.id, adId)}
        />
      ))}
    </div>
  );
}