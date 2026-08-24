from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class StudentInfo(BaseModel):
    mssv: str = Field("", description="Student id read from the answer sheet")
    ma_de: str = Field("", description="Exam code read from the answer sheet")
    name: str = Field("", description="Student name read by OCR")
    ocr_name: str = Field("", description="Raw OCR name before any database matching")
    matched_name: str = Field("", description="Matched student name from database when confidence is high enough")
    name_source: str = Field("ocr", description="Name source used for preview display: ocr or database")
    name_similarity: float = Field(0.0, description="Similarity score between OCR name and database name")


class QuestionDetail(BaseModel):
    question: int
    student_ans: str
    correct_ans: str
    result: str
    is_correct: bool


class GradingResult(BaseModel):
    score: float
    correct_count: float
    total: int
    details: List[QuestionDetail]


class ProcessExamResponse(BaseModel):
    success: bool
    message: str = ""
    submission_id: Optional[int] = None
    student_info: Optional[StudentInfo] = None
    answers: Optional[List[str]] = None
    answers_by_method: Optional[Dict[str, List[str]]] = None
    grading: Optional[GradingResult] = None
    grading_by_method: Optional[Dict[str, Optional[GradingResult]]] = None
    source_image_url: Optional[str] = None
    aligned_image_url: Optional[str] = None
    result_image_url: Optional[str] = None
    crops: Optional[Dict[str, Optional[str]]] = None
    omr_images: Optional[Dict[str, Optional[str]]] = None
    preprocess_images: Optional[Dict[str, Optional[str]]] = None
    error: Optional[str] = None


class GradeRequest(BaseModel):
    student_answers: List[str] = Field(..., description="Answers detected for a student")
    correct_answers: str = Field(..., description="Comma-separated answer key")


class ClassBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    semester: str = Field(default="", max_length=64)


class ClassCreate(ClassBase):
    pass


class ClassUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    semester: Optional[str] = Field(default=None, max_length=64)


class ClassResponse(ClassBase):
    id: int

    class Config:
        from_attributes = True


class StudentBase(BaseModel):
    mssv: str = Field(..., min_length=1, max_length=64)
    full_name: str = Field(..., min_length=1, max_length=255)


class StudentCreate(StudentBase):
    class_id: int


class StudentUpdate(BaseModel):
    mssv: Optional[str] = Field(default=None, min_length=1, max_length=64)
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)


class StudentResponse(StudentBase):
    id: int
    class_id: int

    class Config:
        from_attributes = True


class ExamBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    question_count: int = Field(default=45, ge=1, le=300)


class ExamCreate(ExamBase):
    class_id: int


class ExamUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    question_count: Optional[int] = Field(default=None, ge=1, le=300)


class ExamResponse(ExamBase):
    id: int
    class_id: int

    class Config:
        from_attributes = True


class ExamCodeBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    answer_key: List[str] = Field(default_factory=list)


class ExamCodeCreate(ExamCodeBase):
    exam_id: int


class ExamCodeUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=64)
    answer_key: Optional[List[str]] = Field(default=None)


class ExamCodeResponse(ExamCodeBase):
    id: int
    exam_id: int

    class Config:
        from_attributes = True


class SubmissionBase(BaseModel):
    class_id: int
    exam_id: int
    exam_code_id: Optional[int] = None
    student_id: Optional[int] = None
    detected_mssv: str = ""
    detected_name: str = ""
    detected_exam_code: str = ""
    answers: List[str] = Field(default_factory=list)
    score: float = 0.0
    correct_count: float = 0.0
    total_questions: int = 0
    status: str = "unmatched"
    manual_override: bool = False
    source_image_url: Optional[str] = None
    result_image_url: Optional[str] = None
    student_info: Optional[Dict[str, object]] = None
    grading: Optional[Dict[str, object]] = None
    crops: Optional[Dict[str, Optional[str]]] = None
    omr_images: Optional[Dict[str, Optional[str]]] = None
    preprocess_images: Optional[Dict[str, Optional[str]]] = None


class SubmissionCreate(SubmissionBase):
    pass


class SubmissionUpdate(BaseModel):
    class_id: Optional[int] = None
    exam_id: Optional[int] = None
    exam_code_id: Optional[int] = None
    student_id: Optional[int] = None
    detected_mssv: Optional[str] = None
    detected_name: Optional[str] = None
    detected_exam_code: Optional[str] = None
    answers: Optional[List[str]] = None
    score: Optional[float] = None
    correct_count: Optional[float] = None
    total_questions: Optional[int] = None
    status: Optional[str] = None
    manual_override: Optional[bool] = None
    source_image_url: Optional[str] = None
    result_image_url: Optional[str] = None
    student_info: Optional[Dict[str, object]] = None
    grading: Optional[Dict[str, object]] = None
    crops: Optional[Dict[str, Optional[str]]] = None
    omr_images: Optional[Dict[str, Optional[str]]] = None
    preprocess_images: Optional[Dict[str, Optional[str]]] = None


class SubmissionResponse(SubmissionBase):
    id: int

    class Config:
        from_attributes = True


class AnalyticsSummary(BaseModel):
    total_submissions: int = 0
    average_score: float = 0.0
    median_score: float = 0.0
    highest_score: float = 0.0
    lowest_score: float = 0.0
    pass_count: int = 0
    pass_rate: float = 0.0
    excellent_count: int = 0
    excellent_rate: float = 0.0
    matched_count: int = 0
    unmatched_count: int = 0
    unknown_code_count: int = 0


class AnalyticsDistributionItem(BaseModel):
    label: str
    count: int = 0


class AnalyticsGradeBandItem(BaseModel):
    label: str
    count: int = 0
    percent: float = 0.0


class AnalyticsComparisonItem(BaseModel):
    label: str
    sub_label: str = ""
    count: int = 0
    average_score: float = 0.0


class AnalyticsQuestionInsight(BaseModel):
    question: int
    difficulty: float = 0.0
    blank_rate: float = 0.0
    correct_count: int = 0
    wrong_count: int = 0
    blank_count: int = 0
    trap_option: str = "-"


class AnalyticsResponse(BaseModel):
    scope: str = "overall"
    summary: AnalyticsSummary = Field(default_factory=AnalyticsSummary)
    distribution: List[AnalyticsDistributionItem] = Field(default_factory=list)
    grade_bands: List[AnalyticsGradeBandItem] = Field(default_factory=list)
    comparison: List[AnalyticsComparisonItem] = Field(default_factory=list)
    top_failed_questions: List[AnalyticsQuestionInsight] = Field(default_factory=list)
