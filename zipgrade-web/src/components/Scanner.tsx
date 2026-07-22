import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, ReactNode } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  AlertCircle,
  CheckCircle2,
  Camera,
  Image as ImageIcon,
  List,
  RefreshCw,
  Upload,
  X,
} from 'lucide-react';
import { BackendIdentityResolution, BackendProcessResponse, ClassRoom, ScannedResult } from '../types';
import { gradeAnswers } from '../utils/grading';
import { isStudentNameMatch } from '../utils/studentIdentity';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const uid = () => Math.random().toString(36).slice(2, 10);

const resolveBackendUrl = (url?: string | null) => {
  if (!url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_BASE_URL}${url.startsWith('/') ? url : `/${url}`}`;
};

interface ScannerProps {
  classes: ClassRoom[];
  existingResults: ScannedResult[];
  selectedClassId: string;
  selectedExamId: string;
  onSelectContext: (classId: string, examId: string) => void;
  onResult: (result: ScannedResult) => void;
  onClose: () => void;
}

type ScanStatus = 'initializing' | 'ready' | 'processing' | 'review' | 'error';

type DraftReview = {
  backend: BackendProcessResponse;
  submissionId: number | null;
  name: string;
  mssv: string;
  examCode: string;
  answers: string[];
  resolvedStudentId?: string | null;
};

function normalizeAnswerList(raw: string[] | null | undefined, totalQuestions: number) {
  const list = Array.isArray(raw) ? raw.slice(0, totalQuestions) : [];
  while (list.length < totalQuestions) list.push('');
  return list;
}

function StageCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <section className="bg-[#101a2b] text-white rounded-[28px] shadow-2xl overflow-hidden border border-white/10 flex flex-col min-h-0">
      <div className="px-5 py-4 border-b border-white/10">
        <div className="text-[10px] uppercase tracking-[0.28em] font-black text-slate-400">{subtitle}</div>
        <div className="text-2xl font-black mt-1">{title}</div>
      </div>
      <div className="p-5 min-h-0 flex-1">{children}</div>
    </section>
  );
}

function renderImage(url?: string | null, label?: string, className = 'max-h-64') {
  const resolved = resolveBackendUrl(url);
  if (!resolved) {
    return (
      <div className={`w-full h-40 rounded-2xl border border-dashed border-slate-300 bg-slate-50 flex flex-col items-center justify-center text-slate-400 ${className}`}>
        <ImageIcon size={24} />
        <span className="text-xs mt-2">{label || 'No image'}</span>
      </div>
    );
  }

  return (
    <a href={resolved} target="_blank" rel="noreferrer" className="block group">
      <img
        src={resolved}
        alt={label || 'preview'}
        className={`w-full rounded-xl object-contain ${className}`}
        loading="lazy"
      />
    </a>
  );
}

export default function Scanner({ classes, existingResults, selectedClassId, selectedExamId, onSelectContext, onResult, onClose }: ScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const identityResolutionRef = useRef<HTMLDivElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [status, setStatus] = useState<ScanStatus>('initializing');
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftReview | null>(null);
  const [lastSaved, setLastSaved] = useState<ScannedResult | null>(null);
  const [saveResolution, setSaveResolution] = useState<BackendIdentityResolution | null>(null);
  const [resolutionPrompted, setResolutionPrompted] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [scanExamCode, setScanExamCode] = useState('');
  const [scanArmed, setScanArmed] = useState(true);

  const selectedClass = useMemo(
    () => classes.find(item => item.id === selectedClassId) ?? classes[0],
    [classes, selectedClassId]
  );
  const selectedExam = useMemo(
    () => selectedClass?.exams.find(exam => exam.id === selectedExamId) ?? selectedClass?.exams[0],
    [selectedClass, selectedExamId]
  );

  const selectedExamCode = useMemo(() => {
    if (!draft || !selectedExam) return null;
    return selectedExam.codes.find(code => code.code === draft.examCode) ?? null;
  }, [draft, selectedExam]);

  const currentGrading = useMemo(() => {
    if (!draft || !selectedExamCode) return null;
    return gradeAnswers(draft.answers, selectedExamCode.answerKey);
  }, [draft, selectedExamCode]);

  const totalQuestions = selectedExam?.questionCount ?? draft?.answers.length ?? 0;
  const selectedAnswerKey = selectedExamCode?.answerKey ?? [];
  const isReviewMode = status === 'review' && !!draft;
  const isBusy = status === 'processing' || status === 'review';

  useEffect(() => {
    setScanExamCode(selectedExam?.codes[0]?.code ?? '');
  }, [selectedExam?.id]);

  useEffect(() => {
    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.muted = true;
          videoRef.current.playsInline = true;
          await videoRef.current.play().catch(() => undefined);
          setCameraReady(true);
          setStatus('ready');
        }
      } catch (err) {
        console.error('Camera error:', err);
        setCameraReady(false);
        setError('Cannot access camera. Upload image is still available.');
        setStatus('ready');
      }
    }

    startCamera();

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!resolutionPrompted || !saveResolution?.candidates?.length) return;
    identityResolutionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [resolutionPrompted, saveResolution]);

  const openDraft = useCallback((data: BackendProcessResponse) => {
    const initialExamCode = data.student_info?.ma_de || scanExamCode || selectedExam?.codes[0]?.code || '';
    setDraft({
      backend: data,
      submissionId: data.submission_id ?? null,
      name: data.student_info?.name || '',
      mssv: data.student_info?.mssv || '',
      examCode: initialExamCode,
      answers: normalizeAnswerList(data.answers, selectedExam?.questionCount ?? data.answers?.length ?? 0),
      resolvedStudentId: undefined,
    });
    setSaveResolution(null);
    setResolutionPrompted(false);
    setStatus('review');
  }, [scanExamCode, selectedExam]);

  const processImageBlob = useCallback(async (blob: Blob, filename: string) => {
    if (!selectedClass || !selectedExam) return;
    setError(null);
    setStatus('processing');
    setDraft(null);
    setLastSaved(null);
    setSaveResolution(null);
    setResolutionPrompted(false);

    const formData = new FormData();
    formData.append('file', blob, filename);
    formData.append('class_id', selectedClass.id);
    formData.append('exam_id', selectedExam.id);
    const activeCode = selectedExam.codes.find(code => code.code === scanExamCode) ?? selectedExam.codes[0];
    formData.append('correct_answers', activeCode?.answerKey.join(',') ?? '');
    formData.append('debug_artifacts', 'true');

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/process-exam`, {
        method: 'POST',
        body: formData,
      });
      const data = (await response.json()) as BackendProcessResponse;

      if (response.ok && data.success) {
        openDraft(data);
      } else {
        setError(data.error || data.message || 'OMR server returned an error.');
        setStatus('error');
      }
    } catch (err) {
      console.error(err);
      setError('Cannot connect to the OMR backend server.');
      setStatus('error');
    }
  }, [openDraft, scanExamCode, selectedClass, selectedExam]);

  const uploadImage = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await processImageBlob(file, file.name || 'upload.png');
    event.target.value = '';
  }, [processImageBlob]);

  const resumeCameraPreview = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    if (streamRef.current && video.srcObject !== streamRef.current) {
      video.srcObject = streamRef.current;
    }
    video.play().catch(() => undefined);
  }, []);

  const scan = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (!scanArmed) {
      setError(null);
      setStatus('ready');
      setLastSaved(null);
      setDraft(null);
      setScanArmed(true);
      await resumeCameraPreview();
      return;
    }

    const waitForVideoFrame = async (timeoutMs = 1500) => {
      const hasFrame = () => video.videoWidth > 0 && video.videoHeight > 0 && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA;
      if (hasFrame()) return true;

      await resumeCameraPreview();

      return await new Promise<boolean>((resolve) => {
        const timeout = window.setTimeout(() => {
          cleanup();
          resolve(hasFrame());
        }, timeoutMs);

        const onReady = () => {
          if (!hasFrame()) return;
          cleanup();
          resolve(true);
        };

        const cleanup = () => {
          window.clearTimeout(timeout);
          video.removeEventListener('loadeddata', onReady);
          video.removeEventListener('playing', onReady);
          video.removeEventListener('canplay', onReady);
        };

        video.addEventListener('loadeddata', onReady);
        video.addEventListener('playing', onReady);
        video.addEventListener('canplay', onReady);
        video.play().catch(() => undefined);
      });
    };

    const ready = await waitForVideoFrame();
    if (!ready || video.videoWidth <= 0 || video.videoHeight <= 0) {
      setError('Camera frame is not ready yet. Please wait a moment and scan again.');
      setStatus('error');
      return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/png'));
    if (!blob) {
      setError('Cannot capture an image from the camera frame.');
      setStatus('error');
      return;
    }
    await processImageBlob(blob, 'capture.png');
  }, [processImageBlob, resumeCameraPreview, scanArmed]);

  const saveReview = useCallback(async () => {
    if (!draft || !selectedClass || !selectedExam) return;
    const detectedMssv = draft.mssv.trim();
    const trimmedName = draft.name.trim();
    const classId = Number(selectedClass.id);
    const examId = Number(selectedExam.id);
    const examCodeId = selectedExamCode?.id ? Number(selectedExamCode.id) : null;
    if (!Number.isFinite(classId) || !Number.isFinite(examId) || (examCodeId != null && !Number.isFinite(examCodeId))) {
      setError('Academic data is not synced yet. Please wait a moment and try again.');
      return;
    }
    const autoMatchedStudent = selectedClass.students.find(student => student.mssv === detectedMssv) ?? null;
    const autoNameMatches = autoMatchedStudent ? isStudentNameMatch(trimmedName, autoMatchedStudent.fullName) : false;
    const autoStudentId = autoMatchedStudent?.id ? Number(autoMatchedStudent.id) : null;
    const autoDuplicateResult = existingResults.find(result => {
      const sameClassExam = result.classId === selectedClass.id && result.examId === selectedExam.id;
      if (!sameClassExam) return false;
      if (autoStudentId != null) return result.studentId === String(autoStudentId);
      return result.studentMssv === detectedMssv;
    });

    const needsResolution = draft.resolvedStudentId === undefined && (!!autoDuplicateResult || !autoMatchedStudent);
    let activeResolution = saveResolution;
    const resolutionStale = !activeResolution
      || activeResolution.detected_mssv !== detectedMssv
      || activeResolution.ocr_name !== trimmedName;

    if (needsResolution && resolutionStale) {
      try {
        const resolutionResponse = await fetch(`${API_BASE_URL}/api/v1/submissions/resolve-identity`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            class_id: classId,
            exam_id: examId,
            detected_mssv: detectedMssv,
            detected_name: trimmedName,
          }),
        });
        if (!resolutionResponse.ok) {
          const detail = await resolutionResponse.text();
          throw new Error(detail || `resolve-identity failed: ${resolutionResponse.status}`);
        }
        activeResolution = await resolutionResponse.json() as BackendIdentityResolution;
        setSaveResolution(activeResolution);
        setResolutionPrompted(false);
      } catch (err) {
        console.warn('Failed to resolve submission identity:', err);
        const message = err instanceof Error ? err.message : 'Failed to validate student identity before saving.';
        setError(message);
        return;
      }
    }

    if (needsResolution && activeResolution?.needs_user_selection && draft.resolvedStudentId === undefined && (activeResolution.candidates?.length ?? 0) > 0) {
      setResolutionPrompted(true);
      setError(null);
      return;
    }

    const selectedStudent = draft.resolvedStudentId
      ? selectedClass.students.find(student => student.id === draft.resolvedStudentId)
      : null;

    let effectiveStudent = null as typeof selectedStudent;
    let studentId: number | null = null;
    let canonicalStudentMssv = detectedMssv;
    let canonicalStudentName = trimmedName || 'Unknown student';
    let submissionStatus: 'matched' | 'unmatched' | 'unknown_code' = 'unmatched';

    if (!selectedExamCode) {
      submissionStatus = 'unknown_code';
      if (selectedStudent) {
        effectiveStudent = selectedStudent;
        studentId = Number(selectedStudent.id);
        canonicalStudentMssv = selectedStudent.mssv;
        canonicalStudentName = selectedStudent.fullName;
      } else if (draft.resolvedStudentId === null) {
        submissionStatus = 'unknown_code';
      } else if (autoMatchedStudent && autoNameMatches && !autoDuplicateResult) {
        effectiveStudent = autoMatchedStudent;
        studentId = Number(autoMatchedStudent.id);
        canonicalStudentMssv = autoMatchedStudent.mssv;
        canonicalStudentName = autoMatchedStudent.fullName;
      }
    } else if (selectedStudent) {
      effectiveStudent = selectedStudent;
      studentId = Number(selectedStudent.id);
      canonicalStudentMssv = selectedStudent.mssv;
      canonicalStudentName = selectedStudent.fullName;
      submissionStatus = 'matched';
    } else if (draft.resolvedStudentId === null) {
      submissionStatus = 'unmatched';
    } else if (autoMatchedStudent && autoNameMatches && !autoDuplicateResult) {
      effectiveStudent = autoMatchedStudent;
      studentId = Number(autoMatchedStudent.id);
      canonicalStudentMssv = autoMatchedStudent.mssv;
      canonicalStudentName = autoMatchedStudent.fullName;
      submissionStatus = 'matched';
    } else {
      submissionStatus = 'unmatched';
    }

    if (studentId != null && !Number.isFinite(studentId)) {
      setError('Academic data is not synced yet. Please wait a moment and try again.');
      return;
    }
    const grading = currentGrading ?? gradeAnswers(draft.answers, selectedExamCode?.answerKey ?? []);
    const answers = Object.fromEntries(draft.answers.map((answer, index) => [index + 1, answer || null]));
    const duplicateResult = existingResults.find(result => {
      const sameClassExam = result.classId === selectedClass.id && result.examId === selectedExam.id;
      if (!sameClassExam) return false;
      if (studentId == null) return false;
      return result.studentId === String(studentId);
    });

    if (duplicateResult) {
      const shouldOverwrite = window.confirm(
        `A duplicate submission was found for this student in the current class/code.\n\n` +
        `Existing record: ${duplicateResult.studentName} - ID ${duplicateResult.studentMssv}\n` +
        `Do you want to overwrite the existing record?`
      );
      if (!shouldOverwrite) {
        setError('Duplicate detected. Save cancelled.');
        return;
      }
    }

    const result: ScannedResult = {
      id: uid(),
      submissionId: draft.submissionId != null ? String(draft.submissionId) : undefined,
      classId: selectedClass.id,
      examId: selectedExam.id,
      studentId: effectiveStudent?.id,
      studentMssv: canonicalStudentMssv,
      studentName: canonicalStudentName,
      detectedName: trimmedName,
      examCode: draft.examCode,
      score: grading.score,
      correctCount: grading.correct_count,
      totalQuestions: grading.total,
      answers,
      resultImageUrl: draft.backend.result_image_url ?? null,
      sourceImageUrl: draft.backend.source_image_url ?? null,
      alignedImageUrl: draft.backend.aligned_image_url ?? null,
      crops: draft.backend.crops ?? null,
      omrImages: draft.backend.omr_images ?? null,
      preprocessImages: draft.backend.preprocess_images ?? null,
      details: grading.details,
      scannedAt: Date.now(),
      status: submissionStatus,
    };

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/submissions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          class_id: Number(selectedClass.id),
          exam_id: Number(selectedExam.id),
          exam_code_id: examCodeId,
          student_id: studentId,
          detected_mssv: detectedMssv,
          detected_name: draft.name || '',
          detected_exam_code: draft.examCode,
          answers: draft.answers,
          score: grading.score,
          correct_count: grading.correct_count,
          total_questions: grading.total,
          status: submissionStatus,
          source_image_url: draft.backend.source_image_url ?? null,
          aligned_image_url: draft.backend.aligned_image_url ?? null,
          result_image_url: draft.backend.result_image_url ?? null,
          student_info: {
            ...(draft.backend.student_info ?? {}),
            mssv: canonicalStudentMssv,
            name: canonicalStudentName,
            detected_mssv: detectedMssv,
            detected_name: trimmedName,
            selected_student_id: studentId,
            identity_resolution: activeResolution ?? null,
          },
          grading,
          crops: draft.backend.crops ?? null,
          omr_images: draft.backend.omr_images ?? null,
          preprocess_images: draft.backend.preprocess_images ?? null,
        }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const savedSubmission = await response.json() as { id: number };
      result.id = String(savedSubmission.id);
      result.submissionId = String(savedSubmission.id);
    } catch (err) {
      console.warn('Failed to sync reviewed submission to backend:', err);
      setError('Failed to save reviewed result to backend.');
      setStatus('review');
      return;
    }

    setLastSaved(result);
    onResult(result);
    setStatus('ready');
  }, [draft, selectedClass, selectedExam, selectedExamCode, currentGrading, onResult, existingResults, saveResolution]);

  const resetReview = useCallback(() => {
    setDraft(null);
    setLastSaved(null);
    setError(null);
    setSaveResolution(null);
    setResolutionPrompted(false);
    setScanArmed(false);
    setStatus('ready');
    window.setTimeout(() => resumeCameraPreview(), 0);
  }, [resumeCameraPreview]);

  return (
    <div className="fixed inset-0 bg-black z-[100] flex flex-col overflow-hidden">
      <div className="absolute top-0 left-0 right-0 p-4 flex justify-between items-center z-50 bg-gradient-to-b from-black/70 to-transparent">
        <button onClick={onClose} className="p-3 bg-white/10 backdrop-blur-md rounded-full text-white">
          <X size={24} />
        </button>
        <div className="flex items-center gap-2 bg-white/10 backdrop-blur-md px-4 py-2 rounded-full text-white text-sm font-bold">
          <List size={16} />
          <span>{selectedClass?.code || 'No class'} · {selectedExam?.title || 'No exam'}</span>
        </div>
        <div className="opacity-0 w-10" />
      </div>

      <div className="flex-1 min-h-0 pt-16">
        <AnimatePresence mode="wait">
          {isReviewMode ? (
            <motion.div
              key="review"
              initial={{ opacity: 0, y: 14, scale: 0.99 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10 }}
              className="h-full min-h-0 overflow-y-auto px-4 md:px-6 py-4"
            >
              <div className="min-h-full max-w-[1940px] 2xl:max-w-[2100px] mx-auto grid grid-cols-1 xl:grid-cols-[1.08fr_1.06fr_0.9fr] gap-4 pb-4 items-start">
                <StageCard subtitle="Student information" title="OCR / Identity">
                  <div className="space-y-3 min-h-0">
                    <div className="rounded-2xl bg-[#0d1524] border border-white/10 p-4">
            <div className="text-sm text-slate-400 mb-1">Full name (OCR)</div>
                      <input
                        value={draft.name}
                        onChange={(e) => {
                          setDraft({ ...draft, name: e.target.value, resolvedStudentId: undefined });
                          setSaveResolution(null);
                          setResolutionPrompted(false);
                          setError(null);
                        }}
                        className="w-full bg-transparent text-xl xl:text-[1.7rem] font-black text-white outline-none border-b border-white/10 pb-2"
                        placeholder="Student name"
                      />
                      <div className="mt-3">{renderImage(draft.backend.crops?.ho_va_ten, 'Name crop', 'max-h-20')}</div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div className="rounded-2xl bg-[#0d1524] border border-white/10 p-4">
            <div className="text-sm text-slate-400 mb-1">Student ID (OMR)</div>
                        <input
                          value={draft.mssv}
                          onChange={(e) => {
                            setDraft({ ...draft, mssv: e.target.value, resolvedStudentId: undefined });
                            setSaveResolution(null);
                            setResolutionPrompted(false);
                            setError(null);
                          }}
                          className="w-full bg-transparent text-xl font-black text-cyan-300 outline-none border-b border-white/10 pb-2 font-mono"
            placeholder="Student ID"
                        />
                        <div className="mt-3">{renderImage(draft.backend.crops?.mssv, 'Student ID crop', 'max-h-32')}</div>
                      </div>

                      <div className="rounded-2xl bg-[#0d1524] border border-white/10 p-4">
            <div className="text-sm text-slate-400 mb-1">Exam code (OMR)</div>
                        <input
                          value={draft.examCode}
                          onChange={(e) => setDraft({ ...draft, examCode: e.target.value })}
                          className="w-full bg-transparent text-xl font-black text-fuchsia-300 outline-none border-b border-white/10 pb-2 font-mono"
            placeholder="Exam code"
                        />
                        <div className="mt-3">{renderImage(draft.backend.crops?.ma_de, 'Code crop', 'max-h-32')}</div>
                      </div>
                    </div>

                    {!!saveResolution?.candidates?.length && (
                      <div ref={identityResolutionRef} className="rounded-2xl bg-[#0d1524] border border-amber-400/25 p-4 space-y-3">
                        <div>
                          <div className="text-[10px] uppercase tracking-[0.24em] font-black text-amber-300">Identity resolution</div>
                          <div className="mt-1 text-sm text-white font-bold">
                            {saveResolution?.needs_user_selection
                              ? 'Possible student matches found'
                              : 'Suggested student matches'}
                          </div>
                          {saveResolution?.reason && (
                            <div className="mt-1 text-xs text-slate-300">
                              Reason: {saveResolution.reason.replaceAll('_', ' ')}
                            </div>
                          )}
                          {resolutionPrompted && draft.resolvedStudentId === undefined && (
                            <div className="mt-2 text-xs text-amber-200">
                              Choose one suggested student or keep this scan as unmatched, then press save again.
                            </div>
                          )}
                        </div>

                        <div className="space-y-2">
                          {saveResolution.candidates.map((candidate) => {
                            const isSelected = draft.resolvedStudentId === String(candidate.student_id);
                            return (
                              <button
                                key={candidate.student_id}
                                type="button"
                                onClick={() => {
                                  setDraft({ ...draft, resolvedStudentId: String(candidate.student_id) });
                                  setResolutionPrompted(false);
                                  setError(null);
                                }}
                                className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                                  isSelected
                                    ? 'border-emerald-400 bg-emerald-500/15'
                                    : 'border-white/10 bg-white/5 hover:bg-white/10'
                                }`}
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <div>
                                    <div className="text-sm font-black text-white">{candidate.full_name}</div>
                                    <div className="mt-1 text-xs text-slate-300 font-mono">{candidate.mssv}</div>
                                  </div>
                                  <div className="text-right text-[11px] text-slate-300">
                                    <div>{candidate.reasons.join(', ')}</div>
                                    <div className="mt-1">score {candidate.name_similarity.toFixed(2)}</div>
                                  </div>
                                </div>
                                {candidate.has_existing_submission && (
                                  <div className="mt-2 text-xs text-amber-300">
                                    Existing submission #{candidate.existing_submission_id} already uses this student.
                                  </div>
                                )}
                              </button>
                            );
                          })}
                        </div>

                        <button
                          type="button"
                          onClick={() => {
                            setDraft({ ...draft, resolvedStudentId: null });
                            setResolutionPrompted(false);
                            setError(null);
                          }}
                          className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                            draft.resolvedStudentId === null
                              ? 'border-rose-400 bg-rose-500/15 text-white'
                              : 'border-white/10 bg-white/5 text-slate-200 hover:bg-white/10'
                          }`}
                        >
                          Keep this scan as unmatched
                        </button>
                      </div>
                    )}

                    <div className="rounded-2xl bg-[#0d1524] border border-white/10 p-4 space-y-2.5">
            <div className="text-[10px] uppercase tracking-[0.24em] font-black text-slate-500">OMR evidence</div>
                      <div className="grid grid-cols-3 gap-3">
                        {[
                          ['answer_1', draft.backend.omr_images?.answer_1],
                          ['answer_2', draft.backend.omr_images?.answer_2],
                          ['answer_3', draft.backend.omr_images?.answer_3],
                        ].map(([title, url]) => (
                          <div key={title as string} className="min-w-0">
                            {renderImage(url as string | null, title as string, 'max-h-100 max-w-100 xl:max-h-110 xl:max-w-100')}
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-2xl bg-[#0d1524] border border-white/10 p-4 flex items-center justify-between">
                      <div>
            <div className="text-[10px] uppercase tracking-[0.24em] font-black text-slate-500">OCR / OMR status</div>
            <div className={`text-sm font-black mt-1 ${selectedExamCode ? 'text-white' : 'text-rose-300'}`}>{selectedExamCode ? 'Code matched' : 'No code match'}</div>
            {!selectedExamCode && (
              <div className="mt-1 text-xs text-rose-200/80">
                This exam code is not configured for the selected exam. Saving will mark it as unknown_code.
              </div>
            )}
                      </div>
                      <div className="px-3 py-2 rounded-xl bg-emerald-500/15 text-emerald-300 font-black text-sm">
                        {currentGrading?.score.toFixed(2) ?? '0.00'} / 10
                      </div>
                    </div>
                  </div>
                </StageCard>

                <StageCard subtitle="Bounding box map" title="Scan results">
                  <div className="w-full h-full min-h-[420px] rounded-3xl bg-[#0d1524] border border-white/10 p-4 flex items-center justify-center overflow-hidden">
                    {draft.backend.result_image_url ? (
                      <img
                        src={resolveBackendUrl(draft.backend.result_image_url) || undefined}
                        alt="result"
                        className="w-full h-full object-contain rounded-2xl"
                        loading="lazy"
                      />
                    ) : (
                      <div className="text-slate-500">No visualized image</div>
                    )}
                  </div>
                </StageCard>

                <div className="xl:max-h-[calc(100dvh-7.5rem)] xl:min-h-0 relative z-20 pointer-events-auto">
                <StageCard subtitle="OMR results" title={`${totalQuestions} questions`}>
                  <div className="flex flex-col h-full min-h-0">
                    <div className="flex-1 min-h-0 overflow-y-auto space-y-3 pr-1 xl:overscroll-contain xl:max-h-[calc(100dvh-18rem)]">
                      {Array.from({ length: totalQuestions }, (_, index) => {
                        const student = draft.answers[index] ?? '';
                        const correct = selectedAnswerKey[index] ?? '';
                        return (
                          <div key={index} className="rounded-2xl bg-[#0d1524] border border-white/10 px-4 py-3 flex items-center justify-between gap-3">
                            <div className="min-w-[64px]">
                      <div className="text-[10px] uppercase tracking-[0.24em] text-slate-500 font-black">Q{index + 1}</div>
                              <div className="text-xs text-slate-400 mt-1">{correct || '-'}</div>
                            </div>
                            <input
                              value={student}
                              onChange={(e) => {
                                const next = draft.answers.slice();
                                next[index] = e.target.value.toUpperCase().replace(/[^ABCD]/g, '');
                                setDraft({ ...draft, answers: next });
                              }}
                              onFocus={(e) => e.currentTarget.select()}
                              className="w-24 md:w-28 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-center text-lg font-black text-cyan-300 font-mono outline-none"
                              placeholder="AB"
                            />
                          </div>
                        );
                      })}
                    </div>
                    <div className="sticky bottom-0 z-30 pt-4 border-t border-white/10 bg-[#101a2b] pointer-events-auto flex flex-col gap-3">
                      {resolutionPrompted && saveResolution?.candidates?.length ? (
                        <div className="rounded-2xl border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                          Choose one suggested student or keep this scan as unmatched, then press save again.
                        </div>
                      ) : null}
                      {error ? (
                        <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                          {error}
                        </div>
                      ) : null}
                      <button
                        onClick={saveReview}
                        className="relative z-40 pointer-events-auto w-full py-4 rounded-2xl bg-gradient-to-r from-indigo-500 to-violet-500 text-white font-black text-lg shadow-lg shadow-indigo-900/30"
                      >
                        Save reviewed result
                      </button>
                      <button
                        onClick={resetReview}
                        className="relative z-40 pointer-events-auto w-full py-3 rounded-2xl border border-white/10 bg-white/5 text-white font-bold"
                      >
                        Scan another paper
                      </button>
                    </div>
                  </div>
                </StageCard>
                </div>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="scan"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="h-full min-h-0 px-4 md:px-6 pb-4"
            >
              <div className="h-full max-w-[1800px] mx-auto grid grid-cols-1 xl:grid-cols-[340px_minmax(0,1fr)] gap-4">
                <aside className="hidden lg:flex bg-[#151619]/95 backdrop-blur-xl text-white rounded-[28px] shadow-2xl overflow-hidden border border-white/5 flex-col min-h-0">
                  <div className="p-5 md:p-6 border-b border-white/5">
          <h2 className="text-xl font-bold mb-1">Sheet scanner</h2>
          <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold">Review OCR, student ID, exam code, and OMR before saving</p>
                  </div>

                  <div className="flex-1 min-h-0 overflow-y-auto p-5 md:p-6 space-y-5">
                    <div className="space-y-4">
          <label className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Class</label>
                      <select
                        value={selectedClass?.id ?? ''}
                        onChange={(e) => onSelectContext(e.target.value, classes.find(item => item.id === e.target.value)?.exams[0]?.id ?? '')}
                        className="w-full min-h-12 bg-white/5 border border-white/10 rounded-xl px-3 py-3 text-sm font-bold text-white [&>option]:bg-[#151619] [&>option]:text-white"
                      >
                        {classes.map(item => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}
                      </select>

          <label className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Exam</label>
                      <select
                        value={selectedExam?.id ?? ''}
                        onChange={(e) => selectedClass && onSelectContext(selectedClass.id, e.target.value)}
                        className="w-full min-h-12 bg-white/5 border border-white/10 rounded-xl px-3 py-3 text-sm font-bold text-white [&>option]:bg-[#151619] [&>option]:text-white"
                      >
                        {selectedClass?.exams.map(exam => <option key={exam.id} value={exam.id}>{exam.title}</option>)}
                      </select>

                      <div className="bg-white/5 border border-white/10 rounded-xl p-3">
          <div className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-2">Exam codes</div>
                        <div className="flex flex-wrap gap-2">
                          {selectedExam?.codes.map(code => <span key={code.id} className="px-2 py-1 rounded-lg bg-blue-500/20 text-blue-200 text-xs font-bold">{code.code}</span>)}
                        </div>
                      </div>
                    </div>

                    <div className="bg-white/5 p-4 rounded-2xl border border-white/5">
                      <div className="flex justify-between items-center mb-2 gap-3">
                        <span className="text-xs text-gray-400">Backend</span>
                        <span className="text-xs font-bold text-green-500 break-all text-right">
                          {API_BASE_URL || '/api proxy'}
                        </span>
                      </div>
                      <div className="w-full bg-white/10 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-green-500 w-full h-full" />
                      </div>
                    </div>

                    <button
                      onClick={scan}
                      disabled={isBusy}
                      className={`w-full py-5 rounded-2xl flex flex-col items-center gap-1 shadow-2xl transition-all ${
                        isBusy ? 'bg-gray-600 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500 shadow-blue-900/20 active:scale-95'
                      }`}
                    >
                      <Camera size={32} />
          <span className="font-bold text-lg">Scan sheet</span>
                    </button>

                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isBusy}
                      className={`w-full py-4 rounded-2xl flex items-center justify-center gap-3 border border-white/10 transition-all ${
                        isBusy ? 'bg-gray-700 text-gray-400 cursor-not-allowed' : 'bg-white/5 hover:bg-white/10 text-white active:scale-95'
                      }`}
                    >
                      <Upload size={22} />
                    <span className="font-bold">Upload image</span>
                    </button>
                    <input ref={fileInputRef} type="file" accept="image/*" onChange={uploadImage} className="hidden" />
                  </div>
                </aside>

                <section className="bg-[#070b14]/90 backdrop-blur-xl rounded-[28px] shadow-2xl overflow-hidden border border-white/5 relative min-h-0">
                  <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-cover bg-slate-950 opacity-100" />
                  <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.08),transparent_38%),linear-gradient(to_bottom,rgba(2,6,23,0.05),rgba(2,6,23,0.45))]" />
                  <div className="absolute top-2 left-2 right-2 z-20 flex justify-between items-start gap-2 pointer-events-none">
                    <div className="max-w-[68%] rounded-xl bg-black/20 backdrop-blur-md border border-white/10 px-2.5 py-1.5 text-white shadow-lg">
                      <div className="text-[8px] md:text-[9px] uppercase tracking-[0.28em] text-slate-300 font-black">Camera</div>
                      <div className="text-[11px] md:text-sm font-bold leading-tight">{cameraReady ? 'Live preview ready' : 'Waiting for camera permission'}</div>
                    </div>
                    {!cameraReady && (
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="pointer-events-auto px-3 py-2 rounded-xl bg-white text-slate-900 text-[11px] font-black shadow-lg"
                      >
                        Upload
                      </button>
                    )}
                  </div>

                  <div className="relative z-10 h-full min-h-0 p-3 md:p-6 flex items-center justify-center">
                    <AnimatePresence mode="wait">
                      {status === 'processing' ? (
                        <motion.div key="processing" className="h-full w-full flex items-center justify-center text-white" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                          <div className="flex flex-col items-center gap-4 bg-black/25 backdrop-blur-md px-8 py-10 rounded-3xl border border-white/10">
                            <RefreshCw className="animate-spin" size={48} />
                            <div className="text-lg font-black">Scanning and preparing review...</div>
                            <div className="text-sm text-white/70">Detect text, read OCR, and grade OMR in progress.</div>
                          </div>
                        </motion.div>
                      ) : status === 'error' ? (
                        <motion.div key="error" className="h-full w-full flex items-center justify-center text-white" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                          <div className="max-w-md bg-red-500/85 backdrop-blur-md rounded-3xl p-8 text-center shadow-2xl">
                            <AlertCircle size={64} className="mx-auto mb-4" />
                            <div className="text-2xl font-black mb-2">Processing failed</div>
                            <p className="text-white/95">{error || 'Something went wrong.'}</p>
                            <button onClick={() => setStatus('ready')} className="mt-6 px-4 py-3 rounded-xl bg-white text-red-600 font-black">
                              Back to camera
                            </button>
                          </div>
                        </motion.div>
                      ) : lastSaved ? (
                        <motion.div key="saved" className="relative z-30 h-full w-full flex items-center justify-center text-white pointer-events-auto" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                          <div className="max-w-md bg-emerald-500/85 backdrop-blur-md rounded-3xl p-8 text-center shadow-2xl pointer-events-auto">
                            <CheckCircle2 size={64} className="mx-auto mb-4" />
                            <div className="text-2xl font-black mb-2">Review saved</div>
                            <p className="text-white/95">{lastSaved.studentName}</p>
                            <div className="mt-4 text-sm bg-white/20 px-4 py-2 rounded-lg">ID: {lastSaved.studentMssv} · Code: {lastSaved.examCode}</div>
                            <div className="mt-2 text-xs opacity-90">{lastSaved.correctCount} / {lastSaved.totalQuestions} correct</div>
                            <button type="button" onClick={resetReview} className="mt-6 px-4 py-3 rounded-xl bg-white text-emerald-600 font-black pointer-events-auto">
                              Scan another paper
                            </button>
                          </div>
                        </motion.div>
                      ) : (
                        <motion.div key="camera" className="relative w-full h-full min-h-[420px] md:min-h-[520px] rounded-[24px] border border-white/20 overflow-hidden flex items-center justify-center" initial={{ opacity: 1 }} animate={{ opacity: 1 }}>
                          <div className="relative aspect-[4/3] md:aspect-[3/4] w-full max-w-4xl h-full min-h-[320px] max-h-[calc(100dvh-11rem)] border-2 border-white/30 rounded-2xl overflow-hidden bg-transparent">
                            {!cameraReady && (
                              <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/90 text-white px-6 text-center">
                                <Camera size={42} className="mb-4 text-blue-400" />
                  <div className="text-lg font-black">Camera is not visible yet</div>
                                <p className="text-sm text-white/70 mt-2 max-w-sm">
                                  On mobile, please allow camera access or use the upload button if the browser blocks live preview.
                                </p>
                              </div>
                            )}
                            <div className="absolute -top-1 -left-1 w-8 h-8 border-l-4 border-t-4 border-blue-500 rounded-tl-xl" />
                            <div className="absolute -top-1 -right-1 w-8 h-8 border-r-4 border-t-4 border-blue-500 rounded-tr-xl" />
                            <div className="absolute -bottom-1 -left-1 w-8 h-8 border-l-4 border-b-4 border-blue-500 rounded-bl-xl" />
                            <div className="absolute -bottom-1 -right-1 w-8 h-8 border-r-4 border-b-4 border-blue-500 rounded-br-xl" />
                            {status === 'ready' && (
                              <motion.div
                                className="absolute left-0 right-0 h-1 bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.8)] z-10"
                                animate={{ top: ['5%', '95%', '5%'] }}
                                transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
                              />
                            )}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </section>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {!isReviewMode && (
        <div
          className="lg:hidden fixed z-[120] bg-[#0d0e12]/95 border border-white/10 rounded-[18px] p-2 shadow-2xl backdrop-blur-md"
          style={{ left: '0.5rem', right: '0.5rem', bottom: 'calc(env(safe-area-inset-bottom, 0px) + 0.5rem)' }}
        >
          <div className="grid grid-cols-3 gap-1.5">
            <label className="flex items-center gap-1 text-[8px] text-slate-300 w-full min-w-0 bg-white/5 border border-white/10 px-2 py-1.5 rounded-lg relative">
              <span className="text-slate-400 font-medium whitespace-nowrap shrink-0">Class</span>
              <select
                value={selectedClass?.id ?? ''}
                onChange={(e) => onSelectContext(e.target.value, classes.find(item => item.id === e.target.value)?.exams[0]?.id ?? '')}
                className="bg-transparent text-white outline-none font-bold pr-3 cursor-pointer appearance-none flex-1 truncate text-left min-w-0 text-[11px] leading-none"
              >
                {classes.map(item => <option key={item.id} value={item.id} className="bg-[#0c0d11] text-white">{item.code}</option>)}
              </select>
            </label>

            <label className="flex items-center gap-1 text-[8px] text-slate-300 w-full min-w-0 bg-white/5 border border-white/10 px-2 py-1.5 rounded-lg relative">
              <span className="text-slate-400 font-medium whitespace-nowrap shrink-0">Exam</span>
              <select
                value={selectedExam?.id ?? ''}
                onChange={(e) => selectedClass && onSelectContext(selectedClass.id, e.target.value)}
                className="bg-transparent text-white outline-none font-bold pr-3 cursor-pointer appearance-none flex-1 truncate text-left min-w-0 text-[11px] leading-none"
              >
                {selectedClass?.exams.map(exam => <option key={exam.id} value={exam.id} className="bg-[#0c0d11] text-white">{exam.title}</option>)}
              </select>
            </label>

            <label className="flex items-center gap-1 text-[8px] text-slate-300 w-full min-w-0 bg-white/5 border border-white/10 px-2 py-1.5 rounded-lg relative">
              <span className="text-slate-400 font-medium whitespace-nowrap shrink-0">Code</span>
              <select
                value={scanExamCode || selectedExam?.codes[0]?.code || ''}
                onChange={(e) => setScanExamCode(e.target.value)}
                className="bg-transparent text-white outline-none font-bold pr-3 cursor-pointer appearance-none flex-1 truncate text-left min-w-0 font-mono text-[11px] leading-none"
              >
                {selectedExam?.codes.map(code => <option key={code.id} value={code.code} className="bg-[#0c0d11] text-white">{code.code}</option>)}
              </select>
            </label>
          </div>

          <div className="flex gap-2 mt-2">
            <button
              onClick={scan}
              disabled={isBusy}
              className="flex-[3.6] bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700/50 disabled:text-slate-400 transition-all font-black text-[10px] uppercase tracking-[0.18em] text-white py-3 px-3 rounded-xl flex items-center justify-center gap-2 active:scale-[0.98] shadow-lg shadow-blue-900/10"
            >
              {status === 'processing' ? <RefreshCw className="animate-spin" size={13} /> : <Camera size={13} />}
              <span>Scan</span>
            </button>

            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isBusy}
              className="flex-[1] bg-[#1b1c22] hover:bg-[#23242c] disabled:bg-slate-700/50 transition-all text-slate-300 p-3 rounded-xl border border-white/5 active:scale-95 flex items-center justify-center"
              title="Upload image"
            >
              <Upload size={15} />
            </button>
          </div>
        </div>
      )}

      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
}
