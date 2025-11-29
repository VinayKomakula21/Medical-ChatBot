/**
 * Document Detail Modal
 * Shows detailed metadata for a document
 */

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  FileText,
  Calendar,
  HardDrive,
  Layers,
  Tag,
  CheckCircle,
  AlertCircle
} from 'lucide-react';

interface DocumentMetadata {
  filename: string;
  file_type: string;
  file_size: number;
  page_count?: number;
  created_at: string;
  tags?: string[];
}

interface Document {
  document_id: string;
  metadata: DocumentMetadata;
  chunk_count: number;
  is_indexed: boolean;
}

interface DocumentDetailProps {
  document: Document | null;
  onClose: () => void;
}

export function DocumentDetail({ document, onClose }: DocumentDetailProps) {
  if (!document) return null;

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} bytes`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getFileTypeLabel = (type: string) => {
    switch (type) {
      case '.pdf': return 'PDF Document';
      case '.txt': return 'Text File';
      case '.md': return 'Markdown File';
      case '.docx': return 'Word Document';
      default: return type.toUpperCase().slice(1) + ' File';
    }
  };

  return (
    <Dialog open={!!document} onOpenChange={() => onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-purple-600" />
            Document Details
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Filename */}
          <div>
            <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100 break-all">
              {document.metadata.filename}
            </h3>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={document.is_indexed ? "default" : "secondary"}>
                {document.is_indexed ? (
                  <><CheckCircle className="h-3 w-3 mr-1" /> Indexed</>
                ) : (
                  <><AlertCircle className="h-3 w-3 mr-1" /> Processing</>
                )}
              </Badge>
              <Badge variant="outline">
                {getFileTypeLabel(document.metadata.file_type)}
              </Badge>
            </div>
          </div>

          <Separator />

          {/* Details Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="flex items-start gap-2">
              <HardDrive className="h-4 w-4 text-slate-400 mt-0.5" />
              <div>
                <div className="text-xs text-slate-500 dark:text-slate-400">File Size</div>
                <div className="text-sm font-medium text-slate-800 dark:text-slate-100">
                  {formatFileSize(document.metadata.file_size)}
                </div>
              </div>
            </div>

            <div className="flex items-start gap-2">
              <Layers className="h-4 w-4 text-slate-400 mt-0.5" />
              <div>
                <div className="text-xs text-slate-500 dark:text-slate-400">Chunks</div>
                <div className="text-sm font-medium text-slate-800 dark:text-slate-100">
                  {document.chunk_count} chunks
                </div>
              </div>
            </div>

            {document.metadata.page_count && (
              <div className="flex items-start gap-2">
                <FileText className="h-4 w-4 text-slate-400 mt-0.5" />
                <div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">Pages</div>
                  <div className="text-sm font-medium text-slate-800 dark:text-slate-100">
                    {document.metadata.page_count} pages
                  </div>
                </div>
              </div>
            )}

            <div className="flex items-start gap-2">
              <Calendar className="h-4 w-4 text-slate-400 mt-0.5" />
              <div>
                <div className="text-xs text-slate-500 dark:text-slate-400">Uploaded</div>
                <div className="text-sm font-medium text-slate-800 dark:text-slate-100">
                  {formatDate(document.metadata.created_at)}
                </div>
              </div>
            </div>
          </div>

          {/* Tags */}
          {document.metadata.tags && document.metadata.tags.length > 0 && (
            <>
              <Separator />
              <div>
                <div className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400 mb-2">
                  <Tag className="h-3 w-3" />
                  Tags
                </div>
                <div className="flex flex-wrap gap-1">
                  {document.metadata.tags.map((tag, idx) => (
                    <Badge key={idx} variant="outline" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Document ID */}
          <Separator />
          <div>
            <div className="text-xs text-slate-500 dark:text-slate-400 mb-1">Document ID</div>
            <code className="text-xs text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded block break-all">
              {document.document_id}
            </code>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
