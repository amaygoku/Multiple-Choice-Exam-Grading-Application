import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { BookOpen, Camera, GraduationCap, LayoutDashboard, Plus, Settings, Users } from 'lucide-react';
import { AnswerOption, ClassRoom, Exam, ScannedResult } from './types';
import Dashboard from './components/Dashboard';
import ClassWorkspace from './components/ClassWorkspace';
import Scanner from './components/Scanner';

type AppTab = 'dashboard' | 'classes' | 'scanner' | 'settings';

const uid = () => Math.random().toString(36).slice(2, 10);

const createDemoClass = (): ClassRoom => {
  const classId = uid();
  const examId = uid();
  return {
    id: classId,
    code: 'D21CQCN01-N',
    name: 'Lap trinh ung dung',
    semester: 'HK2 2025-2026',
    createdAt: Date.now(),
    students: [
      { id: uid(), classId, mssv: '21520001', fullName: 'Nguyen Van An' },
      { id: uid(), classId, mssv: '21520002', fullName: 'Tran Thi Binh' },
      { id: uid(), classId, mssv: '21520003', fullName: 'Le Minh Chau' },
    ],
    exams: [
      {
        id: examId,
        classId,
        title: 'Kiem tra giua ky',
        questionCount: 45,
        createdAt: Date.now(),
        codes: ['101', '102'].map(code => ({
          id: uid(),
          examId,
          code,
          answerKey: Array.from({ length: 45 }, (_, index) => ['A', 'B', 'C', 'D'][index % 4] as AnswerOption),
        })),
      },
    ],
  };
};

export default function App() {
  const [activeTab, setActiveTab] = useState<AppTab>('dashboard');
  const [classes, setClasses] = useState<ClassRoom[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [selectedExamId, setSelectedExamId] = useState<string | null>(null);
  const [results, setResults] = useState<ScannedResult[]>([]);

  useEffect(() => {
    const savedClasses = localStorage.getItem('zipgrade_classes');
    const savedResults = localStorage.getItem('zipgrade_results_v2');
    if (savedClasses) {
      const parsed = JSON.parse(savedClasses) as ClassRoom[];
      setClasses(parsed);
      setSelectedClassId(parsed[0]?.id ?? null);
      setSelectedExamId(parsed[0]?.exams[0]?.id ?? null);
    } else {
      const demo = createDemoClass();
      setClasses([demo]);
      setSelectedClassId(demo.id);
      setSelectedExamId(demo.exams[0]?.id ?? null);
    }
    if (savedResults) setResults(JSON.parse(savedResults));
  }, []);

  useEffect(() => {
    localStorage.setItem('zipgrade_classes', JSON.stringify(classes));
  }, [classes]);

  useEffect(() => {
    localStorage.setItem('zipgrade_results_v2', JSON.stringify(results));
  }, [results]);

  const selectedClass = useMemo(
    () => classes.find(item => item.id === selectedClassId) ?? classes[0] ?? null,
    [classes, selectedClassId]
  );
  const selectedExam = useMemo(
    () => selectedClass?.exams.find(exam => exam.id === selectedExamId) ?? selectedClass?.exams[0] ?? null,
    [selectedClass, selectedExamId]
  );

  const createClass = () => {
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

  const updateClass = (updated: ClassRoom) => {
    setClasses(classes.map(item => (item.id === updated.id ? updated : item)));
    setSelectedClassId(updated.id);
    if (!updated.exams.some(exam => exam.id === selectedExamId)) {
      setSelectedExamId(updated.exams[0]?.id ?? null);
    }
  };

  const startScanner = (classId?: string, examId?: string) => {
    if (classId) setSelectedClassId(classId);
    if (examId) setSelectedExamId(examId);
    setActiveTab('scanner');
  };

  return (
    <div className="flex flex-col md:grid md:grid-cols-[240px_1fr] min-h-screen bg-app-bg text-[#1e293b]">
      <nav className="hidden md:flex flex-col bg-sidebar text-[#f8fafc] p-6 border-r border-[#334155]">
        <div className="flex items-center gap-2 text-xl font-bold mb-10 text-[#38bdf8]">
          <GraduationCap size={24} />
          GradeHub
        </div>

        <div className="flex flex-col gap-1.5">
          <NavButton active={activeTab === 'dashboard'} icon={<LayoutDashboard size={18} />} label="Dashboard" onClick={() => setActiveTab('dashboard')} />
          <NavButton active={activeTab === 'classes'} icon={<BookOpen size={18} />} label="Classes" onClick={() => setActiveTab('classes')} />
          <NavButton active={activeTab === 'scanner'} icon={<Camera size={18} />} label="Scanner" onClick={() => setActiveTab('scanner')} />
          <NavButton active={activeTab === 'settings'} icon={<Settings size={18} />} label="Settings" onClick={() => setActiveTab('settings')} />
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

      <div className="flex flex-col h-full overflow-hidden">
        <header className="h-16 bg-white border-b border-border-light flex items-center justify-between px-8 shrink-0 shadow-sm z-10">
          <div>
            <h1 className="text-lg font-bold text-[#0f172a]">
              {activeTab === 'dashboard' ? 'Teaching Dashboard' : activeTab === 'classes' ? 'Classes, Students & Exams' : activeTab === 'scanner' ? 'Scan Answer Sheets' : 'Settings'}
            </h1>
            {selectedClass && <p className="text-xs text-slate-400 font-semibold mt-0.5">{selectedClass.code} · {selectedClass.name}</p>}
          </div>
          <div className="flex items-center gap-3">
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

        <main className="flex-1 overflow-auto p-8 lg:p-10">
          <div className="max-w-7xl mx-auto">
            <AnimatePresence mode="wait">
              {activeTab === 'dashboard' && (
                <motion.div key="dashboard" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                  <Dashboard classes={classes} results={results} onStartScanner={startScanner} onCreateClass={createClass} />
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
                  />
                </motion.div>
              )}

              {activeTab === 'scanner' && selectedClass && selectedExam && (
                <motion.div key="scanner" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <Scanner
                    classes={classes}
                    selectedClassId={selectedClass.id}
                    selectedExamId={selectedExam.id}
                    onSelectContext={(classId, examId) => {
                      setSelectedClassId(classId);
                      setSelectedExamId(examId);
                    }}
                    onResult={(res) => setResults([res, ...results])}
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

              {activeTab === 'settings' && (
                <motion.div key="settings" className="card p-16 text-center" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <Settings size={48} className="mx-auto text-slate-300 mb-4" />
                  <h2 className="text-2xl font-black text-slate-800">Settings</h2>
                  <p className="text-slate-500 mt-2">Backend URL, export formats, and database sync will live here later.</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </main>
      </div>
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
