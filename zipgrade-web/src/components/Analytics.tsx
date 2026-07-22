import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  BarChart3,
  BookOpen,
  Camera,
  ClipboardList,
  Download,
  Filter,
  Lightbulb,
  PieChart,
  Target,
  Trophy,
  TrendingUp,
  Users,
} from 'lucide-react';
import * as XLSX from 'xlsx';
import type { ClassRoom, ScannedResult } from '../types';
import { normalizeAnswerKeyValue } from '../utils/answerKey';

const ALL = '__all__';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

interface AnalyticsProps {
  classes: ClassRoom[];
  results: ScannedResult[];
  onStartScanner: (classId?: string, examId?: string) => void;
}

type CodeOption = {
  value: string;
  classId: string;
  classCode: string;
  examId: string;
  examTitle: string;
  examCode: string;
  answerKey: string[];
};

type SummaryView = {
  count: number;
  avg: number;
  med: number;
  max: number;
  min: number;
  passCount: number;
  excellentCount: number;
  matchedCount: number;
  unmatchedCount: number;
  unknownCodeCount: number;
};

type DistributionView = { label: string; count: number };
type GradeBandView = { label: string; value: number; color: string; percent: string };
type ComparisonView = { label: string; subLabel: string; count: number; avg: number };
type QuestionView = {
  question: number;
  difficulty: number;
  blankRate: number;
  correctCount: number;
  wrongCount: number;
  blankCount: number;
  trapOption: string;
};

type AnalyticsApiResponse = {
  scope: string;
  summary: {
    total_submissions: number;
    average_score: number;
    median_score: number;
    highest_score: number;
    lowest_score: number;
    pass_count: number;
    pass_rate: number;
    excellent_count: number;
    excellent_rate: number;
    matched_count: number;
    unmatched_count: number;
    unknown_code_count: number;
  };
  distribution: Array<{ label: string; count: number }>;
  grade_bands: Array<{ label: string; count: number; percent: number }>;
  comparison: Array<{ label: string; sub_label: string; count: number; average_score: number }>;
  top_failed_questions: Array<{
    question: number;
    difficulty: number;
    blank_rate: number;
    correct_count: number;
    wrong_count: number;
    blank_count: number;
    trap_option: string;
  }>;
};

function mean(values: number[]) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

function median(values: number[]) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

function percent(value: number, total: number) {
  if (total <= 0) return '0%';
  return `${Math.round((value / total) * 100)}%`;
}

function formatScore(value: number) {
  return Number.isInteger(value) ? `${value}` : value.toFixed(2);
}

