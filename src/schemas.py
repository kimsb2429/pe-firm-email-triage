from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


Category = Literal[
    "Deal Flow",
    "Portfolio Update",
    "LP Communication",
    "Compliance",
    "Internal",
    "Press",
    "Other",
]

Priority = Literal["High", "Medium", "Low"]

DayOfWeek = Literal[
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]


class Email(BaseModel):
    id: int
    from_: str = Field(alias="from")
    subject: str
    body: str
    received_at: str

    model_config = {"populate_by_name": True}


class Step1(BaseModel):
    rationale: str
    category: Category
    priority: Priority
    summary: str
    has_deadline: bool
    portco_problem_flagged: bool

    @field_validator("summary")
    @classmethod
    def summary_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("summary cannot be empty")
        return v

    @model_validator(mode="after")
    def problem_flag_requires_portfolio_update(self) -> "Step1":
        if self.portco_problem_flagged and self.category != "Portfolio Update":
            raise ValueError(
                "portco_problem_flagged=True requires category='Portfolio Update'"
            )
        return self


class Deadline(BaseModel):
    deadline_text: str
    deadline_date: Optional[str] = Field(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"
    )  # ISO YYYY-MM-DD; null when not derivable or fails cross-check
    deadline_weekday: Optional[DayOfWeek] = None  # must match deadline_date
    action_required: str

    @field_validator("deadline_text", "action_required")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field cannot be empty")
        return v


class Step2(BaseModel):
    rationale: str
    reply_draft: Optional[str] = None
    deadline: Optional[Deadline] = None
    next_steps: Optional[list[str]] = None

    @field_validator("next_steps")
    @classmethod
    def next_steps_count(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        if not (2 <= len(v) <= 3):
            raise ValueError(f"next_steps must have 2 or 3 items, got {len(v)}")
        for s in v:
            if not s.strip():
                raise ValueError("next_steps items cannot be empty")
        return v


class Actions(BaseModel):
    """Step 2 output and any cross-step violations."""
    rationale: Optional[str] = None
    reply_draft: Optional[str] = None
    deadline: Optional[Deadline] = None
    next_steps: Optional[list[str]] = None
    violations: list[str] = Field(default_factory=list)


class TriageRecord(BaseModel):
    id: int
    from_: str = Field(alias="from")
    subject: str
    body: str
    received_at: str
    classification: Optional[Step1] = None
    actions: Actions = Field(default_factory=Actions)
    status: Literal["ok", "error"] = "ok"
    error: Optional[str] = None

    model_config = {"populate_by_name": True}

    @classmethod
    def from_email(
        cls,
        email: Email,
        *,
        classification: Optional[Step1] = None,
        actions: Optional[Actions] = None,
        status: Literal["ok", "error"] = "ok",
        error: Optional[str] = None,
    ) -> "TriageRecord":
        """Build a TriageRecord by carrying email fields through."""
        return cls(
            id=email.id,
            from_=email.from_,
            subject=email.subject,
            body=email.body,
            received_at=email.received_at,
            classification=classification,
            actions=actions if actions is not None else Actions(),
            status=status,
            error=error,
        )
