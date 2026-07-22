import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { BarChart3, BookOpen, Camera, ClipboardList, GraduationCap, LayoutDashboard, Pencil, Plus, Users } from 'lucide-react';
import { AnswerOption, ClassRoom, ExamCode, ScannedResult, Student, Exam } from './types';
import { ANSWER_OPTIONS, normalizeAnswerKeyList } from './utils/answerKey';
import Dashboard from './components/Dashboard';
import Analytics from './components/Analytics';
import ClassWorkspace from './components/ClassWorkspace';
import AccessGate from './components/AccessGate';
import ReviewAndEdit from './components/ReviewAndEdit';
import Scanner from './components/Scanner';
import { normalizeStudentName } from './utils/studentIdentity';

type AppTab = 'dashboard' | 'review' | 'analytics' | 'classes' | 'scanner';
type ApiClass = { id: number; code: string; name: string; semester: string | null };
type ApiStudent = { id: number; class_id: number; mssv: string; full_name: string };
type ApiExam = { id: number; class_id: number; title: string; question_count: number };
type ApiExamCode = { id: number; exam_id: number; code: string; answer_key: string[] };
type ApiSubmission = {
  id: number;
  class_id: number;
  exam_id: number;
  exam_code_id?: number | null;
  student_id?: number | null;
  detected_mssv: string;
  detected_name: string;
  detected_exam_code: string;
  answers: string[];
  score: number;
  correct_count: number;
  total_questions: number;
  status: string;
  result_image_url?: string | null;
  source_image_url?: string | null;
  aligned_image_url?: string | null;
  student_info?: Record<string, unknown> | null;
  grading?: Record<string, unknown> | null;
  crops?: Record<string, string | null> | null;
  omr_images?: Record<string, string | null> | null;
  preprocess_images?: Record<string, string | null> | null;
  manual_override?: boolean;
  scanned_at?: string;
  created_at?: string;
  updated_at?: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const ACCESS_SESSION_KEY = 'zipgrade-web-access-granted';

const uid = () => Math.random().toString(36).slice(2, 10);
const isNumericId = (value: string) => /^\d+$/.test(value);
const sleep = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms));
const parseApiTime = (value?: string | null) => {
  const parsed = value ? Date.parse(value) : Number.NaN;
  return Number.isFinite(parsed) ? parsed : Date.now();
};

function isSameReviewIdentity(target: ScannedResult, candidate: ScannedResult) {
  if (target.id === candidate.id || target.submissionId === candidate.submissionId) return false;
  if (target.classId !== candidate.classId || target.examId !== candidate.examId) return false;
  if (target.status !== 'matched' || candidate.status !== 'matched') return false;
  if (target.studentId && candidate.studentId && target.studentId === candidate.studentId) return true;
  const targetName = normalizeStudentName(target.studentName || target.detectedName || '');
  const candidateName = normalizeStudentName(candidate.studentName || candidate.detectedName || '');
  return !!targetName && targetName === candidateName;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const message = await response.text();
    let detail = message;
    try {
      const parsed = JSON.parse(message) as { detail?: string };
      if (parsed?.detail) detail = parsed.detail;
    } catch {
      // Keep raw text when the response is not JSON.
    }
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function apiDelete(path: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: 'DELETE' });
  if (!response.ok && response.status !== 204) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
}

function apiClassToFrontend(item: ApiClass): ClassRoom {
  return {
    id: String(item.id),
    code: item.code,
    name: item.name,
    semester: item.semester ?? '',
    createdAt: Date.now(),
    students: [],
    exams: [],
  };
}

const sanitizeExamCode = (examCode: ExamCode, questionCount: number): ExamCode => ({
  ...examCode,
  answerKey: normalizeAnswerKeyList(examCode.answerKey, questionCount).map(value => value || 'A'),
});

const sanitizeClassRoom = (classRoom: ClassRoom): ClassRoom => ({
  ...classRoom,
  exams: classRoom.exams.map(exam => ({
    ...exam,
    codes: exam.codes.map(code => sanitizeExamCode(code, exam.questionCount)),
  })),
});

