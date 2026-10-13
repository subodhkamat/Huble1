import { useState } from 'react';

export default function SearchBar({ value, onChange }) {
  return (
    <input
      type="search"
      placeholder="Search videos"
      aria-label="Search videos"
      className="search-bar"
      value={value}
      onChange={e => onChange(e.target.value)}
    />
  );
}