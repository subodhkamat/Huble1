import React, { useState, useEffect } from 'react';

function Clock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const tick = () => setTime(new Date());
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const pad = (num) => String(num).padStart(2, '0');
  const hours = pad(time.getHours());
  const minutes = pad(time.getMinutes());
  const seconds = pad(time.getSeconds());
  const formattedTime = `${hours}:${minutes}:${seconds}`;

  return (
    <div className="clock" aria-live="polite" aria-atomic="true">
      {formattedTime}
    </div>
  );
}

export default Clock;