async function loadAcademicState(): Promise<{ classes: ClassRoom[]; results: ScannedResult[] }> {
  const [classesRows, studentsRows, examsRows, codesRows, submissionsRows] = await Promise.all([
    apiFetch<ApiClass[]>('/api/v1/classes'),
    apiFetch<ApiStudent[]>('/api/v1/students'),
    apiFetch<ApiExam[]>('/api/v1/exams'),
    apiFetch<ApiExamCode[]>('/api/v1/exam-codes'),
    apiFetch<ApiSubmission[]>('/api/v1/submissions'),
  ]);

  const classMap = new Map<number, ClassRoom>();
  classesRows.forEach((item) => {
    classMap.set(item.id, {
      ...apiClassToFrontend(item),
      students: [],
      exams: [],
    });
  });

  studentsRows.forEach((student) => {
    const target = classMap.get(student.class_id);
    if (target) {
      target.students.push({
        id: String(student.id),
        classId: String(student.class_id),
        mssv: student.mssv,
        fullName: student.full_name,
      });
    }
  });

  const examMap = new Map<number, Exam>();
  examsRows.forEach((exam) => {
    const targetClass = classMap.get(exam.class_id);
    if (!targetClass) return;
    const frontendExam: Exam = {
      id: String(exam.id),
      classId: String(exam.class_id),
      title: exam.title,
      questionCount: exam.question_count,
      codes: [],
      createdAt: Date.now(),
    };
    targetClass.exams.push(frontendExam);
    examMap.set(exam.id, frontendExam);
  });

  codesRows.forEach((code) => {
    const targetExam = examMap.get(code.exam_id);
    if (!targetExam) return;
    targetExam.codes.push({
      id: String(code.id),
      examId: String(code.exam_id),
      code: code.code,
      answerKey: normalizeAnswerKeyList(code.answer_key, targetExam.questionCount).map(value => value || 'A'),
    });
  });

  const results = submissionsRows.map((item) => ({
    id: String(item.id),
    submissionId: String(item.id),
    classId: String(item.class_id),
    examId: String(item.exam_id),
    studentId: item.student_id != null ? String(item.student_id) : undefined,
    studentMssv: item.detected_mssv,
    studentName: item.detected_name,
    detectedName: item.detected_name,
    examCode: item.detected_exam_code,
    score: item.score,
    correctCount: item.correct_count,
    totalQuestions: item.total_questions,
    answers: Object.fromEntries((item.answers ?? []).map((answer, index) => [index + 1, answer || null])),
    resultImageUrl: item.result_image_url ?? null,
    sourceImageUrl: item.source_image_url ?? null,
    alignedImageUrl: item.aligned_image_url ?? null,
    crops: item.crops ?? null,
    omrImages: item.omr_images ?? null,
    preprocessImages: item.preprocess_images ?? null,
    scannedAt: parseApiTime(item.updated_at ?? item.scanned_at ?? item.created_at),
    status: item.status as 'matched' | 'unmatched' | 'unknown_code',
    isEdited: item.manual_override ?? false,
  } satisfies ScannedResult));

  return {
    classes: Array.from(classMap.values()),
    results,
  };
}

async function loadAcademicStateWithRetry(maxAttempts = 5, delayMs = 1200): Promise<{ classes: ClassRoom[]; results: ScannedResult[] }> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return await loadAcademicState();
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) {
        console.warn(`Academic state load attempt ${attempt} failed. Retrying...`, error);
        await sleep(delayMs);
      }
    }
  }
  throw lastError;
}

async function seedDemoAcademicState(): Promise<void> {
  const classRow = await apiFetch<ApiClass>('/api/v1/classes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      code: 'D21CQCN01-N',
      name: 'Lap trinh ung dung',
      semester: 'HK2 2025-2026',
    }),
  });

  const students = [
    { mssv: '21520001', full_name: 'Nguyen Van An' },
    { mssv: '21520002', full_name: 'Tran Thi Binh' },
    { mssv: '21520003', full_name: 'Le Minh Chau' },
  ];
  await Promise.all(students.map(student => apiFetch('/api/v1/students', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ class_id: classRow.id, ...student }),
  })));

  const examRow = await apiFetch<ApiExam>('/api/v1/exams', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      class_id: classRow.id,
      title: 'Kiem tra giua ky',
      question_count: 45,
    }),
  });

  await Promise.all(['101', '102'].map(code => apiFetch('/api/v1/exam-codes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      exam_id: examRow.id,
      code,
      answer_key: Array.from({ length: 45 }, (_, index) => ANSWER_OPTIONS[index % ANSWER_OPTIONS.length]),
    }),
  })));
}

