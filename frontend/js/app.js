class MedicalChatBot {
    constructor() {
        this.apiBaseUrl = '/api/v1';
        this.conversationId = null;
        this.isStreaming = false;
        this.ws = null;

        this.initElements();
        this.initEventListeners();
        this.loadSettings();
    }

    initElements() {
        // Main elements
        this.messagesContainer = document.getElementById('messagesContainer');
        this.messageInput = document.getElementById('messageInput');
        this.chatForm = document.getElementById('chatForm');
        this.sendBtn = document.getElementById('sendBtn');

        // Upload elements
        this.uploadBtn = document.getElementById('uploadBtn');
        this.uploadModal = document.getElementById('uploadModal');
        this.uploadArea = document.getElementById('uploadArea');
        this.fileInput = document.getElementById('fileInput');
        this.closeModal = document.getElementById('closeModal');
        this.uploadProgress = document.getElementById('uploadProgress');
        this.progressFill = document.getElementById('progressFill');
        this.progressText = document.getElementById('progressText');

        // Settings elements
        this.settingsBtn = document.getElementById('settingsBtn');
        this.settingsPanel = document.getElementById('settingsPanel');
        this.closeSettings = document.getElementById('closeSettings');
        this.temperatureSlider = document.getElementById('temperature');
        this.temperatureValue = document.getElementById('temperatureValue');
        this.maxTokensInput = document.getElementById('maxTokens');
        this.streamModeCheckbox = document.getElementById('streamMode');
        this.themeSelect = document.getElementById('theme');
    }

    initEventListeners() {
        // Chat events
        this.chatForm.addEventListener('submit', (e) => this.handleSubmit(e));
        this.messageInput.addEventListener('input', () => this.autoResize());
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSubmit(e);
            }
        });

        // Upload events
        this.uploadBtn.addEventListener('click', () => this.openUploadModal());
        this.closeModal.addEventListener('click', () => this.closeUploadModal());
        this.uploadArea.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        // Drag and drop
        this.uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.uploadArea.classList.add('drag-over');
        });

        this.uploadArea.addEventListener('dragleave', () => {
            this.uploadArea.classList.remove('drag-over');
        });

        this.uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.uploadArea.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                this.handleFileUpload(e.dataTransfer.files[0]);
            }
        });

        // Settings events
        this.settingsBtn.addEventListener('click', () => this.toggleSettings());
        this.closeSettings.addEventListener('click', () => this.toggleSettings());
        this.temperatureSlider.addEventListener('input', (e) => {
            this.temperatureValue.textContent = e.target.value;
            this.saveSettings();
        });
        this.maxTokensInput.addEventListener('change', () => this.saveSettings());
        this.streamModeCheckbox.addEventListener('change', () => {
            this.saveSettings();
            this.reconnectWebSocket();
        });
        this.themeSelect.addEventListener('change', () => {
            this.applyTheme();
            this.saveSettings();
        });

        // Modal backdrop click
        this.uploadModal.addEventListener('click', (e) => {
            if (e.target === this.uploadModal) {
                this.closeUploadModal();
            }
        });
    }

    async handleSubmit(e) {
        e.preventDefault();

        const message = this.messageInput.value.trim();
        if (!message) return;

        // Add user message to chat
        this.addMessage('user', message);

        // Clear input
        this.messageInput.value = '';
        this.autoResize();

        // Disable send button
        this.sendBtn.disabled = true;

        try {
            if (this.streamModeCheckbox.checked) {
                await this.sendWebSocketMessage(message);
            } else {
                await this.sendMessage(message);
            }
        } catch (error) {
            this.addMessage('assistant', 'Sorry, an error occurred. Please try again.', { error: true });
            console.error('Error sending message:', error);
        } finally {
            this.sendBtn.disabled = false;
        }
    }

    async sendMessage(message) {
        // Show typing indicator
        const typingId = this.showTypingIndicator();

        try {
            const response = await fetch(`${this.apiBaseUrl}/chat/message`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    conversation_id: this.conversationId,
                    temperature: parseFloat(this.temperatureSlider.value),
                    max_tokens: parseInt(this.maxTokensInput.value),
                    stream: false
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // Remove typing indicator
            this.removeTypingIndicator(typingId);

            // Add assistant message
            this.addMessage('assistant', data.response, { sources: data.sources });

            // Update conversation ID
            if (data.conversation_id) {
                this.conversationId = data.conversation_id;
            }
        } catch (error) {
            this.removeTypingIndicator(typingId);
            throw error;
        }
    }

    async sendWebSocketMessage(message) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            await this.connectWebSocket();
        }

        const typingId = this.showTypingIndicator();
        let responseText = '';
        let messageElement = null;

        this.ws.send(JSON.stringify({
            message: message,
            conversation_id: this.conversationId,
            temperature: parseFloat(this.temperatureSlider.value),
            max_tokens: parseInt(this.maxTokensInput.value),
            stream: true
        }));

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (!messageElement) {
                this.removeTypingIndicator(typingId);
                messageElement = this.addMessage('assistant', '', { streaming: true });
            }

            if (data.chunk) {
                responseText += data.chunk;
                messageElement.querySelector('.message-text').textContent = responseText;
            }

            if (data.is_final) {
                messageElement.classList.remove('streaming');
                if (data.sources && data.sources.length > 0) {
                    this.addSources(messageElement, data.sources);
                }
            }

            if (data.conversation_id) {
                this.conversationId = data.conversation_id;
            }
        };
    }

    async connectWebSocket() {
        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(`ws://localhost:8000${this.apiBaseUrl}/chat/ws`);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                resolve();
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                reject(error);
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.ws = null;
            };
        });
    }

    reconnectWebSocket() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    addMessage(role, content, options = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;

        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="message-role">${role === 'user' ? 'You' : 'Medical Bot'}</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-content ${options.error ? 'error' : ''}">
                <div class="message-text">${content}</div>
            </div>
        `;

        if (options.streaming) {
            messageDiv.classList.add('streaming');
        }

        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();

        return messageDiv;
    }

    addSources(messageElement, sources) {
        if (!sources || sources.length === 0) return;

        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'message-sources';
        sourcesDiv.innerHTML = `
            <strong>Sources:</strong>
            ${sources.map(s => `<div>${s.metadata?.filename || 'Document'} (Score: ${(s.score || 0).toFixed(2)})</div>`).join('')}
        `;

        messageElement.querySelector('.message-content').appendChild(sourcesDiv);
    }

    showTypingIndicator() {
        const typingId = 'typing-' + Date.now();
        const typingDiv = document.createElement('div');
        typingDiv.id = typingId;
        typingDiv.className = 'message assistant';
        typingDiv.innerHTML = `
            <div class="message-header">
                <span class="message-role">Medical Bot</span>
            </div>
            <div class="message-content">
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        this.messagesContainer.appendChild(typingDiv);
        this.scrollToBottom();
        return typingId;
    }

    removeTypingIndicator(typingId) {
        const element = document.getElementById(typingId);
        if (element) {
            element.remove();
        }
    }

    openUploadModal() {
        this.uploadModal.classList.add('active');
    }

    closeUploadModal() {
        this.uploadModal.classList.remove('active');
        this.uploadProgress.classList.add('hidden');
        this.uploadArea.classList.remove('hidden');
        this.fileInput.value = '';
    }

    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.handleFileUpload(file);
        }
    }

    async handleFileUpload(file) {
        // Validate file
        const validTypes = ['application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
        if (!validTypes.includes(file.type)) {
            alert('Please upload a PDF, TXT, or DOCX file.');
            return;
        }

        if (file.size > 10 * 1024 * 1024) {
            alert('File size must be less than 10MB.');
            return;
        }

        // Show progress
        this.uploadArea.classList.add('hidden');
        this.uploadProgress.classList.remove('hidden');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const xhr = new XMLHttpRequest();

            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    this.progressFill.style.width = percentComplete + '%';
                    this.progressText.textContent = `Uploading... ${Math.round(percentComplete)}%`;
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    this.progressText.textContent = 'Processing complete!';
                    setTimeout(() => {
                        this.closeUploadModal();
                        this.addMessage('assistant', `Document "${response.filename}" uploaded successfully! ${response.chunks_created} chunks created. You can now ask questions about it.`);
                    }, 1000);
                } else {
                    throw new Error('Upload failed');
                }
            });

            xhr.addEventListener('error', () => {
                throw new Error('Upload failed');
            });

            xhr.open('POST', `${this.apiBaseUrl}/documents/upload`);
            xhr.send(formData);

        } catch (error) {
            alert('Error uploading file. Please try again.');
            this.closeUploadModal();
        }
    }

    toggleSettings() {
        this.settingsPanel.classList.toggle('active');
    }

    autoResize() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    loadSettings() {
        const settings = localStorage.getItem('chatSettings');
        if (settings) {
            const parsed = JSON.parse(settings);
            this.temperatureSlider.value = parsed.temperature || 0.5;
            this.temperatureValue.textContent = this.temperatureSlider.value;
            this.maxTokensInput.value = parsed.maxTokens || 512;
            this.streamModeCheckbox.checked = parsed.streamMode || false;
            this.themeSelect.value = parsed.theme || 'light';
        }
        this.applyTheme();
    }

    saveSettings() {
        const settings = {
            temperature: this.temperatureSlider.value,
            maxTokens: this.maxTokensInput.value,
            streamMode: this.streamModeCheckbox.checked,
            theme: this.themeSelect.value
        };
        localStorage.setItem('chatSettings', JSON.stringify(settings));
    }

    applyTheme() {
        const theme = this.themeSelect.value;
        if (theme === 'auto') {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new MedicalChatBot();
});