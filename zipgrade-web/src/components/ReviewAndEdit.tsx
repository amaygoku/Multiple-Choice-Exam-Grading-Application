import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRightLeft,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Edit3,
  Eye,
  Filter,
  Image as ImageIcon,
  Loader2,
  Search,
  User,
  ShieldAlert,
  Trash2,
  X,
} from 'lucide-react';
import { ANSWER_OPTIONS, normalizeAnswerKeyValue } from '../utils/answerKey';
import { gradeAnswers } from '../utils/grading';
import { AnswerOption, ClassRoom, ScannedResult } from '../types';
import { isStudentNameMatch } from '../utils/studentIdentity';

type StatusFilter = 'all' | 'matched' | 'unmatched' | 'unknown_code' | 'edited';
type EditorTab = 'answers' | 'student' | 'crops';

interface ReviewAndEditProps {
  classes: ClassRoom[];
  results: ScannedResult[];
  onUpdateResult: (result: ScannedResult) => void | Promise<void>;
  onDeleteResult: (resultId: string, submissionId?: string) => void | Promise<void>;
  onStartScanner: (classId?: string, examId?: string) => void;
}

interface ReviewDraft {
  classId: string;
  examId: string;
  examCode: string;
  studentId?: string;
  studentMssv: string;
  studentName: string;
  answers: string[];
}

const statusLabels: Record<StatusFilter, string> = {
  all: 'All',
  matched: 'Matched',
  unmatched: 'Unmatched',
  unknown_code: 'Unknown code',
  edited: 'Edited',
};

const statusColors: Record<string, string> = {
  matched: 'bg-emerald-500/15 text-emerald-600 border-emerald-200',
  unmatched: 'bg-amber-500/15 text-amber-700 border-amber-200',
  unknown_code: 'bg-rose-500/15 text-rose-700 border-rose-200',
  edited: 'bg-indigo-500/15 text-indigo-600 border-indigo-200',
};

const answerOrder: Record<AnswerOption, number> = {
  A: 0,
  B: 1,
  C: 2,
  D: 3,
};

