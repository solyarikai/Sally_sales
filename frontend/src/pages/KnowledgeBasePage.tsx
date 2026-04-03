import { useState, useEffect, useRef } from 'react';
import { 
  FileText, Target, Swords, Trophy, Mic2, Ban, Calendar,
  Plus, Trash2, Edit2, Save, ChevronLeft, Upload,
  Building2, Loader2, ExternalLink, File, Check, X,
  RefreshCw, Package, Link2, Folder, FolderPlus, MoreVertical, Eye
} from 'lucide-react';
import * as kb from '../api/knowledgeBase';
import { cn } from '../lib/utils';

type EntityType = 'overview' | 'company' | 'documents' | 'products' | 'segments' | 'competitors' | 'cases' | 'voice' | 'booking' | 'blocklist';

const ENTITY_CARDS: { type: EntityType; label: string; icon: React.ElementType; description: string }[] = [
  { type: 'company', label: 'Company', icon: Building2, description: 'Company profile & info' },
  { type: 'documents', label: 'Documents', icon: FileText, description: 'Upload files, folders, MD conversion' },
  { type: 'products', label: 'Products', icon: Package, description: 'Products & services we sell' },
  { type: 'segments', label: 'Segments', icon: Target, description: 'Target audiences & messaging' },
  { type: 'competitors', label: 'Competitors', icon: Swords, description: 'Competitive analysis' },
  { type: 'cases', label: 'Case Studies', icon: Trophy, description: 'Customer success stories' },
  { type: 'voice', label: 'Voice & Tone', icon: Mic2, description: 'Messaging styles' },
  { type: 'booking', label: 'Booking Links', icon: Calendar, description: 'Calendar links' },
  { type: 'blocklist', label: 'Blocklist', icon: Ban, description: 'Never contact list' },
];

export default function KnowledgeBasePage() {
  const [activeEntity, setActiveEntity] = useState<EntityType>('overview');

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="border-b border-neutral-200 px-6 py-4">
        <div className="flex items-center gap-3">
          {activeEntity !== 'overview' && (
            <button onClick={() => setActiveEntity('overview')} className="p-1.5 hover:bg-neutral-100 rounded-lg">
              <ChevronLeft className="w-5 h-5" />
            </button>
          )}
          <div>
            <h1 className="text-xl font-semibold text-neutral-900">Knowledge Base</h1>
            <p className="text-sm text-neutral-500">Company context for AI personalization</p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {activeEntity === 'overview' && <OverviewGrid onSelect={setActiveEntity} />}
        {activeEntity === 'company' && <CompanyView />}
        {activeEntity === 'documents' && <DocumentsView />}
        {activeEntity === 'products' && <ProductsView />}
        {activeEntity === 'segments' && <SegmentsView />}
        {activeEntity === 'competitors' && <CompetitorsView />}
        {activeEntity === 'cases' && <CaseStudiesView />}
        {activeEntity === 'voice' && <VoiceTonesView />}
        {activeEntity === 'booking' && <BookingLinksView />}
        {activeEntity === 'blocklist' && <BlocklistView />}
      </div>
    </div>
  );
}

// ============ Overview Grid ============

