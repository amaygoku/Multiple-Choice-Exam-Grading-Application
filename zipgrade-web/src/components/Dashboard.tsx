import { Camera, Plus, AlertCircle, BookOpen, ClipboardList, Users } from 'lucide-react';
import type { ReactNode } from 'react';
import { ClassRoom, ScannedResult } from '../types';

interface DashboardProps {
  classes: ClassRoom[];
  results: ScannedResult[];
  onStartScanner: (classId?: string, examId?: string) => void;
  onCreateClass: () => void;
}

export default function Dashboard({ classes, results, onStartScanner, onCreateClass }: DashboardProps) {
  const avgScore = results.length > 0
    ? (results.reduce((acc, curr) => acc + curr.score, 0) / results.length).toFixed(1)
    : '0';
  const studentCount = classes.reduce((sum, item) => sum + item.students.length, 0);
  const examCount = classes.reduce((sum, item) => sum + item.exams.length, 0);
  const matchedCount = results.filter(result => result.status === 'matched').length;

  return (
    <div className="space-y-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h2 className="text-3xl font-bold text-slate-900 tracking-tight">Teacher Workspace</h2>
          <p className="text-slate-500 mt-1">Manage classes, rosters, exams, exam codes, and scanned results.</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={onCreateClass} className="btn-outline flex items-center gap-2">
            <Plus size={18} />
            <span>Create Class</span>
          </button>
          <button onClick={() => onStartScanner()} className="btn-primary flex items-center gap-2 shadow-lg shadow-blue-900/20">
            <Camera size={18} />
            <span>Start Scanning</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard icon={<BookOpen size={20} />} label="Classes" value={`${classes.length}`} />
        <StatCard icon={<Users size={20} />} label="Students" value={`${studentCount}`} />
        <StatCard icon={<ClipboardList size={20} />} label="Exams" value={`${examCount}`} />
        <StatCard icon={<Camera size={20} />} label="Average Score" value={`${avgScore}/10`} />
      </div>

      <section className="grid grid-cols-1 xl:grid-cols-[380px_1fr] gap-8">
        <div className="card p-6">
          <h3 className="text-lg font-black text-slate-900 mb-5">Active Classes</h3>
          <div className="space-y-3">
            {classes.map(item => (
              <div key={item.id} className="border border-border-light rounded-xl p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-black text-slate-800">{item.code}</div>
                    <div className="text-sm text-slate-500 mt-1">{item.name}</div>
                  </div>
                  <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">{item.semester}</span>
                </div>
                <div className="grid grid-cols-3 gap-2 mt-4 text-center">
                  <MiniMetric label="Students" value={item.students.length} />
                  <MiniMetric label="Exams" value={item.exams.length} />
                  <MiniMetric label="Scans" value={results.filter(result => result.classId === item.id).length} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card overflow-hidden">
          <div className="bg-slate-50 px-6 py-3 border-b border-border-light grid grid-cols-[1.5fr_1.1fr_1fr_0.8fr_0.8fr] text-[11px] font-bold text-slate-400 uppercase tracking-widest">
            <div>Student</div>
            <div>Class / Exam</div>
            <div className="text-center">Exam Code</div>
            <div className="text-center">Correct</div>
            <div className="text-right">Status</div>
          </div>

          <div className="divide-y divide-gray-50">
            {results.length > 0 ? (
              results.slice(0, 10).map((result) => (
                <div key={result.id} className="px-6 py-4 grid grid-cols-[1.5fr_1.1fr_1fr_0.8fr_0.8fr] items-center text-sm hover:bg-slate-50/50 transition-colors">
                  <div>
                    <div className="font-semibold text-slate-800">{result.studentName}</div>
                    <div className="font-mono text-[11px] text-slate-400">{result.studentMssv}</div>
                  </div>
                  <div className="text-xs text-slate-500">
                    <div>{classes.find(item => item.id === result.classId)?.code ?? 'Unknown class'}</div>
                    <div className="font-bold text-slate-700">{classes.flatMap(item => item.exams).find(exam => exam.id === result.examId)?.title ?? 'Unknown exam'}</div>
                  </div>
                  <div className="text-center font-mono text-slate-600">{result.examCode}</div>
                  <div className="text-center font-bold text-slate-700">{result.correctCount}/{result.totalQuestions}</div>
                  <div className="text-right">
                    <span className={`px-2 py-1 text-[10px] font-bold uppercase rounded-md border ${result.status === 'matched' ? 'bg-green-50 text-green-700 border-green-100' : 'bg-amber-50 text-amber-700 border-amber-100'}`}>
                      {result.status}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="py-20 flex flex-col items-center justify-center text-center px-10">
                <AlertCircle size={40} className="text-slate-200 mb-4" />
                <p className="text-slate-400 font-medium">No papers have been graded yet.</p>
                <p className="text-slate-300 text-xs mt-1 italic">Create an exam, add exam codes, then scan answer sheets.</p>
              </div>
            )}
          </div>
          {results.length > 0 && (
            <div className="px-6 py-4 border-t border-border-light bg-slate-50/30 flex justify-between items-center">
              <span className="text-xs text-slate-400 font-medium">{matchedCount} matched submissions out of {results.length}</span>
              <button className="btn-outline py-1 px-3 text-[10px] uppercase font-bold">Export CSV</button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="card p-6 border-b-4 border-b-primary/10">
      <div className="flex items-center justify-between mb-4">
        <div className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">{label}</div>
        <div className="text-primary">{icon}</div>
      </div>
      <div className="text-3xl font-black text-slate-900 tracking-tight">{value}</div>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-slate-50 rounded-lg py-2">
      <div className="font-black text-slate-800">{value}</div>
      <div className="text-[9px] font-black uppercase tracking-widest text-slate-400">{label}</div>
    </div>
  );
}
