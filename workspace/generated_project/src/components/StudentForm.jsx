import React, { useState } from 'react';

const StudentForm = ({ onAdd }) => {
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [grade, setGrade] = useState('');
  const [email, setEmail] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name || !age || !grade || !email) return;
    onAdd({ name, age, grade, email });
    setName('');
    setAge('');
    setGrade('');
    setEmail('');
  };

  return (
    <form className="student-form" onSubmit={handleSubmit} aria-label="Add Student Form">
      <div>
        <label htmlFor="name">Name</label>
        <input
          type="text"
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          aria-required="true"
        />
      </div>
      <div>
        <label htmlFor="age">Age</label>
        <input
          type="number"
          id="age"
          value={age}
          onChange={(e) => setAge(e.target.value)}
          required
          min="1"
          aria-required="true"
        />
      </div>
      <div>
        <label htmlFor="grade">Grade</label>
        <input
          type="text"
          id="grade"
          value={grade}
          onChange={(e) => setGrade(e.target.value)}
          required
          aria-required="true"
        />
      </div>
      <div>
        <label htmlFor="email">Email</label>
        <input
          type="email"
          id="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          aria-required="true"
        />
      </div>
      <button type="submit">Add Student</button>
    </form>
  );
};

export default StudentForm;