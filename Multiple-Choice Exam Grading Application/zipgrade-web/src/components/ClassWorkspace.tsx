import { useMemo, useRef, useState } from 'react';
import { Camera, ClipboardList, FileDown, Plus, Trash2, Upload, Users } from 'lucide-react';
import { AnswerOption, ClassRoom, Exam, ExamCode, Student } from '../types';
import { ANSWER_OPTIONS, normalizeAnswerKeyList, normalizeAnswerKeyValue, toggleAnswerKeyValue } from '../utils/answerKey';
import * as XLSX from 'xlsx';

const uid = () => Math.random().toString(36).slice(2, 10);
const options: AnswerOption[] = ANSWER_OPTIONS;

interface ClassWorkspaceProps {
  classes: ClassRoom[];
  selectedClassId: string | null;
  selectedExamId: string | null;
  onSelectClass: (id: string) => void;
  onSelectExam: (id: string) => void;
  onCreateClass: () => void;
  onUpdateClass: (updated: ClassRoom) => void;
  onStartScanner: (classId: string, examId: string) => void;
  onDeleteClass: (classId: string) => void;
  onDeleteStudent: (classId: string, studentId: string) => void;
  onDeleteExam: (classId: string, examId: string) => void;
  onDeleteExamCode: (classId: string, examId: string, examCodeId: string) => void;
}

