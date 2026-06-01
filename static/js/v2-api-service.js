// V2 API Service: Intercepts V1 fetch calls and maps to V2 endpoints with JWT and multi-tenant support
// Usage: Import this file before any other scripts that use fetch

(function() {
    // --- Config ---
    const V1_TO_V2_ENDPOINTS = [];

    // --- Auth State ---
    const AUTH_KEYS = {
        token: 'jwt_token',
        lawFirmId: 'law_firm_id',
        userRole: 'user_role',
        lawFirmName: 'law_firm_name',
    };

    function setAuthState({ token, lawFirmId, userRole, lawFirmName }) {
        if (token) localStorage.setItem(AUTH_KEYS.token, token);
        if (lawFirmId) localStorage.setItem(AUTH_KEYS.lawFirmId, lawFirmId);
        if (userRole) localStorage.setItem(AUTH_KEYS.userRole, userRole);
        if (lawFirmName) localStorage.setItem(AUTH_KEYS.lawFirmName, lawFirmName);
    }
    function getAuthState() {
        return {
            token: localStorage.getItem(AUTH_KEYS.token),
            lawFirmId: localStorage.getItem(AUTH_KEYS.lawFirmId),
            userRole: localStorage.getItem(AUTH_KEYS.userRole),
            lawFirmName: localStorage.getItem(AUTH_KEYS.lawFirmName),
        };
    }
    function clearAuthState() {
        Object.values(AUTH_KEYS).forEach(key => localStorage.removeItem(key));
    }

    function getToken() {
        return getAuthState().token;
    }

    function authHeaders(extra) {
        extra = extra || {};
        const token = getToken();
        const headers = Object.assign({}, extra);
        if (token) headers['Authorization'] = 'Bearer ' + token;
        return headers;
    }

    async function parseJsonResponse(response) {
        const data = await response.json();
        if (!response.ok) {
            const detail = data.detail || data.message || response.statusText;
            throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
        }
        return data;
    }

    // --- Endpoint Mapper ---
    function mapV1toV2(url) {
        for (const [pattern, replacement] of V1_TO_V2_ENDPOINTS) {
            if (typeof url === 'string' && pattern.test(url)) {
                return url.replace(pattern, replacement);
            }
        }
        return url;
    }

    // --- JWT Login ---
    async function v2Login({ username, password, lawFirmId }) {
        const loginUrl = '/auth/login';
        const body = JSON.stringify({ username, password, law_firm_id: lawFirmId });
        const resp = await window._realFetch(loginUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body,
        });
        if (!resp.ok) throw new Error('Login failed');
        const data = await resp.json();
        // Assume response: { access_token, law_firm_id, user_role, law_firm_name }
        setAuthState({
            token: data.access_token,
            lawFirmId: data.law_firm_id,
            userRole: data.user_role,
            lawFirmName: data.law_firm_name,
        });
        return data;
    }

    // --- Intercept fetch ---
    if (!window._realFetch) window._realFetch = window.fetch.bind(window);
    window.fetch = async function(input, init = {}) {
        // Map V1 endpoint to V2
        let url = (typeof input === 'string') ? input : input.url;
        const mappedUrl = mapV1toV2(url);
        // Clone init to avoid mutating caller's object
        let newInit = Object.assign({}, init);
        // Add JWT and law firm headers if available and not a login call
        if (!mappedUrl.endsWith('/auth/login')) {
            const { token, lawFirmId } = getAuthState();
            newInit.headers = newInit.headers || {};
            if (token) newInit.headers['Authorization'] = 'Bearer ' + token;
            if (lawFirmId) newInit.headers['X-Law-Firm-ID'] = lawFirmId;
        }
        // Use mapped URL
        if (typeof input === 'string') {
            input = mappedUrl;
        } else {
            input = new Request(mappedUrl, input);
        }
        return window._realFetch(input, newInit);
    };

    // --- Expose service ---
    window.V2ApiService = {
        login: v2Login,
        setAuthState,
        getAuthState,
        clearAuthState,
        getToken,
        mapV1toV2,

        listCases: async function() {
            const response = await window.fetch(
                '/cases',
                { headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        createCase: async function(body) {
            const response = await window.fetch(
                '/cases',
                {
                    method: 'POST',
                    headers: authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify(body),
                }
            );
            return parseJsonResponse(response);
        },

        uploadDocument: async function(caseId, file) {
            const formData = new FormData();
            formData.append('file', file);
            const response = await window.fetch(
                '/cases/' + caseId + '/documents',
                {
                    method: 'POST',
                    headers: authHeaders(),
                    body: formData,
                }
            );
            return parseJsonResponse(response);
        },

        replaceDocument: async function(caseId, documentId, file) {
            const token = window.V2ApiService.getToken();
            const formData = new FormData();
            formData.append('file', file);
            formData.append('replace_document_id', documentId);
            const response = await fetch(
                '/cases/' + caseId + '/documents',
                {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token },
                    body: formData
                }
            );
            return response.json();
        },

        listCaseDocuments: async function(caseId) {
            const response = await window.fetch(
                '/cases/' + caseId + '/documents',
                { headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        getDocumentDetail: async function(caseId, documentId) {
            const token = window.V2ApiService.getToken();
            const response = await fetch(
                '/cases/' + caseId + '/documents/' + documentId,
                { headers: { 'Authorization': 'Bearer ' + token } }
            );
            return response.json();
        },

        listDocumentVersions: async function(caseId, documentId) {
            const response = await window.fetch(
                '/cases/' + caseId + '/documents/' + documentId + '/versions',
                { headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        classifyVersion: async function(caseId, body) {
            const response = await window.fetch(
                '/cases/' + caseId + '/classify-version',
                {
                    method: 'POST',
                    headers: authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify(body),
                }
            );
            return parseJsonResponse(response);
        },

        getCoverage: async function(caseId, visaType) {
            const response = await window.fetch(
                '/cases/' + caseId + '/coverage?visa_type=' + encodeURIComponent(visaType),
                { headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        submitClassificationFeedback: async function(caseId, classificationResultId, body) {
            const response = await window.fetch(
                '/cases/' + caseId + '/classifications/' + classificationResultId + '/feedback',
                {
                    method: 'POST',
                    headers: authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify(body),
                }
            );
            return parseJsonResponse(response);
        },

        // Review endpoints
        submitReview: async function(caseId, draftId, sectionId, body) {
            const response = await window.fetch(
                '/cases/' + caseId + '/drafts/' + draftId + '/sections/' + sectionId + '/review',
                {
                    method: 'POST',
                    headers: authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify(body),
                }
            );
            return parseJsonResponse(response);
        },

        getReviewStatus: async function(caseId, draftId) {
            const response = await window.fetch(
                '/cases/' + caseId + '/drafts/' + draftId + '/review-status',
                { headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        regenerateSection: async function(caseId, draftId, sectionId, body) {
            const response = await window.fetch(
                '/cases/' + caseId + '/drafts/' + draftId + '/sections/' + sectionId + '/regenerate',
                {
                    method: 'POST',
                    headers: authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify(body),
                }
            );
            return parseJsonResponse(response);
        },

        exportDraft: async function(caseId, draftId, format) {
            const response = await window.fetch(
                '/cases/' + caseId + '/drafts/' + draftId + '/export',
                {
                    method: 'POST',
                    headers: authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify({ export_format: format }),
                }
            );
            return parseJsonResponse(response);
        },

        getExports: async function(caseId, draftId) {
            const response = await window.fetch(
                '/cases/' + caseId + '/drafts/' + draftId + '/exports',
                { headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        // Observability
        getWorkflowState: async function(caseId) {
            const response = await window.fetch(
                '/observability/workflow/' + caseId,
                { headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        getInvariants: async function() {
            const response = await window.fetch(
                '/observability/invariants',
                { headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        getQueueHealth: async function() {
            const response = await window.fetch(
                '/observability/queue-health',
                { headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        // KB
        uploadKBDocument: async function(title, documentType, file) {
            const formData = new FormData();
            formData.append('title', title);
            formData.append('document_type', documentType);
            formData.append('file', file);
            const response = await window.fetch(
                '/kb/documents',
                {
                    method: 'POST',
                    headers: authHeaders(),
                    body: formData,
                }
            );
            return parseJsonResponse(response);
        },

        ingestKBDocument: async function(kbDocumentId) {
            const response = await window.fetch(
                '/kb/documents/' + kbDocumentId + '/ingest',
                { method: 'POST', headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        listKBDocuments: async function() {
            const response = await window.fetch(
                '/kb/documents',
                { method: 'GET', headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        // Draft
        getDraft: async function(caseId, draftId) {
            const response = await window.fetch(
                '/cases/' + caseId + '/drafts/' + draftId,
                { headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        listDrafts: async function(caseId) {
            const response = await window.fetch(
                '/cases/' + caseId + '/drafts',
                { headers: authHeaders() }
            );
            return parseJsonResponse(response);
        },

        generateDraft: async function(caseId, body) {
            const response = await window.fetch(
                '/cases/' + caseId + '/generate',
                {
                    method: 'POST',
                    headers: authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify(body),
                }
            );
            return parseJsonResponse(response);
        },
    };
})();
