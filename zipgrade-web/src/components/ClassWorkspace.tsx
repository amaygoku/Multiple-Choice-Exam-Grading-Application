import { useMemo, useState } from 'react';
import { Camera, ClipboardList, FileDown, Plus, Upload, Users } from 'lucide-react';
import { AnswerOption, ClassRoom, Exam, ExamCode, Student } from '../types';

const uid = () => Math.random().toString(36).slice(2, 10);
const options: AnswerOption[] = ['A', 'B', 'C', 'D', 'E'];

interface ClassWorkspaceProps {
  classes: ClassRoom[];
  selectedClassId: string | null;
  selectedExamId: string | null;
  onSelectClass: (id: string) => void;
  onSelectExam: (id: string) => void;
  onCreateClass: () => void;
  onUpdateClass: (updated: ClassRoom) => void;
  onStartScanner: (classId: string, examId: string) => void;
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
    <div className="grid grid-cols-1 xl:grid-cols-[300px_1fr] gap-8">
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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Field label="Class Code" value={selectedClass.code} onChange={(value) => updateSelectedClass({ code: value })} />
            <Field label="Class Name" value={selectedClass.name} onChange={(value) => updateSelectedClass({ name: value })} />
            <Field label="Semester" value={selectedClass.semester} onChange={(value) => updateSelectedClass({ semester: value })} />
          </div>
        </div>

        <RosterPanel classRoom={selectedClass} onUpdateClass={onUpdateClass} />

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
                <button
                  key={exam.id}
                  onClick={() => onSelectExam(exam.id)}
                  className={`w-full p-3 rounded-xl border text-left transition-all ${selectedExam?.id === exam.id ? 'border-primary bg-blue-50' : 'border-border-light hover:bg-slate-50'}`}
                >
                  <div className="font-bold text-slate-800">{exam.title}</div>
                  <div className="text-xs text-slate-400 mt-1">{exam.questionCount} questions · {exam.codes.length} codes</div>
                </button>
              ))}
            </div>
          </div>

          {selectedExam ? (
            <ExamPanel
              exam={selectedExam}
              onUpdateExam={updateExam}
              onStartScanner={() => onStartScanner(selectedClass.id, selectedExam.id)}
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

function RosterPanel({ classRoom, onUpdateClass }: { classRoom: ClassRoom; onUpdateClass: (updated: ClassRoom) => void }) {
  const [rawImport, setRawImport] = useState('');

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
    const imported = rawImport
      .split('\n')
      .map(line => line.trim())
      .filter(Boolean)
      .map(line => {
        const [mssv, ...nameParts] = line.split(/[,\t]/).map(part => part.trim());
        return { id: uid(), classId: classRoom.id, mssv, fullName: nameParts.join(' ') || 'Unknown student' };
      })
      .filter(student => student.mssv);
    onUpdateClass({ ...classRoom, students: [...classRoom.students, ...imported] });
    setRawImport('');
  };

  return (
    <div className="card p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-black text-slate-900">Student roster</h3>
          <p className="text-sm text-slate-500 mt-1">MSSV is used to match backend OMR output to the official student list.</p>
        </div>
        <button onClick={addStudent} className="btn-outline text-sm flex items-center gap-2">
          <Plus size={16} />
          Add Student
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
        <div className="border border-border-light rounded-xl overflow-hidden">
          <div className="grid grid-cols-[160px_1fr] bg-slate-50 px-4 py-2 text-[10px] font-black uppercase tracking-widest text-slate-400">
            <div>MSSV</div>
            <div>Full name</div>
          </div>
          <div className="max-h-64 overflow-auto divide-y divide-slate-100">
            {classRoom.students.map(student => (
              <div key={student.id} className="grid grid-cols-[160px_1fr] gap-3 p-3">
                <input value={student.mssv} onChange={(e) => updateStudent(student.id, { mssv: e.target.value })} className="bg-white border border-border-light rounded-lg px-3 py-2 font-mono text-sm" />
                <input value={student.fullName} onChange={(e) => updateStudent(student.id, { fullName: e.target.value })} className="bg-white border border-border-light rounded-lg px-3 py-2 text-sm" />
              </div>
            ))}
            {classRoom.students.length === 0 && <div className="p-8 text-center text-sm text-slate-400">No students yet.</div>}
          </div>
        </div>

        <div className="bg-slate-50 border border-border-light rounded-xl p-4">
          <div className="flex items-center gap-2 text-sm font-black text-slate-700 mb-3">
            <Upload size={16} />
            Paste CSV
          </div>
          <textarea
            value={rawImport}
            onChange={(e) => setRawImport(e.target.value)}
            placeholder="21520001,Nguyen Van An&#10;21520002,Tran Thi Binh"
            className="w-full h-28 bg-white border border-border-light rounded-xl p-3 text-sm font-mono resize-none"
          />
          <button onClick={importStudents} className="btn-primary w-full mt-3 text-sm">Import Students</button>
        </div>
      </div>
    </div>
  );
}

function ExamPanel({ exam, onUpdateExam, onStartScanner }: { exam: Exam; onUpdateExam: (updated: Exam) => void; onStartScanner: () => void }) {
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
      answerKey: Array.from({ length: count }, (_, index) => code.answerKey[index] ?? 'A'),
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
        <AnswerKeyEditor examCode={selectedCode} onUpdate={updateCode} />
      )}
    </div>
  );
}

function AnswerKeyEditor({ examCode, onUpdate }: { examCode: ExamCode; onUpdate: (updated: ExamCode) => void }) {
  const setAnswer = (index: number, answer: AnswerOption) => {
    const next = [...examCode.answerKey];
    next[index] = answer;
    onUpdate({ ...examCode, answerKey: next });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <Field label="Exam Code" value={examCode.code} onChange={(value) => onUpdate({ ...examCode, code: value })} />
        <button className="btn-outline text-sm flex items-center gap-2 self-end">
          <FileDown size={16} />
          Export Key
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 max-h-[520px] overflow-auto pr-2">
        {examCode.answerKey.map((answer, index) => (
          <div key={index} className="bg-white border border-border-light p-3 rounded-xl flex items-center justify-between">
            <span className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-[11px] font-black text-slate-500">
              {(index + 1).toString().padStart(2, '0')}
            </span>
            <div className="flex gap-1">
              {options.map(option => (
                <button
                  key={option}
                  onClick={() => setAnswer(index, option)}
                  className={`w-7 h-7 rounded-lg text-[10px] font-black transition-all ${answer === option ? 'bg-primary text-white shadow-lg shadow-blue-900/20' : 'bg-slate-50 text-slate-400 hover:bg-slate-100 border border-transparent hover:border-slate-200'}`}
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
