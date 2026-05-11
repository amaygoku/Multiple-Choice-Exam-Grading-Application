export type AnswerOption = 'A' | 'B' | 'C' | 'D' | 'E';

export interface Student {
  id: string;
  classId: string;
  mssv: string;
  fullName: string;
}

export interface ExamCode {
  id: string;
  examId: string;
  code: string;
  answerKey: AnswerOption[];
}

export interface Exam {
  id: string;
  classId: string;
  title: string;
  questionCount: number;
  codes: ExamCode[];
  createdAt: number;
}

export interface ClassRoom {
  id: string;
  code: string;
  name: string;
  semester: string;
  students: Student[];
  exams: Exam[];
  createdAt: number;
}

export interface ScannedResult {
  id: string;
  classId: string;
  examId: string;
  studentId?: string;
  studentMssv: string;
  studentName: string;
  detectedName: string;
  examCode: string;
  score: number;
  correctCount: number;
  totalQuestions: number;
  answers: Record<number, string | null>;
  resultImageUrl?: string | null;
  crops?: BackendProcessResponse['crops'];
  details?: BackendQuestionDetail[];
  scannedAt: number;
  status: 'matched' | 'unmatched' | 'unknown_code';
}

export interface BackendStudentInfo {
  mssv: string;
  ma_de: string;
  name: string;
}

export interface BackendQuestionDetail {
  question: number;
  student_ans: string;
  correct_ans: string;
  result: string;
  is_correct: boolean;
}

export interface BackendGradingResult {
  score: number;
  correct_count: number;
  total: number;
  details: BackendQuestionDetail[];
}

export interface BackendProcessResponse {
  success: boolean;
  message?: string;
  student_info?: BackendStudentInfo | null;
  answers?: string[] | null;
  grading?: BackendGradingResult | null;
  result_image_url?: string | null;
  crops?: {
    ho_va_ten?: string | null;
    lop?: string | null;
    mssv?: string | null;
    ma_de?: string | null;
  } | null;
  error?: string | null;
}

export interface Point {
  x: number;
  y: number;
}

export interface Question {
  id: number;
  correctAnswer: AnswerOption;
  weight: number;
}

export interface Quiz {
  id: string;
  name: string;
  count: number;
  questions: Question[];
  createdAt: number;
}