function resolveBackendUrl(url?: string | null) {
  if (!url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? '';
  return `${apiBase}${url.startsWith('/') ? url : `/${url}`}`;
}

function normalizeAnswers(raw: Record<number, string | null> | undefined, total: number) {
  return Array.from({ length: total }, (_, index) => raw?.[index + 1] ?? '');
}

function answerLabel(value: string) {
  const normalized = normalizeAnswerKeyValue(value || '');
  return normalized || 'Blank';
}

function scoreLabel(result: ScannedResult) {
  return `${result.score.toFixed(2)}/10`;
}

function submissionOwnerKey(result: ScannedResult) {
  const mssv = String(result.studentMssv ?? '').trim();
  const studentId = String(result.studentId ?? '').trim();
  const detectedName = String(result.detectedName || result.studentName || '').trim().toLowerCase();
  const owner = studentId ? `student:${studentId}` : mssv ? `mssv:${mssv}` : detectedName ? `name:${detectedName}` : `submission:${result.id}`;
  return `${result.classId}::${result.examId}::${owner}`;
}

function keepLatestSubmissions(results: ScannedResult[]) {
  const latest = new Map<string, ScannedResult>();
  [...results]
    .sort((a, b) => b.scannedAt - a.scannedAt)
    .forEach((result) => {
      const key = submissionOwnerKey(result);
      if (!latest.has(key)) latest.set(key, result);
    });
  return Array.from(latest.values()).sort((a, b) => b.scannedAt - a.scannedAt);
}

function rowBorder(active: boolean) {
  return active
    ? 'border-indigo-400/40 bg-indigo-500/10 shadow-[0_0_0_1px_rgba(99,102,241,0.25)]'
    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50';
}

function imagePreview(url?: string | null, label?: string, className = 'h-36', noFrame = false) {
  const resolved = resolveBackendUrl(url);
  if (!resolved) {
    return (
      <div className={`${className} ${noFrame ? '' : 'rounded-2xl border border-dashed border-slate-200 bg-slate-50'} flex items-center justify-center text-slate-400 overflow-hidden`}>
        <div className="text-center">
          <ImageIcon size={20} className="mx-auto" />
          <div className="text-xs mt-2">{label || 'No image'}</div>
        </div>
      </div>
    );
  }

  return (
    <a href={resolved} target="_blank" rel="noreferrer" className="block">
      <img
        src={resolved}
        alt={label || 'preview'}
        className={`w-full ${className} object-contain overflow-hidden ${noFrame ? 'bg-transparent' : 'rounded-2xl border border-slate-200 bg-white'}`}
        loading="lazy"
      />
    </a>
  );
}

export default function ReviewAndEdit({
  classes,
  results,
  onUpdateResult,
  onDeleteResult,
  onStartScanner,
}: ReviewAndEditProps) {
  const [classFilter, setClassFilter] = useState<string>('all');
  const [examFilter, setExamFilter] = useState<string>('all');
  const [codeFilter, setCodeFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [search, setSearch] = useState('');
  const [selectedResultId, setSelectedResultId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ReviewDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editorTab, setEditorTab] = useState<EditorTab>('answers');

  const selectedClass = useMemo(
    () => (classFilter !== 'all' ? classes.find(item => item.id === classFilter) ?? null : null),
    [classes, classFilter]
  );
  const availableExams = useMemo(
    () => (selectedClass ? selectedClass.exams : classes.flatMap(item => item.exams)),
    [classes, selectedClass]
  );
  const selectedExam = useMemo(() => {
    if (examFilter === 'all') return null;
    return availableExams.find(exam => exam.id === examFilter) ?? null;
  }, [availableExams, examFilter]);
  const availableCodes = useMemo(
    () => (selectedExam ? selectedExam.codes : availableExams.flatMap(exam => exam.codes)),
    [availableExams, selectedExam]
  );

  const filteredResults = useMemo(() => {
    const query = search.trim().toLowerCase();
    const matches = results
      .filter(result => (classFilter === 'all' ? true : result.classId === classFilter))
      .filter(result => (examFilter === 'all' ? true : result.examId === examFilter))
      .filter(result => (codeFilter === 'all' ? true : result.examCode === codeFilter))
      .filter(result => {
        if (statusFilter === 'all') return true;
        if (statusFilter === 'edited') return !!result.isEdited;
        return result.status === statusFilter;
      })
      .filter(result => {
        if (!query) return true;
        return [
          result.studentName,
          result.studentMssv,
          result.detectedName,
          result.examCode,
          result.score.toFixed(2),
        ].some(value => value?.toLowerCase().includes(query));
      });
    return keepLatestSubmissions(matches);
  }, [results, classFilter, examFilter, codeFilter, statusFilter, search]);

  const selectedResult = useMemo(() => {
    if (!filteredResults.length) return null;
    if (!selectedResultId) return filteredResults[0];
    return filteredResults.find(result => result.id === selectedResultId) ?? filteredResults[0];
  }, [filteredResults, selectedResultId]);

  const editorClass = useMemo(
    () => classes.find(item => item.id === selectedResult?.classId) ?? null,
    [classes, selectedResult?.classId]
  );
  const editorExam = useMemo(
    () => editorClass?.exams.find(exam => exam.id === selectedResult?.examId) ?? null,
    [editorClass, selectedResult?.examId]
  );
  const draftClass = useMemo(
    () => classes.find(item => item.id === draft?.classId) ?? null,
    [classes, draft?.classId]
  );
  const draftExam = useMemo(
    () => draftClass?.exams.find(exam => exam.id === draft?.examId) ?? null,
    [draftClass, draft?.examId]
  );
  const draftCode = useMemo(
    () => draftExam?.codes.find(code => code.code === draft?.examCode) ?? null,
    [draftExam, draft?.examCode]
  );

  useEffect(() => {
    if (!filteredResults.length) {
      setSelectedResultId(null);
      return;
    }
    if (!selectedResultId || !filteredResults.some(result => result.id === selectedResultId)) {
      setSelectedResultId(filteredResults[0].id);
    }
  }, [filteredResults, selectedResultId]);

  useEffect(() => {
    if (!selectedResult) {
      setDraft(null);
      return;
    }

    const totalQuestions = selectedResult.totalQuestions || editorExam?.questionCount || Object.keys(selectedResult.answers).length;
    setDraft({
      classId: selectedResult.classId,
      examId: selectedResult.examId,
      examCode: selectedResult.examCode,
      studentId: selectedResult.studentId,
      studentMssv: selectedResult.studentMssv,
      studentName: selectedResult.studentName,
      answers: normalizeAnswers(selectedResult.answers, totalQuestions),
    });
  }, [selectedResult?.id, editorExam?.questionCount]);

  const counts = useMemo(() => ({
    total: filteredResults.length,
    matched: filteredResults.filter(result => result.status === 'matched').length,
    unmatched: filteredResults.filter(result => result.status === 'unmatched').length,
    unknown_code: filteredResults.filter(result => result.status === 'unknown_code').length,
    edited: filteredResults.filter(result => result.isEdited).length,
  }), [filteredResults]);

  const activeGrading = useMemo(() => {
    if (!draft || !draftCode) return null;
    return gradeAnswers(draft.answers, draftCode.answerKey);
  }, [draft, draftCode]);

  const selectedClassLabel = classes.find(item => item.id === selectedResult?.classId)?.code ?? selectedResult?.classId ?? '-';
  const selectedExamLabel = classes.flatMap(item => item.exams).find(exam => exam.id === selectedResult?.examId)?.title ?? selectedResult?.examId ?? '-';
  const selectedStatus = selectedResult?.isEdited ? 'edited' : selectedResult?.status ?? 'matched';

  const updateAnswer = (index: number, option: AnswerOption) => {
    if (!draft) return;
    const current = normalizeAnswerKeyValue(draft.answers[index] ?? '');
    const set = new Set(current.split('').filter(Boolean));
    if (set.has(option)) set.delete(option);
    else set.add(option);
    const next = Array.from(set).filter((value): value is AnswerOption => ANSWER_OPTIONS.includes(value as AnswerOption)).sort((a, b) => answerOrder[a] - answerOrder[b]).join('');
    const answers = draft.answers.slice();
    answers[index] = next;
    setDraft({ ...draft, answers });
  };

  const updateDraftClass = (classId: string) => {
    if (!draft) return;
    const nextClass = classes.find(item => item.id === classId) ?? null;
    const nextExam = nextClass?.exams[0] ?? null;
    setDraft({
      ...draft,
      classId,
      examId: nextExam?.id ?? '',
      examCode: nextExam?.codes[0]?.code ?? '',
    });
  };

  const updateDraftExam = (examId: string) => {
    if (!draft) return;
    const nextExam = draftClass?.exams.find(exam => exam.id === examId) ?? null;
    setDraft({
      ...draft,
      examId,
      examCode: nextExam?.codes[0]?.code ?? '',
    });
  };

  const resetDraft = () => {
    if (!selectedResult) return;
    const totalQuestions = selectedResult.totalQuestions || editorExam?.questionCount || Object.keys(selectedResult.answers).length;
    setDraft({
      classId: selectedResult.classId,
      examId: selectedResult.examId,
      examCode: selectedResult.examCode,
      studentId: selectedResult.studentId,
      studentMssv: selectedResult.studentMssv,
      studentName: selectedResult.studentName,
      answers: normalizeAnswers(selectedResult.answers, totalQuestions),
    });
  };

  const saveDraft = async () => {
    if (!selectedResult || !draft) return;
    setSaving(true);
    try {
      const selectedCode = draftCode;
      const matchedStudent = draftClass?.students.find(student => student.mssv === draft.studentMssv) ?? null;
      const nameMatchesStudent = matchedStudent ? isStudentNameMatch(draft.studentName, matchedStudent.fullName) : false;
      const nextStatus = selectedCode ? (matchedStudent && nameMatchesStudent ? 'matched' : 'unmatched') : 'unknown_code';
      const grading = selectedCode ? gradeAnswers(draft.answers, selectedCode.answerKey) : activeGrading;
      const totalQuestions = draftExam?.questionCount || selectedResult.totalQuestions || draft.answers.length;
      const answers = Object.fromEntries(draft.answers.map((answer, index) => [index + 1, answer || null]));

      const updated: ScannedResult = {
        ...selectedResult,
        classId: draft.classId,
        examId: draft.examId,
        studentId: matchedStudent?.id,
        studentMssv: draft.studentMssv.trim(),
        studentName: draft.studentName.trim() || matchedStudent?.fullName || draft.studentName || 'Unknown student',
        examCode: draft.examCode,
        score: grading?.score ?? selectedResult.score,
        correctCount: grading?.correct_count ?? selectedResult.correctCount,
        totalQuestions,
        answers,
        status: nextStatus,
        isEdited: true,
        details: grading?.details ?? selectedResult.details,
      };

      await Promise.resolve(onUpdateResult(updated));
      setSelectedResultId(updated.id);
      setIsEditorOpen(false);
    } finally {
      setSaving(false);
    }
  };

  const openEditor = (resultId?: string) => {
    if (resultId) setSelectedResultId(resultId);
    setEditorTab('answers');
    setIsEditorOpen(true);
  };

  return (
    <>
      <div className="grid grid-cols-1 xl:grid-cols-[300px_minmax(0,1fr)] gap-4 min-h-[calc(100dvh-10rem)]">
        <aside className="bg-white rounded-[28px] border border-slate-200 shadow-sm overflow-hidden min-h-0">
          <div className="px-5 py-4 border-b border-slate-200">
            <div className="flex items-center gap-2 text-slate-900 font-black text-lg">
              <Filter size={18} className="text-indigo-500" />
              Review filters
            </div>
            <p className="text-xs text-slate-500 mt-1">Filter by class, exam, code, and status.</p>
          </div>

          <div className="p-5 space-y-4">
            <label className="block">
              <span className="text-[10px] uppercase tracking-[0.24em] font-black text-slate-500">Class</span>
              <div className="mt-2 relative">
                <select
                  value={classFilter}
                  onChange={(e) => {
                    setClassFilter(e.target.value);
                    setExamFilter('all');
                    setCodeFilter('all');
                  }}
                  className="w-full appearance-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 pr-10 font-semibold outline-none"
                >
                  <option value="all">All classes</option>
                  {classes.map(item => (
                    <option key={item.id} value={item.id}>{item.code} · {item.name}</option>
                  ))}
                </select>
                <ChevronDown size={16} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              </div>
            </label>

            <label className="block">
              <span className="text-[10px] uppercase tracking-[0.24em] font-black text-slate-500">Exam</span>
              <div className="mt-2 relative">
                <select
                  value={examFilter}
                  onChange={(e) => {
                    setExamFilter(e.target.value);
                    setCodeFilter('all');
                  }}
                  className="w-full appearance-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 pr-10 font-semibold outline-none"
                >
                  <option value="all">All exams</option>
                  {availableExams.map(exam => (
                    <option key={exam.id} value={exam.id}>{exam.title} ({exam.questionCount})</option>
                  ))}
                </select>
                <ChevronDown size={16} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              </div>
            </label>

            <label className="block">
              <span className="text-[10px] uppercase tracking-[0.24em] font-black text-slate-500">Exam code</span>
              <div className="mt-2 relative">
                <select
                  value={codeFilter}
                  onChange={(e) => setCodeFilter(e.target.value)}
                  className="w-full appearance-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 pr-10 font-semibold outline-none"
                >
                  <option value="all">All codes</option>
                  {availableCodes.map(code => (
                    <option key={code.id} value={code.code}>{code.code}</option>
                  ))}
                </select>
                <ChevronDown size={16} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              </div>
            </label>

            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] font-black text-slate-500 mb-2">Status</div>
              <div className="grid grid-cols-2 gap-2">
                {(Object.keys(statusLabels) as StatusFilter[]).map(status => (
                  <button
                    key={status}
                    type="button"
                    onClick={() => setStatusFilter(status)}
                    className={`rounded-2xl border px-3 py-2 text-left text-xs font-black transition-all ${statusFilter === status ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-slate-50 text-slate-500 border-slate-200 hover:bg-slate-100'}`}
                  >
                    <div>{statusLabels[status]}</div>
                    <div className="text-[10px] opacity-80">
                      {status === 'all'
                        ? counts.total
                        : status === 'matched'
                          ? counts.matched
                          : status === 'unmatched'
                            ? counts.unmatched
                            : status === 'unknown_code'
                              ? counts.unknown_code
                              : counts.edited}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <label className="block">
              <span className="text-[10px] uppercase tracking-[0.24em] font-black text-slate-500">Search</span>
              <div className="mt-2 relative">
                <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Student name or MSSV"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 pl-11 pr-4 py-3 font-medium outline-none focus:border-indigo-300"
                />
              </div>
            </label>

            <div className="rounded-3xl bg-slate-50 border border-slate-200 p-4">
              <div className="flex items-center gap-2 text-slate-900 font-black">
                <BookOpen size={16} className="text-indigo-500" />
                Quick summary
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4">
                <div className="rounded-2xl bg-white border border-slate-200 p-3">
                  <div className="text-[10px] uppercase tracking-[0.24em] text-slate-400 font-black">Total</div>
                  <div className="text-2xl font-black text-slate-900 mt-1">{counts.total}</div>
                </div>
                <div className="rounded-2xl bg-white border border-slate-200 p-3">
                  <div className="text-[10px] uppercase tracking-[0.24em] text-slate-400 font-black">Edited</div>
                  <div className="text-2xl font-black text-indigo-600 mt-1">{counts.edited}</div>
                </div>
              </div>
            </div>
          </div>
        </aside>

        <section className="bg-white rounded-[28px] border border-slate-200 shadow-sm overflow-hidden min-h-0 flex flex-col">
          <div className="p-5 border-b border-slate-200 flex flex-col gap-3">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
              <div>
                <div className="text-[10px] uppercase tracking-[0.28em] font-black text-slate-400">Review queue</div>
                <div className="text-2xl font-black text-slate-900 mt-1">Submissions</div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  onClick={() => openEditor(selectedResult?.id)}
                  disabled={!selectedResult}
                  className="rounded-2xl border border-slate-200 bg-white px-4 py-3 font-black text-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50"
                >
                  <Edit3 size={16} />
                  Edit selected
                </button>
                <button
                  onClick={() => onStartScanner(selectedClass?.id, selectedExam?.id)}
                  className="rounded-2xl bg-slate-900 text-white px-4 py-3 font-black text-sm flex items-center gap-2"
                >
                  <ArrowRightLeft size={16} />
                  Scan another paper
                </button>
                <div className="px-4 py-3 rounded-2xl bg-slate-50 border border-slate-200 text-sm font-black text-slate-700">
                  {filteredResults.length} record{filteredResults.length === 1 ? '' : 's'}
                </div>
              </div>
            </div>

            <div className="rounded-3xl bg-slate-50 border border-slate-200 p-4">
              {selectedResult ? (
                <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-3 items-center">
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.24em] text-slate-400 font-black">Selected row</div>
                    <div className="text-lg font-black text-slate-900 mt-1">{selectedResult.studentName}</div>
                    <div className="text-sm text-slate-500 mt-1">{selectedClassLabel} · {selectedExamLabel} · Code {selectedResult.examCode}</div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                    <div className="text-[10px] uppercase tracking-[0.24em] text-slate-400 font-black">Score</div>
                    <div className="text-xl font-black text-slate-900 mt-1">{scoreLabel(selectedResult)}</div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                    <div className="text-[10px] uppercase tracking-[0.24em] text-slate-400 font-black">Status</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] ${statusColors[selectedResult.status] ?? 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                        {selectedStatus.replace('_', ' ')}
                      </span>
                      {selectedResult.isEdited && (
                        <span className="inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] bg-indigo-500/15 text-indigo-600 border-indigo-200">
                          Edited
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-slate-500 text-sm">No record selected.</div>
              )}
            </div>
          </div>

          <div className="flex-1 min-h-0 max-h-[calc(100dvh-320px)] overflow-y-auto overscroll-contain pr-2">
            <div className="md:hidden space-y-3 p-3">
              {filteredResults.map(result => {
                const active = result.id === selectedResult?.id;
                return (
                  <div
                    key={result.id}
                    onClick={() => setSelectedResultId(result.id)}
                    role="button"
                    tabIndex={0}
                    className={`w-full text-left rounded-3xl border p-4 transition-all ${rowBorder(active)}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-black text-slate-900 text-base leading-tight truncate">{result.studentName}</div>
                        <div className="text-xs text-slate-400 font-mono mt-1">{result.studentMssv}</div>
                      </div>
                      <span className="inline-flex items-center rounded-xl bg-indigo-50 text-indigo-600 px-2.5 py-1 font-black text-xs shrink-0">
                        {result.examCode}
                      </span>
                    </div>

                    <div className="mt-3 grid grid-cols-[1.2fr_auto] gap-3 items-start">
                      <div>
                        <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400 font-black">Class / exam</div>
                        <div className="font-bold text-slate-700 mt-1">
                          {classes.find(item => item.id === result.classId)?.code ?? result.classId}
                        </div>
                        <div className="text-xs text-slate-400 mt-1">
                          {classes.flatMap(item => item.exams).find(exam => exam.id === result.examId)?.title ?? result.examId}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-black text-slate-900">{scoreLabel(result)}</div>
                        <div className="text-xs text-slate-400 mt-1">{result.correctCount}/{result.totalQuestions} correct</div>
                      </div>
                    </div>

                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] ${statusColors[result.status] ?? 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                        {result.status.replace('_', ' ')}
                      </span>
                      {result.isEdited && (
                        <span className="inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] bg-indigo-500/15 text-indigo-600 border-indigo-200">
                          Edited
                        </span>
                      )}
                    </div>

                    <div className="mt-3 flex items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          openEditor(result.id);
                        }}
                        className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-black text-slate-700 hover:bg-slate-50"
                      >
                        <Edit3 size={14} />
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteResult(result.id, result.submissionId);
                        }}
                        className="inline-flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-black text-rose-600 hover:bg-rose-100"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                );
              })}

              {!filteredResults.length && (
                <div className="rounded-3xl border border-dashed border-slate-200 bg-white p-8 text-center">
                  <CircleAlert size={40} className="mx-auto text-slate-300" />
                  <div className="text-lg font-black text-slate-900 mt-4">No submissions match the filters</div>
                  <div className="text-sm text-slate-500 mt-1">Try another class, exam, or status filter.</div>
                </div>
              )}
            </div>

            <table className="hidden md:table w-full text-left border-collapse">
              <thead className="sticky top-0 z-10 bg-slate-50 border-b border-slate-200">
                <tr className="text-[10px] uppercase tracking-[0.24em] font-black text-slate-400">
                  <th className="px-5 py-4">Student</th>
                  <th className="px-5 py-4">Class / exam</th>
                  <th className="px-5 py-4">Code</th>
                  <th className="px-5 py-4">Score</th>
                  <th className="px-5 py-4">Status</th>
                  <th className="px-5 py-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredResults.map(result => {
                  const active = result.id === selectedResult?.id;
                  return (
                    <tr
                      key={result.id}
                      onClick={() => setSelectedResultId(result.id)}
                      className={`cursor-pointer border-b border-slate-100 transition-all ${rowBorder(active)}`}
                    >
                      <td className="px-5 py-4">
                        <div className="font-black text-slate-900">{result.studentName}</div>
                        <div className="text-xs text-slate-400 font-mono mt-1">{result.studentMssv}</div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="font-bold text-slate-700">{classes.find(item => item.id === result.classId)?.code ?? result.classId}</div>
                        <div className="text-xs text-slate-400 mt-1">{classes.flatMap(item => item.exams).find(exam => exam.id === result.examId)?.title ?? result.examId}</div>
                      </td>
                      <td className="px-5 py-4">
                        <span className="inline-flex items-center rounded-xl bg-indigo-50 text-indigo-600 px-2.5 py-1 font-black text-xs">{result.examCode}</span>
                      </td>
                      <td className="px-5 py-4">
                        <div className="font-black text-slate-900">{scoreLabel(result)}</div>
                        <div className="text-xs text-slate-400 mt-1">{result.correctCount}/{result.totalQuestions} correct</div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap gap-2">
                          <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] ${statusColors[result.status] ?? 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                            {result.status.replace('_', ' ')}
                          </span>
                          {result.isEdited && (
                            <span className="inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em] bg-indigo-500/15 text-indigo-600 border-indigo-200">
                              Edited
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              openEditor(result.id);
                            }}
                            className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-black text-slate-700 hover:bg-slate-50"
                          >
                            <Edit3 size={14} />
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteResult(result.id, result.submissionId);
                            }}
                            className="inline-flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-black text-rose-600 hover:bg-rose-100"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}

                {!filteredResults.length && null}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {isEditorOpen && selectedResult && draft && (
        <div className="fixed inset-0 z-[120] bg-black/75 backdrop-blur-sm p-0 md:p-8 flex items-stretch md:items-center justify-center">
          <div className="w-full max-w-[1500px] h-[100dvh] md:h-[92vh] overflow-hidden rounded-none md:rounded-[32px] bg-[#101a2b] text-white border-0 md:border md:border-white/10 shadow-2xl flex flex-col">
            <div className="px-4 sm:px-5 py-3 md:py-4 border-b border-white/10 flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-[9px] sm:text-[10px] uppercase tracking-[0.28em] font-black text-slate-400">Edit scanned submission</div>
                <div className="text-xl sm:text-2xl font-black mt-1">{draft.studentName || 'Unknown student'}</div>
                <div className="text-xs sm:text-sm text-slate-300 mt-1 font-mono">{draft.studentMssv}</div>
              </div>
              <div className="flex items-center gap-2">
                <div className="rounded-full bg-white/5 border border-white/10 px-3 py-1 text-[11px] sm:text-xs font-black text-slate-200 max-w-[220px] truncate">
                  {selectedClassLabel} · {selectedExamLabel}
                </div>
                <button
                  type="button"
                  onClick={() => setIsEditorOpen(false)}
                  className="rounded-full border border-white/10 bg-white/5 p-2 text-white/80 hover:bg-white/10"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            <div className="flex-1 min-h-0 overflow-hidden p-3 sm:p-4 md:p-6 flex flex-col">
              <div className="mb-3 xl:hidden rounded-2xl border border-white/10 bg-black/20 p-2 shrink-0">
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setEditorTab('answers')}
                    className={`rounded-xl px-3 py-3 text-[11px] font-black uppercase tracking-[0.16em] transition-all border flex items-center justify-center gap-2 ${
                      editorTab === 'answers'
                        ? 'bg-cyan-500/15 text-cyan-300 border-cyan-400 shadow-[0_0_0_1px_rgba(34,211,238,0.15)]'
                        : 'bg-white/5 text-slate-400 border-white/10'
                    }`}
                  >
                    <BookOpen size={14} />
                    Bài làm (.OMR)
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditorTab('student')}
                    className={`rounded-xl px-3 py-3 text-[11px] font-black uppercase tracking-[0.16em] transition-all border flex items-center justify-center gap-2 ${
                      editorTab === 'student'
                        ? 'bg-cyan-500/15 text-cyan-300 border-cyan-400 shadow-[0_0_0_1px_rgba(34,211,238,0.15)]'
                        : 'bg-white/5 text-slate-400 border-white/10'
                    }`}
                  >
                    <User size={14} />
                    Thí sinh
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditorTab('crops')}
                    className={`rounded-xl px-3 py-3 text-[11px] font-black uppercase tracking-[0.16em] transition-all border flex items-center justify-center gap-2 ${
                      editorTab === 'crops'
                        ? 'bg-cyan-500/15 text-cyan-300 border-cyan-400 shadow-[0_0_0_1px_rgba(34,211,238,0.15)]'
                        : 'bg-white/5 text-slate-400 border-white/10'
                    }`}
                  >
                    <Eye size={14} />
                    Crops
                  </button>
                </div>
              </div>

              <div className="flex-1 min-h-0 overflow-hidden grid grid-cols-1 xl:grid-cols-[0.72fr_1.62fr_0.66fr] gap-3 min-w-0">
                <div className={`${editorTab === 'student' ? 'block' : 'hidden'} xl:block h-full space-y-3 min-w-0 min-h-0 overflow-y-auto overscroll-contain pr-1`}>
                  <div className="rounded-2xl bg-[#0d1524] border border-white/10 p-2.5">
                    <div className="text-[9px] sm:text-[10px] uppercase tracking-[0.24em] text-slate-500 font-black">Student information</div>
                    <div className="mt-2.5 rounded-[18px] bg-white/5 border border-white/10 p-2.5">
                      <div className="text-[9px] sm:text-[10px] text-slate-400 mb-1.5">Full name (OCR)</div>
                      <input
                        value={draft.studentName}
                        onChange={(e) => setDraft({ ...draft, studentName: e.target.value })}
                        className="w-full bg-transparent text-lg sm:text-xl xl:text-2xl font-black text-white outline-none border-b border-white/5 pb-1"
                        placeholder="Student name"
                      />
                      <div className="mt-2.5">{imagePreview(selectedResult.crops?.ho_va_ten, 'Name crop', 'h-10 sm:h-12 md:h-12', true)}</div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-[1.2fr_0.8fr] gap-2 mt-2">
                      <div className="rounded-[18px] bg-white/5 border border-white/10 p-2.5">
                        <div className="text-[9px] sm:text-[10px] text-slate-400 mb-1.5">Student ID (OMR)</div>
                        <input
                          value={draft.studentMssv}
                          onChange={(e) => setDraft({ ...draft, studentMssv: e.target.value })}
                          className="w-full bg-transparent text-base sm:text-lg xl:text-xl font-black text-cyan-300 outline-none border-b border-white/5 pb-1 font-mono"
                          placeholder="Student ID"
                        />
                        <div className="mt-2.5">{imagePreview(selectedResult.omrImages?.student_id ?? selectedResult.crops?.mssv, 'OMR MSSV', 'h-24 sm:h-24 md:h-24', true)}</div>
                      </div>

                      <div className="rounded-[18px] bg-white/5 border border-white/10 p-2.5">
                        <div className="text-[9px] sm:text-[10px] text-slate-400 mb-1.5">Exam code (OMR)</div>
                        <input
                          value={draft.examCode}
                          onChange={(e) => setDraft({ ...draft, examCode: e.target.value })}
                          className="w-full bg-transparent text-base sm:text-lg xl:text-xl font-black text-fuchsia-300 outline-none border-b border-white/5 pb-1 font-mono"
                          placeholder="Exam code"
                        />
                        <div className="mt-2.5">{imagePreview(selectedResult.omrImages?.exam_code ?? selectedResult.crops?.ma_de, 'OMR exam code', 'h-20 sm:h-20 md:h-20', true)}</div>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl bg-[#0d1524] border border-white/10 p-2.5 space-y-2">
                    <div className="text-[9px] sm:text-[10px] uppercase tracking-[0.24em] text-slate-500 font-black">Class / exam selection</div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-1 gap-2">
                      <div className="relative">
                        <select
                          value={draft.classId}
                          onChange={(e) => updateDraftClass(e.target.value)}
                          className="w-full appearance-none rounded-2xl border border-white/10 bg-white/5 px-3 py-2 pr-10 text-white outline-none text-sm font-bold"
                        >
                          {classes.map(classRoom => (
                            <option key={classRoom.id} value={classRoom.id} className="bg-slate-900">
                              {classRoom.code} · {classRoom.name}
                            </option>
                          ))}
                        </select>
                        <ChevronDown size={16} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                      </div>
                      <div className="relative">
                        <select
                          value={draft.examId}
                          onChange={(e) => updateDraftExam(e.target.value)}
                          className="w-full appearance-none rounded-2xl border border-white/10 bg-white/5 px-3 py-2 pr-10 text-white outline-none text-sm font-bold"
                        >
                          {(draftClass?.exams ?? []).map(exam => (
                            <option key={exam.id} value={exam.id} className="bg-slate-900">
                              {exam.title}
                            </option>
                          ))}
                        </select>
                        <ChevronDown size={16} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                      </div>
                    </div>

                    <div className="text-[9px] sm:text-[10px] uppercase tracking-[0.24em] text-slate-500 font-black">Exam code selection</div>
                    <div className="relative">
                      <select
                        value={draft.examCode}
                        onChange={(e) => setDraft({ ...draft, examCode: e.target.value })}
                        className="w-full appearance-none rounded-2xl border border-white/10 bg-white/5 px-3 py-2 pr-10 text-white outline-none font-mono text-sm"
                      >
                        {(draftExam?.codes ?? []).map(code => (
                          <option key={code.id} value={code.code} className="bg-slate-900">
                            {code.code}
                          </option>
                        ))}
                      </select>
                      <ChevronDown size={16} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                    </div>
                    <div className="rounded-2xl bg-white/5 border border-white/10 p-2.5">
                      <div className="text-[9px] sm:text-[10px] uppercase tracking-[0.24em] text-slate-500 font-black">OCR / OMR status</div>
                      <div className="mt-1.5 flex items-center justify-between gap-2">
                        <span className="text-xs sm:text-sm text-slate-300">{selectedResult.isEdited ? 'Edited' : 'Original scan'}</span>
                        <span className="rounded-xl bg-emerald-500/15 text-emerald-300 px-2.5 py-1.5 text-xs sm:text-sm font-black">
                          {selectedResult.correctCount}/{selectedResult.totalQuestions} correct
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className={`${editorTab === 'crops' ? 'block' : 'hidden'} xl:block h-full space-y-3 min-w-0 min-h-0 overflow-y-auto overscroll-contain pr-1`}>
                  <div className="rounded-2xl bg-[#0d1524] border border-white/10 p-3">
                    <div className="flex items-center gap-2 text-sm font-black text-slate-300">
                      <Eye size={14} />
                      Evidence previews
                    </div>
                    <div className="space-y-2 mt-3">
                      <div className="text-[9px] sm:text-[10px] uppercase tracking-[0.24em] font-black text-slate-500">Visualized result</div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {imagePreview(selectedResult.sourceImageUrl, 'Original image', 'h-28 sm:h-32 md:h-40', true)}
                        {imagePreview(selectedResult.resultImageUrl ?? selectedResult.alignedImageUrl, 'Visualized result', 'h-28 sm:h-32 md:h-40', true)}
                      </div>
                    </div>
                    <div className="space-y-2 mt-3">
                      <div className="text-[9px] sm:text-[10px] uppercase tracking-[0.24em] font-black text-slate-500">OMR answer crops</div>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
                        {imagePreview(selectedResult.omrImages?.answer_1, 'OMR answer 1', 'h-48 sm:h-[17rem] md:h-[20rem]', true)}
                        {imagePreview(selectedResult.omrImages?.answer_2, 'OMR answer 2', 'h-48 sm:h-[17rem] md:h-[20rem]', true)}
                        {imagePreview(selectedResult.omrImages?.answer_3, 'OMR answer 3', 'h-48 sm:h-[17rem] md:h-[20rem]', true)}
                      </div>
                    </div>
                  </div>
                </div>

                <div className={`${editorTab === 'answers' ? 'flex' : 'hidden'} xl:flex rounded-2xl bg-[#0d1524] border border-white/10 p-3 md:p-4 flex-col min-h-0 h-full overflow-hidden min-w-0`}>
                  <div className="flex items-start sm:items-center justify-between gap-3 flex-col sm:flex-row">
                    <div>
                      <div className="text-[9px] sm:text-[10px] uppercase tracking-[0.24em] text-slate-500 font-black">Answer sheet</div>
                      <div className="text-xs sm:text-sm text-slate-300 mt-1">Tap A, B, C, D to toggle multi-select answers.</div>
                    </div>
                    <div className="rounded-xl bg-white/10 px-3 py-2 text-xs font-black text-white self-start sm:self-auto">
                      {draft.answers.length} questions
                    </div>
                  </div>

                  <div className="mt-4 flex-1 min-h-0 overflow-y-scroll overscroll-contain pr-1 space-y-3 pb-24 md:pb-2">
                    {draft.answers.map((value, index) => {
                      const normalized = normalizeAnswerKeyValue(value || '');
                      const correct = draftCode?.answerKey[index] ?? '';
                      return (
                        <div key={index} className="rounded-2xl border border-white/10 bg-black/15 p-3">
                          <div className="flex items-center justify-between gap-3 mb-3">
                            <div>
                              <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500 font-black">Q{index + 1}</div>
                              <div className="text-xs text-slate-400 mt-1">Correct: {answerLabel(correct)}</div>
                            </div>
                            <button
                              type="button"
                              onClick={() => {
                                const next = draft.answers.slice();
                                next[index] = '';
                                setDraft({ ...draft, answers: next });
                              }}
                              className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-black text-slate-300 hover:bg-white/10"
                            >
                              Clear
                            </button>
                          </div>

                          <div className="grid grid-cols-4 gap-2">
                            {ANSWER_OPTIONS.map(option => {
                              const active = normalized.includes(option);
                              return (
                                <button
                                  type="button"
                                  key={option}
                                  onClick={() => updateAnswer(index, option)}
                                  className={`rounded-2xl px-3 py-2 text-sm font-black transition-all border ${active ? 'bg-cyan-400 text-slate-950 border-cyan-300' : 'bg-white/5 text-white border-white/10 hover:bg-white/10'}`}
                                >
                                  {option}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>

            <div className="border-t border-white/10 bg-black/25 px-4 md:px-6 py-3 shrink-0 sticky bottom-0 backdrop-blur-md">
              <div className="grid grid-cols-3 gap-2.5">
                <button
                  type="button"
                  onClick={saveDraft}
                  disabled={saving}
                  className="col-span-2 rounded-2xl bg-gradient-to-r from-indigo-500 to-violet-500 px-4 py-3 text-white font-black text-sm shadow-lg shadow-indigo-900/30 disabled:opacity-70 flex items-center justify-center gap-2"
                >
                  {saving ? <Loader2 className="animate-spin" size={18} /> : <CheckCircle2 size={18} />}
                  Save & regrade
                </button>
                <button
                  type="button"
                  onClick={resetDraft}
                  className="col-span-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white font-black text-sm hover:bg-white/10 flex items-center justify-center gap-2"
                >
                  <X size={18} />
                  Reset
                </button>
                <button
                  type="button"
                  onClick={() => onStartScanner(draft.classId, draft.examId)}
                  className="col-span-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white font-black text-sm hover:bg-white/10 flex items-center justify-center gap-2"
                >
                  <ArrowRightLeft size={18} />
                  Scan again
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {!isEditorOpen && selectedResult && (
        <button
          type="button"
          onClick={() => openEditor(selectedResult.id)}
          className="fixed right-4 bottom-[calc(env(safe-area-inset-bottom,0px)+4.5rem)] z-[110] rounded-full bg-white border border-slate-200 shadow-lg px-4 py-3 text-sm font-black text-slate-700 hover:bg-slate-50"
        >
          Open edit panel
        </button>
      )}
    </>
  );
}
