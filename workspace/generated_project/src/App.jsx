import React, { useState } from 'react';
import {
  format,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  addMonths,
  subMonths,
  isSameMonth,
  getDay,
  isSameDay,
} from 'date-fns';

const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const Calendar = () => {
  const today = new Date();
  const [currentDate, setCurrentDate] = useState(today);

  const monthStart = startOfMonth(currentDate);
  const monthEnd = endOfMonth(monthStart);
  const days = eachDayOfInterval({ start: monthStart, end: monthEnd });

  const handlePrev = () => setCurrentDate(subMonths(currentDate, 1));
  const handleNext = () => setCurrentDate(addMonths(currentDate, 1));
  const handleToday = () => setCurrentDate(today);

  const isToday = (day) => isSameDay(day, today);

  return (
    <div className="calendar">
      <header className="calendar-header">
        <button
          onClick={handlePrev}
          aria-label="Previous month"
          className="nav-button"
        >
          ‹
        </button>
        <h2>{format(monthStart, 'MMMM yyyy')}</h2>
        <button
          onClick={handleNext}
          aria-label="Next month"
          className="nav-button"
        >
          ›
        </button>
        <button
          onClick={handleToday}
          aria-label="Today"
          className="nav-button nav-button--today"
        >
          Today
        </button>
      </header>
      <section className="calendar-grid">
        {weekdays.map((day) => (
          <div key={day} className="calendar-weekday">
            {day}
          </div>
        ))}
        {days.map((day) => (
          <div
            key={day}
            className={`calendar-day ${isSameMonth(day, monthStart) ? '' : 'calendar-day--disabled'} ${isToday(day) ? 'calendar-day--today' : ''}`}
          >
            {format(day, 'd')}
          </div>
        ))}
      </section>
    </div>
  );
};

const App = () => (
  <div className="app">
    <h1>My Calendar</h1>
    <Calendar />
  </div>
);

export default App;