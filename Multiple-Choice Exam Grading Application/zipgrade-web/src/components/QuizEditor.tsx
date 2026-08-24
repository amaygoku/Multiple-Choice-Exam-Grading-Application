import React, { useState, useRef } from 'react';
import { Quiz, AnswerOption } from '../types';
import { Check, Trash2, Edit3, Save, Upload, FileDown, AlertCircle } from 'lucide-react';
import { ANSWER_OPTIONS, normalizeAnswerKeyValue, toggleAnswerKeyValue } from '../utils/answerKey';
import * as XLSX from 'xlsx';

interface QuizEditorProps {
  quiz: Quiz;
  onUpdate: (updated: Quiz) => void;
}

export default function QuizEditor({ quiz, onUpdate }: QuizEditorProps) {
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState(quiz.name);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const options: AnswerOption[] = ANSWER_OPTIONS;

  const updateAnswer = (questionId: number, option: AnswerOption) => {
    const updatedQuestions = quiz.questions.map(q => 
      q.id === questionId
        ? { ...q, correctAnswer: toggleAnswerKeyValue(q.correctAnswer, option) }
        : q
    );
    onUpdate({ ...quiz, questions: updatedQuestions });
  };

  const updateName = () => {
    onUpdate({ ...quiz, name: name });
    setEditingName(false);
  };

  const updateCount = (newCount: number) => {
    let newQuestions = [...quiz.questions];
    if (newCount > quiz.questions.length) {
      const additional = Array.from({ length: newCount - quiz.questions.length }, (_, i) => ({
        id: quiz.questions.length + i + 1,
        correctAnswer: 'A',
        weight: 1
      }));
      newQuestions = [...newQuestions, ...additional];
    } else {
      newQuestions = newQuestions.slice(0, newCount);
    }
    onUpdate({ ...quiz, count: newCount, questions: newQuestions });
  };

  const handleCsvImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      const lines = text.split('\n');
      const newQuestions = [...quiz.questions];

      lines.forEach(line => {
        const parts = line.split(/[,;\t]/);
        if (parts.length >= 2) {
          const qId = parseInt(parts[0].trim());
          const ans = normalizeAnswerKeyValue(parts[1].trim());

          if (!isNaN(qId)) {
            const index = newQuestions.findIndex(q => q.id === qId);
            if (index !== -1) {
              newQuestions[index] = { ...newQuestions[index], correctAnswer: ans };
            }
          }
        }
      });

      onUpdate({ ...quiz, questions: newQuestions });
      if (fileInputRef.current) fileInputRef.current.value = '';
    };
    reader.readAsText(file);
  };

  const handleFileImport = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext === 'xlsx' || ext === 'xls') {
      const buffer = await file.arrayBuffer();
      const workbook = XLSX.read(buffer, { type: 'array' });
      const sheetName = workbook.SheetNames[0];
      if (!sheetName) return;
      const sheet = workbook.Sheets[sheetName];
      const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, { defval: '' });
      const nextQuestions = [...quiz.questions];

      rows.forEach((row) => {
        const qId = Number.parseInt(String(row.question ?? row.Question ?? row.id ?? row.ID ?? '').trim(), 10);
        const ans = normalizeAnswerKeyValue(String(row.answer ?? row.Answer ?? row.correctAnswer ?? row.correct_answer ?? '').trim());
        if (!Number.isFinite(qId) || qId < 1) return;
        const index = nextQuestions.findIndex(q => q.id === qId);
        if (index !== -1) {
          nextQuestions[index] = { ...nextQuestions[index], correctAnswer: ans };
        }
      });

      onUpdate({ ...quiz, questions: nextQuestions });
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    await new Promise<void>((resolve) => {
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target?.result as string;
        const lines = text.split('\n').map(line => line.trim()).filter(Boolean);
        const nextQuestions = [...quiz.questions];

        lines.forEach((line) => {
          const parts = line.split(/[,;\t]/).map(cell => cell.trim());
          if (parts.length < 2) return;
          const qId = Number.parseInt(parts[0], 10);
          const ans = normalizeAnswerKeyValue(parts[1]);
          if (!Number.isFinite(qId) || qId < 1) return;
          const index = nextQuestions.findIndex(q => q.id === qId);
          if (index !== -1) {
            nextQuestions[index] = { ...nextQuestions[index], correctAnswer: ans };
          }
        });

        onUpdate({ ...quiz, questions: nextQuestions });
        if (fileInputRef.current) fileInputRef.current.value = '';
        resolve();
      };
      reader.readAsText(file);
    });
  };

  const downloadTemplate = () => {
    const csvContent = "data:text/csv;charset=utf-8," + 
      quiz.questions.map(q => `${q.id},${q.correctAnswer}`).join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `template_${quiz.name}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-8 lg:space-y-10">
      {/* Header Info */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-slate-50 border border-border-light p-5 sm:p-6 lg:p-8 rounded-2xl">
        <div className="flex-1">
          <label className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em] mb-2 block">Exam Subject</label>
          {editingName ? (
            <div className="flex gap-2">
              <input 
                value={name} 
                onChange={(e) => setName(e.target.value)}
                className="text-2xl font-bold bg-white border border-primary/20 rounded-xl px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 flex-1 shadow-sm"
                autoFocus
              />
              <button onClick={updateName} className="p-3 bg-primary text-white rounded-xl shadow-md hover:scale-105 transition-transform active:scale-95"><Save size={20} /></button>
            </div>
          ) : (
            <div className="flex items-center gap-3 group">
              <h2 className="text-2xl font-black text-slate-800 tracking-tight">{quiz.name}</h2>
              <button onClick={() => setEditingName(true)} className="opacity-0 group-hover:opacity-100 p-2 text-primary hover:bg-white rounded-lg shadow-sm transition-all"><Edit3 size={18} /></button>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-2 w-full md:min-w-[180px] md:w-auto">
          <label className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em]">Sheet Template</label>
          <select 
            value={quiz.count}
            onChange={(e) => updateCount(parseInt(e.target.value))}
            className="bg-white border border-border-light rounded-xl px-4 py-3 font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary/20 shadow-sm appearance-none cursor-pointer"
          >
            <option value={45}>Standard 45 Questions</option>
            <option value={20}>Short 20 Questions</option>
            <option value={50}>Detailed 50 Questions</option>
            <option value={100}>Extensive 100 Questions</option>
          </select>
        </div>
      </div>

      {/* Answer Key Grid */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between px-1 gap-3">
          <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest">Answer Key Assignment</h3>
          <div className="flex flex-wrap gap-2">
            <button 
              onClick={downloadTemplate}
              className="flex items-center gap-2 text-[10px] font-bold text-slate-400 hover:text-primary transition-colors py-1 px-2"
            >
              <FileDown size={14} />
              <span>Download CSV Template</span>
            </button>
            <button 
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 text-[10px] font-bold bg-primary/10 text-primary hover:bg-primary hover:text-white transition-all py-1 px-3 rounded-lg border border-primary/20"
            >
              <Upload size={14} />
              <span>Import CSV/XLSX</span>
            </button>
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (file) await handleFileImport(file);
                e.target.value = '';
              }} 
              accept=".csv,.xlsx,.xls" 
              className="hidden" 
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 sm:gap-4 max-h-[calc(100dvh-340px)] sm:max-h-[520px] overflow-y-auto overscroll-contain pr-2">
        {quiz.questions.map((q) => (
          <div key={q.id} className="bg-white border border-border-light p-4 rounded-xl shadow-sm hover:border-primary/20 transition-all flex items-center justify-between gap-3">
            <span className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-[11px] font-black text-slate-500">
              {q.id.toString().padStart(2, '0')}
            </span>
            <div className="flex gap-1">
              {options.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => updateAnswer(q.id, opt)}
                  className={`w-7 h-7 rounded-lg text-[10px] font-black transition-all ${q.correctAnswer.includes(opt) ? 'bg-primary text-white shadow-lg shadow-blue-900/20' : 'bg-slate-50 text-slate-400 hover:bg-slate-100 border border-transparent hover:border-slate-200'}`}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        ))}
        </div>
      </section>

      {/* Printable Placeholder (Footer) */}
      <div className="bg-slate-900 text-white p-6 sm:p-10 rounded-[2rem] flex flex-col items-center text-center shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/10 rounded-full blur-3xl -mr-32 -mt-32" />
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl -ml-32 -mb-32" />
        
        <h3 className="text-2xl font-black mb-3">Download Grading Forms</h3>
        <p className="text-slate-400 mb-8 max-w-lg leading-relaxed">Ensure scanning precision by using our standardized OMR bubbling sheets. Optimized for detection accuracy with current {quiz.count}-question configuration.</p>
        <button className="bg-white text-slate-900 px-10 py-4 rounded-xl font-black text-sm uppercase tracking-widest hover:scale-105 transition-all active:scale-95 shadow-xl">
          Generate PDF Forms
        </button>
      </div>
    </div>
  );
}
