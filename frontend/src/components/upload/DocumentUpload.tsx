import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { apiService } from '@/services/api';
import { toast } from 'sonner';
import { Upload, FileText, X, CheckCircle } from 'lucide-react';

interface DocumentUploadProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DocumentUpload({ open, onOpenChange }: DocumentUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

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
    setProgress(0);

    try {
      const response = await apiService.uploadDocument(
        selectedFile,
        (progressValue) => setProgress(progressValue)
      );

      toast.success(`Document "${response.filename}" uploaded successfully! ${response.chunks_created} chunks created.`);
      onOpenChange(false);
      setSelectedFile(null);
      setProgress(0);
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Failed to upload document. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const handleClose = () => {
    if (!uploading) {
      onOpenChange(false);
      setSelectedFile(null);
      setProgress(0);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Upload Medical Document</DialogTitle>
          <DialogDescription>
            Upload PDF, TXT, or DOCX files for analysis. Maximum file size: 10MB.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {!selectedFile ? (
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
                ${isDragActive
                  ? 'border-primary bg-primary/10 dark:bg-primary/20'
                  : 'border-muted-foreground/25 dark:border-muted-foreground/40 hover:border-primary dark:hover:border-primary'
                }`}
            >
              <input {...getInputProps()} />
              <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground dark:text-muted-foreground" />
              <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                {isDragActive
                  ? 'Drop the file here...'
                  : 'Drag and drop a file here, or click to browse'}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 border border-slate-200 dark:border-slate-700 rounded-lg bg-muted/50 dark:bg-slate-800/50">
                <div className="flex items-center space-x-3">
                  <FileText className="h-8 w-8 text-primary dark:text-primary" />
                  <div>
                    <p className="font-medium text-foreground">{selectedFile.name}</p>
                    <p className="text-sm text-muted-foreground dark:text-muted-foreground">
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
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm text-foreground">
                    <span>Uploading...</span>
                    <span>{Math.round(progress)}%</span>
                  </div>
                  <Progress value={progress} className="w-full" />
                </div>
              )}

              {progress === 100 && !uploading && (
                <div className="flex items-center justify-center text-green-600 dark:text-green-400">
                  <CheckCircle className="h-5 w-5 mr-2" />
                  <span>Upload complete!</span>
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end space-x-2">
            <Button
              variant="outline"
              onClick={handleClose}
              disabled={uploading}
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpload}
              disabled={!selectedFile || uploading}
            >
              {uploading ? 'Uploading...' : 'Upload'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}