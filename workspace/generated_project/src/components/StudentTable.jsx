import React from 'react';

const StudentTable = ({ students, onDelete }) => {
  if (!students.length) {
    return <p>No students added yet.</p>;
  }

  return (
    <div className="responsive-table" aria-label="Student List">
      <table className="student-table">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Age</th>
            <th scope="col">Grade</th>
            <th scope="col">Email</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {students.map((student) => (
            <tr key={student.id}>
              <td>{student.name}</td>
              <td>{student.age}</td>
              <td>{student.grade}</td>
              <td>{student.email}</td>
              <td>
                <button
                  onClick={() => onDelete(student.id)}
                  aria-label={`Delete ${student.name}`}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default StudentTable