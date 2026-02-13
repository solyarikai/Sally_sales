import { useState, useEffect, useCallback } from 'react';
import {
  Loader2, Plus, Pencil, Trash2, ChevronDown, ChevronUp,
  Send, Save, X, ToggleLeft, ToggleRight, Sparkles,
} from 'lucide-react';
import {
  pipelineApi,
  type CampaignPushRule,
  type CampaignPushRuleCreate,
  type SmartleadEmailAccount,
  type GenerateSequencesRequest,
} from '../api/pipeline';
import { cn } from '../lib/utils';

interface Props {
  projectId: number;
}

const LANG_OPTIONS = [
  { value: 'ru', label: 'Russian (Cyrillic)' },
  { value: 'en', label: 'English (Latin)' },
  { value: 'any', label: 'Any language' },
];

const NAME_OPTIONS = [
  { value: 'true', label: 'Has personal name' },
  { value: 'false', label: 'No name (generic emails)' },
  { value: 'null', label: 'Any (name or generic)' },
];

export function CampaignPushRules({ projectId }: Props) {
  const [rules, setRules] = useState<CampaignPushRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [pushing, setPushing] = useState(false);
  const [pushResult, setPushResult] = useState<string | null>(null);
  const [emailAccounts, setEmailAccounts] = useState<SmartleadEmailAccount[]>([]);

  const loadRules = useCallback(async () => {
    try {
      setLoading(true);
      const data = await pipelineApi.listPushRules(projectId);
      setRules(data);
    } catch (err: any) {
      setError(err.userMessage || 'Failed to load push rules');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadRules(); }, [loadRules]);

  // Load email accounts once
  useEffect(() => {
    pipelineApi.listSmartleadEmailAccounts().then(setEmailAccounts).catch(() => {});
  }, []);

  const handlePush = async () => {
    if (!confirm('Push new contacts to SmartLead campaigns? This will create campaigns and upload leads.')) return;
    setPushing(true);
    setPushResult(null);
    try {
      const result = await pipelineApi.pushToSmartlead(projectId);
      setPushResult(result.status === 'started' ? 'Push started! Check pipeline status for progress.' : `Status: ${result.status}`);
    } catch (err: any) {
      setPushResult(err.userMessage || 'Push failed');
    } finally {
      setPushing(false);
    }
  };

  const handleDelete = async (ruleId: number) => {
    if (!confirm('Delete this push rule?')) return;
    try {
      await pipelineApi.deletePushRule(ruleId);
      await loadRules();
    } catch (err: any) {
      alert(err.userMessage || 'Delete failed');
    }
  };

  const handleToggleActive = async (rule: CampaignPushRule) => {
    try {
      await pipelineApi.updatePushRule(rule.id, { is_active: !rule.is_active });
      await loadRules();
    } catch (err: any) {
      alert(err.userMessage || 'Update failed');
    }
  };

  if (loading && rules.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-neutral-400" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-neutral-900">Campaign Push Rules</h3>
          <p className="text-sm text-neutral-500 mt-0.5">
            Define rules for automatically routing contacts to SmartLead campaigns
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handlePush}
            disabled={pushing || rules.length === 0}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {pushing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Push to SmartLead
          </button>
          <button
            onClick={() => { setCreating(true); setEditingId(null); }}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-neutral-200 text-neutral-700 hover:bg-neutral-50 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Rule
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
      )}

      {pushResult && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-blue-700 text-sm">{pushResult}</div>
      )}

      {/* Rules list */}
      <div className="space-y-2">
        {rules.map(rule => (
          <div key={rule.id} className={cn(
            "bg-white rounded-lg border transition-colors",
            rule.is_active ? "border-neutral-200" : "border-neutral-100 opacity-60",
          )}>
            {/* Rule summary row */}
            <div
              className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-neutral-50"
              onClick={() => setExpandedId(expandedId === rule.id ? null : rule.id)}
            >
              <div className="flex items-center gap-3">
                <button
                  onClick={e => { e.stopPropagation(); handleToggleActive(rule); }}
                  className="text-neutral-400 hover:text-blue-600 transition-colors"
                  title={rule.is_active ? 'Deactivate' : 'Activate'}
                >
                  {rule.is_active
                    ? <ToggleRight className="w-5 h-5 text-blue-600" />
                    : <ToggleLeft className="w-5 h-5" />
                  }
                </button>
                <div>
                  <span className="font-medium text-neutral-900">{rule.name}</span>
                  <div className="flex items-center gap-2 mt-0.5 text-xs text-neutral-500">
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-neutral-100 font-mono">
                      {rule.language}
                    </span>
                    <span>{rule.has_first_name === true ? 'With name' : rule.has_first_name === false ? 'No name' : 'Any'}</span>
                    <span className="text-neutral-300">|</span>
                    <span>Priority: {rule.priority}</span>
                    <span className="text-neutral-300">|</span>
                    <span>Max: {rule.max_leads_per_campaign}/campaign</span>
                    {rule.current_campaign_id && (
                      <>
                        <span className="text-neutral-300">|</span>
                        <span className="text-blue-600">Campaign: {rule.current_campaign_id} ({rule.current_campaign_lead_count ?? 0} leads)</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={e => { e.stopPropagation(); setEditingId(rule.id); setCreating(false); }}
                  className="p-1.5 text-neutral-400 hover:text-blue-600 rounded-md hover:bg-blue-50 transition-colors"
                >
                  <Pencil className="w-4 h-4" />
                </button>
                <button
                  onClick={e => { e.stopPropagation(); handleDelete(rule.id); }}
                  className="p-1.5 text-neutral-400 hover:text-red-600 rounded-md hover:bg-red-50 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
                {expandedId === rule.id ? <ChevronUp className="w-4 h-4 text-neutral-400" /> : <ChevronDown className="w-4 h-4 text-neutral-400" />}
              </div>
            </div>

            {/* Expanded detail */}
            {expandedId === rule.id && (
              <div className="px-4 pb-4 border-t border-neutral-100 pt-3 space-y-3">
                {rule.description && (
                  <p className="text-sm text-neutral-600">{rule.description}</p>
                )}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-neutral-500">Campaign template:</span>
                    <div className="font-mono text-neutral-800 mt-1">{rule.campaign_name_template}</div>
                  </div>
                  <div>
                    <span className="text-neutral-500">Sequence language:</span>
                    <div className="mt-1">{rule.sequence_language === 'ru' ? 'Russian' : 'English'}</div>
                  </div>
                  <div>
                    <span className="text-neutral-500">Use {{first_name}}:</span>
                    <div className="mt-1">{rule.use_first_name_var ? 'Yes' : 'No'}</div>
                  </div>
                  <div>
                    <span className="text-neutral-500">Email accounts:</span>
                    <div className="mt-1">{rule.email_account_ids?.length ?? 0} assigned</div>
                  </div>
                </div>

                {/* Sequence preview */}
                {rule.sequence_template && rule.sequence_template.length > 0 && (
                  <div>
                    <span className="text-sm text-neutral-500">Sequences ({rule.sequence_template.length} steps):</span>
                    <div className="mt-2 space-y-2">
                      {rule.sequence_template.map((seq: any, idx: number) => (
                        <div key={idx} className="bg-neutral-50 rounded-lg p-3 text-sm">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-neutral-700">Step {seq.seq_number}</span>
                            {seq.seq_delay_details?.delay_in_days > 0 && (
                              <span className="text-xs text-neutral-400">+{seq.seq_delay_details.delay_in_days} days</span>
                            )}
                          </div>
                          <div className="font-medium text-neutral-800">{seq.subject}</div>
                          <div
                            className="mt-1 text-neutral-600 text-xs leading-relaxed max-h-20 overflow-hidden"
                            dangerouslySetInnerHTML={{ __html: seq.email_body }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Inline edit */}
            {editingId === rule.id && (
              <RuleEditor
                rule={rule}
                emailAccounts={emailAccounts}
                projectId={projectId}
                onSave={async (updates) => {
                  await pipelineApi.updatePushRule(rule.id, updates);
                  setEditingId(null);
                  await loadRules();
                }}
                onCancel={() => setEditingId(null)}
              />
            )}
          </div>
        ))}

        {rules.length === 0 && !creating && (
          <div className="text-center py-12 text-neutral-400 text-sm">
            No push rules configured. Add a rule to start pushing contacts to SmartLead.
          </div>
        )}
      </div>

      {/* Create new rule */}
      {creating && (
        <div className="bg-white rounded-lg border border-blue-200">
          <div className="px-4 py-3 border-b border-blue-100 bg-blue-50">
            <h4 className="font-medium text-blue-800">New Push Rule</h4>
          </div>
          <RuleEditor
            emailAccounts={emailAccounts}
            projectId={projectId}
            onSave={async (data) => {
              await pipelineApi.createPushRule(projectId, data as CampaignPushRuleCreate);
              setCreating(false);
              await loadRules();
            }}
            onCancel={() => setCreating(false)}
          />
        </div>
      )}
    </div>
  );
}

// ============ Rule Editor Form ============

interface RuleEditorProps {
  rule?: CampaignPushRule;
  emailAccounts: SmartleadEmailAccount[];
  projectId: number;
  onSave: (data: Partial<CampaignPushRuleCreate>) => Promise<void>;
  onCancel: () => void;
}

function RuleEditor({ rule, emailAccounts, projectId, onSave, onCancel }: RuleEditorProps) {
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generatedSequences, setGeneratedSequences] = useState<any[] | null>(rule?.sequence_template ?? null);
  const [form, setForm] = useState({
    name: rule?.name ?? '',
    description: rule?.description ?? '',
    language: rule?.language ?? 'any',
    has_first_name: rule?.has_first_name === true ? 'true' : rule?.has_first_name === false ? 'false' : 'null',
    campaign_name_template: rule?.campaign_name_template ?? '{project} {date}',
    sequence_language: rule?.sequence_language ?? 'ru',
    use_first_name_var: rule?.use_first_name_var ?? true,
    max_leads_per_campaign: rule?.max_leads_per_campaign ?? 500,
    priority: rule?.priority ?? 0,
    email_account_ids: rule?.email_account_ids ?? [],
  });

  const handleGenerateSequences = async () => {
    setGenerating(true);
    try {
      const result = await pipelineApi.generateSequences({
        project_id: projectId,
        language: form.sequence_language,
        use_first_name: form.use_first_name_var,
        tone: 'professional',
        num_steps: 3,
      });
      setGeneratedSequences(result.sequences);
    } catch (err: any) {
      alert(err.userMessage || 'AI generation failed. Try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave({
        name: form.name,
        description: form.description || undefined,
        language: form.language,
        has_first_name: form.has_first_name === 'null' ? undefined : form.has_first_name === 'true',
        campaign_name_template: form.campaign_name_template,
        sequence_language: form.sequence_language,
        sequence_template: generatedSequences ?? undefined,
        use_first_name_var: form.use_first_name_var,
        max_leads_per_campaign: form.max_leads_per_campaign,
        priority: form.priority,
        email_account_ids: form.email_account_ids.length > 0 ? form.email_account_ids : undefined,
      });
    } catch (err: any) {
      alert(err.userMessage || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="px-4 py-4 space-y-4 border-t border-neutral-100">
      <div className="grid grid-cols-2 gap-4">
        {/* Name */}
        <div>
          <label className="block text-xs font-medium text-neutral-500 mb-1">Rule Name</label>
          <input
            type="text"
            required
            value={form.name}
            onChange={e => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="e.g. Russian + name"
          />
        </div>

        {/* Campaign name template */}
        <div>
          <label className="block text-xs font-medium text-neutral-500 mb-1">Campaign Name Template</label>
          <input
            type="text"
            required
            value={form.campaign_name_template}
            onChange={e => setForm({ ...form, campaign_name_template: e.target.value })}
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            placeholder="Deliryo {date} Из РФ"
          />
          <p className="text-xs text-neutral-400 mt-1">{'{date}'} = current date (dd.mm)</p>
        </div>

        {/* Language */}
        <div>
          <label className="block text-xs font-medium text-neutral-500 mb-1">Contact Language</label>
          <select
            value={form.language}
            onChange={e => setForm({ ...form, language: e.target.value })}
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {LANG_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {/* Has name */}
        <div>
          <label className="block text-xs font-medium text-neutral-500 mb-1">Name Requirement</label>
          <select
            value={form.has_first_name}
            onChange={e => setForm({ ...form, has_first_name: e.target.value })}
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {NAME_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {/* Sequence language */}
        <div>
          <label className="block text-xs font-medium text-neutral-500 mb-1">Sequence Language</label>
          <select
            value={form.sequence_language}
            onChange={e => setForm({ ...form, sequence_language: e.target.value })}
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ru">Russian</option>
            <option value="en">English</option>
          </select>
        </div>

        {/* Use first_name var */}
        <div>
          <label className="block text-xs font-medium text-neutral-500 mb-1">Use {'{{first_name}}'}</label>
          <button
            type="button"
            onClick={() => setForm({ ...form, use_first_name_var: !form.use_first_name_var })}
            className={cn(
              "flex items-center gap-2 px-3 py-2 text-sm rounded-lg border transition-colors",
              form.use_first_name_var
                ? "border-blue-200 bg-blue-50 text-blue-700"
                : "border-neutral-200 bg-white text-neutral-500",
            )}
          >
            {form.use_first_name_var
              ? <><ToggleRight className="w-4 h-4" /> Enabled</>
              : <><ToggleLeft className="w-4 h-4" /> Disabled</>
            }
          </button>
        </div>

        {/* Max leads */}
        <div>
          <label className="block text-xs font-medium text-neutral-500 mb-1">Max Leads / Campaign</label>
          <input
            type="number"
            min={1}
            max={5000}
            value={form.max_leads_per_campaign}
            onChange={e => setForm({ ...form, max_leads_per_campaign: parseInt(e.target.value) || 500 })}
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Priority */}
        <div>
          <label className="block text-xs font-medium text-neutral-500 mb-1">Priority</label>
          <input
            type="number"
            value={form.priority}
            onChange={e => setForm({ ...form, priority: parseInt(e.target.value) || 0 })}
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-neutral-400 mt-1">Higher = checked first</p>
        </div>
      </div>

      {/* Description */}
      <div>
        <label className="block text-xs font-medium text-neutral-500 mb-1">Description</label>
        <textarea
          value={form.description}
          onChange={e => setForm({ ...form, description: e.target.value })}
          rows={2}
          className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Description of this rule..."
        />
      </div>

      {/* Sequence generation */}
      <div className="border border-neutral-200 rounded-lg p-4 space-y-3 bg-gradient-to-br from-purple-50/30 to-blue-50/30">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-medium text-neutral-700">Email Sequences</h4>
            <p className="text-xs text-neutral-500 mt-0.5">
              {generatedSequences ? `${generatedSequences.length} steps configured` : 'No sequences yet — generate with AI or paste manually'}
            </p>
          </div>
          <button
            type="button"
            onClick={handleGenerateSequences}
            disabled={generating}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 transition-colors"
          >
            {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            Generate with AI
          </button>
        </div>
        {generatedSequences && generatedSequences.length > 0 && (
          <div className="space-y-2">
            {generatedSequences.map((seq: any, idx: number) => (
              <div key={idx} className="bg-white rounded-lg p-3 text-sm border border-neutral-100">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-neutral-700">Step {seq.seq_number}</span>
                  {seq.seq_delay_details?.delay_in_days > 0 && (
                    <span className="text-xs text-neutral-400">+{seq.seq_delay_details.delay_in_days} days</span>
                  )}
                </div>
                <div className="font-medium text-neutral-800 text-xs">{seq.subject}</div>
                <div
                  className="mt-1 text-neutral-600 text-xs leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: seq.email_body }}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Email accounts */}
      {emailAccounts.length > 0 && (
        <div>
          <label className="block text-xs font-medium text-neutral-500 mb-1">Email Accounts ({form.email_account_ids.length} selected)</label>
          <div className="grid grid-cols-3 gap-1 max-h-32 overflow-y-auto bg-neutral-50 rounded-lg p-2">
            {emailAccounts.map(acc => (
              <label key={acc.id} className="flex items-center gap-1.5 text-xs text-neutral-700 cursor-pointer hover:bg-white rounded px-1.5 py-1">
                <input
                  type="checkbox"
                  checked={form.email_account_ids.includes(acc.id)}
                  onChange={e => {
                    const ids = e.target.checked
                      ? [...form.email_account_ids, acc.id]
                      : form.email_account_ids.filter((id: number) => id !== acc.id);
                    setForm({ ...form, email_account_ids: ids });
                  }}
                  className="rounded border-neutral-300"
                />
                <span className="truncate">{acc.email}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2">
        <button
          type="submit"
          disabled={saving || !form.name || !form.campaign_name_template}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-neutral-200 text-neutral-700 hover:bg-neutral-50 transition-colors"
        >
          <X className="w-4 h-4" />
          Cancel
        </button>
      </div>
    </form>
  );
}
