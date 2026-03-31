from .user import User, Environment, Company, UserActivityLog
from .dataset import Dataset, DataRow, PromptTemplate, EnrichmentJob, EnrichmentStatus, Folder, IntegrationSetting
from .knowledge_base import (
    Document, DocumentType, DocumentFolder, CompanyProfile, 
    Product, Segment, SegmentColumn, DEFAULT_SEGMENT_COLUMNS,
    Competitor, CaseStudy, VoiceTone, Blocklist, BookingLink
)
from .prospect import Prospect, ProspectActivity
from .reply import ReplyAutomation, ProcessedReply, ReplyCategory, ThreadMessage
from .contact import Contact, Project, ContactActivity
from .campaign import Campaign, ChannelAccount
from .domain import (
    Domain, DomainStatus, DomainSource,
    SearchJob, SearchJobStatus, SearchEngine,
    SearchQuery, SearchQueryStatus,
    SearchResult,
    ProjectBlacklist,
    ProjectSearchKnowledge,
)
from .pipeline import (
    DiscoveredCompany, DiscoveredCompanyStatus,
    ExtractedContact, ContactSource,
    PipelineEvent, PipelineEventType,
    EnrichmentAttempt, EnrichmentEffectiveness,
    EmailVerification,
    CampaignPushRule,
)
from .task import OperatorTask
from .chat import ProjectChatMessage
from .project_knowledge import ProjectKnowledge
from .learning import LearningLog, OperatorCorrection, ReferenceExample
from .campaign_audit_log import CampaignAuditLog
from .pipeline_run import (
    PipelineRun, PipelineRunStatus, PipelinePhase,
    PipelinePhaseLog, PipelinePhaseStatus,
    CostEvent,
)
from .lookalike import (
    LookalikeCluster, ClusterMember, LookalikeRun,
    LookalikeRunStatus, LookalikePhase,
)
from .igaming import (
    IGamingContact, IGamingCompany, IGamingEmployee, IGamingImport,
    IGamingAIColumn, BusinessType, IGamingImportStatus, EmployeeSource,
)
from .telegram_outreach import (
    TgAccount, TgAccountTag, TgAccountTagLink,
    TgProxyGroup, TgProxy,
    TgCampaign, TgCampaignAccount,
    TgRecipient, TgSequence, TgSequenceStep, TgStepVariant, TgOutreachMessage,
    TgIncomingReply,
    TgAccountStatus, TgSpamblockType, TgProxyProtocol,
    TgCampaignStatus, TgRecipientStatus, TgMessageStatus,
)

__all__ = [
    # User & Multi-tenancy
    "User", "Environment", "Company", "UserActivityLog",
    # Datasets
    "Dataset", "DataRow", "PromptTemplate", "EnrichmentJob", "EnrichmentStatus", "Folder", "IntegrationSetting",
    # Knowledge Base
    "Document", "DocumentType", "DocumentFolder", "CompanyProfile",
    "Product", "Segment", "SegmentColumn", "DEFAULT_SEGMENT_COLUMNS",
    "Competitor", "CaseStudy", "VoiceTone", "Blocklist", "BookingLink",
    # Prospects
    "Prospect", "ProspectActivity",
    # Reply Automation
    "ReplyAutomation", "ProcessedReply", "ReplyCategory", "ThreadMessage",
    # CRM
    "Contact", "Project", "ContactActivity",
    # Campaigns & Channels
    "Campaign", "ChannelAccount",
    # Domain & Search
    "Domain", "DomainStatus", "DomainSource",
    "SearchJob", "SearchJobStatus", "SearchEngine",
    "SearchQuery", "SearchQueryStatus",
    "SearchResult",
    "ProjectBlacklist",
    "ProjectSearchKnowledge",
    # Pipeline
    "DiscoveredCompany", "DiscoveredCompanyStatus",
    "ExtractedContact", "ContactSource",
    "PipelineEvent", "PipelineEventType",
    "EnrichmentAttempt", "EnrichmentEffectiveness",
    "EmailVerification",
    "CampaignPushRule",
    # Tasks
    "OperatorTask",
    # Chat
    "ProjectChatMessage",
    # Project Knowledge
    "ProjectKnowledge",
    # Learning System
    "LearningLog", "OperatorCorrection", "ReferenceExample",
    # Campaign Audit
    "CampaignAuditLog",
    # Pipeline Runs & Cost
    "PipelineRun", "PipelineRunStatus", "PipelinePhase",
    "PipelinePhaseLog", "PipelinePhaseStatus",
    "CostEvent",
    # Lookalike / TAM
    "LookalikeCluster", "ClusterMember", "LookalikeRun",
    "LookalikeRunStatus", "LookalikePhase",
    # iGaming
    "IGamingContact", "IGamingCompany", "IGamingEmployee", "IGamingImport",
    "IGamingAIColumn", "BusinessType", "IGamingImportStatus", "EmployeeSource",
    # Telegram Outreach
    "TgAccount", "TgAccountTag", "TgAccountTagLink",
    "TgProxyGroup", "TgProxy",
    "TgCampaign", "TgCampaignAccount",
    "TgRecipient", "TgSequence", "TgSequenceStep", "TgStepVariant", "TgOutreachMessage",
    "TgIncomingReply",
    "TgAccountStatus", "TgSpamblockType", "TgProxyProtocol",
    "TgCampaignStatus", "TgRecipientStatus", "TgMessageStatus",
]