async function persistAcademicState(classes: ClassRoom[]): Promise<void> {
  for (const classRoom of classes) {
    const classId = isNumericId(classRoom.id)
      ? Number(classRoom.id)
      : (await apiFetch<ApiClass>('/api/v1/classes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code: classRoom.code,
            name: classRoom.name,
            semester: classRoom.semester,
          }),
        })).id;

    if (isNumericId(classRoom.id)) {
      await apiFetch(`/api/v1/classes/${classId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: classRoom.code,
          name: classRoom.name,
          semester: classRoom.semester,
        }),
      });
    }

    for (const student of classRoom.students) {
      if (isNumericId(student.id)) {
        await apiFetch(`/api/v1/students/${Number(student.id)}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            mssv: student.mssv,
            full_name: student.fullName,
          }),
        });
      } else {
        await apiFetch('/api/v1/students', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            class_id: classId,
            mssv: student.mssv,
            full_name: student.fullName,
          }),
        });
      }
    }

    for (const exam of classRoom.exams) {
      const examId = isNumericId(exam.id)
        ? Number(exam.id)
        : (await apiFetch<ApiExam>('/api/v1/exams', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              class_id: classId,
              title: exam.title,
              question_count: exam.questionCount,
            }),
          })).id;

      if (isNumericId(exam.id)) {
        await apiFetch(`/api/v1/exams/${examId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: exam.title,
            question_count: exam.questionCount,
          }),
        });
      }

      for (const code of exam.codes) {
        if (isNumericId(code.id)) {
          await apiFetch(`/api/v1/exam-codes/${Number(code.id)}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              code: code.code,
              answer_key: code.answerKey,
            }),
          });
        } else {
          await apiFetch('/api/v1/exam-codes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              exam_id: examId,
              code: code.code,
              answer_key: code.answerKey,
            }),
          });
        }
      }
    }
  }
}

