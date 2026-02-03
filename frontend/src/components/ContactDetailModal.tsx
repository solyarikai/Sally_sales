import { useState, useEffect } from 'react';
import { X, Mail, User, Building, MapPin, Linkedin, MessageSquare, Send, Clock, AlertTriangle, FolderPlus } from 'lucide-react';
import { cn } from '../lib/utils';
import type { Contact } from '../api/contacts';

interface Activity {
  id: number;
  type: string;
  content: string;
  timestamp: string;
  direction: 'inbound' | 'outbound';
  channel?: 'email' | 'linkedin';
  campaign?: string;
  automation?: string;
}

interface ContactDetailModalProps {
  contact: Contact | null;
  isOpen: boolean;
  onClose: () => void;
}

export function ContactDetailModal({ contact, isOpen, onClose }: ContactDetailModalProps) {
  const [activeTab, setActiveTab] = useState<'details' | 'conversation'>('details');
  const [activities, setActivities] = useState<Activity[]>([]);
  const [draftReply, setDraftReply] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [savedDraft, setSavedDraft] = useState(false);
  const [projects, setProjects] = useState<Array<{id: number, name: string}>>([]);
  const [selectedProject, setSelectedProject] = useState<number | null>(null);
  const [isAddingToProject, setIsAddingToProject] = useState(false);
  const [addedToProject, setAddedToProject] = useState(false);

  useEffect(() => {
    if (contact && isOpen) {
      // Reset state when contact changes
      setDraftReply('');
      setSavedDraft(false);
      setActiveTab('details');
      setSelectedProject(contact.project_id || null);
      setAddedToProject(false);
      
      // Fetch projects list
      const fetchProjects = async () => {
        try {
          const response = await fetch('/api/contacts/projects/list');
          if (response.ok) {
            const data = await response.json();
            setProjects(data);
          }
        } catch (err) {
          console.error('Failed to fetch projects:', err);
        }
      };
      fetchProjects();
      
      // Fetch activities/history from API
      const fetchHistory = async () => {
        try {
          const response = await fetch(`/api/contacts/${contact.id}/history`);
          if (response.ok) {
            const data = await response.json();
            // Convert to activities format
            const allActivities: Activity[] = [
              ...data.email_history.map((e: any, i: number) => ({
                id: e.id || i,
                type: e.type,
                content: e.body || e.snippet || '',
                timestamp: e.timestamp,
                direction: e.direction as 'inbound' | 'outbound',
                channel: 'email' as const,
                campaign: e.campaign,
              })),
              ...data.linkedin_history.map((l: any, i: number) => ({
                id: l.id || i + 1000,
                type: l.type,
                content: l.body || l.snippet || '',
                timestamp: l.timestamp,
                direction: l.direction as 'inbound' | 'outbound',
                channel: 'linkedin' as const,
                automation: l.automation,
              })),
            ].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
            
            setActivities(allActivities);
          }
        } catch (err) {
          console.error('Failed to fetch history:', err);
        }
      };
      
      fetchHistory();
    }
  }, [contact, isOpen]);

  if (!isOpen || !contact) return null;

  const handleAddToProject = async () => {
    if (!selectedProject || !contact) return;
    
    setIsAddingToProject(true);
    try {
      const response = await fetch(`/api/contacts/${contact.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: selectedProject })
      });
      
      if (response.ok) {
        setAddedToProject(true);
      }
    } catch (err) {
      console.error('Failed to add to project:', err);
    }
    setIsAddingToProject(false);
  };
  
  const handleSaveDraft = async () => {
    if (!draftReply.trim()) return;
    
    setIsSaving(true);
    // Simulate saving draft (NO ACTUAL SENDING)
    await new Promise(resolve => setTimeout(resolve, 500));
    setSavedDraft(true);
    setIsSaving(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50" 
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-lg font-semibold">
              {contact.first_name?.[0]}{contact.last_name?.[0]}
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                {contact.first_name} {contact.last_name}
              </h2>
              <p className="text-sm text-gray-500">{contact.email}</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b px-6">
          <button
            onClick={() => setActiveTab('details')}
            className={cn(
              "px-4 py-3 text-sm font-medium border-b-2 transition-colors",
              activeTab === 'details' 
                ? "border-blue-500 text-blue-600" 
                : "border-transparent text-gray-500 hover:text-gray-700"
            )}
          >
            <User className="w-4 h-4 inline mr-2" />
            Details
          </button>
          <button
            onClick={() => setActiveTab('conversation')}
            className={cn(
              "px-4 py-3 text-sm font-medium border-b-2 transition-colors",
              activeTab === 'conversation' 
                ? "border-blue-500 text-blue-600" 
                : "border-transparent text-gray-500 hover:text-gray-700"
            )}
          >
            <MessageSquare className="w-4 h-4 inline mr-2" />
            Conversation
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {activeTab === 'details' && (
            <div className="grid grid-cols-2 gap-6">
              {/* Contact Info */}
              <div className="space-y-4">
                <h3 className="font-semibold text-gray-900">Contact Information</h3>
                
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Mail className="w-4 h-4 text-gray-400" />
                    <a href={`mailto:${contact.email}`} className="text-blue-600 hover:underline">
                      {contact.email}
                    </a>
                  </div>
                  
                  {contact.company_name && (
                    <div className="flex items-center gap-3">
                      <Building className="w-4 h-4 text-gray-400" />
                      <span>{contact.company_name}</span>
                    </div>
                  )}
                  
                  {contact.job_title && (
                    <div className="flex items-center gap-3">
                      <User className="w-4 h-4 text-gray-400" />
                      <span>{contact.job_title}</span>
                    </div>
                  )}
                  
                  {contact.location && (
                    <div className="flex items-center gap-3">
                      <MapPin className="w-4 h-4 text-gray-400" />
                      <span>{contact.location}</span>
                    </div>
                  )}
                  
                  {contact.linkedin_url && (
                    <div className="flex items-center gap-3">
                      <Linkedin className="w-4 h-4 text-gray-400" />
                      <a 
                        href={`https://${contact.linkedin_url}`} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        View LinkedIn Profile
                      </a>
                    </div>
                  )}
                </div>
              </div>

              {/* Status & Source */}
              <div className="space-y-4">
                <h3 className="font-semibold text-gray-900">Status</h3>
                
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-500">Source:</span>
                    <span className={cn(
                      "px-2 py-1 rounded text-xs font-medium",
                      contact.source === 'smartlead' ? "bg-purple-100 text-purple-700" :
                      contact.source === 'getsales' ? "bg-blue-100 text-blue-700" :
                      "bg-gray-100 text-gray-700"
                    )}>
                      {contact.source}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-500">Status:</span>
                    <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-700">
                      {contact.status}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-500">Has Replied:</span>
                    <span className={cn(
                      "px-2 py-1 rounded text-xs font-medium",
                      contact.has_replied ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"
                    )}>
                      {contact.has_replied ? 'Yes' : 'No'}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-500">
                      Added {new Date(contact.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                {contact.notes && (
                  <div className="mt-4">
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Notes</h4>
                    <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg">
                      {contact.notes}
                    </p>
                  </div>
                )}
                
                {/* Add to Project */}
                <div className="mt-6 p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-200">
                  <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <FolderPlus className="w-4 h-4 text-green-600" />
                    Add to Project
                  </h4>
                  
                  <div className="flex items-center gap-3">
                    <select
                      value={selectedProject || ''}
                      onChange={(e) => setSelectedProject(e.target.value ? Number(e.target.value) : null)}
                      className="flex-1 px-3 py-2 border rounded-lg text-sm bg-white"
                    >
                      <option value="">Select a project...</option>
                      {projects.map((project) => (
                        <option key={project.id} value={project.id}>
                          {project.name}
                        </option>
                      ))}
                    </select>
                    
                    <button
                      onClick={handleAddToProject}
                      disabled={!selectedProject || isAddingToProject}
                      className={cn(
                        "px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2",
                        selectedProject && !isAddingToProject
                          ? "bg-green-600 text-white hover:bg-green-700"
                          : "bg-gray-200 text-gray-500 cursor-not-allowed"
                      )}
                    >
                      {isAddingToProject ? 'Adding...' : addedToProject ? 'Added!' : 'Add to Project'}
                    </button>
                  </div>
                  
                  {addedToProject && (
                    <p className="mt-2 text-sm text-green-600 flex items-center gap-1">
                      <Check className="w-4 h-4" /> Contact added to project successfully
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'conversation' && (
            <div className="space-y-6">
              {/* Conversation History */}
              <div className="space-y-4">
                <h3 className="font-semibold text-gray-900">Conversation History</h3>
                
                {activities.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p>No conversation history yet</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {activities.map((activity) => (
                      <div 
                        key={activity.id}
                        className={cn(
                          "p-4 rounded-lg",
                          activity.direction === 'outbound' ? "bg-blue-50 ml-8" : "bg-gray-50 mr-8"
                        )}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className={cn(
                              "px-2 py-0.5 rounded text-xs font-medium",
                              activity.channel === 'email' ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"
                            )}>
                              {activity.channel === 'email' ? 'Email' : 'LinkedIn'}
                            </span>
                            <span className="text-xs font-medium text-gray-500">
                              {activity.direction === 'outbound' ? 'You' : contact?.first_name}
                            </span>
                            {activity.campaign && (
                              <span className="text-xs text-gray-400">• {activity.campaign}</span>
                            )}
                            {activity.automation && (
                              <span className="text-xs text-gray-400">• {activity.automation}</span>
                            )}
                          </div>
                          <span className="text-xs text-gray-400">
                            {new Date(activity.timestamp).toLocaleString()}
                          </span>
                        </div>
                        <p className="text-sm whitespace-pre-wrap">{activity.content}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Reply Composer */}
              <div className="border-t pt-6">
                <div className="flex items-center gap-2 mb-4 p-3 bg-amber-50 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-amber-600" />
                  <p className="text-sm text-amber-700">
                    Draft mode only - replies are saved but NOT sent automatically
                  </p>
                </div>
                
                <h3 className="font-semibold text-gray-900 mb-3">Compose Reply</h3>
                
                <textarea
                  value={draftReply}
                  onChange={(e) => {
                    setDraftReply(e.target.value);
                    setSavedDraft(false);
                  }}
                  placeholder="Write your reply here..."
                  className="w-full h-32 p-4 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                
                <div className="flex items-center justify-between mt-4">
                  <div className="text-sm text-gray-500">
                    {savedDraft && (
                      <span className="text-green-600 flex items-center gap-1">
                        <Check className="w-4 h-4" /> Draft saved
                      </span>
                    )}
                  </div>
                  
                  <button
                    onClick={handleSaveDraft}
                    disabled={!draftReply.trim() || isSaving}
                    className={cn(
                      "px-4 py-2 rounded-lg flex items-center gap-2 transition-colors",
                      draftReply.trim() 
                        ? "bg-blue-600 text-white hover:bg-blue-700" 
                        : "bg-gray-200 text-gray-500 cursor-not-allowed"
                    )}
                  >
                    <Send className="w-4 h-4" />
                    {isSaving ? 'Saving...' : 'Save Draft'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Helper component for checkmark
function Check({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