function OverviewGrid({ onSelect }: { onSelect: (type: EntityType) => void }) {
  return (
    <div className="max-w-5xl mx-auto">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {ENTITY_CARDS.map(({ type, label, icon: Icon, description }) => (
          <button
            key={type}
            onClick={() => onSelect(type)}
            className="card p-5 text-left hover:border-neutral-400 transition-colors group"
          >
            <div className="w-12 h-12 rounded-lg bg-neutral-100 group-hover:bg-neutral-200 flex items-center justify-center mb-3 transition-colors">
              <Icon className="w-6 h-6 text-neutral-600" />
            </div>
            <h3 className="font-semibold text-neutral-900">{label}</h3>
            <p className="text-sm text-neutral-500 mt-1">{description}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

// ============ Company View ============

function CompanyView() {
  const [company, setCompany] = useState<kb.CompanyProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: '', website: '' });

  useEffect(() => {
    kb.getCompanyProfile()
      .then(data => {
        setCompany(data);
        if (data) {
          setForm({ name: data.name || '', website: data.website || '' });
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    try {
      const updated = await kb.saveCompanyProfile(form);
      setCompany(updated);
      setEditing(false);
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-5 h-5 animate-spin" /></div>;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Company Info */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold">Company Profile</h2>
          {!editing && (
            <button onClick={() => setEditing(true)} className="btn btn-secondary text-sm">
              <Edit2 className="w-4 h-4" />
              Edit
            </button>
          )}
        </div>
        
        {editing ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Company Name</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="input w-full"
                placeholder="Your Company Name"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Website</label>
              <input
                type="url"
                value={form.website}
                onChange={(e) => setForm({ ...form, website: e.target.value })}
                className="input w-full"
                placeholder="https://example.com"
              />
            </div>
            <div className="flex gap-2 justify-end pt-4">
              <button onClick={() => setEditing(false)} className="btn btn-ghost">Cancel</button>
              <button onClick={handleSave} className="btn btn-primary">
                <Save className="w-4 h-4" />
                Save
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-xl bg-neutral-100 flex items-center justify-center">
                <Building2 className="w-8 h-8 text-neutral-600" />
              </div>
              <div>
                <h3 className="text-xl font-semibold">{company?.name || 'Not set'}</h3>
                {company?.website && (
                  <a href={company.website} target="_blank" rel="noopener" className="text-blue-600 hover:underline flex items-center gap-1">
                    {company.website} <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Company Summary */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold">Company Summary</h2>
            <p className="text-sm text-neutral-500">Auto-generated from uploaded documents</p>
          </div>
        </div>
        
        {company?.summary ? (
          <pre className="whitespace-pre-wrap text-sm text-neutral-700 font-sans bg-neutral-50 p-4 rounded-lg max-h-96 overflow-auto">
            {company.summary}
          </pre>
        ) : (
          <div className="bg-neutral-50 p-6 rounded-lg text-center">
            <FileText className="w-10 h-10 text-neutral-300 mx-auto mb-2" />
            <p className="text-neutral-500">No summary yet</p>
            <p className="text-sm text-neutral-400 mt-1">Upload documents and click "Regenerate" in the Documents section</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ============ Documents View (Full File Manager) ============

function DocumentsView() {
  const [documents, setDocuments] = useState<kb.KBDocument[]>([]);
  const [folders, setFolders] = useState<kb.DocumentFolder[]>([]);
  const [company, setCompany] = useState<kb.CompanyProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  
  // Current folder navigation
  const [currentFolderId, setCurrentFolderId] = useState<number | null>(null);
  
  // Edit states
  const [editingDocId, setEditingDocId] = useState<number | null>(null);
  const [editingDocName, setEditingDocName] = useState('');
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [showMoveMenu, setShowMoveMenu] = useState<number | null>(null);
  const [previewDoc, setPreviewDoc] = useState<kb.KBDocument | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [docs, foldersData, companyData] = await Promise.all([
        kb.getDocuments(),
        kb.getFolders(),
        kb.getCompanyProfile()
      ]);
      setDocuments(docs);
      setFolders(foldersData);
      setCompany(companyData);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    setUploading(true);
    
    try {
      for (const file of Array.from(e.target.files)) {
        const doc = await kb.uploadDocument(file, undefined, undefined, currentFolderId || undefined);
        setDocuments(prev => [doc, ...prev]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this document?')) return;
    try {
      await kb.deleteDocument(id);
      setDocuments(prev => prev.filter(d => d.id !== id));
    } catch (e) {
      console.error(e);
    }
  };

  const handleRename = async (id: number) => {
    if (!editingDocName.trim()) return;
    try {
      const updated = await kb.updateDocument(id, { name: editingDocName });
      setDocuments(prev => prev.map(d => d.id === id ? updated : d));
      setEditingDocId(null);
      setEditingDocName('');
    } catch (e) {
      console.error(e);
    }
  };

  const handleMoveToFolder = async (docId: number, folderId: number | null | undefined) => {
    try {
      const updated = await kb.updateDocument(docId, { folder_id: folderId ?? undefined });
      setDocuments(prev => prev.map(d => d.id === docId ? updated : d));
      setShowMoveMenu(null);
    } catch (e) {
      console.error(e);
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    try {
      const folder = await kb.createFolder({ name: newFolderName, parent_id: currentFolderId || undefined });
      setFolders(prev => [...prev, folder]);
      setNewFolderName('');
      setShowNewFolder(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteFolder = async (id: number) => {
    if (!confirm('Delete this folder? Documents will be moved to root.')) return;
    try {
      await kb.deleteFolder(id);
      setFolders(prev => prev.filter(f => f.id !== id));
      // Refresh documents as they might have moved
      const docs = await kb.getDocuments();
      setDocuments(docs);
    } catch (e) {
      console.error(e);
    }
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const result = await kb.regenerateSummary();
      setCompany(prev => prev ? { ...prev, summary: result.summary } : null);
    } catch (e) {
      console.error(e);
    } finally {
      setRegenerating(false);
    }
  };

  // Get current folder's items
  const currentFolders = folders.filter(f => f.parent_id === currentFolderId);
  const currentDocuments = documents.filter(d => d.folder_id === currentFolderId);
  const currentFolder = currentFolderId ? folders.find(f => f.id === currentFolderId) : null;

  // Breadcrumb path
  const getBreadcrumb = () => {
    const path: { id: number | null; name: string }[] = [{ id: null, name: 'Documents' }];
    if (currentFolder) {
      path.push({ id: currentFolder.id, name: currentFolder.name });
    }
    return path;
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-5 h-5 animate-spin" /></div>;
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Company Summary Card */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold">Company Summary</h2>
            <p className="text-sm text-neutral-500">Auto-generated from uploaded documents</p>
          </div>
          <button 
            onClick={handleRegenerate} 
            disabled={regenerating || documents.filter(d => d.status === 'processed').length === 0}
            className="btn btn-secondary text-sm"
          >
            <RefreshCw className={cn("w-4 h-4", regenerating && "animate-spin")} />
            {regenerating ? 'Regenerating...' : 'Regenerate'}
          </button>
        </div>
        
        {company?.summary ? (
          <pre className="whitespace-pre-wrap text-sm text-neutral-700 font-sans bg-neutral-50 p-4 rounded-lg max-h-48 overflow-auto">
            {company.summary}
          </pre>
        ) : (
          <p className="text-sm text-neutral-400 bg-neutral-50 p-4 rounded-lg">
            Upload documents and click "Regenerate" to create a company summary
          </p>
        )}
      </div>

      {/* Documents Manager */}
      <div className="card">
        {/* Toolbar */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            {/* Breadcrumb */}
            {getBreadcrumb().map((item, i) => (
              <div key={item.id ?? 'root'} className="flex items-center gap-2">
                {i > 0 && <span className="text-neutral-300">/</span>}
                <button
                  onClick={() => setCurrentFolderId(item.id)}
                  className={cn(
                    "text-sm hover:text-neutral-900",
                    item.id === currentFolderId ? "font-medium text-neutral-900" : "text-neutral-500"
                  )}
                >
                  {item.name}
                </button>
              </div>
            ))}
          </div>
          
          <div className="flex items-center gap-2">
            <button onClick={() => setShowNewFolder(true)} className="btn btn-ghost text-sm">
              <FolderPlus className="w-4 h-4" />
              New Folder
            </button>
            <label className="btn btn-primary text-sm cursor-pointer">
              <Upload className="w-4 h-4" />
              {uploading ? 'Uploading...' : 'Upload'}
              <input type="file" multiple onChange={handleUpload} className="hidden" accept=".pdf,.docx,.txt,.md,.csv" />
            </label>
          </div>
        </div>

        {/* New Folder Input */}
        {showNewFolder && (
          <div className="flex items-center gap-2 p-4 bg-neutral-50 border-b">
            <Folder className="w-5 h-5 text-neutral-400" />
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="Folder name"
              className="input flex-1"
              autoFocus
              onKeyDown={(e) => e.key === 'Enter' && handleCreateFolder()}
            />
            <button onClick={handleCreateFolder} disabled={!newFolderName.trim()} className="btn btn-primary btn-sm">
              <Check className="w-4 h-4" />
            </button>
            <button onClick={() => { setShowNewFolder(false); setNewFolderName(''); }} className="btn btn-ghost btn-sm">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Content */}
        <div className="divide-y">
          {/* Folders */}
          {currentFolders.map(folder => (
            <div key={folder.id} className="flex items-center gap-3 p-4 hover:bg-neutral-50 group">
              <Folder className="w-5 h-5 text-amber-500" />
              <button
                onClick={() => setCurrentFolderId(folder.id)}
                className="flex-1 text-left font-medium text-sm hover:text-neutral-900"
              >
                {folder.name}
              </button>
              <button
                onClick={() => handleDeleteFolder(folder.id)}
                className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-neutral-200 rounded"
              >
                <Trash2 className="w-4 h-4 text-neutral-400" />
              </button>
            </div>
          ))}

          {/* Documents */}
          {currentDocuments.map(doc => (
            <div key={doc.id} className="flex items-center gap-3 p-4 hover:bg-neutral-50 group">
              <File className="w-5 h-5 text-neutral-400" />
              
              {editingDocId === doc.id ? (
                <div className="flex-1 flex items-center gap-2">
                  <input
                    type="text"
                    value={editingDocName}
                    onChange={(e) => setEditingDocName(e.target.value)}
                    className="input flex-1"
                    autoFocus
                    onKeyDown={(e) => e.key === 'Enter' && handleRename(doc.id)}
                  />
                  <button onClick={() => handleRename(doc.id)} className="btn btn-primary btn-sm">
                    <Check className="w-4 h-4" />
                  </button>
                  <button onClick={() => setEditingDocId(null)} className="btn btn-ghost btn-sm">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{doc.name}</p>
                    <p className="text-xs text-neutral-500">
                      {doc.status === 'processed' ? (
                        <span className="text-green-600">Processed</span>
                      ) : doc.status === 'processing' ? (
                        <span className="text-amber-600">Processing...</span>
                      ) : doc.status === 'failed' ? (
                        <span className="text-red-600">Failed</span>
                      ) : (
                        <span className="text-neutral-400">Pending</span>
                      )}
                      {doc.original_filename && doc.original_filename !== doc.name && (
                        <span className="ml-2 text-neutral-400">({doc.original_filename})</span>
                      )}
                    </p>
                  </div>
                  
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
                    {doc.content_md && (
                      <button
                        onClick={() => setPreviewDoc(doc)}
                        className="p-1.5 hover:bg-neutral-200 rounded"
                        title="Preview"
                      >
                        <Eye className="w-4 h-4 text-neutral-500" />
                      </button>
                    )}
                    <button
                      onClick={() => { setEditingDocId(doc.id); setEditingDocName(doc.name); }}
                      className="p-1.5 hover:bg-neutral-200 rounded"
                      title="Rename"
                    >
                      <Edit2 className="w-4 h-4 text-neutral-500" />
                    </button>
                    
                    {/* Move to folder dropdown */}
                    <div className="relative">
                      <button
                        onClick={() => setShowMoveMenu(showMoveMenu === doc.id ? null : doc.id)}
                        className="p-1.5 hover:bg-neutral-200 rounded"
                        title="Move"
                      >
                        <MoreVertical className="w-4 h-4 text-neutral-500" />
                      </button>
                      
                      {showMoveMenu === doc.id && (
                        <div className="absolute right-0 top-full mt-1 w-48 bg-white border rounded-lg shadow-lg z-10">
                          <div className="p-2 text-xs font-medium text-neutral-500 border-b">Move to folder</div>
                          <button
                            onClick={() => handleMoveToFolder(doc.id, null)}
                            className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2"
                          >
                            <FileText className="w-4 h-4" />
                            Root (Documents)
                          </button>
                          {folders.map(folder => (
                            <button
                              key={folder.id}
                              onClick={() => handleMoveToFolder(doc.id, folder.id)}
                              className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2"
                            >
                              <Folder className="w-4 h-4 text-amber-500" />
                              {folder.name}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    
                    <button
                      onClick={() => handleDelete(doc.id)}
                      className="p-1.5 hover:bg-neutral-200 rounded"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4 text-neutral-500" />
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}

          {/* Empty state */}
          {currentFolders.length === 0 && currentDocuments.length === 0 && (
            <div className="p-12 text-center">
              <FileText className="w-10 h-10 text-neutral-300 mx-auto mb-3" />
              <p className="text-neutral-500">No documents in this folder</p>
              <p className="text-sm text-neutral-400 mt-1">Upload files or create a folder</p>
            </div>
          )}
        </div>
      </div>

      {/* Document Preview Modal */}
      {previewDoc && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-6">
          <div className="bg-white rounded-xl max-w-3xl w-full max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-semibold">{previewDoc.name}</h3>
              <button onClick={() => setPreviewDoc(null)} className="p-1 hover:bg-neutral-100 rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4">
              <pre className="whitespace-pre-wrap text-sm font-mono bg-neutral-50 p-4 rounded-lg">
                {previewDoc.content_md}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ============ Products View ============

function ProductsView() {
  const [products, setProducts] = useState<kb.Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<kb.Product | null>(null);
  const [isNew, setIsNew] = useState(false);

  useEffect(() => {
    kb.getProducts().then(setProducts).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!editing) return;
    try {
      if (isNew) {
        const created = await kb.createProduct(editing);
        setProducts(prev => [...prev, created]);
      } else {
        const updated = await kb.updateProduct(editing.id, editing);
        setProducts(prev => prev.map(p => p.id === updated.id ? updated : p));
      }
      setEditing(null);
      setIsNew(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this product?')) return;
    try {
      await kb.deleteProduct(id);
      setProducts(prev => prev.filter(p => p.id !== id));
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-5 h-5 animate-spin" /></div>;
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Products & Services</h2>
        <button 
          onClick={() => { setEditing({ id: 0, name: '', is_active: true, sort_order: 0, created_at: '' }); setIsNew(true); }}
          className="btn btn-primary"
        >
          <Plus className="w-4 h-4" />
          Add Product
        </button>
      </div>

      {editing && (
        <div className="card p-6 mb-6">
          <h3 className="font-medium mb-4">{isNew ? 'New Product' : 'Edit Product'}</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium mb-1">Name *</label>
              <input
                type="text"
                value={editing.name}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                className="input w-full"
                placeholder="Product name"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Description</label>
              <textarea
                value={editing.description || ''}
                onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                className="input w-full"
                rows={3}
                placeholder="What does this product do?"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Features (one per line)</label>
              <textarea
                value={(editing.features || []).join('\n')}
                onChange={(e) => setEditing({ ...editing, features: e.target.value.split('\n').filter(Boolean) })}
                className="input w-full"
                rows={4}
                placeholder="Feature 1&#10;Feature 2&#10;Feature 3"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Email Snippet</label>
              <textarea
                value={editing.email_snippet || ''}
                onChange={(e) => setEditing({ ...editing, email_snippet: e.target.value })}
                className="input w-full"
                rows={2}
                placeholder="Short description for emails"
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => { setEditing(null); setIsNew(false); }} className="btn btn-ghost">Cancel</button>
              <button onClick={handleSave} disabled={!editing.name} className="btn btn-primary">
                <Save className="w-4 h-4" />
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {products.length === 0 ? (
          <p className="text-center text-neutral-400 py-12">No products yet</p>
        ) : (
          products.map(product => (
            <div key={product.id} className="card p-4 flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-neutral-100 flex items-center justify-center flex-shrink-0">
                <Package className="w-5 h-5 text-neutral-600" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-medium">{product.name}</h3>
                {product.description && <p className="text-sm text-neutral-500 mt-1">{product.description}</p>}
                {product.features && product.features.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {product.features.slice(0, 3).map((f, i) => (
                      <span key={i} className="px-2 py-0.5 bg-neutral-100 text-xs rounded">{f}</span>
                    ))}
                    {product.features.length > 3 && (
                      <span className="px-2 py-0.5 text-xs text-neutral-400">+{product.features.length - 3} more</span>
                    )}
                  </div>
                )}
              </div>
              <div className="flex gap-1">
                <button onClick={() => { setEditing(product); setIsNew(false); }} className="p-2 hover:bg-neutral-100 rounded">
                  <Edit2 className="w-4 h-4 text-neutral-500" />
                </button>
                <button onClick={() => handleDelete(product.id)} className="p-2 hover:bg-neutral-100 rounded">
                  <Trash2 className="w-4 h-4 text-neutral-500" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ============ Segments View (Table + Cards) ============

type SegmentViewMode = 'table' | 'cards';

function SegmentsView() {
  const [segments, setSegments] = useState<kb.Segment[]>([]);
  const [, setColumns] = useState<kb.SegmentColumn[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<SegmentViewMode>('table');
  const [expandedSegment, setExpandedSegment] = useState<number | null>(null);
  const [editingCell, setEditingCell] = useState<{ segmentId: number; field: string } | null>(null);
  const [editingValue, setEditingValue] = useState<string>('');
  const [showAddColumn, setShowAddColumn] = useState(false);
  const [newColumnName, setNewColumnName] = useState('');
  const [newColumnType, setNewColumnType] = useState('text');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Define display columns for table view
  // ICP columns - only fields with data
  const tableColumns = [
    { key: 'name', label: 'Name', width: '200px' },
    { key: 'segment_code', label: 'Code', width: '140px' },
    { key: 'priority', label: 'Priority', width: '90px' },
    { key: 'employee_count', label: 'Employees', width: '100px' },
    { key: 'revenue', label: 'Revenue', width: '120px' },
    { key: 'target_countries', label: 'Countries', width: '150px' },
    { key: 'license_types', label: 'License Types', width: '150px' },
    { key: 'examples', label: 'Examples', width: '200px' },
    { key: 'problems_we_solve', label: 'Pain Points', width: '400px' },
    { key: 'our_offer', label: 'Our Offer', width: '300px' },
    { key: 'paybis_products', label: 'Paybis Products', width: '180px' },
    { key: 'regulatory_deadline', label: 'Reg. Deadline', width: '150px' },
    { key: 'comment', label: 'Comment', width: '250px' },
  ];

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [segs, cols] = await Promise.all([kb.getSegments(), kb.getSegmentColumns()]);
      setSegments(segs);
      setColumns(cols);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleAddSegment = async () => {
    try {
      const seg = await kb.createSegment({ name: 'New Segment', data: { name: 'New Segment' } });
      setSegments(prev => [...prev, seg]);
      if (viewMode === 'cards') {
        setExpandedSegment(seg.id);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteSegment = async (id: number) => {
    if (!confirm('Delete this segment?')) return;
    try {
      await kb.deleteSegment(id);
      setSegments(prev => prev.filter(s => s.id !== id));
    } catch (e) {
      console.error(e);
    }
  };

  const handleCellEdit = (segmentId: number, field: string, currentValue: string | string[]) => {
    setEditingCell({ segmentId, field });
    setEditingValue(Array.isArray(currentValue) ? currentValue.join('\n') : (currentValue || ''));
  };

  const handleCellSave = async () => {
    if (!editingCell) return;
    const { segmentId, field } = editingCell;
    const segment = segments.find(s => s.id === segmentId);
    if (!segment) return;

    // Determine if field should be array
    const isArrayField = ['examples', 'license_types', 'target_countries', 'job_titles', 'paybis_products'].includes(field);
    const newValue = isArrayField ? editingValue.split('\n').filter(Boolean) : editingValue;

    try {
      const updatedData = { ...segment.data, [field]: newValue };
      const updatedName = field === 'name' ? editingValue : segment.name;
      
      const updated = await kb.updateSegment(segmentId, {
        name: updatedName,
        data: updatedData
      });
      setSegments(prev => prev.map(s => s.id === updated.id ? updated : s));
    } catch (e) {
      console.error(e);
    }
    setEditingCell(null);
    setEditingValue('');
  };

  const handleAddColumn = async () => {
    if (!newColumnName) return;
    try {
      const col = await kb.createSegmentColumn({
        name: newColumnName.toLowerCase().replace(/\s+/g, '_'),
        display_name: newColumnName,
        column_type: newColumnType as 'text' | 'number' | 'list' | 'rich_text' | 'case_select'
      });
      setColumns(prev => [...prev, col]);
      setNewColumnName('');
      setNewColumnType('text');
      setShowAddColumn(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleCSVImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    try {
      const result = await kb.importSegmentsCSV(e.target.files[0]);
      if (result.success) {
        loadData();
      }
      if (result.errors.length > 0) {
        alert(`Import completed with errors:\n${result.errors.join('\n')}`);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const getCellValue = (segment: kb.Segment, key: string): string => {
    const value = segment.data[key];
    if (Array.isArray(value)) return value.join(', ');
    if (value === undefined || value === null) return '';
    return String(value);
  };

  const getPriorityColor = (priority: string) => {
    switch (priority?.toUpperCase()) {
      case 'HIGH': return 'bg-red-100 text-red-700';
      case 'MEDIUM': return 'bg-amber-100 text-amber-700';
      case 'LOW': return 'bg-green-100 text-green-700';
      default: return 'bg-neutral-100 text-neutral-600';
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-5 h-5 animate-spin" /></div>;
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold">Segments</h2>
          {/* View Toggle */}
          <div className="flex bg-neutral-100 rounded-lg p-1">
            <button
              onClick={() => setViewMode('table')}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
                viewMode === 'table' ? "bg-white shadow-sm text-neutral-900" : "text-neutral-500 hover:text-neutral-700"
              )}
            >
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                Table
              </span>
            </button>
            <button
              onClick={() => setViewMode('cards')}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-md transition-colors",
                viewMode === 'cards' ? "bg-white shadow-sm text-neutral-900" : "text-neutral-500 hover:text-neutral-700"
              )}
            >
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                </svg>
                Cards
              </span>
            </button>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowAddColumn(true)} className="btn btn-ghost text-sm">
            <Plus className="w-4 h-4" />
            Add Column
          </button>
          <label className="btn btn-secondary text-sm cursor-pointer">
            <Upload className="w-4 h-4" />
            Import CSV
            <input ref={fileInputRef} type="file" accept=".csv" onChange={handleCSVImport} className="hidden" />
          </label>
          <button onClick={handleAddSegment} className="btn btn-primary">
            <Plus className="w-4 h-4" />
            Add Segment
          </button>
        </div>
      </div>

      {/* Add Column Modal */}
      {showAddColumn && (
        <div className="card p-4 mb-4 flex items-end gap-4 flex-shrink-0">
          <div className="flex-1">
            <label className="block text-xs font-medium mb-1">Column Name</label>
            <input
              type="text"
              value={newColumnName}
              onChange={(e) => setNewColumnName(e.target.value)}
              className="input w-full"
              placeholder="e.g. Budget Range"
            />
          </div>
          <div className="w-40">
            <label className="block text-xs font-medium mb-1">Type</label>
            <select
              value={newColumnType}
              onChange={(e) => setNewColumnType(e.target.value)}
              className="input w-full"
            >
              <option value="text">Text</option>
              <option value="rich_text">Rich Text</option>
              <option value="list">List</option>
              <option value="number">Number</option>
            </select>
          </div>
          <button onClick={() => setShowAddColumn(false)} className="btn btn-ghost">Cancel</button>
          <button onClick={handleAddColumn} disabled={!newColumnName} className="btn btn-primary">Add</button>
        </div>
      )}

      {/* Content */}
      {viewMode === 'table' ? (
        /* ===== TABLE VIEW ===== */
        <div className="flex-1 overflow-hidden card">
          <div className="h-full overflow-auto">
            <table className="w-max min-w-full border-collapse">
              <thead className="bg-neutral-50 sticky top-0 z-10">
                <tr>
                  <th className="text-left text-xs font-medium text-neutral-500 uppercase tracking-wider px-3 py-3 border-b border-r bg-neutral-50 sticky left-0 z-20" style={{ width: '200px', minWidth: '200px' }}>
                    Name
                  </th>
                  {tableColumns.slice(1).map(col => (
                    <th 
                      key={col.key} 
                      className="text-left text-xs font-medium text-neutral-500 uppercase tracking-wider px-3 py-3 border-b border-r whitespace-nowrap"
                      style={{ width: col.width, minWidth: col.width }}
                    >
                      {col.label}
                    </th>
                  ))}
                  <th className="w-12 border-b bg-neutral-50 sticky right-0 z-20"></th>
                </tr>
              </thead>
              <tbody>
                {segments.length === 0 ? (
                  <tr>
                    <td colSpan={tableColumns.length + 1} className="px-4 py-12 text-center text-neutral-400">
                      No segments yet. Add one or import from CSV.
                    </td>
                  </tr>
                ) : (
                  segments.map((seg, rowIdx) => (
                    <tr key={seg.id} className={cn("hover:bg-blue-50/50", rowIdx % 2 === 0 ? "bg-white" : "bg-neutral-50/50")}>
                      {/* Sticky Name Column */}
                      <td 
                        className={cn(
                          "px-3 py-2 border-b border-r font-medium sticky left-0 z-10",
                          rowIdx % 2 === 0 ? "bg-white" : "bg-neutral-50"
                        )}
                        style={{ width: '200px', minWidth: '200px' }}
                      >
                        {editingCell?.segmentId === seg.id && editingCell?.field === 'name' ? (
                          <input
                            type="text"
                            value={editingValue}
                            onChange={(e) => setEditingValue(e.target.value)}
                            onBlur={handleCellSave}
                            onKeyDown={(e) => e.key === 'Enter' && handleCellSave()}
                            className="w-full px-2 py-1 border rounded text-sm"
                            autoFocus
                          />
                        ) : (
                          <div 
                            className="cursor-pointer hover:bg-blue-100 px-2 py-1 rounded -mx-2 -my-1 text-sm"
                            onClick={() => handleCellEdit(seg.id, 'name', seg.name)}
                          >
                            {seg.name}
                          </div>
                        )}
                      </td>
                      {/* Other Columns */}
                      {tableColumns.slice(1).map(col => (
                        <td 
                          key={col.key} 
                          className="px-3 py-2 border-b border-r text-sm"
                          style={{ width: col.width, minWidth: col.width }}
                        >
                          {editingCell?.segmentId === seg.id && editingCell?.field === col.key ? (
                            <textarea
                              value={editingValue}
                              onChange={(e) => setEditingValue(e.target.value)}
                              onBlur={handleCellSave}
                              onKeyDown={(e) => e.key === 'Escape' && setEditingCell(null)}
                              className="w-full px-2 py-1 border rounded text-sm resize-none"
                              rows={3}
                              autoFocus
                            />
                          ) : (
                            <div 
                              className={cn(
                                "cursor-pointer hover:bg-blue-100 px-2 py-1 rounded -mx-2 -my-1 max-h-20 overflow-hidden text-ellipsis",
                                col.key === 'priority' && seg.data[col.key] && getPriorityColor(seg.data[col.key])
                              )}
                              onClick={() => handleCellEdit(seg.id, col.key, seg.data[col.key])}
                              title={getCellValue(seg, col.key)}
                            >
                              {col.key === 'priority' && seg.data[col.key] ? (
                                <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", getPriorityColor(seg.data[col.key]))}>
                                  {seg.data[col.key]}
                                </span>
                              ) : (
                                <span className="text-neutral-600 whitespace-pre-wrap line-clamp-3">
                                  {getCellValue(seg, col.key) || <span className="text-neutral-300">-</span>}
                                </span>
                              )}
                            </div>
                          )}
                        </td>
                      ))}
                      {/* Delete Button */}
                      <td className={cn(
                        "px-2 py-2 border-b sticky right-0 z-10",
                        rowIdx % 2 === 0 ? "bg-white" : "bg-neutral-50"
                      )}>
                        <button 
                          onClick={() => handleDeleteSegment(seg.id)} 
                          className="p-1.5 hover:bg-red-100 rounded text-neutral-400 hover:text-red-500"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* ===== CARDS VIEW ===== */
        <div className="flex-1 overflow-auto">
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {segments.length === 0 ? (
              <div className="col-span-full card p-12 text-center">
                <Target className="w-10 h-10 text-neutral-300 mx-auto mb-3" />
                <p className="text-neutral-500">No segments yet</p>
                <p className="text-sm text-neutral-400 mt-1">Add one or import from CSV</p>
              </div>
            ) : (
              segments.map(seg => (
                <div key={seg.id} className="card overflow-hidden">
                  {/* Card Header - Always Visible */}
                  <button
                    onClick={() => setExpandedSegment(expandedSegment === seg.id ? null : seg.id)}
                    className="w-full p-4 text-left hover:bg-neutral-50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          {seg.data.priority && (
                            <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", getPriorityColor(seg.data.priority))}>
                              {seg.data.priority}
                            </span>
                          )}
                        </div>
                        <h3 className="font-semibold text-neutral-900 truncate">{seg.name}</h3>
                        {seg.data.segment_code && (
                          <p className="text-xs text-neutral-400 font-mono mt-0.5">{seg.data.segment_code}</p>
                        )}
                      </div>
                      <ChevronLeft className={cn(
                        "w-5 h-5 text-neutral-400 transition-transform flex-shrink-0",
                        expandedSegment === seg.id ? "-rotate-90" : "rotate-180"
                      )} />
                    </div>
                    {/* Quick Info */}
                    <div className="flex flex-wrap gap-2 mt-3">
                      {seg.data.employee_count && (
                        <span className="text-xs px-2 py-1 bg-neutral-100 rounded">{seg.data.employee_count} employees</span>
                      )}
                      {seg.data.revenue && (
                        <span className="text-xs px-2 py-1 bg-neutral-100 rounded">{seg.data.revenue}</span>
                      )}
                    </div>
                  </button>

                  {/* Expanded Content */}
                  {expandedSegment === seg.id && (
                    <div className="border-t bg-neutral-50 max-h-[60vh] overflow-y-auto">
                      <div className="p-4 space-y-4">
                        {/* Quick Stats Row */}
                        <div className="grid grid-cols-3 gap-2 pb-3 border-b">
                          {seg.data.expected_deal_size && (
                            <div className="text-center p-2 bg-green-50 rounded">
                              <div className="text-xs text-green-600 font-medium">Deal Size</div>
                              <div className="text-sm font-semibold text-green-800">{seg.data.expected_deal_size}</div>
                            </div>
                          )}
                          {seg.data.sales_cycle && (
                            <div className="text-center p-2 bg-blue-50 rounded">
                              <div className="text-xs text-blue-600 font-medium">Sales Cycle</div>
                              <div className="text-sm font-semibold text-blue-800">{seg.data.sales_cycle}</div>
                            </div>
                          )}
                          {seg.data.vertical && (
                            <div className="text-center p-2 bg-neutral-100 rounded">
                              <div className="text-xs text-neutral-600 font-medium">Vertical</div>
                              <div className="text-sm font-semibold text-neutral-800">{seg.data.vertical}</div>
                            </div>
                          )}
                        </div>

                        {/* Description */}
                        {seg.data.description && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Description</h4>
                            <p className="text-sm text-neutral-700">{seg.data.description}</p>
                          </div>
                        )}

                        {/* Business Model */}
                        {seg.data.business_model && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Business Model</h4>
                            <p className="text-sm text-neutral-700">{seg.data.business_model}</p>
                          </div>
                        )}

                        {/* Examples */}
                        {seg.data.examples && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Company Examples</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.examples) ? seg.data.examples : [seg.data.examples]).map((ex: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded">{ex}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* License Types */}
                        {seg.data.license_types && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">License Types</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.license_types) ? seg.data.license_types : [seg.data.license_types]).map((lt: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-purple-100 text-purple-700 rounded">{lt}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Countries */}
                        {seg.data.target_countries && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Target Countries</h4>
                            <p className="text-sm text-neutral-700">
                              {Array.isArray(seg.data.target_countries) ? seg.data.target_countries.join(', ') : seg.data.target_countries}
                            </p>
                          </div>
                        )}

                        {/* Buying Triggers */}
                        {seg.data.buying_triggers && (
                          <div>
                            <h4 className="text-xs font-medium text-orange-600 uppercase mb-1">🎯 Buying Triggers</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.buying_triggers) ? seg.data.buying_triggers : [seg.data.buying_triggers]).map((bt: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-orange-100 text-orange-700 rounded">{bt}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Urgency Signals */}
                        {seg.data.urgency_signals && (
                          <div>
                            <h4 className="text-xs font-medium text-red-600 uppercase mb-1">🔥 Urgency Signals</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.urgency_signals) ? seg.data.urgency_signals : [seg.data.urgency_signals]).map((us: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-red-100 text-red-700 rounded">{us}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Pain Points */}
                        {seg.data.pain_points && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Pain Points</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.pain_points) ? seg.data.pain_points : [seg.data.pain_points]).map((pp: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-amber-100 text-amber-700 rounded">{pp}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Desired Outcomes */}
                        {seg.data.desired_outcomes && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Desired Outcomes</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.desired_outcomes) ? seg.data.desired_outcomes : [seg.data.desired_outcomes]).map((do_: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-emerald-100 text-emerald-700 rounded">{do_}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Decision Makers */}
                        {seg.data.decision_makers && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Decision Makers (DMs)</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.decision_makers) ? seg.data.decision_makers : [seg.data.decision_makers]).map((dm: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-indigo-100 text-indigo-700 rounded font-medium">{dm}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Our Offer */}
                        {seg.data.our_offer && (
                          <div>
                            <h4 className="text-xs font-medium text-green-600 uppercase mb-1">💼 Our Offer</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.our_offer) ? seg.data.our_offer : [seg.data.our_offer]).map((o: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded">{o}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Current Solutions */}
                        {seg.data.current_solutions && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Current Solutions (Competitors)</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.current_solutions) ? seg.data.current_solutions : [seg.data.current_solutions]).map((cs: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-neutral-200 rounded">{cs}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Differentiators */}
                        {seg.data.differentiators && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Differentiators</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.differentiators) ? seg.data.differentiators : [seg.data.differentiators]).map((d: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-cyan-100 text-cyan-700 rounded">{d}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Social Proof */}
                        {seg.data.social_proof && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Social Proof</h4>
                            <p className="text-sm text-neutral-700">{seg.data.social_proof}</p>
                          </div>
                        )}

                        {/* Cases */}
                        {seg.data.cases && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Cases</h4>
                            <p className="text-sm text-neutral-700 whitespace-pre-wrap">{seg.data.cases}</p>
                          </div>
                        )}

                        {/* Negative ICP Flags */}
                        {seg.data.negative_icp_flags && (
                          <div>
                            <h4 className="text-xs font-medium text-red-500 uppercase mb-1">⛔ Negative ICP Flags (Dont Target)</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.negative_icp_flags) ? seg.data.negative_icp_flags : [seg.data.negative_icp_flags]).map((nf: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-red-50 text-red-600 rounded">{nf}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Data Sources */}
                        {seg.data.data_sources && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Data Sources</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.data_sources) ? seg.data.data_sources : [seg.data.data_sources]).map((ds: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-violet-100 text-violet-700 rounded">{ds}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Paybis Products */}
                        {seg.data.paybis_products && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Paybis Products</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.paybis_products) ? seg.data.paybis_products : [seg.data.paybis_products]).map((p: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded">{p}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Regulatory Deadline */}
                        {seg.data.regulatory_deadline && (
                          <div>
                            <h4 className="text-xs font-medium text-red-600 uppercase mb-1">⏰ Regulatory Deadline</h4>
                            <p className="text-sm font-medium text-red-600">{seg.data.regulatory_deadline}</p>
                          </div>
                        )}

                        {/* Comment */}
                        {seg.data.comment && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Comment</h4>
                            <p className="text-sm text-neutral-600 italic bg-yellow-50 p-2 rounded">{seg.data.comment}</p>
                          </div>
                        )}

                        {/* Job Titles - legacy support */}
                        {seg.data.job_titles && !seg.data.decision_makers && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Job Titles</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.job_titles) ? seg.data.job_titles : [seg.data.job_titles]).map((jt: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-neutral-200 rounded">{jt}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Paybis Products */}
                        {seg.data.paybis_products && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Paybis Products</h4>
                            <div className="flex flex-wrap gap-1">
                              {(Array.isArray(seg.data.paybis_products) ? seg.data.paybis_products : [seg.data.paybis_products]).map((p: string, i: number) => (
                                <span key={i} className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded">{p}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Regulatory Deadline */}
                        {seg.data.regulatory_deadline && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Regulatory Deadline</h4>
                            <p className="text-sm font-medium text-red-600">{seg.data.regulatory_deadline}</p>
                          </div>
                        )}

                        {/* Comment */}
                        {seg.data.comment && (
                          <div>
                            <h4 className="text-xs font-medium text-neutral-500 uppercase mb-1">Comment</h4>
                            <p className="text-sm text-neutral-600 italic">{seg.data.comment}</p>
                          </div>
                        )}

                        {/* Delete Button */}
                        <div className="pt-2 border-t">
                          <button 
                            onClick={() => handleDeleteSegment(seg.id)}
                            className="text-sm text-red-500 hover:text-red-700 flex items-center gap-1"
                          >
                            <Trash2 className="w-4 h-4" />
                            Delete Segment
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ============ Competitors View ============

function CompetitorsView() {
  const [competitors, setCompetitors] = useState<kb.Competitor[]>([]);
  const [loading, setLoading] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    kb.getCompetitors().then(setCompetitors).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleCSVImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    try {
      const result = await kb.importCompetitorsCSV(e.target.files[0]);
      if (result.success) {
        const updated = await kb.getCompetitors();
        setCompetitors(updated);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this competitor?')) return;
    try {
      await kb.deleteCompetitor(id);
      setCompetitors(prev => prev.filter(c => c.id !== id));
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-5 h-5 animate-spin" /></div>;
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Competitors</h2>
        <label className="btn btn-primary cursor-pointer">
          <Upload className="w-4 h-4" />
          Import CSV
          <input ref={fileInputRef} type="file" accept=".csv" onChange={handleCSVImport} className="hidden" />
        </label>
      </div>

      <div className="space-y-3">
        {competitors.length === 0 ? (
          <div className="card p-12 text-center">
            <Swords className="w-10 h-10 text-neutral-300 mx-auto mb-3" />
            <p className="text-neutral-500">No competitors yet</p>
            <p className="text-sm text-neutral-400 mt-1">Import from CSV to add competitors</p>
          </div>
        ) : (
          competitors.map(comp => (
            <div key={comp.id} className="card p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-medium">{comp.name}</h3>
                  {comp.website && <a href={comp.website} target="_blank" className="text-sm text-blue-600 hover:underline">{comp.website}</a>}
                  {comp.description && <p className="text-sm text-neutral-500 mt-2">{comp.description}</p>}
                </div>
                <button onClick={() => handleDelete(comp.id)} className="p-2 hover:bg-neutral-100 rounded">
                  <Trash2 className="w-4 h-4 text-neutral-400" />
                </button>
              </div>
              {(comp.their_strengths?.length || comp.our_advantages?.length) && (
                <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t">
                  {comp.their_strengths && comp.their_strengths.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-neutral-500 mb-1">Their Strengths</p>
                      <ul className="text-sm space-y-1">
                        {comp.their_strengths.slice(0, 3).map((s, i) => <li key={i}>• {s}</li>)}
                      </ul>
                    </div>
                  )}
                  {comp.our_advantages && comp.our_advantages.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-neutral-500 mb-1">Our Advantages</p>
                      <ul className="text-sm space-y-1">
                        {comp.our_advantages.slice(0, 3).map((s, i) => <li key={i}>• {s}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ============ Case Studies View ============

function CaseStudiesView() {
  const [cases, setCases] = useState<kb.CaseStudy[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<kb.CaseStudy | null>(null);
  const [isNew, setIsNew] = useState(false);

  useEffect(() => {
    kb.getCaseStudies().then(setCases).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!editing) return;
    try {
      if (isNew) {
        const created = await kb.createCaseStudy(editing);
        setCases(prev => [...prev, created]);
      } else {
        const updated = await kb.updateCaseStudy(editing.id, editing);
        setCases(prev => prev.map(c => c.id === updated.id ? updated : c));
      }
      setEditing(null);
      setIsNew(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this case study?')) return;
    try {
      await kb.deleteCaseStudy(id);
      setCases(prev => prev.filter(c => c.id !== id));
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-5 h-5 animate-spin" /></div>;
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Case Studies</h2>
        <button 
          onClick={() => { setEditing({ id: 0, client_name: '', is_public: true, created_at: '' }); setIsNew(true); }}
          className="btn btn-primary"
        >
          <Plus className="w-4 h-4" />
          Add Case Study
        </button>
      </div>

      {editing && (
        <div className="card p-6 mb-6 space-y-4">
          <input
            type="text"
            value={editing.client_name}
            onChange={(e) => setEditing({ ...editing, client_name: e.target.value })}
            className="input w-full text-lg font-medium"
            placeholder="Client Name"
          />
          <div className="grid grid-cols-2 gap-4">
            <input type="text" value={editing.client_industry || ''} onChange={(e) => setEditing({ ...editing, client_industry: e.target.value })} className="input" placeholder="Industry" />
            <input type="text" value={editing.client_size || ''} onChange={(e) => setEditing({ ...editing, client_size: e.target.value })} className="input" placeholder="Company Size" />
          </div>
          <textarea value={editing.challenge || ''} onChange={(e) => setEditing({ ...editing, challenge: e.target.value })} className="input w-full" rows={2} placeholder="Challenge" />
          <textarea value={editing.solution || ''} onChange={(e) => setEditing({ ...editing, solution: e.target.value })} className="input w-full" rows={2} placeholder="Solution" />
          <textarea value={editing.results || ''} onChange={(e) => setEditing({ ...editing, results: e.target.value })} className="input w-full" rows={2} placeholder="Results" />
          <textarea value={editing.testimonial || ''} onChange={(e) => setEditing({ ...editing, testimonial: e.target.value })} className="input w-full" rows={2} placeholder="Testimonial quote" />
          <div className="flex gap-2 justify-end">
            <button onClick={() => { setEditing(null); setIsNew(false); }} className="btn btn-ghost">Cancel</button>
            <button onClick={handleSave} disabled={!editing.client_name} className="btn btn-primary">Save</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        {cases.length === 0 ? (
          <div className="col-span-2 card p-12 text-center">
            <Trophy className="w-10 h-10 text-neutral-300 mx-auto mb-3" />
            <p className="text-neutral-500">No case studies yet</p>
          </div>
        ) : (
          cases.map(c => (
            <div key={c.id} className="card p-4">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h3 className="font-medium">{c.client_name}</h3>
                  {c.client_industry && <span className="text-xs text-neutral-500">{c.client_industry}</span>}
                </div>
                <div className="flex gap-1">
                  <button onClick={() => { setEditing(c); setIsNew(false); }} className="p-1 hover:bg-neutral-100 rounded">
                    <Edit2 className="w-4 h-4 text-neutral-400" />
                  </button>
                  <button onClick={() => handleDelete(c.id)} className="p-1 hover:bg-neutral-100 rounded">
                    <Trash2 className="w-4 h-4 text-neutral-400" />
                  </button>
                </div>
              </div>
              {c.results && <p className="text-sm text-neutral-600">{c.results.slice(0, 150)}{c.results.length > 150 ? '...' : ''}</p>}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ============ Voice Tones View ============

function VoiceTonesView() {
  const [tones, setTones] = useState<kb.VoiceTone[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<kb.VoiceTone | null>(null);
  const [isNew, setIsNew] = useState(false);

  useEffect(() => {
    kb.getVoiceTones().then(setTones).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!editing) return;
    try {
      if (isNew) {
        const created = await kb.createVoiceTone(editing);
        setTones(prev => [...prev, created]);
      } else {
        const updated = await kb.updateVoiceTone(editing.id, editing);
        setTones(prev => prev.map(t => t.id === updated.id ? updated : t));
      }
      setEditing(null);
      setIsNew(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this voice tone?')) return;
    try {
      await kb.deleteVoiceTone(id);
      setTones(prev => prev.filter(t => t.id !== id));
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-5 h-5 animate-spin" /></div>;
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Voice & Tone</h2>
        <button 
          onClick={() => { setEditing({ id: 0, name: '', formality_level: 5, emoji_usage: false, is_default: false, created_at: '' }); setIsNew(true); }}
          className="btn btn-primary"
        >
          <Plus className="w-4 h-4" />
          Add Voice Tone
        </button>
      </div>

      {editing && (
        <div className="card p-6 mb-6 space-y-4">
          <input
            type="text"
            value={editing.name}
            onChange={(e) => setEditing({ ...editing, name: e.target.value })}
            className="input w-full"
            placeholder="Name (e.g. Professional, Friendly)"
          />
          <textarea
            value={editing.description || ''}
            onChange={(e) => setEditing({ ...editing, description: e.target.value })}
            className="input w-full"
            rows={2}
            placeholder="Description"
          />
          <textarea
            value={editing.writing_style || ''}
            onChange={(e) => setEditing({ ...editing, writing_style: e.target.value })}
            className="input w-full"
            rows={2}
            placeholder="Writing style guidelines"
          />
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium mb-1">Do Use (one per line)</label>
              <textarea
                value={(editing.do_use || []).join('\n')}
                onChange={(e) => setEditing({ ...editing, do_use: e.target.value.split('\n').filter(Boolean) })}
                className="input w-full"
                rows={3}
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Don't Use (one per line)</label>
              <textarea
                value={(editing.dont_use || []).join('\n')}
                onChange={(e) => setEditing({ ...editing, dont_use: e.target.value.split('\n').filter(Boolean) })}
                className="input w-full"
                rows={3}
              />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2">
              <span className="text-sm">Formality: {editing.formality_level}/10</span>
              <input
                type="range"
                min={1}
                max={10}
                value={editing.formality_level}
                onChange={(e) => setEditing({ ...editing, formality_level: Number(e.target.value) })}
                className="w-32"
              />
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={editing.emoji_usage}
                onChange={(e) => setEditing({ ...editing, emoji_usage: e.target.checked })}
              />
              <span className="text-sm">Use emojis</span>
            </label>
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={() => { setEditing(null); setIsNew(false); }} className="btn btn-ghost">Cancel</button>
            <button onClick={handleSave} disabled={!editing.name} className="btn btn-primary">Save</button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {tones.length === 0 ? (
          <div className="card p-12 text-center">
            <Mic2 className="w-10 h-10 text-neutral-300 mx-auto mb-3" />
            <p className="text-neutral-500">No voice tones yet</p>
          </div>
        ) : (
          tones.map(tone => (
            <div key={tone.id} className="card p-4 flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-neutral-100 flex items-center justify-center flex-shrink-0">
                <Mic2 className="w-5 h-5 text-neutral-600" />
              </div>
              <div className="flex-1">
                <h3 className="font-medium">{tone.name}</h3>
                {tone.description && <p className="text-sm text-neutral-500 mt-1">{tone.description}</p>}
                <div className="flex gap-2 mt-2 text-xs text-neutral-400">
                  <span>Formality: {tone.formality_level}/10</span>
                  {tone.emoji_usage && <span>• Emojis</span>}
                </div>
              </div>
              <div className="flex gap-1">
                <button onClick={() => { setEditing(tone); setIsNew(false); }} className="p-2 hover:bg-neutral-100 rounded">
                  <Edit2 className="w-4 h-4 text-neutral-500" />
                </button>
                <button onClick={() => handleDelete(tone.id)} className="p-2 hover:bg-neutral-100 rounded">
                  <Trash2 className="w-4 h-4 text-neutral-500" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ============ Booking Links View ============

function BookingLinksView() {
  const [links, setLinks] = useState<kb.BookingLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<kb.BookingLink | null>(null);
  const [isNew, setIsNew] = useState(false);

  useEffect(() => {
    kb.getBookingLinks().then(setLinks).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!editing) return;
    try {
      if (isNew) {
        const created = await kb.createBookingLink(editing);
        setLinks(prev => [...prev, created]);
      } else {
        const updated = await kb.updateBookingLink(editing.id, editing);
        setLinks(prev => prev.map(l => l.id === updated.id ? updated : l));
      }
      setEditing(null);
      setIsNew(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this booking link?')) return;
    try {
      await kb.deleteBookingLink(id);
      setLinks(prev => prev.filter(l => l.id !== id));
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-5 h-5 animate-spin" /></div>;
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Booking Links</h2>
        <button 
          onClick={() => { setEditing({ id: 0, name: '', url: '', is_active: true, created_at: '' }); setIsNew(true); }}
          className="btn btn-primary"
        >
          <Plus className="w-4 h-4" />
          Add Link
        </button>
      </div>

      {editing && (
        <div className="card p-6 mb-6 space-y-4">
          <input
            type="text"
            value={editing.name}
            onChange={(e) => setEditing({ ...editing, name: e.target.value })}
            className="input w-full"
            placeholder="Name (e.g. Demo Call - John)"
          />
          <input
            type="url"
            value={editing.url}
            onChange={(e) => setEditing({ ...editing, url: e.target.value })}
            className="input w-full"
            placeholder="https://calendly.com/..."
          />
          <textarea
            value={editing.when_to_use || ''}
            onChange={(e) => setEditing({ ...editing, when_to_use: e.target.value })}
            className="input w-full"
            rows={2}
            placeholder="When to use this link (e.g. for enterprise leads, when booking for John)"
          />
          <div className="flex gap-2 justify-end">
            <button onClick={() => { setEditing(null); setIsNew(false); }} className="btn btn-ghost">Cancel</button>
            <button onClick={handleSave} disabled={!editing.name || !editing.url} className="btn btn-primary">Save</button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {links.length === 0 ? (
          <div className="card p-12 text-center">
            <Calendar className="w-10 h-10 text-neutral-300 mx-auto mb-3" />
            <p className="text-neutral-500">No booking links yet</p>
          </div>
        ) : (
          links.map(link => (
            <div key={link.id} className="card p-4 flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-neutral-100 flex items-center justify-center flex-shrink-0">
                <Link2 className="w-5 h-5 text-neutral-600" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-medium">{link.name}</h3>
                <a href={link.url} target="_blank" className="text-sm text-blue-600 hover:underline truncate block">{link.url}</a>
                {link.when_to_use && <p className="text-xs text-neutral-500 mt-1">{link.when_to_use}</p>}
              </div>
              <div className="flex gap-1">
                <button onClick={() => { setEditing(link); setIsNew(false); }} className="p-2 hover:bg-neutral-100 rounded">
                  <Edit2 className="w-4 h-4 text-neutral-500" />
                </button>
                <button onClick={() => handleDelete(link.id)} className="p-2 hover:bg-neutral-100 rounded">
                  <Trash2 className="w-4 h-4 text-neutral-500" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ============ Blocklist View ============

function BlocklistView() {
  const [entries, setEntries] = useState<kb.BlocklistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [newEntry, setNewEntry] = useState({ domain: '', email: '', reason: '' });
  const [showAdd, setShowAdd] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    kb.getBlocklist().then(setEntries).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleAdd = async () => {
    if (!newEntry.domain && !newEntry.email) return;
    try {
      const created = await kb.addToBlocklist(newEntry);
      setEntries(prev => [...prev, created]);
      setNewEntry({ domain: '', email: '', reason: '' });
      setShowAdd(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await kb.removeFromBlocklist(id);
      setEntries(prev => prev.filter(e => e.id !== id));
    } catch (e) {
      console.error(e);
    }
  };

  const handleCSVImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    try {
      const result = await kb.importBlocklistCSV(e.target.files[0]);
      if (result.success) {
        const updated = await kb.getBlocklist();
        setEntries(updated);
      }
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-5 h-5 animate-spin" /></div>;
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Blocklist</h2>
        <div className="flex gap-2">
          <label className="btn btn-secondary cursor-pointer">
            <Upload className="w-4 h-4" />
            Import CSV
            <input ref={fileInputRef} type="file" accept=".csv" onChange={handleCSVImport} className="hidden" />
          </label>
          <button onClick={() => setShowAdd(true)} className="btn btn-primary">
            <Plus className="w-4 h-4" />
            Add Entry
          </button>
        </div>
      </div>

      {showAdd && (
        <div className="card p-4 mb-4 space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <input
              type="text"
              value={newEntry.domain}
              onChange={(e) => setNewEntry({ ...newEntry, domain: e.target.value })}
              className="input"
              placeholder="Domain (e.g. example.com)"
            />
            <input
              type="email"
              value={newEntry.email}
              onChange={(e) => setNewEntry({ ...newEntry, email: e.target.value })}
              className="input"
              placeholder="Email"
            />
          </div>
          <input
            type="text"
            value={newEntry.reason}
            onChange={(e) => setNewEntry({ ...newEntry, reason: e.target.value })}
            className="input w-full"
            placeholder="Reason (optional)"
          />
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowAdd(false)} className="btn btn-ghost">Cancel</button>
            <button onClick={handleAdd} disabled={!newEntry.domain && !newEntry.email} className="btn btn-primary">Add</button>
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full">
          <thead className="bg-neutral-50 border-b">
            <tr>
              <th className="text-left text-xs font-medium text-neutral-500 uppercase px-4 py-3">Domain</th>
              <th className="text-left text-xs font-medium text-neutral-500 uppercase px-4 py-3">Email</th>
              <th className="text-left text-xs font-medium text-neutral-500 uppercase px-4 py-3">Reason</th>
              <th className="w-16"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {entries.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-12 text-center text-neutral-400">Blocklist is empty</td>
              </tr>
            ) : (
              entries.map(entry => (
                <tr key={entry.id} className="hover:bg-neutral-50">
                  <td className="px-4 py-3 text-sm">{entry.domain || '-'}</td>
                  <td className="px-4 py-3 text-sm">{entry.email || '-'}</td>
                  <td className="px-4 py-3 text-sm text-neutral-500">{entry.reason || '-'}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => handleDelete(entry.id)} className="p-1 hover:bg-neutral-200 rounded">
                      <Trash2 className="w-4 h-4 text-neutral-400" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
