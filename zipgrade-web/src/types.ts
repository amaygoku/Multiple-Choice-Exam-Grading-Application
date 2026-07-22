export type AnswerOption = 'A' | 'B' | 'C' | 'D';
export type AnswerKeyValue = string;

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
  answerKey: AnswerKeyValue[];
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
  submissionId?: string;
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
  sourceImageUrl?: string | null;
  alignedImageUrl?: string | null;
  crops?: BackendProcessResponse['crops'];
  omrImages?: BackendProcessResponse['omr_images'];
  preprocessImages?: BackendProcessResponse['preprocess_images'];
  details?: BackendQuestionDetail[];
  scannedAt: number;
  status: 'matched' | 'unmatched' | 'unknown_code';
  isEdited?: boolean;
}

export interface BackendStudentInfo {
  mssv: string;
  ma_de: string;
  name: string;
  ocr_name?: string;
  matched_name?: string;
  name_source?: string;
  name_similarity?: number;
}

export interface BackendIdentityCandidate {
  student_id: number;
  full_name: string;
  mssv: string;
  reasons: string[];
  name_similarity: number;
  has_existing_submission: boolean;
  existing_submission_id?: number | null;
}

export interface BackendIdentityResolution {
  detected_mssv: string;
  ocr_name: string;
  needs_user_selection: boolean;
  reason: string;
  candidates: BackendIdentityCandidate[];
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
  submission_id?: number | null;
  student_info?: BackendStudentInfo | null;
  identity_resolution?: BackendIdentityResolution | null;
  answers?: string[] | null;
  grading?: BackendGradingResult | null;
  result_image_url?: string | null;
  crops?: {
    ho_va_ten?: string | null;
    lop?: string | null;
    mssv?: string | null;
    ma_de?: string | null;
  } | null;
  omr_images?: {
    answer_1?: string | null;
    answer_2?: string | null;
    answer_3?: string | null;
    student_id?: string | null;
    exam_code?: string | null;
  } | null;
  preprocess_images?: Record<string, string | null> | null;
  error?: string | null;
}

export interface Point {
  x: number;
  y: number;
}

export interface Question {
  id: number;
  correctAnswer: AnswerKeyValue;
  weight: number;
}

export interface Quiz {
  id: string;
  name: string;
  count: number;
  questions: Question[];
  createdAt: number;
}