export default function ClassWorkspace({
  classes,
  selectedClassId,
  selectedExamId,
  onSelectClass,
  onSelectExam,
  onCreateClass,
  onUpdateClass,
  onStartScanner,
  onDeleteClass,
  onDeleteStudent,
  onDeleteExam,
  onDeleteExamCode,
}: ClassWorkspaceProps) {
  const selectedClass = classes.find(item => item.id === selectedClassId) ?? classes[0] ?? null;
  const selectedExam = selectedClass?.exams.find(exam => exam.id === selectedExamId) ?? selectedClass?.exams[0] ?? null;

  if (!selectedClass) {
    return (
      <div className="card p-20 text-center">
        <Users size={52} className="mx-auto text-slate-300 mb-4" />
        <h2 className="text-2xl font-black text-slate-800">No classes yet</h2>
        <p className="text-slate-500 mt-2">Create a class, import students, then add exams and exam codes.</p>
        <button onClick={onCreateClass} className="btn-primary mt-8">Create Class</button>
      </div>
    );
  }

  const updateSelectedClass = (patch: Partial<ClassRoom>) => {
    onUpdateClass({ ...selectedClass, ...patch });
  };

  const createExam = () => {
    const examId = uid();
    const exam: Exam = {
      id: examId,
      classId: selectedClass.id,
      title: `Exam ${selectedClass.exams.length + 1}`,
      questionCount: 45,
      createdAt: Date.now(),
      codes: [
        {
          id: uid(),
          examId,
          code: '101',
          answerKey: Array.from({ length: 45 }, () => 'A' as AnswerOption),
        },
      ],
    };
    onUpdateClass({ ...selectedClass, exams: [exam, ...selectedClass.exams] });
    onSelectExam(examId);
  };

  const updateExam = (updatedExam: Exam) => {
    onUpdateClass({
      ...selectedClass,
      exams: selectedClass.exams.map(exam => (exam.id === updatedExam.id ? updatedExam : exam)),
    });
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[300px_1fr] gap-6 lg:gap-8">
      <aside className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-black text-slate-400 uppercase tracking-widest">Classes</h2>
          <button onClick={onCreateClass} className="p-2 bg-white border border-border-light rounded-lg hover:bg-slate-50">
            <Plus size={16} />
          </button>
        </div>
        <div className="space-y-3">
          {classes.map(item => (
            <button
              key={item.id}
              onClick={() => onSelectClass(item.id)}
              className={`w-full text-left card p-4 transition-all ${item.id === selectedClass.id ? 'border-primary ring-2 ring-primary/10' : 'hover:border-slate-300'}`}
            >
              <div className="font-black text-slate-800">{item.code}</div>
              <div className="text-sm text-slate-500 mt-1">{item.name}</div>
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-3">
                {item.students.length} students · {item.exams.length} exams
              </div>
            </button>
          ))}
        </div>
      </aside>

      <section className="space-y-8">
        <div className="card p-6">
          <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 flex-1">
              <Field label="Class Code" value={selectedClass.code} onChange={(value) => updateSelectedClass({ code: value })} />
              <Field label="Class Name" value={selectedClass.name} onChange={(value) => updateSelectedClass({ name: value })} />
              <Field label="Semester" value={selectedClass.semester} onChange={(value) => updateSelectedClass({ semester: value })} />
            </div>
            <button
              onClick={() => onDeleteClass(selectedClass.id)}
              className="btn-outline border-red-200 text-red-600 hover:bg-red-50 flex items-center gap-2 self-start lg:self-end"
            >
              <Trash2 size={16} />
              Delete Class
            </button>
          </div>
        </div>

        <RosterPanel classRoom={selectedClass} onUpdateClass={onUpdateClass} onDeleteStudent={onDeleteStudent} />

        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
          <div className="card p-5">
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-black text-slate-900">Exams</h3>
              <button onClick={createExam} className="btn-primary text-xs flex items-center gap-1">
                <Plus size={14} />
                Add
              </button>
            </div>
            <div className="space-y-2">
              {selectedClass.exams.map(exam => (
                <div
                  key={exam.id}
                  className={`w-full p-3 rounded-xl border text-left transition-all ${selectedExam?.id === exam.id ? 'border-primary bg-blue-50' : 'border-border-light hover:bg-slate-50'}`}
                >
                  <button onClick={() => onSelectExam(exam.id)} className="w-full text-left">
                    <div className="font-bold text-slate-800">{exam.title}</div>
                    <div className="text-xs text-slate-400 mt-1">{exam.questionCount} questions · {exam.codes.length} codes</div>
                  </button>
                  <div className="mt-3 flex justify-end">
                    <button
                      onClick={() => onDeleteExam(selectedClass.id, exam.id)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-black text-red-600 hover:bg-red-50"
                    >
                      <Trash2 size={12} />
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {selectedExam ? (
            <ExamPanel
              classId={selectedClass.id}
              exam={selectedExam}
              onUpdateExam={updateExam}
              onStartScanner={() => onStartScanner(selectedClass.id, selectedExam.id)}
              onDeleteExamCode={onDeleteExamCode}
            />
          ) : (
            <div className="card p-14 text-center">
              <ClipboardList size={42} className="mx-auto text-slate-300 mb-4" />
              <h3 className="text-xl font-black text-slate-800">No exam in this class</h3>
              <button onClick={createExam} className="btn-primary mt-6">Create Exam</button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full bg-slate-50 border border-border-light rounded-xl px-4 py-3 font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary/20"
      />
    </label>
  );
}

function RosterPanel({
  classRoom,
  onUpdateClass,
  onDeleteStudent,
}: {
  classRoom: ClassRoom;
  onUpdateClass: (updated: ClassRoom) => void;
  onDeleteStudent: (classId: string, studentId: string) => void;
}) {
  const [rawImport, setRawImport] = useState('');
  const [importFeedback, setImportFeedback] = useState<{ tone: 'success' | 'warning'; message: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const normalizeStudentId = (value: string) => value.trim();

  const isStudentHeader = (value: unknown) => {
    const normalized = String(value ?? '')
      .trim()
      .toLowerCase()
      .replace(/[\s_-]+/g, '');
    return ['mssv', 'studentid', 'studentcode', 'id', 'masv'].includes(normalized);
  };

  const buildImportedStudents = (rows: Array<{ mssv: string; fullName: string }>) => {
    const existingIds = new Set(classRoom.students.map(student => normalizeStudentId(student.mssv)).filter(Boolean));
    const seenInBatch = new Set<string>();
    const imported: Student[] = [];
    let duplicateCount = 0;

    rows.forEach((row) => {
      const mssv = normalizeStudentId(row.mssv);
      const fullName = row.fullName.trim() || 'Unknown student';
      if (!mssv) return;
      if (existingIds.has(mssv) || seenInBatch.has(mssv)) {
        duplicateCount += 1;
        return;
      }

      seenInBatch.add(mssv);
      imported.push({
        id: uid(),
        classId: classRoom.id,
        mssv,
        fullName,
      });
    });

    if (imported.length > 0) {
      onUpdateClass({ ...classRoom, students: [...classRoom.students, ...imported] });
    }

    if (imported.length === 0 && duplicateCount > 0) {
      setImportFeedback({
        tone: 'warning',
        message: `No new students were imported. ${duplicateCount} duplicate student ID(s) already exist in this class.`,
      });
      return;
    }

    if (imported.length === 0) {
      setImportFeedback({
        tone: 'warning',
        message: 'No valid student rows were found in the imported data.',
      });
      return;
    }

    setImportFeedback({
      tone: duplicateCount > 0 ? 'warning' : 'success',
      message:
        duplicateCount > 0
          ? `Imported ${imported.length} student(s). Skipped ${duplicateCount} duplicate student ID(s) in this class.`
          : `Imported ${imported.length} student(s) successfully.`,
    });
  };

  const addStudent = () => {
    const student: Student = {
      id: uid(),
      classId: classRoom.id,
      mssv: '',
      fullName: '',
    };
    onUpdateClass({ ...classRoom, students: [...classRoom.students, student] });
  };

  const updateStudent = (id: string, patch: Partial<Student>) => {
    onUpdateClass({
      ...classRoom,
      students: classRoom.students.map(student => (student.id === id ? { ...student, ...patch } : student)),
    });
  };

  const importStudents = () => {
    const importedRows = rawImport
      .split('\n')
      .map(line => line.trim())
      .filter(Boolean)
      .map(line => {
        const [mssv, ...nameParts] = line.split(/[,\t;]/).map(part => part.trim());
        return { mssv, fullName: nameParts.join(' ') || 'Unknown student' };
      })
      .filter(student => student.mssv)
      .filter((student, index) => !(index === 0 && isStudentHeader(student.mssv)));

    buildImportedStudents(importedRows);
    setRawImport('');
  };

  const downloadStudentTemplate = () => {
    const csvRows = [
      'student_id,full_name',
      '21520001,Nguyen Van An',
      '21520002,Tran Thi Binh',
      '21520003,Le Minh Chau',
    ];
    const csvContent = `data:text/csv;charset=utf-8,${csvRows.join('\n')}`;
    const link = document.createElement('a');
    link.setAttribute('href', encodeURI(csvContent));
    link.setAttribute('download', `student_roster_template_${classRoom.code || 'class'}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleImportFile = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();

    if (ext === 'xlsx' || ext === 'xls') {
      const buffer = await file.arrayBuffer();
      const workbook = XLSX.read(buffer, { type: 'array' });
      const sheetName = workbook.SheetNames[0];
      if (!sheetName) {
        setImportFeedback({ tone: 'warning', message: 'The selected spreadsheet does not contain any sheet.' });
        return;
      }

      const sheet = workbook.Sheets[sheetName];
      const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, { defval: '' });
      const normalizedRows = rows
        .map((row) => ({
          mssv: String(
            row.student_id ??
            row.StudentID ??
            row.studentId ??
            row.mssv ??
            row.MSSV ??
            row.id ??
            ''
          ).trim(),
          fullName: String(
            row.full_name ??
            row.FullName ??
            row.fullName ??
            row.name ??
            row.Name ??
            row.ho_ten ??
            ''
          ).trim(),
        }))
        .filter((row) => row.mssv);
      buildImportedStudents(normalizedRows);
      return;
    }

    const text = await file.text();
    const rows = text
      .split(/\r?\n/)
      .map(line => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [mssv, ...nameParts] = line.split(/[,;\t]/).map(part => part.trim());
        return { mssv, fullName: nameParts.join(' ') };
      })
      .filter((row) => row.mssv)
      .filter((row, index) => !(index === 0 && isStudentHeader(row.mssv)));

    buildImportedStudents(rows);
  };

  return (
    <div className="card p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-black text-slate-900">Student roster</h3>
          <p className="text-sm text-slate-500 mt-1">Student ID is used to match backend OMR output to the official student list.</p>
        </div>
        <button onClick={addStudent} className="btn-outline text-sm flex items-center gap-2">
          <Plus size={16} />
          Add Student
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
        <div className="border border-border-light rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <div className="min-w-[320px]">
              <div className="grid grid-cols-[120px_1fr] sm:grid-cols-[160px_1fr] bg-slate-50 px-4 py-2 text-[10px] font-black uppercase tracking-widest text-slate-400">
                <div>Student ID</div>
                <div>Full name</div>
              </div>
              <div className="max-h-[calc(100dvh-360px)] sm:max-h-64 overflow-y-auto overscroll-contain divide-y divide-slate-100">
                {classRoom.students.map(student => (
                  <div key={student.id} className="grid grid-cols-[120px_1fr_auto] sm:grid-cols-[160px_1fr_auto] gap-3 p-3 items-center">
                    <input value={student.mssv} onChange={(e) => updateStudent(student.id, { mssv: e.target.value })} className="bg-white border border-border-light rounded-lg px-3 py-2 font-mono text-sm min-w-0" />
                    <input value={student.fullName} onChange={(e) => updateStudent(student.id, { fullName: e.target.value })} className="bg-white border border-border-light rounded-lg px-3 py-2 text-sm min-w-0" />
                    <button
                      onClick={() => onDeleteStudent(classRoom.id, student.id)}
                      className="p-2 rounded-lg text-red-600 hover:bg-red-50"
                      title="Delete student"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
                {classRoom.students.length === 0 && <div className="p-8 text-center text-sm text-slate-400">No students yet.</div>}
              </div>
            </div>
          </div>
        </div>

        <div className="bg-slate-50 border border-border-light rounded-xl p-4">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div className="flex items-center gap-2 text-sm font-black text-slate-700">
              <Upload size={16} />
              Import roster
            </div>
            <button onClick={downloadStudentTemplate} className="btn-outline text-xs flex items-center gap-2">
              <FileDown size={14} />
              CSV Template
            </button>
          </div>
          <textarea
            value={rawImport}
            onChange={(e) => {
              setRawImport(e.target.value);
              if (importFeedback) setImportFeedback(null);
            }}
            placeholder="student_id,full_name&#10;21520001,Nguyen Van An&#10;21520002,Tran Thi Binh"
            className="w-full h-28 bg-white border border-border-light rounded-xl p-3 text-sm font-mono resize-none"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-3">
            <button onClick={importStudents} className="btn-primary text-sm">Import from Text</button>
            <button onClick={() => fileInputRef.current?.click()} className="btn-outline text-sm flex items-center justify-center gap-2">
              <Upload size={14} />
              Upload CSV/XLSX
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) {
                await handleImportFile(file);
              }
              e.target.value = '';
            }}
          />
          {importFeedback && (
            <div
              className={`mt-3 rounded-xl px-3 py-2 text-sm font-semibold ${
                importFeedback.tone === 'success'
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'bg-amber-50 text-amber-700 border border-amber-200'
              }`}
            >
              {importFeedback.message}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ExamPanel({
  classId,
  exam,
  onUpdateExam,
  onStartScanner,
  onDeleteExamCode,
}: {
  classId: string;
  exam: Exam;
  onUpdateExam: (updated: Exam) => void;
  onStartScanner: () => void;
  onDeleteExamCode: (classId: string, examId: string, examCodeId: string) => void;
}) {
  const [selectedCodeId, setSelectedCodeId] = useState(exam.codes[0]?.id ?? '');
  const selectedCode = useMemo(
    () => exam.codes.find(code => code.id === selectedCodeId) ?? exam.codes[0] ?? null,
    [exam.codes, selectedCodeId]
  );

  const updateCode = (updatedCode: ExamCode) => {
    onUpdateExam({ ...exam, codes: exam.codes.map(code => (code.id === updatedCode.id ? updatedCode : code)) });
  };

  const addCode = () => {
    const code: ExamCode = {
      id: uid(),
      examId: exam.id,
      code: `${101 + exam.codes.length}`,
      answerKey: Array.from({ length: exam.questionCount }, () => 'A' as AnswerOption),
    };
    onUpdateExam({ ...exam, codes: [...exam.codes, code] });
    setSelectedCodeId(code.id);
  };

  const updateQuestionCount = (count: number) => {
    const nextCodes = exam.codes.map(code => ({
      ...code,
      answerKey: normalizeAnswerKeyList(code.answerKey, count).map(value => value || 'A'),
    }));
    onUpdateExam({ ...exam, questionCount: count, codes: nextCodes });
  };

  return (
    <div className="card p-6 space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_170px] gap-3 flex-1">
          <Field label="Exam Title" value={exam.title} onChange={(value) => onUpdateExam({ ...exam, title: value })} />
          <label className="block">
            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Questions</span>
            <select value={exam.questionCount} onChange={(e) => updateQuestionCount(Number(e.target.value))} className="mt-2 w-full bg-slate-50 border border-border-light rounded-xl px-4 py-3 font-bold">
              <option value={45}>45 questions</option>
              <option value={20}>20 questions</option>
              <option value={50}>50 questions</option>
              <option value={100}>100 questions</option>
            </select>
          </label>
        </div>
        <button onClick={onStartScanner} className="btn-primary flex items-center justify-center gap-2">
          <Camera size={18} />
          Scan This Exam
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {exam.codes.map(code => (
          <button key={code.id} onClick={() => setSelectedCodeId(code.id)} className={`px-4 py-2 rounded-xl border text-sm font-black ${selectedCode?.id === code.id ? 'bg-primary text-white border-primary' : 'bg-white border-border-light text-slate-600'}`}>
            Code {code.code}
          </button>
        ))}
        <button onClick={addCode} className="px-4 py-2 rounded-xl border border-dashed border-slate-300 text-sm font-black text-slate-400 hover:text-primary">
          + Add Code
        </button>
      </div>

      {selectedCode && (
        <AnswerKeyEditor
          examCode={selectedCode}
          onUpdate={updateCode}
          onDelete={() => onDeleteExamCode(classId, exam.id, selectedCode.id)}
        />
      )}
    </div>
  );
}

function AnswerKeyEditor({
  examCode,
  onUpdate,
  onDelete,
}: {
  examCode: ExamCode;
  onUpdate: (updated: ExamCode) => void;
  onDelete: () => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const toggleAnswer = (index: number, option: AnswerOption) => {
    const next = [...examCode.answerKey];
    next[index] = toggleAnswerKeyValue(next[index] ?? '', option);
    onUpdate({ ...examCode, answerKey: next });
  };

  const downloadTemplate = () => {
    const csvRows = ['question,answer', ...examCode.answerKey.map((answer, index) => `${index + 1},${answer}`)];
    const csvContent = `data:text/csv;charset=utf-8,${csvRows.map(row => row.replace(/"/g, '""')).join('\n')}`;
    const link = document.createElement('a');
    link.setAttribute('href', encodeURI(csvContent));
    link.setAttribute('download', `answer_key_${examCode.code || 'template'}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const applyImportedRows = (rows: Array<Record<string, unknown>>) => {
    const next = [...examCode.answerKey];
    rows.forEach((row) => {
      const questionValue =
        row.question ??
        row.Question ??
        row.q ??
        row.Q ??
        row.id ??
        row.ID ??
        row.stt ??
        row.STT ??
        row['Câu'] ??
        row['Cau'];

      const answerValue =
        row.answer ??
        row.Answer ??
        row.correctAnswer ??
        row.correct_answer ??
        row.correct ??
        row['Đáp án'] ??
        row['Dap an'] ??
        row['dap_an'];

      const questionNumber = Number.parseInt(String(questionValue ?? '').trim(), 10);
      if (!Number.isFinite(questionNumber) || questionNumber < 1 || questionNumber > next.length) return;

      next[questionNumber - 1] = normalizeAnswerKeyValue(String(answerValue ?? ''));
    });

    onUpdate({ ...examCode, answerKey: next });
  };

  const handleImportFile = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext === 'xlsx' || ext === 'xls') {
      const buffer = await file.arrayBuffer();
      const workbook = XLSX.read(buffer, { type: 'array' });
      const sheetName = workbook.SheetNames[0];
      if (!sheetName) return;
      const sheet = workbook.Sheets[sheetName];
      const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, { defval: '' });
      applyImportedRows(rows);
      return;
    }

    const text = await file.text();
    const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
    const rows = lines.map(line => {
      const parts = line.split(/[,;\t]/).map(cell => cell.trim());
      return {
        question: parts[0],
        answer: parts[1] ?? '',
      };
    });

    const hasHeader = rows[0] && normalizeAnswerKeyValue(String(rows[0].question ?? '').toLowerCase()) === '';
    applyImportedRows(hasHeader ? rows.slice(1) : rows);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <Field label="Exam Code" value={examCode.code} onChange={(value) => onUpdate({ ...examCode, code: value })} />
        <div className="flex items-end gap-2">
          <button onClick={onDelete} className="btn-outline text-sm flex items-center gap-2 self-end border-red-200 text-red-600 hover:bg-red-50">
            <Trash2 size={16} />
            Delete Code
          </button>
          <button onClick={downloadTemplate} className="btn-outline text-sm flex items-center gap-2 self-end">
            <FileDown size={16} />
            Export CSV
          </button>
          <button onClick={() => fileInputRef.current?.click()} className="btn-outline text-sm flex items-center gap-2 self-end">
            <Upload size={16} />
            Import CSV/XLSX
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) {
                await handleImportFile(file);
              }
              e.target.value = '';
            }}
          />
        </div>
      </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 max-h-[calc(100dvh-360px)] sm:max-h-[520px] overflow-y-auto overscroll-contain pr-2">
        {examCode.answerKey.map((answer, index) => (
          <div key={index} className="bg-white border border-border-light p-3 rounded-xl flex items-center justify-between gap-3">
            <span className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-[11px] font-black text-slate-500">
              {(index + 1).toString().padStart(2, '0')}
            </span>
            <div className="flex gap-1">
              {options.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => toggleAnswer(index, option)}
                  className={`w-7 h-7 rounded-lg text-[10px] font-black transition-all ${answer.includes(option) ? 'bg-primary text-white shadow-lg shadow-blue-900/20' : 'bg-slate-50 text-slate-400 hover:bg-slate-100 border border-transparent hover:border-slate-200'}`}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
