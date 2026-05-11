import { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import type { ChangeEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, Camera, RefreshCw, CheckCircle2, AlertCircle, List, Upload } from 'lucide-react';
import { BackendProcessResponse, ClassRoom, ScannedResult } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const uid = () => Math.random().toString(36).slice(2, 10);

interface ScannerProps {
  classes: ClassRoom[];
  selectedClassId: string;
  selectedExamId: string;
  onSelectContext: (classId: string, examId: string) => void;
  onResult: (result: ScannedResult) => void;
  onClose: () => void;
}

export default function Scanner({ classes, selectedClassId, selectedExamId, onSelectContext, onResult, onClose }: ScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<'initializing' | 'ready' | 'processing' | 'success' | 'error'>('initializing');
  const [lastResult, setLastResult] = useState<ScannedResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedClass = useMemo(
    () => classes.find(item => item.id === selectedClassId) ?? classes[0],
    [classes, selectedClassId]
  );
  const selectedExam = useMemo(
    () => selectedClass?.exams.find(exam => exam.id === selectedExamId) ?? selectedClass?.exams[0],
    [selectedClass, selectedExamId]
  );

  useEffect(() => {
    let stream: MediaStream | null = null;

    async function startCamera() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          setStatus('ready');
        }
      } catch (err) {
        console.error('Camera error:', err);
        setError('Cannot access camera. Upload image is still available.');
        setStatus('ready');
      }
    }

    startCamera();

    return () => {
      if (stream) stream.getTracks().forEach(track => track.stop());
    };
  }, []);

  const processImageBlob = useCallback(async (blob: Blob, filename: string) => {
    if (!selectedClass || !selectedExam) return;
    setError(null);
    setStatus('processing');

    const formData = new FormData();
    formData.append('file', blob, filename);
    formData.append('correct_answers', selectedExam.codes[0]?.answerKey.join(',') ?? '');
    formData.append('debug_artifacts', 'true');

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/process-exam`, {
        method: 'POST',
        body: formData,
      });
      const data = (await response.json()) as BackendProcessResponse;

      if (response.ok && data.success) {
        const detectedCode = data.student_info?.ma_de || 'N/A';
        const matchedCode = selectedExam.codes.find(code => code.code === detectedCode);
        let grading = data.grading;

        if (matchedCode && matchedCode.answerKey.join(',') !== (selectedExam.codes[0]?.answerKey.join(',') ?? '')) {
          const regradeResponse = await fetch(`${API_BASE_URL}/api/v1/grade`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              student_answers: data.answers ?? [],
              correct_answers: matchedCode.answerKey.join(','),
            }),
          });
          if (regradeResponse.ok) {
            grading = await regradeResponse.json();
          }
        }

        const detectedMssv = data.student_info?.mssv || 'N/A';
        const matchedStudent = selectedClass.students.find(student => student.mssv === detectedMssv);
        const answers = Object.fromEntries((data.answers ?? []).map((answer, index) => [index + 1, answer || null]));
        const result: ScannedResult = {
          id: uid(),
          classId: selectedClass.id,
          examId: selectedExam.id,
          studentId: matchedStudent?.id,
          studentMssv: detectedMssv,
          studentName: matchedStudent?.fullName || data.student_info?.name || 'Unknown student',
          detectedName: data.student_info?.name || '',
          examCode: detectedCode,
          score: grading?.score ?? 0,
          correctCount: grading?.correct_count ?? 0,
          totalQuestions: grading?.total ?? selectedExam.questionCount,
          answers,
          resultImageUrl: data.result_image_url ?? null,
          crops: data.crops ?? null,
          details: grading?.details ?? [],
          scannedAt: Date.now(),
          status: !matchedCode ? 'unknown_code' : matchedStudent ? 'matched' : 'unmatched',
        };

        setLastResult(result);
        onResult(result);
        setStatus('success');
      } else {
        setError(data.error || data.message || 'OMR server returned an error.');
        setStatus('error');
      }
    } catch (err) {
      console.error(err);
      setError('Cannot connect to the OMR backend server.');
      setStatus('error');
    }

    setTimeout(() => setStatus('ready'), 3500);
  }, [selectedClass, selectedExam, onResult]);

  const scan = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

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
  }, [processImageBlob]);

  const uploadImage = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await processImageBlob(file, file.name || 'upload.png');
    event.target.value = '';
  }, [processImageBlob]);

  return (
    <div className="fixed inset-0 bg-black z-[100] flex flex-col md:flex-row overflow-hidden">
      <div className="absolute top-0 left-0 right-0 p-4 flex justify-between items-center z-50 bg-gradient-to-b from-black/60 to-transparent">
        <button onClick={onClose} className="p-3 bg-white/10 backdrop-blur-md rounded-full text-white">
          <X size={24} />
        </button>
        <div className="flex items-center gap-2 bg-white/10 backdrop-blur-md px-4 py-2 rounded-full text-white text-sm font-bold">
          <List size={16} />
          <span>{selectedClass?.code || 'No class'} · {selectedExam?.title || 'No exam'}</span>
        </div>
        <div className="opacity-0 w-10" />
      </div>

      <div className="flex-1 relative flex items-center justify-center bg-black">
        <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover md:object-contain" />

        <div className="absolute inset-0 flex items-center justify-center p-8 pointer-events-none">
          <div className="relative aspect-[3/4] w-full max-w-md border-2 border-white/30 rounded-2xl">
            <div className="absolute -top-1 -left-1 w-8 h-8 border-l-4 border-t-4 border-blue-500 rounded-tl-xl" />
            <div className="absolute -top-1 -right-1 w-8 h-8 border-r-4 border-t-4 border-blue-500 rounded-tr-xl" />
            <div className="absolute -bottom-1 -left-1 w-8 h-8 border-l-4 border-b-4 border-blue-500 rounded-bl-xl" />
            <div className="absolute -bottom-1 -right-1 w-8 h-8 border-r-4 border-b-4 border-blue-500 rounded-br-xl" />

            {status === 'ready' && <motion.div className="absolute left-0 right-0 h-1 bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.8)] z-10" animate={{ top: ['5%', '95%', '5%'] }} transition={{ duration: 3, repeat: Infinity, ease: 'linear' }} />}

            <AnimatePresence>
              {status === 'success' && lastResult && (
                <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-green-500/80 backdrop-blur-sm rounded-2xl flex flex-col items-center justify-center text-white p-6 text-center">
                  <CheckCircle2 size={72} className="mb-4" />
                  <h3 className="text-4xl font-black mb-2">{lastResult.score.toFixed(2)} / 10</h3>
                  <p className="text-lg font-medium opacity-90">{lastResult.studentName}</p>
                  <div className="mt-4 text-sm bg-white/20 px-4 py-2 rounded-lg">MSSV: {lastResult.studentMssv} · Code {lastResult.examCode}</div>
                  <div className="mt-2 text-xs opacity-90">{lastResult.correctCount} / {lastResult.totalQuestions} correct · {lastResult.status}</div>
                </motion.div>
              )}
              {status === 'processing' && <motion.div className="absolute inset-0 bg-blue-500/20 backdrop-blur-[2px] rounded-2xl flex items-center justify-center"><RefreshCw className="text-white animate-spin" size={48} /></motion.div>}
              {status === 'error' && <motion.div className="absolute inset-0 bg-red-500/80 backdrop-blur-sm rounded-2xl flex flex-col items-center justify-center text-white p-6"><AlertCircle size={64} className="mb-4" /><p className="text-center font-bold px-4">{error || 'Processing failed'}</p></motion.div>}
            </AnimatePresence>
          </div>
        </div>
      </div>

      <div className="w-full md:w-88 bg-[#151619] text-white p-6 flex flex-col gap-6 border-l border-white/5 relative z-[60]">
        <div className="hidden md:block">
          <h2 className="text-xl font-bold mb-1">Sheet scanner</h2>
          <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-6">Class roster + exam-code answer keys</p>
        </div>

        <div className="space-y-4">
          <label className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Class</label>
          <select value={selectedClass?.id ?? ''} onChange={(e) => onSelectContext(e.target.value, classes.find(item => item.id === e.target.value)?.exams[0]?.id ?? '')} className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-3 text-sm font-bold">
            {classes.map(item => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}
          </select>

          <label className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Exam</label>
          <select value={selectedExam?.id ?? ''} onChange={(e) => selectedClass && onSelectContext(selectedClass.id, e.target.value)} className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-3 text-sm font-bold">
            {selectedClass?.exams.map(exam => <option key={exam.id} value={exam.id}>{exam.title}</option>)}
          </select>

          <div className="bg-white/5 border border-white/10 rounded-xl p-3">
            <div className="text-[10px] uppercase tracking-widest text-gray-500 font-bold mb-2">Exam codes</div>
            <div className="flex flex-wrap gap-2">
              {selectedExam?.codes.map(code => <span key={code.id} className="px-2 py-1 rounded-lg bg-blue-500/20 text-blue-200 text-xs font-bold">{code.code}</span>)}
            </div>
          </div>
        </div>

        <div className="mt-auto space-y-4">
          <div className="bg-white/5 p-4 rounded-2xl border border-white/5">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs text-gray-400">Backend</span>
              <span className="text-xs font-bold text-green-500">{API_BASE_URL}</span>
            </div>
            <div className="w-full bg-white/10 h-1.5 rounded-full overflow-hidden"><div className="bg-green-500 w-full h-full" /></div>
          </div>

          <button onClick={scan} disabled={status === 'processing'} className={`w-full py-5 rounded-2xl flex flex-col items-center gap-1 shadow-2xl transition-all ${status === 'processing' ? 'bg-gray-600 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500 shadow-blue-900/20 active:scale-95'}`}>
            <Camera size={32} />
            <span className="font-bold text-lg">Scan sheet</span>
          </button>

          <button onClick={() => fileInputRef.current?.click()} disabled={status === 'processing'} className={`w-full py-4 rounded-2xl flex items-center justify-center gap-3 border border-white/10 transition-all ${status === 'processing' ? 'bg-gray-700 text-gray-400 cursor-not-allowed' : 'bg-white/5 hover:bg-white/10 text-white active:scale-95'}`}>
            <Upload size={22} />
            <span className="font-bold">Upload image</span>
          </button>
          <input ref={fileInputRef} type="file" accept="image/*" onChange={uploadImage} className="hidden" />
        </div>
      </div>

      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
}
