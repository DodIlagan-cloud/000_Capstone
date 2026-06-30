"""M12 - Email Ingestion Module Start
Defines email ingestion automated pathway request and result contracts.
M12 End"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class FindingSeverity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class EmailIngestionStatus(str, Enum):
    completed = "completed"
    completed_with_warnings = "completed_with_warnings"
    failed = "failed"
    blocked = "blocked"


class AttachmentStatus(str, Enum):
    retrieved = "retrieved"
    skipped = "skipped"
    duplicate = "duplicate"
    failed = "failed"
    handed_off = "handed_off"
    password_required = "password_required"
    password_failed = "password_failed"
    unlocked = "unlocked"


class EmailFinding(BaseModel):
    code: str
    severity: FindingSeverity
    message: str
    message_id: Optional[str] = None
    attachment_name: Optional[str] = None


class EmailProvider(str, Enum):
    synthetic = "synthetic"
    yahoo_imap = "yahoo_imap"
    gmail_imap = "gmail_imap"
    outlook_imap = "outlook_imap"
    custom_imap = "custom_imap"


class SourceConnectionStatus(str, Enum):
    connected = "connected"
    needs_setup = "needs_setup"
    failed = "failed"
    not_tested = "not_tested"


class PdfPasswordDefaultAction(str, Enum):
    ask_user = "ask_user"
    use_source_secret = "use_source_secret"
    pending_review = "pending_review"


class PdfPasswordRule(BaseModel):
    rule_id: str
    display_name: str
    password_secret_ref: str
    password: Optional[str] = Field(default=None, exclude=True)
    sender_contains: list[str] = Field(default_factory=list)
    subject_contains: list[str] = Field(default_factory=list)
    filename_contains: list[str] = Field(default_factory=list)
    enabled: bool = True

    @field_validator("password_secret_ref")
    @classmethod
    def normalize_password_secret_ref(cls, value: str) -> str:
        import re

        return re.sub(r"[^a-zA-Z0-9-]+", "-", value).strip("-").lower()


class AttachmentPolicy(BaseModel):
    allowed_extensions: list[str] = Field(default_factory=list)
    allowed_mime_types: list[str] = Field(default_factory=list)
    max_attachment_size_bytes: Optional[int] = None


class PdfPasswordPolicy(BaseModel):
    default_action: PdfPasswordDefaultAction = PdfPasswordDefaultAction.ask_user
    password_secret_ref: Optional[str] = None
    password_rules: list[PdfPasswordRule] = Field(default_factory=list)
    allow_one_time_password: bool = True


class PostProcessPolicy(BaseModel):
    mark_as_read: bool = False
    move_to_folder: Optional[str] = None


class EmailConnectionSettings(BaseModel):
    imap_host: Optional[str] = None
    imap_port: int = 993
    use_ssl: bool = True


class EmailSourceProfileBase(BaseModel):
    display_name: str
    provider: EmailProvider = EmailProvider.custom_imap
    email_address: str
    enabled: bool = True
    folder: str = "Inbox"
    connection_settings: EmailConnectionSettings = Field(default_factory=EmailConnectionSettings)
    sender_allowlist: list[str] = Field(default_factory=list)
    subject_contains: list[str] = Field(default_factory=list)
    attachment_policy: AttachmentPolicy = Field(default_factory=AttachmentPolicy)
    pdf_password_policy: PdfPasswordPolicy = Field(default_factory=PdfPasswordPolicy)
    post_process_policy: PostProcessPolicy = Field(default_factory=PostProcessPolicy)


class EmailSourceProfileCreate(EmailSourceProfileBase):
    source_id: Optional[str] = None
    app_password: Optional[str] = None
    secret_ref: Optional[str] = None


class EmailSourceProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    provider: Optional[EmailProvider] = None
    email_address: Optional[str] = None
    enabled: Optional[bool] = None
    folder: Optional[str] = None
    connection_settings: Optional[EmailConnectionSettings] = None
    sender_allowlist: Optional[list[str]] = None
    subject_contains: Optional[list[str]] = None
    attachment_policy: Optional[AttachmentPolicy] = None
    pdf_password_policy: Optional[PdfPasswordPolicy] = None
    post_process_policy: Optional[PostProcessPolicy] = None
    app_password: Optional[str] = None
    secret_ref: Optional[str] = None


class EmailSourceProfile(EmailSourceProfileBase):
    source_id: str
    secret_ref: Optional[str] = None
    connection_status: SourceConnectionStatus = SourceConnectionStatus.not_tested
    last_tested_at: Optional[str] = None
    last_run_id: Optional[str] = None
    last_run_status: Optional[str] = None


class EmailSourceProfileList(BaseModel):
    sources: list[EmailSourceProfile] = Field(default_factory=list)


class TestConnectionRequest(BaseModel):
    app_password: Optional[str] = None
    folder: Optional[str] = None


class TestConnectionResult(BaseModel):
    source_id: str
    status: SourceConnectionStatus
    provider: EmailProvider
    folder: str
    message: str


class MailboxAuthorizationContext(BaseModel):
    provider: str = "synthetic"
    account_id: Optional[str] = None
    tenant_id: Optional[str] = None
    connection_profile: Optional[str] = None
    access_token_present: bool = False


class RetrievalRequest(BaseModel):
    mailbox_folder: Optional[str] = None
    received_after: Optional[str] = None
    received_before: Optional[str] = None
    sender_allowlist: list[str] = Field(default_factory=list)
    subject_contains: list[str] = Field(default_factory=list)
    # None means use DEFAULT_MAX_MESSAGES. 0 means no message limit.
    max_messages: Optional[int] = None


class IntakePolicy(BaseModel):
    allowed_extensions: Optional[list[str]] = None
    allowed_mime_types: Optional[list[str]] = None
    max_attachment_size_bytes: Optional[int] = None
    deduplicate: bool = True
    handoff_to_file_ingestion: bool = False
    dry_run: bool = True
    detect_password_protected_pdfs: bool = True


class EmailAttachmentInput(BaseModel):
    attachment_id: str
    filename: str
    content_type: str
    size_bytes: int
    content_base64: Optional[str] = None
    sha256: Optional[str] = None
    is_password_protected: Optional[bool] = None


class EmailMessageInput(BaseModel):
    message_id: str
    internet_message_id: Optional[str] = None
    sender: str
    subject: Optional[str] = None
    received_at: str
    attachments: list[EmailAttachmentInput] = Field(default_factory=list)


class AutomatedEmailIngestionRequest(BaseModel):
    source_id: str
    mode: Optional[str] = None
    authorization: MailboxAuthorizationContext = Field(default_factory=MailboxAuthorizationContext)
    retrieval: RetrievalRequest = Field(default_factory=RetrievalRequest)
    policy: IntakePolicy = Field(default_factory=IntakePolicy)
    messages: list[EmailMessageInput] = Field(default_factory=list)


class EmailSourceMetadata(BaseModel):
    source_id: str
    provider: str
    account_id: Optional[str] = None
    message_id: str
    internet_message_id: Optional[str] = None
    sender: str
    subject_redacted: Optional[str] = None
    received_at: str
    attachment_id: str
    attachment_name: str


class FileIngestionHandoff(BaseModel):
    attempted: bool = False
    ingestion_id: Optional[str] = None
    status: Optional[str] = None
    content_reference: Optional[str] = None
    error: Optional[str] = None


class AttachmentCandidate(BaseModel):
    candidate_id: str
    status: AttachmentStatus
    filename: str
    content_type: str
    size_bytes: int
    sha256: Optional[str] = None
    source: EmailSourceMetadata
    handoff: Optional[FileIngestionHandoff] = None
    password_state: Optional[str] = None
    password_rule_id: Optional[str] = None
    password_secret_ref: Optional[str] = None
    findings: list[EmailFinding] = Field(default_factory=list)


class EmailIngestionSummary(BaseModel):
    message_count: int
    attachment_count: int
    retrieved_count: int
    skipped_count: int
    duplicate_count: int
    failed_count: int
    handed_off_count: int
    password_required_count: int = 0
    password_failed_count: int = 0


class EmailIngestionEvaluation(BaseModel):
    run_id: str
    source_id: str
    provider: str
    status: EmailIngestionStatus
    finding_counts: dict[str, int]
    dry_run: bool


class AutomatedEmailIngestionResult(BaseModel):
    run_id: str
    status: EmailIngestionStatus
    source_id: str
    provider: str
    folder: str
    candidates: list[AttachmentCandidate] = Field(default_factory=list)
    summary: EmailIngestionSummary
    evaluation: EmailIngestionEvaluation
    findings: list[EmailFinding] = Field(default_factory=list)