export default function App() {
  const [isUnlocked, setIsUnlocked] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.sessionStorage.getItem(ACCESS_SESSION_KEY) === '1';
  });
  const [activeTab, setActiveTab] = useState<AppTab>('dashboard');
  const [classes, setClasses] = useState<ClassRoom[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [selectedExamId, setSelectedExamId] = useState<string | null>(null);
  const [results, setResults] = useState<ScannedResult[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const syncTimerRef = useRef<number | null>(null);
  const syncLockRef = useRef(false);
  const dirtyRef = useRef(false);

  useEffect(() => {
    if (!isUnlocked) return;
    let cancelled = false;

    (async () => {
      try {
        let snapshot = await loadAcademicStateWithRetry();
        if (snapshot.classes.length === 0) {
          await seedDemoAcademicState();
          snapshot = await loadAcademicStateWithRetry();
        }
        if (cancelled) return;
        dirtyRef.current = false;
        setClasses(snapshot.classes.map(sanitizeClassRoom));
        setResults(snapshot.results);
        setSelectedClassId(snapshot.classes[0]?.id ?? null);
        setSelectedExamId(snapshot.classes[0]?.exams[0]?.id ?? null);
      } catch (error) {
        console.error('Failed to load academic state:', error);
        if (!cancelled) {
          setClasses([]);
          setResults([]);
          setSelectedClassId(null);
          setSelectedExamId(null);
        }
      } finally {
        if (!cancelled) setHydrated(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isUnlocked]);

  useEffect(() => {
    if (!isUnlocked) return;
    if (!hydrated || syncLockRef.current || !dirtyRef.current) return;
    if (syncTimerRef.current) window.clearTimeout(syncTimerRef.current);
    syncTimerRef.current = window.setTimeout(async () => {
      try {
        syncLockRef.current = true;
        await persistAcademicState(classes);
        const snapshot = await loadAcademicState();
        dirtyRef.current = false;
        setClasses(snapshot.classes.map(sanitizeClassRoom));
        setResults(snapshot.results);
        setSelectedClassId(currentSelectedClassId =>
          snapshot.classes.some(item => item.id === currentSelectedClassId)
            ? currentSelectedClassId
            : snapshot.classes[0]?.id ?? null
        );
        setSelectedExamId(currentSelectedExamId => {
          const currentClass = snapshot.classes.find(item => item.id === selectedClassId) ?? snapshot.classes[0];
          if (!currentClass) return null;
          return currentClass.exams.some(exam => exam.id === currentSelectedExamId)
            ? currentSelectedExamId
            : currentClass.exams[0]?.id ?? null;
        });
      } catch (error) {
        console.error('Failed to sync academic state:', error);
        const message = error instanceof Error ? error.message : 'Failed to sync academic state.';
        if (message.toLowerCase().includes('duplicate student id')) {
          alert('Import rejected: duplicate student ID already exists in this class.');
        } else {
          alert(message);
        }
        try {
          const snapshot = await loadAcademicState();
          dirtyRef.current = false;
          setClasses(snapshot.classes.map(sanitizeClassRoom));
          setResults(snapshot.results);
        } catch (reloadError) {
          console.error('Failed to reload academic state after sync error:', reloadError);
        }
      } finally {
        syncLockRef.current = false;
      }
    }, 700);

    return () => {
      if (syncTimerRef.current) window.clearTimeout(syncTimerRef.current);
    };
  }, [classes, hydrated, isUnlocked]);

  const selectedClass = useMemo(
    () => classes.find(item => item.id === selectedClassId) ?? classes[0] ?? null,
    [classes, selectedClassId]
  );
  const selectedExam = useMemo(
    () => selectedClass?.exams.find(exam => exam.id === selectedExamId) ?? selectedClass?.exams[0] ?? null,
    [selectedClass, selectedExamId]
  );

  const createClass = () => {
    dirtyRef.current = true;
    const classId = uid();
    const newClass: ClassRoom = {
      id: classId,
      code: `CLASS-${classes.length + 1}`,
      name: `Lop moi ${classes.length + 1}`,
      semester: 'HK2 2025-2026',
      students: [],
      exams: [],
      createdAt: Date.now(),
    };
    setClasses([newClass, ...classes]);
    setSelectedClassId(classId);
    setSelectedExamId(null);
    setActiveTab('classes');
  };

  const cancelPendingSync = () => {
    dirtyRef.current = false;
    if (syncTimerRef.current) {
      window.clearTimeout(syncTimerRef.current);
      syncTimerRef.current = null;
    }
  };

  const updateClass = (updated: ClassRoom) => {
    dirtyRef.current = true;
    const sanitized = sanitizeClassRoom(updated);
    setClasses(classes.map(item => (item.id === sanitized.id ? sanitized : item)));
    setSelectedClassId(sanitized.id);
    if (!sanitized.exams.some(exam => exam.id === selectedExamId)) {
      setSelectedExamId(sanitized.exams[0]?.id ?? null);
    }
  };

  const deleteClass = async (classId: string) => {
    if (!window.confirm('Delete this class and all its students, exams, and submissions?')) return;
    try {
      cancelPendingSync();
      if (isNumericId(classId)) {
        await apiDelete(`/api/v1/classes/${Number(classId)}`);
      }
      setClasses((prev) => {
        const next = prev.filter(item => item.id !== classId);
        const currentClass = next.find(item => item.id === selectedClassId) ?? next[0] ?? null;
        const currentExam = currentClass?.exams.find(exam => exam.id === selectedExamId) ?? currentClass?.exams[0] ?? null;
        setSelectedClassId(currentClass?.id ?? null);
        setSelectedExamId(currentExam?.id ?? null);
        return next;
      });
      setResults(prev => prev.filter(result => result.classId !== classId));
    } catch (error) {
      console.error('Failed to delete class:', error);
      alert('Failed to delete class.');
    }
  };

  const deleteStudent = async (classId: string, studentId: string) => {
    if (!window.confirm('Delete this student?')) return;
    try {
      cancelPendingSync();
      if (isNumericId(studentId)) {
        await apiDelete(`/api/v1/students/${Number(studentId)}`);
      }
      setClasses(prev => prev.map(classRoom => (
        classRoom.id === classId
          ? { ...classRoom, students: classRoom.students.filter(student => student.id !== studentId) }
          : classRoom
      )));
    } catch (error) {
      console.error('Failed to delete student:', error);
      alert('Failed to delete student.');
    }
  };

  const deleteExam = async (classId: string, examId: string) => {
    if (!window.confirm('Delete this exam and all its exam codes and submissions?')) return;
    try {
      cancelPendingSync();
      if (isNumericId(examId)) {
        await apiDelete(`/api/v1/exams/${Number(examId)}`);
      }
      setClasses(prev => {
        const next = prev.map(classRoom => (
          classRoom.id === classId
            ? { ...classRoom, exams: classRoom.exams.filter(exam => exam.id !== examId) }
            : classRoom
        ));
        const currentClass = next.find(item => item.id === selectedClassId) ?? next[0] ?? null;
        const currentExam = currentClass?.exams.find(exam => exam.id === selectedExamId) ?? currentClass?.exams[0] ?? null;
        setSelectedClassId(currentClass?.id ?? null);
        setSelectedExamId(currentExam?.id ?? null);
        return next;
      });
      setResults(prev => prev.filter(result => result.examId !== examId));
    } catch (error) {
      console.error('Failed to delete exam:', error);
      alert('Failed to delete exam.');
    }
  };

  const deleteExamCode = async (classId: string, examId: string, examCodeId: string) => {
    if (!window.confirm('Delete this exam code?')) return;
    try {
      cancelPendingSync();
      if (isNumericId(examCodeId)) {
        await apiDelete(`/api/v1/exam-codes/${Number(examCodeId)}`);
      }
      setClasses(prev => prev.map(classRoom => (
        classRoom.id === classId
          ? {
              ...classRoom,
              exams: classRoom.exams.map(exam => (
                exam.id === examId
                  ? { ...exam, codes: exam.codes.filter(code => code.id !== examCodeId) }
                  : exam
              )),
            }
          : classRoom
      )));
    } catch (error) {
      console.error('Failed to delete exam code:', error);
      alert('Failed to delete exam code.');
    }
  };

  const deleteResult = async (resultId: string, submissionId?: string) => {
    if (!window.confirm('Delete this scan history entry?')) return;
    try {
      const backendSubmissionId = submissionId ?? (isNumericId(resultId) ? resultId : null);
      if (backendSubmissionId && isNumericId(backendSubmissionId)) {
        await apiDelete(`/api/v1/submissions/${Number(backendSubmissionId)}`);
      }
      setResults(prev => prev.filter(result => result.id !== resultId));
    } catch (error) {
      console.error('Failed to delete result:', error);
      alert('Failed to delete scan history entry.');
    }
  };

  const updateResult = async (updatedResult: ScannedResult) => {
    try {
      const currentExam = classes.flatMap(item => item.exams).find(exam => exam.id === updatedResult.examId) ?? null;
      const currentCode = currentExam?.codes.find(code => code.code === updatedResult.examCode) ?? null;
      const backendSubmissionId = updatedResult.submissionId ?? updatedResult.id;

      if (backendSubmissionId && isNumericId(backendSubmissionId)) {
        await apiFetch(`/api/v1/submissions/${Number(backendSubmissionId)}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            class_id: Number(updatedResult.classId),
            exam_id: Number(updatedResult.examId),
            exam_code_id: currentCode?.id ? Number(currentCode.id) : null,
            student_id: updatedResult.studentId && isNumericId(updatedResult.studentId) ? Number(updatedResult.studentId) : null,
            detected_mssv: updatedResult.studentMssv,
            detected_name: updatedResult.studentName,
            detected_exam_code: updatedResult.examCode,
            answers: Object.keys(updatedResult.answers)
              .map(Number)
              .sort((a, b) => a - b)
              .map((key) => updatedResult.answers[key] ?? ''),
            score: updatedResult.score,
            correct_count: updatedResult.correctCount,
            total_questions: updatedResult.totalQuestions,
            status: updatedResult.status,
            manual_override: true,
          }),
        });
      }

      const duplicates = results.filter(item => isSameReviewIdentity(updatedResult, item));
      await Promise.all(
        duplicates
          .map(item => item.submissionId ?? item.id)
          .filter((id): id is string => !!id && isNumericId(id))
          .map(id => apiDelete(`/api/v1/submissions/${Number(id)}`))
      );

      setResults(prev => [
        { ...updatedResult, isEdited: true },
        ...prev.filter(item =>
          item.id !== updatedResult.id
          && item.submissionId !== updatedResult.submissionId
          && !isSameReviewIdentity(updatedResult, item)
        ),
      ]);
    } catch (error) {
      console.error('Failed to update result:', error);
      alert('Failed to update review result.');
    }
  };

  const startScanner = (classId?: string, examId?: string) => {
    if (classId) setSelectedClassId(classId);
    if (examId) setSelectedExamId(examId);
    setActiveTab('scanner');
  };

  const handleUnlock = (password: string) => {
    const requiredPassword = import.meta.env.VITE_APP_LOCK_PASSWORD ?? '123456';
    if (password !== requiredPassword) {
      return false;
    }
    window.sessionStorage.setItem(ACCESS_SESSION_KEY, '1');
    setIsUnlocked(true);
    return true;
  };

  if (!isUnlocked) {
    return <AccessGate onUnlock={handleUnlock} />;
  }

  return (
    <div className="flex flex-col md:grid md:grid-cols-[240px_1fr] min-h-[100dvh] bg-app-bg text-[#1e293b] overflow-x-hidden">
      <nav className="hidden md:flex flex-col bg-sidebar text-[#f8fafc] p-6 border-r border-[#334155]">
        <div className="flex items-center gap-2 text-xl font-bold mb-10 text-[#38bdf8]">
          <GraduationCap size={24} />
          GradeHub
        </div>

        <div className="flex flex-col gap-1.5">
          <NavButton active={activeTab === 'dashboard'} icon={<LayoutDashboard size={18} />} label="Dashboard" onClick={() => setActiveTab('dashboard')} />
          <NavButton active={activeTab === 'review'} icon={<Pencil size={18} />} label="Review & Edit" onClick={() => setActiveTab('review')} />
          <NavButton active={activeTab === 'analytics'} icon={<BarChart3 size={18} />} label="Analytics" onClick={() => setActiveTab('analytics')} />
          <NavButton active={activeTab === 'classes'} icon={<BookOpen size={18} />} label="My Quizzes" onClick={() => setActiveTab('classes')} />
          <NavButton active={activeTab === 'scanner'} icon={<Camera size={18} />} label="Scanner" onClick={() => setActiveTab('scanner')} />
        </div>

        <button
          onClick={() => startScanner()}
          className="mt-10 bg-primary text-white flex items-center justify-center gap-2 rounded-lg py-3 font-semibold shadow-lg shadow-blue-900/40 hover:bg-blue-600 transition-all active:scale-95"
        >
          <Camera size={20} />
          <span>Scan Papers</span>
        </button>

        <div className="mt-auto p-4 bg-[#334155]/40 rounded-xl flex items-center gap-3 border border-white/5">
          <div className="w-10 h-10 rounded-full bg-[#38bdf8]/20 flex items-center justify-center text-[#38bdf8] font-bold text-sm">GV</div>
          <div className="truncate">
            <p className="text-sm font-bold truncate">Teacher Workspace</p>
            <p className="text-[10px] text-gray-400 font-medium">{classes.length} classes</p>
          </div>
        </div>
      </nav>

      <div className="md:hidden flex items-center justify-between px-6 py-4 bg-sidebar text-white sticky top-0 z-50">
        <div className="flex items-center gap-2 text-lg font-bold text-[#38bdf8]">
          <GraduationCap size={22} />
          GradeHub
        </div>
        <button onClick={() => setActiveTab('scanner')} className="p-2.5 bg-[#334155] rounded-xl">
          <Camera size={20} />
        </button>
      </div>

      <div className="flex flex-col min-h-0 overflow-hidden">
        <header className="min-h-16 bg-white border-b border-border-light flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 px-4 sm:px-6 lg:px-8 py-4 shrink-0 shadow-sm z-10">
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-[#0f172a]">
              {activeTab === 'dashboard' ? 'Teaching Dashboard' : activeTab === 'review' ? 'Review & Grading Correction' : activeTab === 'analytics' ? 'Overview Statistics' : activeTab === 'classes' ? 'My Quizzes' : 'Scan Answer Sheets'}
            </h1>
            {selectedClass && <p className="text-xs text-slate-400 font-semibold mt-0.5">{selectedClass.code} · {selectedClass.name}</p>}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button onClick={createClass} className="btn-outline text-sm flex items-center gap-2">
              <Plus size={16} />
              New Class
            </button>
            <button onClick={() => startScanner()} className="btn-primary text-sm flex items-center gap-2">
              <Camera size={16} />
              Scan
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-4 pb-24 sm:p-6 lg:p-10">
          <div className="max-w-7xl mx-auto w-full">
            <AnimatePresence mode="wait">
              {activeTab === 'dashboard' && (
                <motion.div key="dashboard" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                  <Dashboard
                    classes={classes}
                    results={results}
                    onStartScanner={startScanner}
                    onCreateClass={createClass}
                    onDeleteResult={deleteResult}
                  />
                </motion.div>
              )}

              {activeTab === 'review' && (
                <motion.div key="review" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                  <ReviewAndEdit
                    classes={classes}
                    results={results}
                    onUpdateResult={updateResult}
                    onDeleteResult={deleteResult}
                    onStartScanner={startScanner}
                  />
                </motion.div>
              )}

              {activeTab === 'analytics' && (
                <motion.div key="analytics" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                  <Analytics
                    classes={classes}
                    results={results}
                    onStartScanner={startScanner}
                  />
                </motion.div>
              )}

              {activeTab === 'classes' && (
                <motion.div key="classes" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                  <ClassWorkspace
                    classes={classes}
                    selectedClassId={selectedClass?.id ?? null}
                    selectedExamId={selectedExam?.id ?? null}
                    onSelectClass={(id) => {
                      const nextClass = classes.find(item => item.id === id);
                      setSelectedClassId(id);
                      setSelectedExamId(nextClass?.exams[0]?.id ?? null);
                    }}
                    onSelectExam={setSelectedExamId}
                    onCreateClass={createClass}
                    onUpdateClass={updateClass}
                    onStartScanner={startScanner}
                    onDeleteClass={deleteClass}
                    onDeleteStudent={deleteStudent}
                    onDeleteExam={deleteExam}
                    onDeleteExamCode={deleteExamCode}
                  />
                </motion.div>
              )}

              {activeTab === 'scanner' && selectedClass && selectedExam && (
                <motion.div key="scanner" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <Scanner
                    classes={classes}
                    existingResults={results}
                    selectedClassId={selectedClass.id}
                    selectedExamId={selectedExam.id}
                    onSelectContext={(classId, examId) => {
                      setSelectedClassId(classId);
                      setSelectedExamId(examId);
                    }}
                    onResult={(res) => setResults(prev => [res, ...prev.filter(item => item.submissionId !== res.submissionId && item.id !== res.id)])}
                    onClose={() => setActiveTab('dashboard')}
                  />
                </motion.div>
              )}

              {activeTab === 'scanner' && (!selectedClass || !selectedExam) && (
                <motion.div key="empty-scanner" className="card p-16 text-center" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <Users size={48} className="mx-auto text-slate-300 mb-4" />
                  <h2 className="text-2xl font-black text-slate-800">Create a class and exam first</h2>
                  <p className="text-slate-500 mt-2">Scanner needs a class roster and at least one exam with exam-code answer keys.</p>
                  <button onClick={() => setActiveTab('classes')} className="btn-primary mt-8">Go to Classes</button>
                </motion.div>
              )}

            </AnimatePresence>
          </div>
        </main>
      </div>

      <nav className="md:hidden grid grid-cols-5 bg-white border-t border-border-light fixed bottom-0 left-0 right-0 z-50 h-16 shadow-[0_-4px_12px_rgba(0,0,0,0.05)]">
        <MobileNavButton active={activeTab === 'dashboard'} icon={<LayoutDashboard size={20} />} onClick={() => setActiveTab('dashboard')} />
        <MobileNavButton active={activeTab === 'review'} icon={<Pencil size={20} />} onClick={() => setActiveTab('review')} />
        <MobileNavButton active={activeTab === 'analytics'} icon={<BarChart3 size={20} />} onClick={() => setActiveTab('analytics')} />
        <MobileNavButton active={activeTab === 'classes'} icon={<ClipboardList size={20} />} onClick={() => setActiveTab('classes')} />
        <MobileNavButton active={activeTab === 'scanner'} icon={<Camera size={20} />} onClick={() => setActiveTab('scanner')} />
      </nav>
    </div>
  );
}

function NavButton({ active, icon, label, onClick }: { active: boolean; icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${active ? 'bg-[#334155] text-white shadow-xl' : 'text-[#f8fafc]/60 hover:bg-[#273548] hover:text-white'}`}
    >
      <span className={active ? 'text-[#38bdf8]' : 'text-current'}>{icon}</span>
      <span>{label}</span>
      {active && <div className="ml-auto w-1 h-4 bg-[#38bdf8] rounded-full" />}
    </button>
  );
}

function MobileNavButton({ active, icon, onClick }: { active: boolean; icon: React.ReactNode; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center justify-center transition-colors ${active ? 'text-primary' : 'text-slate-400'}`}
    >
      <div className={`p-2.5 rounded-xl ${active ? 'bg-blue-50' : ''}`}>
        {icon}
      </div>
    </button>
  );
}
