/**
 * Document List Component
 * Displays uploaded documents with status, metadata, and actions
 */

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  FileText,
  Trash2,
  Loader2,
  RefreshCw,
  FileIcon,
  Clock,
  Layers,
  ChevronLeft,
  ChevronRight,
  Info
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/services/apiClient';
import { DocumentDetail } from './DocumentDetail';

interface Document {
  document_id: string;
  metadata: {
    filename: string;
    file_type: string;
    file_size: number;
    page_count?: number;
    created_at: string;
    tags?: string[];
  };
  chunk_count: number;
  is_indexed: boolean;
}

interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
}

interface DocumentListProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DocumentList({ open, onOpenChange }: DocumentListProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 10;

  useEffect(() => {
    if (open) {
      fetchDocuments();
    }
  }, [open, page]);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const data = await api.get<DocumentListResponse>(
        `/api/v1/documents/?page=${page}&page_size=${pageSize}`
      );
      setDocuments(data.documents);
      setTotal(data.total);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('Delete this document? This will also remove it from the knowledge base.')) {
      return;
    }

    try {
      setDeletingId(docId);
      await api.delete(`/api/v1/documents/${docId}`);
      setDocuments(prev => prev.filter(d => d.document_id !== docId));
      setTotal(prev => prev - 1);
    } catch (error) {
      console.error('Failed to delete document:', error);
    } finally {
      setDeletingId(null);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const getFileIcon = (fileType: string) => {
    if (fileType === '.pdf') {
      return <FileText className="h-5 w-5 text-red-500" />;
    }
    return <FileIcon className="h-5 w-5 text-blue-500" />;
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between">
              <span>Document Library</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={fetchDocuments}
                disabled={loading}
              >
                <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              </Button>
            </DialogTitle>
          </DialogHeader>

          <ScrollArea className="flex-1 -mx-6 px-6">
            {loading && documents.length === 0 ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
              </div>
            ) : documents.length === 0 ? (
              <div className="text-center py-12">
                <FileText className="h-12 w-12 text-slate-300 dark:text-slate-600 mx-auto mb-4" />
                <p className="text-slate-600 dark:text-slate-400">
                  No documents uploaded yet
                </p>
                <p className="text-sm text-slate-500 dark:text-slate-500 mt-1">
                  Upload documents to enhance MediBot's knowledge
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {documents.map((doc) => (
                  <div
                    key={doc.document_id}
                    className="flex items-start gap-3 p-3 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                  >
                    {getFileIcon(doc.metadata.file_type)}

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-slate-800 dark:text-slate-100 truncate">
                          {doc.metadata.filename}
                        </span>
                        <Badge
                          variant={doc.is_indexed ? "default" : "secondary"}
                          className="text-xs"
                        >
                          {doc.is_indexed ? "Indexed" : "Processing"}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-3 mt-1 text-xs text-slate-500 dark:text-slate-400">
                        <span>{formatFileSize(doc.metadata.file_size)}</span>
                        <span className="flex items-center gap-1">
                          <Layers className="h-3 w-3" />
                          {doc.chunk_count} chunks
                        </span>
                        {doc.metadata.page_count && (
                          <span>{doc.metadata.page_count} pages</span>
                        )}
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDate(doc.metadata.created_at)}
                        </span>
                      </div>

                      {doc.metadata.tags && doc.metadata.tags.length > 0 && (
                        <div className="flex gap-1 mt-2">
                          {doc.metadata.tags.map((tag, idx) => (
                            <Badge key={idx} variant="outline" className="text-xs">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setSelectedDoc(doc)}
                        className="h-8 w-8"
                        title="View details"
                      >
                        <Info className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(doc.document_id)}
                        disabled={deletingId === doc.document_id}
                        className="h-8 w-8 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
                        title="Delete document"
                      >
                        {deletingId === doc.document_id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t border-slate-200 dark:border-slate-700">
              <span className="text-sm text-slate-600 dark:text-slate-400">
                Showing {((page - 1) * pageSize) + 1}-{Math.min(page * pageSize, total)} of {total}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm text-slate-600 dark:text-slate-400">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Document Detail Modal */}
      <DocumentDetail
        document={selectedDoc}
        onClose={() => setSelectedDoc(null)}
      />
    </>
  );
}
