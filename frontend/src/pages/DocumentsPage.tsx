/**
 * Documents Page
 * Full page view of all uploaded documents with upload capability
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
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
  Info,
  Upload,
  ArrowLeft,
  X,
  CheckCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/services/apiClient';
import { apiService } from '@/services/api';
import { toast } from 'sonner';
import { DocumentDetail } from '@/components/documents/DocumentDetail';

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

export function DocumentsPage() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 10;

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  useEffect(() => {
    fetchDocuments();
  }, [page]);

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

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];

      const validTypes = ['application/pdf', 'text/plain',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];

      if (!validTypes.includes(file.type)) {
        toast.error('Please upload a PDF, TXT, or DOCX file.');
        return;
      }

      if (file.size > 10 * 1024 * 1024) {
        toast.error('File size must be less than 10MB.');
        return;
      }

      setSelectedFile(file);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx']
    },
    maxFiles: 1,
    disabled: uploading
  });

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setUploadProgress(0);

    try {
      const response = await apiService.uploadDocument(
        selectedFile,
        (progressValue) => setUploadProgress(progressValue)
      );

      toast.success(`Document "${response.filename}" uploaded successfully! ${response.chunks_created} chunks created.`);
      setSelectedFile(null);
      setUploadProgress(0);
      fetchDocuments();
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Failed to upload document. Please try again.');
    } finally {
      setUploading(false);
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
      toast.success('Document deleted successfully');
    } catch (error) {
      console.error('Failed to delete document:', error);
      toast.error('Failed to delete document');
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
    <div className="min-h-screen bg-white dark:bg-slate-950">
      {/* Header */}
      <div className="border-b border-gray-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => navigate('/')}
                className="text-gray-600 dark:text-slate-400"
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <div>
                <h1 className="text-xl font-semibold text-gray-900 dark:text-slate-100">
                  Document Library
                </h1>
                <p className="text-sm text-gray-500 dark:text-slate-400">
                  Manage your uploaded medical documents
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchDocuments}
              disabled={loading}
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
        {/* Upload Section */}
        <div className="mb-8">
          <h2 className="text-sm font-medium text-gray-700 dark:text-slate-300 mb-3">
            Upload New Document
          </h2>

          {!selectedFile ? (
            <div
              {...getRootProps()}
              className={cn(
                "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all",
                isDragActive
                  ? "border-[#7C3AED] bg-violet-50 dark:bg-violet-950/30"
                  : "border-gray-200 dark:border-slate-700 hover:border-[#7C3AED] hover:bg-gray-50 dark:hover:bg-slate-800/50"
              )}
            >
              <input {...getInputProps()} />
              <Upload className="h-10 w-10 mx-auto mb-3 text-gray-400 dark:text-slate-500" />
              <p className="text-sm text-gray-600 dark:text-slate-400">
                {isDragActive
                  ? 'Drop the file here...'
                  : 'Drag and drop a file here, or click to browse'}
              </p>
              <p className="text-xs text-gray-400 dark:text-slate-500 mt-2">
                PDF, TXT, or DOCX files up to 10MB
              </p>
            </div>
          ) : (
            <div className="border border-gray-200 dark:border-slate-700 rounded-xl p-4">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <FileText className="h-8 w-8 text-[#7C3AED]" />
                  <div>
                    <p className="font-medium text-gray-900 dark:text-slate-100">{selectedFile.name}</p>
                    <p className="text-sm text-gray-500 dark:text-slate-400">
                      {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </div>
                {!uploading && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setSelectedFile(null)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>

              {uploading && (
                <div className="space-y-2 mb-4">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600 dark:text-slate-400">Uploading...</span>
                    <span className="text-gray-900 dark:text-slate-100">{Math.round(uploadProgress)}%</span>
                  </div>
                  <Progress value={uploadProgress} className="w-full" />
                </div>
              )}

              {uploadProgress === 100 && !uploading && (
                <div className="flex items-center justify-center text-green-600 dark:text-green-400 mb-4">
                  <CheckCircle className="h-5 w-5 mr-2" />
                  <span>Upload complete!</span>
                </div>
              )}

              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => setSelectedFile(null)}
                  disabled={uploading}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="bg-[#7C3AED] hover:bg-[#6D28D9]"
                >
                  {uploading ? 'Uploading...' : 'Upload'}
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Documents List */}
        <div>
          <h2 className="text-sm font-medium text-gray-700 dark:text-slate-300 mb-3">
            Your Documents ({total})
          </h2>

          {loading && documents.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
            </div>
          ) : documents.length === 0 ? (
            <div className="text-center py-12 border border-dashed border-gray-200 dark:border-slate-700 rounded-xl">
              <FileText className="h-12 w-12 text-gray-300 dark:text-slate-600 mx-auto mb-4" />
              <p className="text-gray-600 dark:text-slate-400">
                No documents uploaded yet
              </p>
              <p className="text-sm text-gray-500 dark:text-slate-500 mt-1">
                Upload documents to enhance MediBot's knowledge
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {documents.map((doc) => (
                <div
                  key={doc.document_id}
                  className="flex items-start gap-4 p-4 rounded-xl border border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-800/50 transition-colors"
                >
                  <div className="p-2 rounded-lg bg-gray-100 dark:bg-slate-800">
                    {getFileIcon(doc.metadata.file_type)}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 dark:text-slate-100 truncate">
                        {doc.metadata.filename}
                      </span>
                      <Badge
                        variant={doc.is_indexed ? "default" : "secondary"}
                        className={cn(
                          "text-xs",
                          doc.is_indexed && "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                        )}
                      >
                        {doc.is_indexed ? "Indexed" : "Processing"}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-4 mt-2 text-sm text-gray-500 dark:text-slate-400">
                      <span>{formatFileSize(doc.metadata.file_size)}</span>
                      <span className="flex items-center gap-1">
                        <Layers className="h-3.5 w-3.5" />
                        {doc.chunk_count} chunks
                      </span>
                      {doc.metadata.page_count && (
                        <span>{doc.metadata.page_count} pages</span>
                      )}
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        {formatDate(doc.metadata.created_at)}
                      </span>
                    </div>

                    {doc.metadata.tags && doc.metadata.tags.length > 0 && (
                      <div className="flex gap-1.5 mt-2">
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
                      className="h-9 w-9"
                      title="View details"
                    >
                      <Info className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(doc.document_id)}
                      disabled={deletingId === doc.document_id}
                      className="h-9 w-9 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950"
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

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-6 mt-6 border-t border-gray-200 dark:border-slate-700">
              <span className="text-sm text-gray-600 dark:text-slate-400">
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
                <span className="text-sm text-gray-600 dark:text-slate-400">
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
        </div>
      </div>

      {/* Document Detail Modal */}
      <DocumentDetail
        document={selectedDoc}
        onClose={() => setSelectedDoc(null)}
      />
    </div>
  );
}
