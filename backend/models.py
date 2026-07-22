from datetime import datetime

from sqlalchemy import (
    Boolean,
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class ClassRoom(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    semester: Mapped[str] = mapped_column(String(64), nullable=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    students = relationship("Student", back_populates="classroom", cascade="all, delete-orphan")
    exams = relationship("Exam", back_populates="classroom", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="classroom", cascade="all, delete-orphan")


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("class_id", "mssv", name="uq_students_class_mssv"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    mssv: Mapped[str] = mapped_column(String(64), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    classroom = relationship("ClassRoom", back_populates="students")
    submissions = relationship("Submission", back_populates="student")


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=45)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    classroom = relationship("ClassRoom", back_populates="exams")
    exam_codes = relationship("ExamCode", back_populates="exam", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="exam", cascade="all, delete-orphan")


class ExamCode(Base):
    __tablename__ = "exam_codes"
    __table_args__ = (UniqueConstraint("exam_id", "code", name="uq_exam_codes_exam_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    answer_key: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    exam = relationship("Exam", back_populates="exam_codes")
    submissions = relationship("Submission", back_populates="exam_code")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    exam_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("exam_codes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    detected_mssv: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    detected_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    detected_exam_code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    answers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    correct_count: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unmatched")
    manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    aligned_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    student_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    grading: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    crops: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    omr_images: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    preprocess_images: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    classroom = relationship("ClassRoom", back_populates="submissions")
    exam = relationship("Exam", back_populates="submissions")
    exam_code = relationship("ExamCode", back_populates="submissions")
    student = relationship("Student", back_populates="submissions")
