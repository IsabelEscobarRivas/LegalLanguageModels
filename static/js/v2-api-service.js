// V2 API Service: Intercepts V1 fetch calls and maps to V2 endpoints with JWT and multi-tenant support
// Usage: Import this file before any other scripts that use fetch

(function() {
    // --- Config ---
    const V1_TO_V2_ENDPOINTS = [
        // [V1 pattern, V2 replacement]
        [/^\/documents\//, '/api/v2/documents/'],
        [/^\/cases\//, '/api/v2/cases/'],
        [/^\/files\//, '/api/v2/files/'],
        [/^\/upload\//, '/api/v2/upload/'],
        [/^\/preview\//, '/api/v2/preview/'],
        [/^\/download\//, '/api/v2/download/'],
        [/^\/document_types\//, '/api/v2/document_types/'],
        [/^\/auth\/login/, '/api/v2/auth/login'],
    ];

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
        const loginUrl = '/api/v2/auth/login';
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
        mapV1toV2,
    };
})(); 