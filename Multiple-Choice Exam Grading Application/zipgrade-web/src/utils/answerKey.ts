import type { AnswerOption } from '../types';

export const ANSWER_OPTIONS: AnswerOption[] = ['A', 'B', 'C', 'D'];

export const normalizeAnswerKeyValue = (value: string) => {
  const unique = new Set<AnswerOption>();
  value
    .toUpperCase()
    .replace(/\s+/g, '')
    .split('')
    .forEach((choice) => {
      if ((ANSWER_OPTIONS as readonly string[]).includes(choice)) {
        unique.add(choice as AnswerOption);
      }
    });

  return ANSWER_OPTIONS.filter((choice) => unique.has(choice)).join('');
};

export const toggleAnswerKeyValue = (value: string, option: AnswerOption) => {
  const current = new Set(normalizeAnswerKeyValue(value).split('') as AnswerOption[]);
  if (current.has(option)) {
    current.delete(option);
  } else {
    current.add(option);
  }

  return ANSWER_OPTIONS.filter((choice) => current.has(choice)).join('');
};

export const normalizeAnswerKeyList = (values: string[] | null | undefined, totalQuestions: number) => {
  const list = Array.isArray(values) ? values.slice(0, totalQuestions) : [];
  return Array.from({ length: totalQuestions }, (_, index) => normalizeAnswerKeyValue(list[index] ?? ''));
};
