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
from .call_transcript import CallTranscript
from .campaign_audit_log import CampaignAuditLog
from .gtm_log import GTMStrategyLog
from .telegram_chat import TelegramChat, TelegramChatMessage, TelegramChatInsight
from .telegram_dm import TelegramDMAccount
from .telegram_outreach import (
    TgProxyGroup, TgProxy, TgAccountTag, TgAccountTagLink, TgAccount,
    TgCampaign, TgCampaignAccount, TgRecipient,
    TgSequence, TgSequenceStep, TgStepVariant,
    TgOutreachMessage, TgIncomingReply, TgAutoReplyConfig,
    TgConversation, TgInboxDialog, TgContact,
)
from .meeting import Meeting, MeetingStatus, MeetingOutcome
from .outreach_stats import OutreachStats
from .reply_analysis import ReplyAnalysis
from .pipeline_run import (
    PipelineRun, PipelineRunStatus, PipelinePhase,
    PipelinePhaseLog, PipelinePhaseStatus,
    CostEvent,
)
from .gathering import (
    GatheringRun, CompanySourceLink, CompanyScrape,
    GatheringPrompt, AnalysisRun, AnalysisResult, ApprovalGate,
)
from .project_report import (
    ProjectReport, ProjectPlan, ProjectProgressItem,
    ProjectReportSubscription, ReportRole, ProgressStatus,
)
from .campaign_intelligence import (
    CampaignSnapshot, CampaignPattern, CampaignIntelligenceRun, GeneratedSequence,
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
    # Call Transcripts
    "CallTranscript",
    # Campaign Audit
    "CampaignAuditLog",
    # GTM Strategy Logs
    "GTMStrategyLog",
    # Telegram Chat Monitoring
    "TelegramChat", "TelegramChatMessage", "TelegramChatInsight",
    # Telegram DM Inbox
    "TelegramDMAccount",
    # Telegram Inbox Dialogs
    "TgInboxDialog",
    # Meetings
    "Meeting", "MeetingStatus", "MeetingOutcome",
    # Outreach Stats
    "OutreachStats",
    # Reply Intelligence
    "ReplyAnalysis",
    # Pipeline Runs & Cost
    "PipelineRun", "PipelineRunStatus", "PipelinePhase",
    "PipelinePhaseLog", "PipelinePhaseStatus",
    "CostEvent",
    # Project Reports
    "ProjectReport", "ProjectPlan", "ProjectProgressItem",
    "ProjectReportSubscription", "ReportRole", "ProgressStatus",
    # TAM Gathering
    "GatheringRun", "CompanySourceLink", "CompanyScrape",
    "GatheringPrompt", "AnalysisRun", "AnalysisResult", "ApprovalGate",
    # Campaign Intelligence (GOD_SEQUENCE)
    "CampaignSnapshot", "CampaignPattern", "CampaignIntelligenceRun", "GeneratedSequence",
]
