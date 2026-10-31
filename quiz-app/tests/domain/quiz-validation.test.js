import test from 'node:test';
import assert from 'node:assert/strict';
import { validateQuizData } from '../../src/utils/utils.js';

const validQuiz = () => ({
  questions: [
    {
      question: 'What is the capital of France?',
      options: ['London', 'Paris', 'Berlin'],
      correctAnswer: 1,
      explanation: 'Paris is the capital of France.',
    },
    {
      question: 'Which are JavaScript runtimes?',
      options: ['Node.js', 'Django', 'Deno', 'Rails'],
      correctAnswer: [0, 2],
      shuffle: 0,
    },
  ],
});

test('accepts a valid quiz containing single-choice and multiple-choice questions', () => {
  assert.equal(validateQuizData(validQuiz()), null);
});

test('requires a top-level questions array', () => {
  assert.equal(validateQuizData({}), 'Định dạng không hợp lệ: thiếu mảng "questions"');
  assert.equal(validateQuizData({ questions: 'not-an-array' }), 'Định dạng không hợp lệ: thiếu mảng "questions"');
});

test('requires each question to include non-empty text, options, and correctAnswer', () => {
  const cases = [
    { question: '', options: ['A', 'B'], correctAnswer: 0 },
    { question: '   ', options: ['A', 'B'], correctAnswer: 0 },
    { options: ['A', 'B'], correctAnswer: 0 },
    { question: 'Missing options', correctAnswer: 0 },
    { question: 'Missing answer', options: ['A', 'B'] },
  ];

  for (const question of cases) {
    assert.equal(
      validateQuizData({ questions: [question] }),
      'Định dạng câu hỏi không hợp lệ ở vị trí 0',
    );
  }
});

test('requires at least two non-empty string options per question', () => {
  assert.equal(
    validateQuizData({ questions: [{ question: 'Only one?', options: ['A'], correctAnswer: 0 }] }),
    'Câu 0 phải có ít nhất 2 đáp án',
  );

  for (const options of [['A', ''], ['A', '   '], ['A', 2]]) {
    assert.equal(
      validateQuizData({ questions: [{ question: 'Bad option?', options, correctAnswer: 0 }] }),
      'Câu 0 có đáp án không hợp lệ',
    );
  }
});

test('requires single-choice correctAnswer to be an integer option index', () => {
  const invalidAnswers = [-1, 2, 1.5, '1', Number.NaN, Number.POSITIVE_INFINITY];

  for (const correctAnswer of invalidAnswers) {
    assert.equal(
      validateQuizData({ questions: [{ question: 'Pick one', options: ['A', 'B'], correctAnswer }] }),
      'Chỉ số correctAnswer của câu 0 không hợp lệ',
    );
  }
});

test('requires multiple-choice correctAnswer to contain unique integer option indices', () => {
  assert.equal(
    validateQuizData({ questions: [{ question: 'Pick many', options: ['A', 'B'], correctAnswer: [] }] }),
    'Câu 0 phải có ít nhất một đáp án đúng',
  );

  assert.equal(
    validateQuizData({ questions: [{ question: 'Pick many', options: ['A', 'B'], correctAnswer: [0, 2] }] }),
    'Chỉ số 2 trong correctAnswer của câu 0 không hợp lệ',
  );

  assert.equal(
    validateQuizData({ questions: [{ question: 'Pick many', options: ['A', 'B'], correctAnswer: [0, '1'] }] }),
    'Chỉ số 1 trong correctAnswer của câu 0 không hợp lệ',
  );

  assert.equal(
    validateQuizData({ questions: [{ question: 'Pick many', options: ['A', 'B'], correctAnswer: [0, 0] }] }),
    'Chỉ số 0 bị lặp trong correctAnswer của câu 0',
  );
});

test('accepts a one-item correctAnswer array because it behaves as single choice', () => {
  assert.equal(
    validateQuizData({ questions: [{ question: 'Pick one', options: ['A', 'B'], correctAnswer: [1] }] }),
    null,
  );
});
