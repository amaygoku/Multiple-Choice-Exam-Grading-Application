import { normalizeAnswerKeyValue } from './answerKey';
import type { BackendGradingResult } from '../types';

export function gradeAnswers(studentAnswers: string[], correctAnswers: string[]): BackendGradingResult {
  const total = correctAnswers.length;
  if (total === 0) {
    return { score: 0, correct_count: 0, total: 0, details: [] };
  }

  let correctCount = 0;
  const details = correctAnswers.map((correctAns, index) => {
    const studentAns = normalizeAnswerKeyValue(studentAnswers[index] ?? '');
    const normalizedCorrect = normalizeAnswerKeyValue(correctAns ?? '');
    const studentSet = new Set(studentAns.split('').filter(Boolean));
    const correctSet = new Set(normalizedCorrect.split('').filter(Boolean));

    let result = 'WRONG';
    let isCorrect = false;
    let score = 0;

    if (studentSet.size === 0) {
      result = 'BLANK';
    } else if (![...studentSet].every(item => correctSet.has(item))) {
      result = 'WRONG';
    } else if (studentSet.size === correctSet.size && [...studentSet].every(item => correctSet.has(item))) {
      result = 'CORRECT';
      isCorrect = true;
      score = 1;
      correctCount += 1;
    } else if (correctSet.size > 0) {
      score = studentSet.size / correctSet.size;
      result = 'PARTIAL';
      correctCount += score;
    }

    return {
      question: index + 1,
      student_ans: studentAns || 'Blank',
      correct_ans: normalizedCorrect,
      result,
      is_correct: isCorrect || score > 0,
    };
  });

  const score = total > 0 ? (correctCount / total) * 10 : 0;
  return {
    score: Number(score.toFixed(2)),
    correct_count: Number(correctCount.toFixed(2)),
    total,
    details,
  };
}