function downloadCsv(filename: string, rows: string[][]) {
  const csv = rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function normalizeAnswer(value: unknown) {
  return normalizeAnswerKeyValue(String(value ?? ''));
}

function getAnswer(result: ScannedResult, index: number) {
  return normalizeAnswer(result.answers[index + 1] ?? result.answers[String(index + 1)] ?? '');
}

function getStudentIdentity(result: ScannedResult) {
  const studentId = String(result.studentId ?? '').trim();
  if (studentId) return `student:${studentId}`;
  const mssv = String(result.studentMssv ?? '').trim();
  if (mssv) return `mssv:${mssv}`;
  return `result:${result.id}`;
}

function dedupeResultsByStudent(results: ScannedResult[]) {
  const sorted = [...results].sort((a, b) => b.scannedAt - a.scannedAt);
  const latestByStudent = new Map<string, ScannedResult>();
  sorted.forEach((result) => {
    const key = getStudentIdentity(result);
    if (!latestByStudent.has(key)) {
      latestByStudent.set(key, result);
    }
  });
  return Array.from(latestByStudent.values());
}

function buildLocalDistribution(scores: number[]): DistributionView[] {
  const buckets = Array.from({ length: 10 }, (_, index) => ({ label: `${index}-${index + 1}`, count: 0 }));
  scores.forEach(score => {
    buckets[Math.min(9, Math.max(0, Math.floor(score)))].count += 1;
  });
  return buckets;
}

function buildLocalGradeBands(items: ScannedResult[]): GradeBandView[] {
  const total = items.length;
  const bands = [
    { label: 'Excellent (>= 8.0)', value: items.filter(item => item.score >= 8).length, color: 'bg-emerald-500' },
    { label: 'Good (6.5 - 7.9)', value: items.filter(item => item.score >= 6.5 && item.score < 8).length, color: 'bg-blue-500' },
    { label: 'Average (5.0 - 6.4)', value: items.filter(item => item.score >= 5 && item.score < 6.5).length, color: 'bg-amber-500' },
    { label: 'Weak (< 5.0)', value: items.filter(item => item.score < 5).length, color: 'bg-red-500' },
  ];
  return bands.map(item => ({ ...item, percent: percent(item.value, total) }));
}

function buildLocalComparison(
  classes: ClassRoom[],
  filteredResults: ScannedResult[],
  selectedClassId: string,
  selectedExamId: string,
  codeOptions: CodeOption[],
): ComparisonView[] {
  if (selectedClassId === ALL) {
    return classes
      .map(classRoom => {
        const group = filteredResults.filter(item => item.classId === classRoom.id);
        return {
          label: classRoom.code,
          subLabel: classRoom.name,
          count: group.length,
          avg: mean(group.map(item => item.score)),
        };
      })
      .filter(item => item.count > 0)
      .sort((a, b) => b.avg - a.avg);
  }

  if (selectedExamId === ALL) {
    const classRoom = classes.find(item => item.id === selectedClassId) ?? null;
    return (classRoom?.exams ?? [])
      .map(exam => {
        const group = filteredResults.filter(item => item.examId === exam.id);
        return {
          label: exam.title,
          subLabel: `${exam.codes.length} code(s)`,
          count: group.length,
          avg: mean(group.map(item => item.score)),
        };
      })
      .filter(item => item.count > 0)
      .sort((a, b) => b.avg - a.avg);
  }

  return codeOptions
    .map(code => {
      const group = filteredResults.filter(item => item.examId === code.examId && item.examCode === code.examCode);
      return {
        label: code.examCode,
        subLabel: `${code.classCode} - ${code.examTitle}`,
        count: group.length,
        avg: mean(group.map(item => item.score)),
      };
    })
    .filter(item => item.count > 0)
    .sort((a, b) => b.avg - a.avg);
}

function buildLocalQuestions(filteredResults: ScannedResult[], answerKey: string[]): QuestionView[] {
  if (!answerKey.length || !filteredResults.length) return [];

  return Array.from({ length: answerKey.length }, (_, index) => {
    const correctKey = normalizeAnswer(answerKey[index] ?? '');
    const correctSet = new Set(correctKey.split('').filter(Boolean));
    const counts = { A: 0, B: 0, C: 0, D: 0 };
    let blankCount = 0;
    let correctCount = 0;

    filteredResults.forEach(result => {
      const answer = getAnswer(result, index);
      if (!answer) {
        blankCount += 1;
        return;
      }

      answer.split('').forEach(letter => {
        if (letter in counts) counts[letter as keyof typeof counts] += 1;
      });

      const studentSet = new Set(answer.split('').filter(Boolean));
      const isCorrect = studentSet.size === correctSet.size && [...studentSet].every(item => correctSet.has(item));
      if (isCorrect) correctCount += 1;
    });

    const total = filteredResults.length;
    const wrongCount = Math.max(0, total - correctCount - blankCount);
    const trapOption = (Object.entries(counts)
      .filter(([key]) => !correctSet.has(key))
      .sort((a, b) => b[1] - a[1])[0]?.[0] ?? '-');

    return {
      question: index + 1,
      difficulty: total > 0 ? correctCount / total : 0,
      blankRate: total > 0 ? blankCount / total : 0,
      correctCount,
      wrongCount,
      blankCount,
      trapOption,
    };
  }).sort((a, b) => b.wrongCount - a.wrongCount || a.difficulty - b.difficulty);
}

export default function Analytics({ classes, results, onStartScanner }: AnalyticsProps) {
  const [selectedClassId, setSelectedClassId] = useState<string>(ALL);
  const [selectedExamId, setSelectedExamId] = useState<string>(ALL);
  const [selectedCodeKey, setSelectedCodeKey] = useState<string>(ALL);
  const [remoteAnalytics, setRemoteAnalytics] = useState<AnalyticsApiResponse | null>(null);
  const [remoteLoading, setRemoteLoading] = useState(false);
  const [remoteError, setRemoteError] = useState<string | null>(null);

  const selectedClass = useMemo(
    () => (selectedClassId === ALL ? null : classes.find(item => item.id === selectedClassId) ?? null),
    [classes, selectedClassId]
  );

  const examOptions = useMemo(() => {
    if (selectedClassId !== ALL) return selectedClass?.exams ?? [];
    return classes.flatMap(classRoom => classRoom.exams.map(exam => ({ ...exam, classCode: classRoom.code })));
  }, [classes, selectedClass, selectedClassId]);

  const codeOptions = useMemo<CodeOption[]>(() => {
    const classesPool = selectedClassId === ALL ? classes : classes.filter(item => item.id === selectedClassId);
    const examsPool = selectedExamId === ALL
      ? classesPool.flatMap(classRoom => classRoom.exams)
      : classesPool.flatMap(classRoom => classRoom.exams.filter(exam => exam.id === selectedExamId));

    return examsPool.flatMap(exam => {
      const classRoom = classes.find(item => item.id === exam.classId) ?? null;
      return exam.codes.map(code => ({
        value: `${exam.id}::${code.code}`,
        classId: exam.classId,
        classCode: classRoom?.code ?? 'Unknown class',
        examId: exam.id,
        examTitle: exam.title,
        examCode: code.code,
        answerKey: code.answerKey,
      }));
    });
  }, [classes, selectedClassId, selectedExamId]);

  const selectedCode = useMemo(
    () => (selectedCodeKey === ALL ? null : codeOptions.find(item => item.value === selectedCodeKey) ?? null),
    [codeOptions, selectedCodeKey]
  );

  useEffect(() => {
    setSelectedExamId(ALL);
    setSelectedCodeKey(ALL);
  }, [selectedClassId]);

  useEffect(() => {
    setSelectedCodeKey(ALL);
  }, [selectedExamId]);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    (async () => {
      try {
        setRemoteLoading(true);
        setRemoteError(null);
        const params = new URLSearchParams();
        if (selectedClassId !== ALL) params.set('class_id', selectedClassId);
        if (selectedExamId !== ALL) params.set('exam_id', selectedExamId);
        if (selectedCode) params.set('exam_code', selectedCode.examCode);
        const url = `${API_BASE_URL}/api/v1/analytics${params.toString() ? `?${params.toString()}` : ''}`;
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const data = (await response.json()) as AnalyticsApiResponse;
        if (!cancelled) setRemoteAnalytics(data);
      } catch (error) {
        if (!cancelled && !(error instanceof DOMException && error.name === 'AbortError')) {
          setRemoteAnalytics(null);
          setRemoteError(error instanceof Error ? error.message : 'Failed to load analytics');
        }
      } finally {
        if (!cancelled) setRemoteLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [selectedClassId, selectedCode, selectedExamId]);

  const filteredResults = useMemo(() => {
    return results.filter(result => {
      if (selectedClassId !== ALL && result.classId !== selectedClassId) return false;
      if (selectedExamId !== ALL && result.examId !== selectedExamId) return false;
      if (selectedCode) return result.examId === selectedCode.examId && result.examCode === selectedCode.examCode;
      return true;
    });
  }, [results, selectedClassId, selectedCode, selectedExamId]);

  const filteredStudentResults = useMemo(
    () => dedupeResultsByStudent(filteredResults),
    [filteredResults]
  );

  const matchedStudentResults = useMemo(
    () => filteredStudentResults.filter(item => item.status === 'matched'),
    [filteredStudentResults]
  );

  const summaryFallback = useMemo<SummaryView>(() => {
    const scores = matchedStudentResults.map(item => item.score);
    return {
      count: filteredStudentResults.length,
      avg: mean(scores),
      med: median(scores),
      max: scores.length ? Math.max(...scores) : 0,
      min: scores.length ? Math.min(...scores) : 0,
      passCount: matchedStudentResults.filter(item => item.score >= 5).length,
      excellentCount: matchedStudentResults.filter(item => item.score >= 8).length,
      matchedCount: matchedStudentResults.length,
      unmatchedCount: filteredStudentResults.filter(item => item.status === 'unmatched').length,
      unknownCodeCount: filteredStudentResults.filter(item => item.status === 'unknown_code').length,
    };
  }, [filteredStudentResults, matchedStudentResults]);

  const summary = useMemo<SummaryView>(() => {
    if (!remoteAnalytics) return summaryFallback;
    return {
      count: remoteAnalytics.summary.total_submissions,
      avg: remoteAnalytics.summary.average_score,
      med: remoteAnalytics.summary.median_score,
      max: remoteAnalytics.summary.highest_score,
      min: remoteAnalytics.summary.lowest_score,
      passCount: remoteAnalytics.summary.pass_count,
      excellentCount: remoteAnalytics.summary.excellent_count,
      matchedCount: remoteAnalytics.summary.matched_count,
      unmatchedCount: remoteAnalytics.summary.unmatched_count,
      unknownCodeCount: remoteAnalytics.summary.unknown_code_count,
    };
  }, [remoteAnalytics, summaryFallback]);

  const scoreDistribution = useMemo<DistributionView[]>(() => {
    if (remoteAnalytics) return remoteAnalytics.distribution;
    return buildLocalDistribution(matchedStudentResults.map(item => item.score));
  }, [matchedStudentResults, remoteAnalytics]);

  const gradeBands = useMemo<GradeBandView[]>(() => {
    if (remoteAnalytics) {
      const colors = ['bg-emerald-500', 'bg-blue-500', 'bg-amber-500', 'bg-red-500'];
      return remoteAnalytics.grade_bands.map((band, index) => ({
        label: band.label,
        value: band.count,
        percent: `${Math.round(band.percent * 100)}%`,
        color: colors[index] ?? 'bg-slate-500',
      }));
    }
    return buildLocalGradeBands(matchedStudentResults);
  }, [matchedStudentResults, remoteAnalytics]);

  const comparisonItems = useMemo<ComparisonView[]>(() => {
    if (remoteAnalytics) {
      return remoteAnalytics.comparison.map(item => ({
        label: item.label,
        subLabel: item.sub_label,
        count: item.count,
        avg: item.average_score,
      }));
    }
    return buildLocalComparison(classes, matchedStudentResults, selectedClassId, selectedExamId, codeOptions);
  }, [classes, codeOptions, matchedStudentResults, remoteAnalytics, selectedClassId, selectedExamId]);

  const selectedExam = useMemo(() => {
    if (selectedExamId === ALL) return null;
    return selectedClass?.exams.find(exam => exam.id === selectedExamId)
      ?? classes.flatMap(item => item.exams).find(exam => exam.id === selectedExamId)
      ?? null;
  }, [classes, selectedClass, selectedExamId]);

  const selectedAnswerKey = selectedCode?.answerKey ?? (selectedExam?.codes?.length === 1 ? selectedExam.codes[0].answerKey : []);
  const questionAnalysis = useMemo<QuestionView[]>(() => {
    if (remoteAnalytics && remoteAnalytics.top_failed_questions.length > 0) {
      return remoteAnalytics.top_failed_questions.map(item => ({
        question: item.question,
        difficulty: item.difficulty,
        blankRate: item.blank_rate,
        correctCount: item.correct_count,
        wrongCount: item.wrong_count,
        blankCount: item.blank_count,
        trapOption: item.trap_option,
      }));
    }
    return buildLocalQuestions(matchedStudentResults, selectedAnswerKey);
  }, [matchedStudentResults, remoteAnalytics, selectedAnswerKey]);

  const filteredCountLabel = remoteAnalytics
    ? `${remoteAnalytics.summary.total_submissions} student${remoteAnalytics.summary.total_submissions > 1 ? 's' : ''}`
    : filteredStudentResults.length > 0
      ? `${filteredStudentResults.length} student${filteredStudentResults.length > 1 ? 's' : ''}`
      : 'No students';

  const canShowStudentScores = selectedClassId !== ALL && selectedExamId !== ALL;
  const studentScoreRows = useMemo(() => {
    const submissionsByMssv = new Map<string, ScannedResult>();
    matchedStudentResults.forEach((result) => {
      const mssv = result.studentMssv?.trim();
      if (!mssv) return;
      const current = submissionsByMssv.get(mssv);
      if (!current || result.scannedAt > current.scannedAt) {
        submissionsByMssv.set(mssv, result);
      }
    });

    const rosterRows = selectedClass?.students.map((student) => {
      const submission = submissionsByMssv.get(student.mssv);
      return {
        id: student.id,
        studentName: student.fullName,
        studentId: student.mssv,
        examCode: submission?.examCode?.trim() ?? '',
        score: submission?.score ?? null,
        scannedAt: submission?.scannedAt ?? 0,
      };
    }) ?? [];

    return rosterRows
      .sort((a, b) => {
        const byName = a.studentName.localeCompare(b.studentName, undefined, { sensitivity: 'base' });
        if (byName !== 0) return byName;
        const byId = a.studentId.localeCompare(b.studentId, undefined, { sensitivity: 'base' });
        if (byId !== 0) return byId;
        return b.scannedAt - a.scannedAt;
      });
  }, [matchedStudentResults, selectedClass]);

  const currentScannerClassId = selectedClassId !== ALL ? selectedClassId : classes[0]?.id;
  const currentScannerExamId = selectedExamId !== ALL
    ? selectedExamId
    : (selectedClassId !== ALL ? selectedClass?.exams[0]?.id : classes[0]?.exams[0]?.id);

  const exportFilteredCsv = () => {
    const rows = [
      ['class', 'exam', 'code', 'student_name', 'mssv', 'score', 'correct_count', 'total_questions', 'status'],
      ...matchedStudentResults.map(result => {
        const classRoom = classes.find(item => item.id === result.classId);
        const exam = classes.flatMap(item => item.exams).find(item => item.id === result.examId);
        return [
          classRoom?.code ?? result.classId,
          exam?.title ?? result.examId,
          result.examCode,
          result.studentName,
          result.studentMssv,
          formatScore(result.score),
          formatScore(result.correctCount),
          String(result.totalQuestions),
          result.status,
        ];
      }),
    ];
    downloadCsv('analytics_filtered_results.csv', rows);
  };

  const exportStudentScoresCsv = () => {
    const rows = [
      ['student_name', 'student_id', 'exam_code', 'score'],
      ...studentScoreRows.map((row) => [
        row.studentName,
        row.studentId,
        row.examCode,
        row.score == null ? '' : formatScore(row.score),
      ]),
    ];
    downloadCsv('student_score_list.csv', rows);
  };

  const exportStudentScoresExcel = () => {
    const workbook = XLSX.utils.book_new();
    const worksheet = XLSX.utils.json_to_sheet(
      studentScoreRows.map((row) => ({
        student_name: row.studentName,
        student_id: row.studentId,
        exam_code: row.examCode,
        score: row.score == null ? '' : Number(formatScore(row.score)),
      }))
    );
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Scores');
    XLSX.writeFile(workbook, 'student_score_list.xlsx');
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.3em] font-black text-slate-400">Overview Statistics</div>
          <h2 className="text-2xl md:text-3xl font-black text-slate-900 mt-2">Exam Analytics</h2>
          <p className="text-slate-500 mt-1 max-w-2xl">
            Track score distribution, item difficulty, and comparisons across classes, exams, and exam codes.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={exportFilteredCsv} className="btn-outline text-sm flex items-center gap-2">
            <Download size={16} />
            Export CSV
          </button>
          <button
            onClick={() => onStartScanner(currentScannerClassId, currentScannerExamId)}
            className="btn-primary text-sm flex items-center gap-2"
            disabled={!currentScannerClassId || !currentScannerExamId}
          >
            <Camera size={16} />
            Start Grading
          </button>
        </div>
      </div>

      <section className="p-5 md:p-6 rounded-xl border !bg-[#101a2b] !text-white !border-white/10 shadow-2xl overflow-hidden">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] font-black text-slate-400">
          <Filter size={14} />
          Analytics filters
        </div>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="block">
            <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">Level 1: Class</span>
            <select
              value={selectedClassId}
              onChange={(e) => setSelectedClassId(e.target.value)}
              className="mt-2 w-full !bg-white/5 border border-white/10 rounded-xl px-4 py-3 font-bold !text-white outline-none"
            >
              <option value={ALL} className="bg-[#0f172a]">All classes</option>
              {classes.map(classRoom => (
                <option key={classRoom.id} value={classRoom.id} className="bg-[#0f172a]">
                  {classRoom.code} · {classRoom.name}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">Level 2: Exam</span>
            <select
              value={selectedExamId}
              onChange={(e) => setSelectedExamId(e.target.value)}
              className="mt-2 w-full !bg-white/5 border border-white/10 rounded-xl px-4 py-3 font-bold !text-white outline-none"
            >
              <option value={ALL} className="bg-[#0f172a]">All exams</option>
              {examOptions.map((exam) => {
                const classRoom = classes.find(item => item.id === exam.classId);
                return (
                  <option key={exam.id} value={exam.id} className="bg-[#0f172a]">
                    {classRoom?.code ?? 'Unknown class'} · {exam.title}
                  </option>
                );
              })}
            </select>
          </label>

          <label className="block">
            <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">Level 3: Exam code</span>
            <select
              value={selectedCodeKey}
              onChange={(e) => setSelectedCodeKey(e.target.value)}
              className="mt-2 w-full !bg-white/5 border border-white/10 rounded-xl px-4 py-3 font-bold !text-white outline-none"
            >
              <option value={ALL} className="bg-[#0f172a]">All codes</option>
              {codeOptions.map(code => (
                <option key={code.value} value={code.value} className="bg-[#0f172a]">
                  {selectedExamId !== ALL ? code.examCode : `${code.classCode} · ${code.examTitle} · ${code.examCode}`}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-slate-300">
            Viewing: <span className="font-black text-white">{filteredCountLabel}</span>
            {remoteLoading && <span className="ml-2 text-blue-300">(loading...)</span>}
            {remoteError && <span className="ml-2 text-amber-300">(local fallback)</span>}
          </div>
          <div className="inline-flex items-center gap-2 rounded-xl bg-blue-500/15 px-3 py-2 text-xs font-black text-blue-200">
            <BarChart3 size={14} />
            Live updates from the current filter
          </div>
        </div>
      </section>

      {filteredResults.length === 0 ? (
        <div className="card p-10 md:p-14 text-center">
          <ClipboardList size={48} className="mx-auto text-slate-300 mb-4" />
          <h3 className="text-2xl font-black text-slate-800">No analytics data yet</h3>
          <p className="text-slate-500 mt-2">
            Select a class, exam, or code that already has graded student results to view analytics.
          </p>
        </div>
      ) : (
        <>
          <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <StatCard icon={<ClipboardList size={18} />} label="Total submissions" value={`${summary.count}`} helper={`${summary.matchedCount} matched · ${summary.unmatchedCount + summary.unknownCodeCount} need review`} />
            <StatCard icon={<TrendingUp size={18} />} label="Average score" value={`${formatScore(summary.avg)}/10`} helper={`Median ${formatScore(summary.med)} · matched only`} />
            <StatCard icon={<Target size={18} />} label="Highest / Lowest" value={`${formatScore(summary.max)} · ${formatScore(summary.min)}`} helper="Actual score range" />
            <StatCard icon={<Users size={18} />} label="Pass rate" value={`${percent(summary.passCount, summary.matchedCount)}`} helper={`Excellent: ${percent(summary.excellentCount, summary.matchedCount)}`} />
          </section>

          <section className="grid grid-cols-1 xl:grid-cols-[1.15fr_0.85fr] gap-6">
            <div className="card p-6">
              <div className="flex items-center justify-between gap-3 mb-5">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.28em] text-slate-400 font-black">Score distribution</div>
                  <h3 className="text-xl font-black text-slate-900 mt-1">Score Distribution</h3>
                </div>
                <PieChart size={18} className="text-primary" />
              </div>
              <div className="space-y-3">
                {scoreDistribution.map(bucket => {
                  const maxCount = Math.max(...scoreDistribution.map(item => item.count), 1);
                  const width = `${Math.max(6, (bucket.count / maxCount) * 100)}%`;
                  return (
                    <div key={bucket.label} className="grid grid-cols-[56px_1fr_52px] items-center gap-3">
                      <div className="text-[11px] font-black text-slate-400">{bucket.label}</div>
                      <div className="h-3 rounded-full bg-slate-100 overflow-hidden">
                        <div className="h-full rounded-full bg-primary" style={{ width }} />
                      </div>
                      <div className="text-right text-sm font-black text-slate-700">{bucket.count}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="card p-6">
              <div className="flex items-center justify-between gap-3 mb-5">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.28em] text-slate-400 font-black">Grade bands</div>
                  <h3 className="text-xl font-black text-slate-900 mt-1">Grade Bands</h3>
                </div>
                <Target size={18} className="text-primary" />
              </div>
              <div className="space-y-4">
                {gradeBands.map(band => (
                  <div key={band.label}>
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-semibold text-slate-700">{band.label}</span>
                      <span className="font-black text-slate-900">{band.value} students ({band.percent})</span>
                    </div>
                    <div className="mt-2 h-3 rounded-full bg-slate-100 overflow-hidden">
                      <div className={`${band.color} h-full rounded-full`} style={{ width: band.percent }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-6">
            <div className="card p-6 flex flex-col min-h-0">
              <div className="flex items-center justify-between gap-3 mb-5">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.28em] text-slate-400 font-black">Most missed questions</div>
                  <h3 className="text-xl font-black text-slate-900 mt-1">
                    {selectedCode ? `Analysis for code ${selectedCode.examCode}` : 'Select a code to analyze questions'}
                  </h3>
                </div>
                <Lightbulb size={18} className="text-primary" />
              </div>

              {selectedCode ? (
                <div className="flex-1 min-h-0 max-h-[72vh] overflow-y-auto pr-2 space-y-3">
                  {questionAnalysis.map(item => (
                    <div key={item.question} className="rounded-2xl border border-slate-200 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-[10px] uppercase tracking-[0.24em] text-slate-400 font-black">Q{item.question}</div>
                          <div className="text-sm text-slate-600 mt-1">
                            Difficulty p = {item.difficulty.toFixed(2)} · Blank {percent(item.blankCount, summary.matchedCount)} · Trap answer: <span className="font-black text-slate-900">{item.trapOption}</span>
                          </div>
                        </div>
                        <div className={`px-3 py-1.5 rounded-xl text-sm font-black ${item.difficulty < 0.2 ? 'bg-red-50 text-red-700' : item.difficulty > 0.8 ? 'bg-emerald-50 text-emerald-700' : 'bg-blue-50 text-blue-700'}`}>
                          {Math.round(item.difficulty * 100)}%
                        </div>
                      </div>
                      <div className="mt-3 h-3 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className={item.difficulty < 0.2 ? 'bg-red-500 h-full rounded-full' : item.difficulty > 0.8 ? 'bg-emerald-500 h-full rounded-full' : 'bg-blue-500 h-full rounded-full'}
                          style={{ width: `${Math.max(6, item.difficulty * 100)}%` }}
                        />
                      </div>
                      <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                        <div className="rounded-xl bg-slate-50 p-2 text-center">
                          <div className="text-slate-400 font-black uppercase tracking-widest">Correct</div>
                          <div className="mt-1 font-black text-slate-900">{item.correctCount}</div>
                        </div>
                        <div className="rounded-xl bg-slate-50 p-2 text-center">
                          <div className="text-slate-400 font-black uppercase tracking-widest">Wrong</div>
                          <div className="mt-1 font-black text-slate-900">{item.wrongCount}</div>
                        </div>
                        <div className="rounded-xl bg-slate-50 p-2 text-center">
                          <div className="text-slate-400 font-black uppercase tracking-widest">Blank</div>
                          <div className="mt-1 font-black text-slate-900">{item.blankCount}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl bg-slate-50 border border-dashed border-slate-200 p-8 text-center">
                  <BookOpen size={40} className="mx-auto text-slate-300 mb-3" />
                  <p className="font-semibold text-slate-600">
                    Chon mot ma de cu the de he thong tinh do kho cau hoi va top cau sai chinh xac.
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-6">
              <div className="card p-6">
                <div className="flex items-center justify-between gap-3 mb-5">
                  <div>
                  <div className="text-[10px] uppercase tracking-[0.28em] text-slate-400 font-black">Performance comparison</div>
                    <h3 className="text-xl font-black text-slate-900 mt-1">Comparison</h3>
                  </div>
                  <TrendingUp size={18} className="text-primary" />
                </div>

                <div className="space-y-3">
                  {comparisonItems.length > 0 ? comparisonItems.slice(0, 6).map(item => (
                    <div key={`${item.label}-${item.subLabel}`} className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-black text-slate-900">{item.label}</div>
                          <div className="text-xs text-slate-400 mt-1">{item.subLabel}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-black text-primary">{item.avg.toFixed(2)} / 10</div>
                          <div className="text-[11px] uppercase tracking-widest text-slate-400 font-black">{item.count} students</div>
                        </div>
                      </div>
                    </div>
                  )) : (
                    <div className="text-sm text-slate-500">
                      No comparison data for the current filters.
                    </div>
                  )}
                </div>
              </div>

              <div className="card p-6 !bg-[#0f172a] !text-white !border-white/10 shadow-2xl overflow-hidden">
                <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] text-slate-300 font-black">
                  <Trophy size={14} />
                  Student scores
                </div>
                <div className="mt-2 flex items-start justify-between gap-3">
                  <h3 className="text-xl font-black text-white">Student score list</h3>
                  {canShowStudentScores && studentScoreRows.length > 0 && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={exportStudentScoresCsv}
                        className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/8 px-3 py-2 text-xs font-black text-white hover:bg-white/12"
                      >
                        <Download size={14} />
                        CSV
                      </button>
                      <button
                        onClick={exportStudentScoresExcel}
                        className="inline-flex items-center gap-2 rounded-xl border border-cyan-400/20 bg-cyan-400/10 px-3 py-2 text-xs font-black text-cyan-100 hover:bg-cyan-400/15"
                      >
                        <Download size={14} />
                        Excel
                      </button>
                    </div>
                  )}
                </div>
                <p className="mt-2 text-sm font-medium text-slate-200">
                  {canShowStudentScores
                    ? selectedCode
                      ? `Showing students for exam code ${selectedCode.examCode}.`
                      : 'Showing students for the selected class and exam.'
                    : 'Choose a class and an exam to display the student list and corresponding scores.'}
                </p>

                {canShowStudentScores ? (
                  studentScoreRows.length > 0 ? (
                    <div className="mt-4 overflow-hidden rounded-2xl border border-white/10 bg-slate-950/25">
                      <div className="grid grid-cols-[minmax(0,3fr)_64px_72px] gap-3 border-b border-white/10 px-4 py-3 text-[11px] uppercase tracking-[0.24em] text-slate-300 font-black">
                        <div>Student</div>
                        <div className="text-center">Code</div>
                        <div className="text-right">Score</div>
                      </div>
                      <div className="max-h-[420px] overflow-y-auto divide-y divide-white/5">
                        {studentScoreRows.map((row) => (
                          <div
                            key={row.id}
                            className="grid grid-cols-[minmax(0,3fr)_64px_72px] gap-3 px-4 py-3 items-center"
                          >
                            <div className="min-w-0">
                              <div
                                className="text-sm font-black leading-5 text-white break-words whitespace-normal"
                                title={row.studentName}
                              >
                                {row.studentName}
                              </div>
                              <div className="mt-1 text-xs font-semibold tracking-wide text-slate-300 break-all">{row.studentId}</div>
                            </div>
                            <div className="text-center text-sm font-black tabular-nums text-slate-100">{row.examCode}</div>
                            <div className="text-right text-sm font-black tabular-nums text-cyan-200">{row.score == null ? '' : formatScore(row.score)}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="mt-4 rounded-2xl border border-dashed border-white/15 bg-white/5 p-5 text-sm text-slate-300">
                      No student results match the current class, exam, and exam-code filters.
                    </div>
                  )
                ) : (
                  <div className="mt-4 rounded-2xl border border-dashed border-white/15 bg-white/5 p-5 text-sm text-slate-300">
                    The list stays hidden until both a class and an exam are selected.
                  </div>
                )}

                {false && (
                <ul className="mt-4 space-y-3 text-sm text-slate-300 leading-6">
                  <li>• Questions with <span className="font-black text-white">p &lt; 0.2</span> should be reviewed for answer-key or difficulty issues.</li>
                  <li>• Questions with <span className="font-black text-white">p &gt; 0.8</span> are very easy and work well as warm-up items.</li>
                  <li>• A high blank rate may indicate unclear wording or weak understanding.</li>
                  <li>• If one code's score distribution differs sharply, check the exam balance.</li>
                </ul>
                )}
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, helper }: { icon: ReactNode; label: string; value: string; helper: string }) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="text-[10px] uppercase tracking-[0.28em] font-black text-slate-400">{label}</div>
        <div className="text-primary">{icon}</div>
      </div>
      <div className="mt-3 text-3xl font-black text-slate-900">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{helper}</div>
    </div>
  );
}
