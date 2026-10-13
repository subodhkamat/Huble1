import React, { useState } from 'react';

const choices = ['Rock', 'Paper', 'Scissors'];

function getComputerChoice() {
  const index = Math.floor(Math.random() * choices.length);
  return choices[index];
}

function determineWinner(player, computer) {
  if (player === computer) return 'Tie';
  if (
    (player === 'Rock' && computer === 'Scissors') ||
    (player === 'Paper' && computer === 'Rock') ||
    (player === 'Scissors' && computer === 'Paper')
  ) {
    return 'You win!';
  }
  return 'You lose!';
}

function ChoiceButton({ choice, onClick }) {
  return (
    <button className="choice-button" onClick={() => onClick(choice)} aria-label={choice}>
      {choice}
    </button>
  );
}

export default function App() {
  const [playerChoice, setPlayerChoice] = useState(null);
  const [computerChoice, setComputerChoice] = useState(null);
  const [result, setResult] = useState('');

  const handleChoice = (choice) => {
    const comp = getComputerChoice();
    setPlayerChoice(choice);
    setComputerChoice(comp);
    setResult(determineWinner(choice, comp));
  };

  const handleReset = () => {
    setPlayerChoice(null);
    setComputerChoice(null);
    setResult('');
  };

  return (
    <main className="app">
      <h1>Stone Paper Scissors</h1>
      <div className="choices">
        {choices.map((c) => (
          <ChoiceButton key={c} choice={c} onClick={handleChoice} />
        ))}
      </div>
      {result && (
        <section className="result">
          <p>You chose <strong>{playerChoice}</strong></p>
          <p>Computer chose <strong>{computerChoice}</strong></p>
          <h2>{result}</h2>
          <button className="reset-button" onClick={handleReset}>
            Play Again
          </button>
        </section>
      )}
    </main>
  );
}