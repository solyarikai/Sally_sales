import { useState, useEffect, useCallback } from 'react';
import {
  Loader2, Globe, Mail, ChevronDown, ChevronUp,
  Target, AlertCircle, ExternalLink, User,
} from 'lucide-react';
import { pipelineApi, type DiscoveredCompany, type DiscoveredCompanyDetail } from '../api/pipeline';
import { cn } from '../lib/utils';

interface Props {
  projectId: number;
}

export function TargetCompaniesViewer({ projectId }: Props) {
  const [companies, setCompanies] = useState<DiscoveredCompany[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<DiscoveredCompanyDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const result = await pipelineApi.listDiscoveredCompanies({
        project_id: projectId,
        is_target: true,
        sort_by: 'confidence',
        sort_order: 'desc',
        page,
        page_size: 30,
      });
      setCompanies(result.items);
      setTotal(result.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [projectId, page]);

  useEffect(() => { load(); }, [load]);

  const handleExpand = async (companyId: number) => {
    if (expandedId === companyId) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(companyId);
    setDetailLoading(true);
    try {
      const d = await pipelineApi.getDiscoveredCompany(companyId);
      setDetail(d);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const totalPages = Math.ceil(total / 30);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-neutral-900">Target Companies</h3>
          <p className="text-sm text-neutral-500 mt-0.5">
            {total} companies identified as targets with AI reasoning
          </p>
        </div>
      </div>

      {loading && companies.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-5 h-5 animate-spin text-neutral-400" />
        </div>
      ) : (
        <>
          <div className="space-y-2">
            {companies.map(company => (
              <div key={company.id} className="bg-white rounded-lg border border-neutral-200">
                {/* Summary row */}
                <div
                  className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-neutral-50 transition-colors"
                  onClick={() => handleExpand(company.id)}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center">
                      <Globe className="w-4 h-4 text-blue-600" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-neutral-900 truncate">
                          {company.name || company.domain}
                        </span>
                        <a
                          href={company.url || `https://${company.domain}`}
                          target="_blank"
                          rel="noreferrer"
                          onClick={e => e.stopPropagation()}
                          className="text-blue-500 hover:text-blue-700"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-neutral-500 mt-0.5">
                        <span className="font-mono">{company.domain}</span>
                        {company.confidence && (
                          <>
                            <span className="text-neutral-300">|</span>
                            <span className={cn(
                              "font-medium",
                              company.confidence >= 0.8 ? "text-green-600" :
                              company.confidence >= 0.5 ? "text-yellow-600" : "text-red-600"
                            )}>
                              {Math.round(company.confidence * 100)}% confidence
                            </span>
                          </>
                        )}
                        <span className="text-neutral-300">|</span>
                        <span className={cn(
                          "px-1.5 py-0.5 rounded text-[10px] font-medium uppercase",
                          company.status === 'enriched' ? 'bg-green-100 text-green-700' :
                          company.status === 'contacts_extracted' ? 'bg-blue-100 text-blue-700' :
                          'bg-neutral-100 text-neutral-600'
                        )}>
                          {company.status.replace(/_/g, ' ')}
                        </span>
                        {company.contacts_count > 0 && (
                          <>
                            <span className="text-neutral-300">|</span>
                            <span className="flex items-center gap-1">
                              <Mail className="w-3 h-3" />
                              {company.contacts_count} contacts
                            </span>
                          </>
                        )}
                        {company.apollo_people_count > 0 && (
                          <>
                            <span className="text-neutral-300">|</span>
                            <span className="flex items-center gap-1">
                              <User className="w-3 h-3" />
                              {company.apollo_people_count} Apollo
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  {expandedId === company.id
                    ? <ChevronUp className="w-4 h-4 text-neutral-400 flex-shrink-0" />
                    : <ChevronDown className="w-4 h-4 text-neutral-400 flex-shrink-0" />
                  }
                </div>

                {/* Expanded detail */}
                {expandedId === company.id && (
                  <div className="px-4 pb-4 border-t border-neutral-100 pt-3 space-y-3">
                    {detailLoading ? (
                      <div className="flex items-center gap-2 text-sm text-neutral-400">
                        <Loader2 className="w-4 h-4 animate-spin" /> Loading...
                      </div>
                    ) : detail ? (
                      <>
                        {/* Why target */}
                        {(company.reasoning || company.company_info) && (
                          <div className="bg-green-50 rounded-lg p-3">
                            <div className="flex items-center gap-2 text-sm font-medium text-green-800 mb-1">
                              <Target className="w-4 h-4" />
                              Why This Company Is a Target
                            </div>
                            {company.reasoning && (
                              <p className="text-sm text-green-700">{company.reasoning}</p>
                            )}
                            {company.company_info && (
                              <div className="mt-2 text-xs text-green-600 space-y-0.5">
                                {company.company_info.description && (
                                  <p>{company.company_info.description}</p>
                                )}
                                {company.company_info.services && (
                                  <p>Services: {company.company_info.services.join(', ')}</p>
                                )}
                                {company.company_info.location && (
                                  <p>Location: {company.company_info.location}</p>
                                )}
                                {company.company_info.industry && (
                                  <p>Industry: {company.company_info.industry}</p>
                                )}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Contacts */}
                        {detail.extracted_contacts.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium text-neutral-700 mb-2">
                              Contacts ({detail.extracted_contacts.length})
                            </h4>
                            <div className="bg-neutral-50 rounded-lg overflow-hidden">
                              <table className="w-full text-sm">
                                <thead>
                                  <tr className="text-left text-xs text-neutral-500 border-b border-neutral-200">
                                    <th className="px-3 py-2">Name</th>
                                    <th className="px-3 py-2">Email</th>
                                    <th className="px-3 py-2">Title</th>
                                    <th className="px-3 py-2">Source</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {detail.extracted_contacts.map(c => (
                                    <tr key={c.id} className="border-b border-neutral-100 last:border-0">
                                      <td className="px-3 py-2">
                                        {[c.first_name, c.last_name].filter(Boolean).join(' ') || '-'}
                                      </td>
                                      <td className="px-3 py-2 font-mono text-xs">
                                        {c.email || '-'}
                                      </td>
                                      <td className="px-3 py-2 text-neutral-600">{c.job_title || '-'}</td>
                                      <td className="px-3 py-2">
                                        <span className={cn(
                                          "px-1.5 py-0.5 rounded text-[10px] font-medium",
                                          c.source === 'apollo' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                                        )}>
                                          {c.source}
                                        </span>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}

                        {/* Events */}
                        {detail.events.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium text-neutral-700 mb-2">
                              Audit Trail ({detail.events.length})
                            </h4>
                            <div className="space-y-1 max-h-40 overflow-y-auto">
                              {detail.events.slice(0, 10).map(evt => (
                                <div key={evt.id} className="flex items-center gap-2 text-xs text-neutral-500">
                                  <span className="font-mono bg-neutral-100 px-1 py-0.5 rounded">
                                    {evt.event_type.replace(/_/g, ' ')}
                                  </span>
                                  <span>{evt.created_at ? new Date(evt.created_at).toLocaleString() : ''}</span>
                                  {evt.detail && (
                                    <span className="text-neutral-400 truncate max-w-xs">
                                      {JSON.stringify(evt.detail).slice(0, 80)}
                                    </span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="text-sm text-neutral-400 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" /> Failed to load details
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-sm rounded-lg border border-neutral-200 hover:bg-neutral-50 disabled:opacity-50 transition-colors"
              >
                Prev
              </button>
              <span className="text-sm text-neutral-500">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1.5 text-sm rounded-lg border border-neutral-200 hover:bg-neutral-50 disabled:opacity-50 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
