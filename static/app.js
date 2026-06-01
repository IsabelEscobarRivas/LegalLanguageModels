const { useState, useRef, useEffect } = React;

const DocumentIngestion = ({ caseId, setCaseId, visaType, setVisaType }) => {
    const [category, setCategory] = useState('');
    const [selectedFile, setSelectedFile] = useState(null);
    const [uploadStatus, setUploadStatus] = useState('');
    const [existingCases, setExistingCases] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [fileSearchTerm, setFileSearchTerm] = useState('');
    const [caseFiles, setCaseFiles] = useState([]);
    const fileInputRef = useRef(null);
    // New state variables for preview
    const [previewContent, setPreviewContent] = useState('');
    const [isPreviewLoading, setIsPreviewLoading] = useState(false);
    const [showPreviewModal, setShowPreviewModal] = useState(false);
    const [selectedPreviewFile, setSelectedPreviewFile] = useState(null);
    // New state variables for document type
    const [documentType, setDocumentType] = useState('');
    const [documentTypes, setDocumentTypes] = useState([]);
    
	const EB1_CATEGORIES = [
        "A. Evidence of receipt of lesser nationally or internationally recognized prizes or awards for excellence",
        "B. Evidence of membership in associations in the field which demand outstanding achievement",
        "C. Evidence of published material about the applicant",
        "D. Evidence that the applicant has been asked to judge the work of others",
        "E. Evidence of the applicant's original scientific, scholarly contributions",
        "F. Evidence of the applicant's authorship of scholarly articles",
        "G. Evidence that the applicant's work has been displayed",
        "H. Evidence of the applicant's performance of a leading or critical role",
        "I. Evidence that the applicant commands a high salary",
        "J. Evidence of the applicant's commercial successes",
        "Letters of Support",
        "Professional Plan"
    ];

    const EB2_CATEGORIES = [
        "01_General_Documents",
        "02_Applicant_Background",
        "03_NIW_Criterion_1_Significant_Merit_and_Importance",
        "04_NIW_Criterion_2_Positioned_to_Advance_the_Field",
        "05_NIW_Criterion_3_Benefit_to_USA_Without_Labor_Certification",
        "06_Letters_of_Recommendation",
        "07_Peer_Reviewed_Publications",
        "08_Additional_Supporting_Documents"
    ];

    useEffect(() => {
        fetchExistingCases();
    }, [visaType]);

    // New effect to fetch document types when visa type changes
    useEffect(() => {
        if (visaType) {
            fetchDocumentTypes();
        }
    }, [visaType]);

    // New function to fetch document types
    const fetchDocumentTypes = async () => {
        try {
            const response = await fetch(`/document_types/${visaType}`);
            const data = await response.json();
            if (response.ok && data.document_types) {
                setDocumentTypes(data.document_types);
                setDocumentType(''); // Reset selection when visa type changes
            }
        } catch (error) {
            console.error('Error fetching document types:', error);
            setDocumentTypes([]);
        }
    };

    const fetchExistingCases = async () => {
        try {
            const response = await fetch('/documents/');
            const data = await response.json();
            const casesMap = data.reduce((acc, doc) => {
                if (!acc[doc.case_id]) {
                    acc[doc.case_id] = { id: doc.case_id, visaTypes: new Set() };
                }
                acc[doc.case_id].visaTypes.add(doc.visa_type);
                return acc;
            }, {});

            const uniqueCases = Object.values(casesMap).map(c => ({
                id: c.id,
                visaTypes: Array.from(c.visaTypes)
            }));
            setExistingCases(uniqueCases);
        } catch (error) {
            console.error('Error fetching cases:', error);
        }
    };
	
	const fetchCaseFiles = async (selectedCaseId) => {
        try {
            console.log('Fetching files for case ID:', selectedCaseId);
            const response = await fetch(`/cases/${selectedCaseId}`);
            const data = await response.json();
            
            if (response.ok && data.files) {
                console.log('Setting files:', data.files);
                setCaseFiles(data.files);
            } else {
                console.log('No files found or invalid case data');
                setCaseFiles([]);
            }
        } catch (error) {
            console.error('Error in fetchCaseFiles:', error);
            setCaseFiles([]);
        }
    };

    const handleDeleteFile = async (fileId, filename) => {
        if (window.confirm(`Are you sure you want to delete ${filename}?`)) {
            try {
                const response = await fetch(`/files/${fileId}`, {
                    method: 'DELETE',
                });
                
                if (response.ok) {
                    fetchCaseFiles(caseId);
                } else {
                    throw new Error('Failed to delete file');
                }
            } catch (error) {
                console.error('Error deleting file:', error);
                alert('Failed to delete file. Please try again.');
            }
        }
    };

    const handleDeleteCase = async (caseToDelete) => {
        if (window.confirm(`Are you sure you want to delete case ${caseToDelete}?`)) {
            try {
                const response = await fetch(`/documents/${caseToDelete}`, {
                    method: 'DELETE',
                });
                if (response.ok) {
                    fetchExistingCases();
                    if (caseId === caseToDelete) {
                        setCaseId('');
                        setCaseFiles([]);
                    }
                }
            } catch (error) {
                console.error('Error deleting case:', error);
            }
        }
    };

    // New preview handler
    const handlePreviewFile = async (fileId, filename) => {
        setIsPreviewLoading(true);
        setShowPreviewModal(true);
        setSelectedPreviewFile(filename);
        try {
            const response = await fetch(`/preview/${fileId}`);
            if (!response.ok) {
                throw new Error('Failed to fetch preview');
            }
            const data = await response.json();
            setPreviewContent(data.text);
        } catch (error) {
            console.error('Error previewing file:', error);
            setPreviewContent('Error loading preview');
        } finally {
            setIsPreviewLoading(false);
        }
    };

    // New download handler
    const handleDownloadFile = async (fileId, filename) => {
        try {
            const response = await fetch(`/download/${fileId}`);
            if (!response.ok) {
                throw new Error('Failed to download file');
            }
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            console.error('Error downloading file:', error);
            alert('Failed to download file');
        }
    };
	const handleFileSelect = (e) => {
        setSelectedFile(e.target.files[0]);
    };

    const handleUpload = async () => {
        if (!selectedFile || !caseId || !visaType || !category || !documentType) {
            setUploadStatus('Please fill in all fields and select a file');
            return;
        }

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('case_id', caseId);
        formData.append('visa_type', visaType);
        formData.append('category', category);
        formData.append('document_type', documentType); // Add document type to form data

        try {
            setUploadStatus('Uploading...');
            
            const response = await fetch('/upload/', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Upload failed');
            }

            setUploadStatus('Upload successful!');
            setSelectedFile(null);
            fetchExistingCases();
            fetchCaseFiles(caseId);
            
        } catch (error) {
            console.error('Upload error:', error);
            setUploadStatus(`Upload failed: ${error.message}`);
        }
    };

    const filteredCases = existingCases.filter(caseData =>
        caseData.id.toLowerCase().includes(searchTerm.toLowerCase()) &&
        (!visaType || caseData.visaTypes.includes(visaType))
    );

    const filteredFiles = caseFiles.filter(file =>
        file.filename.toLowerCase().includes(fileSearchTerm.toLowerCase())
    );
	
	return (
        <div className="max-w-4xl mx-auto p-6">
            <div className="bg-white rounded-lg shadow-lg p-6">
                <h1 className="custom-heading">
                    Xplore Immigration - Document Upload
                </h1>

                {/* Visa Type Selection FIRST */}
                <div className="mb-6">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                        Visa Type
                    </label>
                    <div className="grid grid-cols-2 gap-4">
                        <button
                            onClick={() => {
                                setVisaType('EB1');
                                setCaseId('');
                                setCategory('');
                                setDocumentType('');
                                setCaseFiles([]);
                            }}
                            className={`p-2 rounded ${
                                visaType === 'EB1' 
                                    ? 'bg-[#1a365d] text-white' 
                                    : 'bg-gray-100 hover:bg-gray-200'
                            }`}
                        >
                            EB1
                        </button>
                        <button
                            onClick={() => {
                                setVisaType('EB2');
                                setCaseId('');
                                setCategory('');
                                setDocumentType('');
                                setCaseFiles([]);
                            }}
                            className={`p-2 rounded ${
                                visaType === 'EB2' 
                                    ? 'bg-[#1a365d] text-white' 
                                    : 'bg-gray-100 hover:bg-gray-200'
                            }`}
                        >
                            EB2
                        </button>
                    </div>
                </div>
				
				
                {/* Case List and Selection SECOND */}
                {visaType && (
                    <div className="mb-6">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Select or Enter Case ID
                        </label>
                        <input
                            type="text"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            placeholder="Search existing cases..."
                            className="w-full p-2 border rounded mb-4 focus:ring-2 focus:ring-blue-500"
                        />
                        <div className="max-h-40 overflow-y-auto mb-4 border rounded">
                            {filteredCases.map(caseData => (
                                <div 
                                    key={caseData.id} 
                                    className="flex justify-between items-center p-2 hover:bg-gray-100 cursor-pointer border-b"
                                >
                                    <div 
                                        onClick={() => {
                                            console.log('Selected case:', caseData.id);
                                            setCaseId(caseData.id);
                                            fetchCaseFiles(caseData.id);
                                        }}
                                        className="flex-1"
                                    >
                                        <span className={caseId === caseData.id ? 'font-bold' : ''}>
                                            {caseData.id}
                                        </span>
                                        <span className="ml-2 text-sm text-gray-500">
                                            ({caseData.visaTypes.join(', ')})
                                        </span>
                                    </div>
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleDeleteCase(caseData.id);
                                        }}
                                        className="text-red-500 hover:text-red-700 px-2"
                                    >
                                        Delete
                                    </button>
                                </div>
                            ))}
                        </div>
                        <input
                            type="text"
                            value={caseId}
                            onChange={(e) => setCaseId(e.target.value)}
                            placeholder="Or enter new Case ID"
                            className="w-full p-2 border rounded focus:ring-2 focus:ring-blue-500"
                        />
						
						
						{/* Files Display */}
                        {caseId && (
                            <div className="mt-4">
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Uploaded Files
                                </label>
                                <input
                                    type="text"
                                    value={fileSearchTerm}
                                    onChange={(e) => setFileSearchTerm(e.target.value)}
                                    placeholder="Search through files..."
                                    className="w-full p-2 border rounded mb-4 focus:ring-2 focus:ring-blue-500"
                                />
                                <div className="max-h-40 overflow-y-auto border rounded">
                                    {filteredFiles.length > 0 ? (
                                        filteredFiles.map(file => (
                                            <div 
                                                key={file.id} 
                                                className="flex justify-between items-center p-2 hover:bg-gray-100 border-b"
                                            >
                                                <div className="flex flex-col flex-grow">
                                                    <span className="font-medium">{file.filename}</span>
                                                    <span className="text-sm text-gray-500">
                                                        {file.category}
                                                    </span>
                                                </div>
                                                <div className="flex items-center">
                                                    <span className="text-sm text-gray-500 mr-4">
                                                        {new Date(file.uploaded_at).toLocaleDateString()}
                                                    </span>
                                                    {/* Preview Button */}
                                                    <button
                                                        onClick={() => handlePreviewFile(file.id, file.filename)}
                                                        className="text-blue-500 hover:text-blue-700 p-1 mr-2"
                                                        title="Preview file"
                                                    >
                                                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                                            <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                                                            <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                                                        </svg>
                                                    </button>
                                                    {/* Download Button */}
                                                    <button
                                                        onClick={() => handleDownloadFile(file.id, file.filename)}
                                                        className="text-green-500 hover:text-green-700 p-1 mr-2"
                                                        title="Download file"
                                                    >
                                                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                                            <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
                                                        </svg>
                                                    </button>
                                                    {/* Delete Button */}
                                                    <button
                                                        onClick={() => handleDeleteFile(file.id, file.filename)}
                                                        className="text-red-500 hover:text-red-700 p-1"
                                                        title="Delete file"
                                                    >
                                                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                                            <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                                                        </svg>
                                                    </button>
                                                </div>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="p-4 text-gray-500 text-center">
                                            No files uploaded for this case yet
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}
				
				
				{/* Category Selection THIRD */}
                {visaType && caseId && (
                    <div className="mb-6">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Document Category
                        </label>
                        <select
                            value={category}
                            onChange={(e) => setCategory(e.target.value)}
                            className="w-full p-2 border rounded focus:ring-2 focus:ring-blue-500"
                        >
                            <option value="">Select a category</option>
                            {(visaType === 'EB1' ? EB1_CATEGORIES : EB2_CATEGORIES).map((cat) => (
                                <option key={cat} value={cat}>
                                    {cat}
                                </option>
                            ))}
                        </select>
                    </div>
                )}

                {/* Document Type Selection - NEW SECTION */}
                {visaType && caseId && category && (
                    <div className="mb-6">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Document Type
                        </label>
                        <select
                            value={documentType}
                            onChange={(e) => setDocumentType(e.target.value)}
                            className="w-full p-2 border rounded focus:ring-2 focus:ring-blue-500"
                        >
                            <option value="">Select a document type</option>
                            {documentTypes.map((type) => (
                                <option key={type} value={type}>
                                    {type.replace(/_/g, ' ')}
                                </option>
                            ))}
                        </select>
                    </div>
                )}

                {/* File Upload Section LAST */}
                {category && documentType && (
                    <div className="mt-8 space-y-4">
                        <input
                            type="file"
                            ref={fileInputRef}
                            onChange={handleFileSelect}
                            className="hidden"
                            accept=".pdf,.doc,.docx"
                        />
                        <div className="flex space-x-4">
                            <button
                                onClick={() => fileInputRef.current.click()}
                                className="w-1/2 bg-gray-200 text-gray-700 py-2 px-4 rounded hover:bg-gray-300"
                            >
                                Browse Files
                            </button>
                            <button
                                onClick={handleUpload}
                                disabled={!selectedFile}
                                className={`w-1/2 py-2 px-4 rounded ${
                                    selectedFile 
                                    ? 'bg-[#1a365d] text-white hover:bg-[#2a466d]' 
                                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                }`}
                            >
                                Upload
                            </button>
                        </div>
                        {selectedFile && (
                            <p className="text-sm text-gray-600">
                                Selected file: {selectedFile.name}
                            </p>
                        )}
                        {uploadStatus && (
                            <p className={`text-sm ${
                                uploadStatus.includes('successful') 
                                    ? 'text-green-600' 
                                    : uploadStatus === 'Uploading...' 
                                    ? 'text-blue-600' 
                                    : 'text-red-600'
                            }`}>
                                {uploadStatus}
                            </p>
                        )}
                    </div>
                )}

                {/* Preview Modal */}
                {showPreviewModal && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                        <div className="bg-white rounded-lg max-w-2xl w-full max-h-[80vh] flex flex-col">
                            <div className="p-4 border-b flex justify-between items-center">
                                <h3 className="text-lg font-medium">
                                    {selectedPreviewFile}
                                </h3>
                                <button
                                    onClick={() => {
                                        setShowPreviewModal(false);
                                        setPreviewContent('');
                                        setSelectedPreviewFile(null);
                                    }}
                                    className="text-gray-500 hover:text-gray-700"
                                >
                                    <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                            <div className="p-4 flex-1 overflow-y-auto">
                                {isPreviewLoading ? (
                                    <div className="flex items-center justify-center h-full">
                                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
                                    </div>
                                ) : (
                                    <pre className="whitespace-pre-wrap font-sans text-sm">
                                        {previewContent}
                                    </pre>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

const SECTION_LABELS = {
    background: 'Background',
    experience: 'Experience',
    expert_opinion: 'Expert Opinion',
    achievements: 'Achievements',
    impact: 'Impact',
    conclusion: 'Conclusion',
};

function formatSectionCode(code) {
    return SECTION_LABELS[code] || code.replace(/_/g, ' ').replace(/\b\w/g, function(c) {
        return c.toUpperCase();
    });
}

function lifecycleBadgeClass(state) {
    if (state === 'failed') return 'bg-red-100 text-red-800';
    if (state === 'indexed' || state === 'final' || state === 'reviewed') return 'bg-green-100 text-green-800';
    if (state === 'chunked' || state === 'embedded') return 'bg-yellow-100 text-yellow-800';
    return 'bg-gray-100 text-gray-800';
}

function participationBadgeClass(state) {
    if (state === 'active') return 'bg-green-100 text-green-800';
    if (state === 'excluded_from_retrieval') return 'bg-red-100 text-red-800';
    if (state === 'excluded_from_generation') return 'bg-orange-100 text-orange-800';
    if (state === 'quarantined') return 'bg-red-200 text-red-900';
    if (state === 'archived') return 'bg-gray-200 text-gray-600';
    if (state === 'ingestion_failed') return 'bg-red-100 text-red-700';
    return 'bg-gray-100 text-gray-600';
}

function participationLabel(state) {
    if (state === 'active') return 'Active';
    if (state === 'excluded_from_retrieval') return 'Excluded';
    if (state === 'excluded_from_generation') return 'Gen. Excluded';
    if (state === 'quarantined') return 'Quarantined';
    if (state === 'archived') return 'Archived';
    if (state === 'ingestion_failed') return 'Ingestion Failed';
    return state || 'Unknown';
}

function extractionMethodLabel(method) {
    if (method === 'pypdf2') return 'Native PDF';
    if (method === 'docx') return 'Native DOCX';
    if (method === 'txt') return 'Plain Text';
    if (method === 'textract') return 'AWS Textract';
    if (method === 'ocr') return 'OCR (Tesseract)';
    return method || 'Unknown';
}

function reviewBadgeClass(action) {
    if (action === 'approved') return 'bg-green-100 text-green-800';
    if (action === 'edited') return 'bg-blue-100 text-blue-800';
    if (action === 'rejected') return 'bg-red-100 text-red-800';
    return 'bg-gray-100 text-gray-600';
}

function ProvenanceInspector({ section, traces, kbGuidanceApplied, kbTraceCount, onFeedback }) {
    return (
        <div className="mt-4 space-y-3">
            <div className="border-2 border-blue-400 rounded-lg p-4 bg-blue-50">
                <h4 className="font-semibold text-blue-900 mb-3">Evidence Traces</h4>
                {traces && traces.length > 0 ? traces.map(function(trace, idx) {
                    return (
                        <div key={trace.classification_result_id || idx} className="mb-3 pb-3 border-b border-blue-200 last:border-0">
                            <p className="text-sm italic text-gray-800">
                                &ldquo;{trace.citation_text || 'See source document'}&rdquo;
                            </p>
                            <p className="text-xs text-gray-600 mt-1">
                                Source: {trace.source_document || '—'}
                            </p>
                            <p className="text-xs text-gray-600">
                                Criteria: {trace.criteria_code || '—'}
                                {trace.confidence_score != null && (
                                    <span> · Confidence: {Math.round(trace.confidence_score * 100)}%</span>
                                )}
                            </p>
                            {trace.classification_result_id && (
                                <div className="mt-2 flex gap-2">
                                    <button
                                        onClick={function() { onFeedback(trace.classification_result_id, 'confirmed'); }}
                                        className="text-xs bg-green-600 text-white px-2 py-1 rounded"
                                    >
                                        Confirm
                                    </button>
                                    <button
                                        onClick={function() { onFeedback(trace.classification_result_id, 'rejected'); }}
                                        className="text-xs bg-red-600 text-white px-2 py-1 rounded"
                                    >
                                        Reject
                                    </button>
                                </div>
                            )}
                        </div>
                    );
                }) : (
                    <p className="text-sm text-gray-600">No evidence traces for this section.</p>
                )}
            </div>
            {kbGuidanceApplied && (
                <div className="border-2 border-purple-400 rounded-lg p-4 bg-purple-50">
                    <h4 className="font-semibold text-purple-900">KB Style Guidance Applied</h4>
                    <p className="text-sm text-purple-800 mt-1">
                        Guidance influences rhetoric only — not cited as evidence
                    </p>
                    {kbTraceCount != null && (
                        <p className="text-xs text-purple-700 mt-2">
                            {kbTraceCount} KB guidance trace{kbTraceCount === 1 ? '' : 's'} recorded
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}

function DraftReviewScreen({ caseId, draftId, visaType, onBack }) {
    const [draft, setDraft] = useState(null);
    const [reviewStatus, setReviewStatus] = useState(null);
    const [exportHistory, setExportHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [openProvenance, setOpenProvenance] = useState(null);
    const [editingSection, setEditingSection] = useState(null);
    const [editText, setEditText] = useState('');
    const [actionMessage, setActionMessage] = useState('');

    const loadAll = async function() {
        setLoading(true);
        setError('');
        if (!caseId || !draftId) {
            setError('Missing case ID or draft ID — cannot load draft.');
            setLoading(false);
            return;
        }
        try {
            const token = window.V2ApiService.getToken();
            const headers = {};
            if (token) {
                headers['Authorization'] = 'Bearer ' + token;
            }
            const draftUrl = '/cases/' + caseId + '/drafts/' + draftId;
            const draftResponse = await fetch(draftUrl, { headers: headers });
            const draftText = await draftResponse.text();
            console.log('Draft response status:', draftResponse.status);
            console.log('Draft response first 200 chars:', draftText.substring(0, 200));
            if (!draftResponse.ok) {
                console.error('Draft load failed:', draftResponse.status, draftText);
                setError('Failed to load draft: ' + draftResponse.status);
                return;
            }
            let draftData;
            try {
                draftData = JSON.parse(draftText);
            } catch (parseErr) {
                console.error('Draft JSON parse failed:', parseErr, draftText);
                setError(
                    'Failed to parse draft response: ' + parseErr.message +
                    '\n\nRaw response:\n' + draftText.slice(0, 500)
                );
                return;
            }
            const statusData = await window.V2ApiService.getReviewStatus(caseId, draftId);
            const exportData = await window.V2ApiService.getExports(caseId, draftId);
            setDraft(draftData);
            setReviewStatus(statusData);
            setExportHistory(exportData.exports || []);
        } catch (err) {
            setError(err.message || 'Failed to load draft');
        } finally {
            setLoading(false);
        }
    };

    useEffect(function() {
        loadAll();
    }, [caseId, draftId]);

    const reviewBySectionId = {};
    if (reviewStatus && reviewStatus.sections) {
        reviewStatus.sections.forEach(function(s) {
            reviewBySectionId[s.section_id] = s;
        });
    }

    const orderedSections = (draft && draft.sections) ? draft.sections : [];

    const handleApprove = async function(sectionId) {
        try {
            await window.V2ApiService.submitReview(caseId, draftId, sectionId, { action: 'approved' });
            setActionMessage('Section approved.');
            await loadAll();
        } catch (err) {
            setActionMessage('Approve failed: ' + err.message);
        }
    };

    const handleSaveEdit = async function(sectionId) {
        try {
            await window.V2ApiService.submitReview(caseId, draftId, sectionId, {
                action: 'edited',
                reviewer_edit: editText,
            });
            setEditingSection(null);
            setEditText('');
            setActionMessage('Edit saved.');
            await loadAll();
        } catch (err) {
            setActionMessage('Edit failed: ' + err.message);
        }
    };

    const handleRejectRegenerate = async function(sectionId) {
        try {
            await window.V2ApiService.submitReview(caseId, draftId, sectionId, {
                action: 'rejected',
                regeneration_requested: true,
                rejection_reason: 'Attorney requested regeneration',
            });
            await window.V2ApiService.regenerateSection(caseId, draftId, sectionId, {
                visa_type: visaType,
                force_generate: true,
            });
            setActionMessage('Section regenerated.');
            await loadAll();
        } catch (err) {
            setActionMessage('Reject/regenerate failed: ' + err.message);
        }
    };

    const handleExport = async function(format) {
        try {
            const result = await window.V2ApiService.exportDraft(caseId, draftId, format);
            if (format === 'txt' && typeof result.content === 'string') {
                const blob = new Blob([result.content], { type: 'text/plain' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'draft-' + draftId + '.txt';
                a.click();
                window.URL.revokeObjectURL(url);
            } else if (format === 'json') {
                const blob = new Blob([JSON.stringify(result.content, null, 2)], { type: 'application/json' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'draft-' + draftId + '.json';
                a.click();
                window.URL.revokeObjectURL(url);
            }
            setActionMessage('Export completed.');
            await loadAll();
        } catch (err) {
            setActionMessage('Export failed: ' + err.message);
        }
    };

    const handleClassificationFeedback = async function(classificationResultId, action) {
        try {
            await window.V2ApiService.submitClassificationFeedback(caseId, classificationResultId, {
                action: action,
                rationale: action === 'confirmed'
                    ? 'Confirmed by attorney during draft review.'
                    : 'Rejected by attorney during draft review.',
            });
            setActionMessage('Classification feedback recorded.');
        } catch (err) {
            setActionMessage('Classification feedback failed: ' + err.message);
        }
    };

    if (loading) {
        return <div className="p-6 text-center text-gray-600">Loading draft...</div>;
    }

    if (error) {
        return (
            <div className="p-6">
                <p className="text-red-600">{error}</p>
                <button onClick={onBack} className="mt-4 text-[#1a365d] underline">Back to dashboard</button>
            </div>
        );
    }

    return (
        <div className="max-w-5xl mx-auto p-6">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-[#1a365d]">Draft Review</h1>
                    <p className="text-sm text-gray-600">Case: {caseId} · Draft: {draftId}</p>
                </div>
                <button onClick={onBack} className="bg-gray-200 px-4 py-2 rounded hover:bg-gray-300">
                    Back to Dashboard
                </button>
            </div>

            {actionMessage && (
                <p className="mb-4 text-sm text-blue-700 bg-blue-50 p-2 rounded">{actionMessage}</p>
            )}

            {orderedSections.map(function(section) {
                const review = reviewBySectionId[section.id] || {};
                const displayContent = review.latest_action === 'edited' && review.reviewer_edit
                    ? review.reviewer_edit
                    : section.content;
                const statusLabel = review.latest_action || 'pending';

                return (
                    <div key={section.id} className="bg-white rounded-lg shadow p-6 mb-6">
                        <div className="flex flex-wrap items-center gap-2 mb-4">
                            <h2 className="text-lg font-semibold text-[#1a365d]">
                                {formatSectionCode(section.section_code)}
                            </h2>
                            <span className={'text-xs px-2 py-1 rounded ' + reviewBadgeClass(review.latest_action)}>
                                {statusLabel}
                            </span>
                            {section.kb_guidance_applied && (
                                <span className="text-xs px-2 py-1 rounded bg-purple-100 text-purple-800">
                                    KB Guided
                                </span>
                            )}
                        </div>

                        {editingSection === section.id ? (
                            <div className="mb-4">
                                <textarea
                                    className="w-full p-3 border rounded h-48"
                                    value={editText}
                                    onChange={function(e) { setEditText(e.target.value); }}
                                />
                                <div className="mt-2 flex gap-2">
                                    <button
                                        onClick={function() { handleSaveEdit(section.id); }}
                                        className="bg-[#1a365d] text-white px-4 py-2 rounded"
                                    >
                                        Save Edit
                                    </button>
                                    <button
                                        onClick={function() { setEditingSection(null); setEditText(''); }}
                                        className="bg-gray-200 px-4 py-2 rounded"
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="prose max-w-none mb-4">
                                <p className="whitespace-pre-wrap text-gray-800 text-sm leading-relaxed">
                                    {displayContent}
                                </p>
                            </div>
                        )}

                        <button
                            onClick={function() {
                                setOpenProvenance(openProvenance === section.id ? null : section.id);
                            }}
                            className="text-sm text-[#1a365d] underline mb-4"
                        >
                            {openProvenance === section.id ? 'Hide Provenance' : 'Show Provenance'}
                        </button>

                        {openProvenance === section.id && (
                            <ProvenanceInspector
                                section={section}
                                traces={section.traces || []}
                                kbGuidanceApplied={section.kb_guidance_applied}
                                kbTraceCount={section.kb_trace_count}
                                onFeedback={handleClassificationFeedback}
                            />
                        )}

                        {editingSection !== section.id && (
                            <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t">
                                <button
                                    onClick={function() { handleApprove(section.id); }}
                                    className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
                                >
                                    Approve
                                </button>
                                <button
                                    onClick={function() {
                                        setEditingSection(section.id);
                                        setEditText(displayContent);
                                    }}
                                    className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                                >
                                    Edit
                                </button>
                                <button
                                    onClick={function() { handleRejectRegenerate(section.id); }}
                                    className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
                                >
                                    Reject + Regenerate
                                </button>
                            </div>
                        )}
                    </div>
                );
            })}

            {reviewStatus && reviewStatus.export_eligible && (
                <div className="bg-white rounded-lg shadow p-6 mb-6">
                    <h3 className="text-lg font-semibold text-[#1a365d] mb-4">Export Draft</h3>
                    <div className="flex gap-3 mb-4">
                        <button
                            onClick={function() { handleExport('json'); }}
                            className="bg-[#1a365d] text-white px-4 py-2 rounded"
                        >
                            Export as JSON
                        </button>
                        <button
                            onClick={function() { handleExport('txt'); }}
                            className="bg-[#1a365d] text-white px-4 py-2 rounded"
                        >
                            Export as TXT
                        </button>
                    </div>
                    {exportHistory.length > 0 && (
                        <div>
                            <h4 className="font-medium text-gray-700 mb-2">Export History</h4>
                            <ul className="text-sm text-gray-600 space-y-1">
                                {exportHistory.map(function(exp) {
                                    return (
                                        <li key={exp.id}>
                                            {exp.export_format.toUpperCase()} · {exp.exported_by} · {new Date(exp.created_at).toLocaleString()}
                                        </li>
                                    );
                                })}
                            </ul>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

function DocumentProvenancePanel({ caseId, document, onClose, onReplace }) {
    const [detail, setDetail] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [replacing, setReplacing] = React.useState(false);
    const [replaceFile, setReplaceFile] = React.useState(null);
    const [replaceStatus, setReplaceStatus] = React.useState(null);

    React.useEffect(function() {
        window.V2ApiService.getDocumentDetail(caseId, document.id)
            .then(function(data) {
                setDetail(data);
                setLoading(false);
            })
            .catch(function() { setLoading(false); });
    }, [document.id]);

    return (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center
                        justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl
                            max-h-screen overflow-y-auto p-6">
                <div className="flex justify-between items-start mb-4">
                    <h3 className="text-lg font-semibold text-gray-800">
                        Document Provenance
                    </h3>
                    <button onClick={onClose}
                        className="text-gray-400 hover:text-gray-600 text-xl">
                        ✕
                    </button>
                </div>

                <p className="text-sm font-medium text-gray-700 mb-4 truncate">
                    {document.original_name}
                </p>

                {loading && (
                    <p className="text-sm text-gray-400">Loading provenance...</p>
                )}

                {!loading && detail && (
                    <div className="space-y-4">

                        {/* Extraction Diagnostics */}
                        <div className="border rounded-lg p-4 bg-gray-50">
                            <h4 className="text-sm font-semibold text-gray-700 mb-3">
                                Extraction Diagnostics
                            </h4>
                            <div className="grid grid-cols-2 gap-2 text-sm">
                                <span className="text-gray-500">Extraction Method</span>
                                <span className="font-medium">
                                    {extractionMethodLabel(detail.extraction_method)}
                                </span>
                                <span className="text-gray-500">Confidence</span>
                                <span className="font-medium">
                                    {detail.extraction_confidence != null
                                        ? Math.round(detail.extraction_confidence * 100) + '%'
                                        : '—'}
                                </span>
                                <span className="text-gray-500">Text Density</span>
                                <span className="font-medium">
                                    {detail.text_density != null
                                        ? detail.text_density.toFixed(3)
                                        : '—'}
                                </span>
                                <span className="text-gray-500">Integrity</span>
                                <span className={'font-medium ' +
                                    (detail.integrity_status === 'passed'
                                        ? 'text-green-600'
                                        : detail.integrity_status === 'passed_ocr'
                                            ? 'text-yellow-600'
                                            : detail.integrity_status === 'pending'
                                                ? 'text-gray-400'
                                                : 'text-red-600')}>
                                    {detail.integrity_status || '—'}
                                </span>
                                <span className="text-gray-500">Pages</span>
                                <span className="font-medium">
                                    {detail.page_count || '—'}
                                </span>
                            </div>
                        </div>

                        {/* Participation */}
                        <div className="border rounded-lg p-4 bg-gray-50">
                            <h4 className="text-sm font-semibold text-gray-700 mb-3">
                                Participation
                            </h4>
                            <div className="grid grid-cols-2 gap-2 text-sm">
                                <span className="text-gray-500">State</span>
                                <span className={'inline-block px-2 py-0.5 rounded text-xs font-medium ' +
                                    participationBadgeClass(detail.participation_state)}>
                                    {participationLabel(detail.participation_state)}
                                </span>
                                <span className="text-gray-500">Retrieval</span>
                                <span className={detail.retrieval_eligible
                                    ? 'text-green-600 font-medium'
                                    : 'text-red-600 font-medium'}>
                                    {detail.retrieval_eligible ? 'Eligible' : 'Excluded'}
                                </span>
                                <span className="text-gray-500">Generation</span>
                                <span className={detail.generation_eligible
                                    ? 'text-green-600 font-medium'
                                    : 'text-red-600 font-medium'}>
                                    {detail.generation_eligible ? 'Eligible' : 'Excluded'}
                                </span>
                            </div>
                        </div>

                        {/* Evidence Excerpts */}
                        <div className="border rounded-lg p-4 bg-blue-50">
                            <h4 className="text-sm font-semibold text-gray-700 mb-3">
                                Evidence Excerpts
                            </h4>
                            <div className="grid grid-cols-2 gap-2 text-sm">
                                <span className="text-gray-500">
                                    Evidence Excerpts
                                </span>
                                <span className="font-medium">
                                    {detail.evidence_excerpt_count != null ? detail.evidence_excerpt_count : '—'}
                                </span>
                                <span className="text-gray-500">
                                    Classifications
                                </span>
                                <span className="font-medium">
                                    {detail.classification_count != null ? detail.classification_count : '—'}
                                </span>
                            </div>
                        </div>

                        {/* Draft Section Contributions */}
                        <div className="border rounded-lg p-4 bg-green-50">
                            <h4 className="text-sm font-semibold text-gray-700 mb-3">
                                Draft Section Contributions
                            </h4>
                            {detail.draft_section_contributions &&
                             detail.draft_section_contributions.length > 0 ? (
                                <div className="flex flex-wrap gap-2">
                                    {detail.draft_section_contributions.map(
                                        function(section) {
                                            return (
                                                <span key={section}
                                                    className="px-2 py-1 bg-green-100
                                                               text-green-800 rounded
                                                               text-xs font-medium capitalize">
                                                    {section.replace('_', ' ')}
                                                </span>
                                            );
                                        }
                                    )}
                                </div>
                            ) : (
                                <div className="text-sm text-gray-500">
                                    <p className="font-medium">No draft participation</p>
                                    {detail.integrity_status &&
                                     detail.integrity_status.startsWith('failed') && (
                                        <p className="text-red-500 mt-1">
                                            Reason: ingestion integrity failed
                                        </p>
                                    )}
                                    {!detail.retrieval_eligible && (
                                        <p className="text-red-500 mt-1">
                                            Reason: excluded from retrieval
                                        </p>
                                    )}
                                    {detail.retrieval_eligible &&
                                     detail.evidence_excerpt_count === 0 && (
                                        <p className="text-gray-400 mt-1">
                                            Reason: no eligible evidence excerpts
                                        </p>
                                    )}
                                </div>
                            )}
                        </div>

                        {(detail.participation_state === 'ingestion_failed' ||
                          (detail.integrity_status && detail.integrity_status.startsWith('failed'))) && (
                            <div className="border rounded-lg p-4 bg-red-50 mt-4">
                                <h4 className="text-sm font-semibold text-red-700 mb-2">
                                    Ingestion Failed — Action Required
                                </h4>
                                <p className="text-xs text-red-600 mb-3">
                                    This document could not be processed and is excluded from
                                    retrieval and generation. Common causes: scanned image-only PDF,
                                    corrupted text layer, or encoding issues.
                                </p>
                                <p className="text-xs text-gray-600 mb-3">
                                    To fix: upload a text-searchable version of the same document.
                                    The original will remain in the audit trail.
                                </p>

                                {!replacing && (
                                    <button
                                        onClick={function() { setReplacing(true); }}
                                        className="text-sm px-3 py-1.5 bg-red-600 text-white
                                                   rounded hover:bg-red-700">
                                        Replace Document
                                    </button>
                                )}

                                {replacing && (
                                    <div className="space-y-2">
                                        <input
                                            type="file"
                                            accept=".pdf,.docx,.txt"
                                            onChange={function(e) {
                                                setReplaceFile(e.target.files[0] || null);
                                            }}
                                            className="text-sm text-gray-600"
                                        />
                                        <div className="flex gap-2">
                                            <button
                                                onClick={async function() {
                                                    if (!replaceFile) return;
                                                    setReplaceStatus('uploading');
                                                    try {
                                                        const result = await window.V2ApiService
                                                            .replaceDocument(caseId, document.id, replaceFile);
                                                        if (result && result.document_id) {
                                                            setReplaceStatus('success');
                                                            setReplacing(false);
                                                            setReplaceFile(null);
                                                            if (onReplace) onReplace();
                                                        } else {
                                                            setReplaceStatus('error');
                                                        }
                                                    } catch(e) {
                                                        setReplaceStatus('error');
                                                    }
                                                }}
                                                disabled={!replaceFile || replaceStatus === 'uploading'}
                                                className="text-sm px-3 py-1.5 bg-red-600 text-white
                                                           rounded hover:bg-red-700 disabled:opacity-50">
                                                {replaceStatus === 'uploading' ? 'Uploading...' : 'Upload Replacement'}
                                            </button>
                                            <button
                                                onClick={function() {
                                                    setReplacing(false);
                                                    setReplaceFile(null);
                                                    setReplaceStatus(null);
                                                }}
                                                className="text-sm px-3 py-1.5 bg-gray-200 text-gray-700
                                                           rounded hover:bg-gray-300">
                                                Cancel
                                            </button>
                                        </div>
                                        {replaceStatus === 'success' && (
                                            <p className="text-xs text-green-600">
                                                Replacement uploaded. Classify the new document to include
                                                it in generation.
                                            </p>
                                        )}
                                        {replaceStatus === 'error' && (
                                            <p className="text-xs text-red-600">
                                                Upload failed. Check the file and try again.
                                            </p>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}

                    </div>
                )}

                {!loading && !detail && (
                    <p className="text-sm text-red-500">
                        Could not load provenance details.
                    </p>
                )}
            </div>
        </div>
    );
}

function CaseDashboard({ caseId, setCaseId, visaType, setVisaType, onReviewDraft, onBack }) {
    const [existingCases, setExistingCases] = useState([]);
    const [caseSearch, setCaseSearch] = useState('');
    const [casesLoading, setCasesLoading] = useState(false);
    const [workflow, setWorkflow] = useState(null);
    const [documents, setDocuments] = useState([]);
    const [coverage, setCoverage] = useState(null);
    const [invariantsOk, setInvariantsOk] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    const [generating, setGenerating] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [classifyingId, setClassifyingId] = useState(null);
    const [selectedFile, setSelectedFile] = useState(null);
    const [kbTitle, setKbTitle] = useState('');
    const [kbDocumentType, setKbDocumentType] = useState('style_guide');
    const [kbFile, setKbFile] = useState(null);
    const [kbUploading, setKbUploading] = useState(false);
    const [newCaseRef, setNewCaseRef] = useState('');
    const [localCaseId, setLocalCaseId] = useState(caseId || '');
    const [localVisaType, setLocalVisaType] = useState(visaType || 'EB2');
    const [provenanceDoc, setProvenanceDoc] = useState(null);

    useEffect(function() {
        setLocalCaseId(caseId || '');
    }, [caseId]);

    useEffect(function() {
        setLocalVisaType(visaType || 'EB2');
    }, [visaType]);

    const activeCaseId = caseId || localCaseId;

    const loadCases = async function() {
        if (!window.V2ApiService.getToken()) return;
        setCasesLoading(true);
        try {
            const data = await window.V2ApiService.listCases();
            setExistingCases(data.cases || []);
        } catch (err) {
            setMessage('Case retrieval failed: ' + err.message);
        } finally {
            setCasesLoading(false);
        }
    };

    useEffect(function() {
        loadCases();
    }, []);

    const loadState = async function() {
        if (!activeCaseId) return;
        setLoading(true);
        setError('');
        try {
            const wf = await window.V2ApiService.getWorkflowState(activeCaseId);
            setWorkflow(wf);
            const docs = await window.V2ApiService.listCaseDocuments(activeCaseId);
            setDocuments(docs.documents || []);
            try {
                const coverageData = await window.V2ApiService.getCoverage(activeCaseId, localVisaType || visaType || 'EB2');
                setCoverage(coverageData);
            } catch (coverageErr) {
                setCoverage(null);
            }
            const inv = await window.V2ApiService.getInvariants();
            const allOk = Object.values(inv.checks || {}).every(function(c) {
                return c.status === 'ok';
            });
            setInvariantsOk(allOk);
        } catch (err) {
            setError(err.message || 'Failed to load workflow state');
        } finally {
            setLoading(false);
        }
    };

    useEffect(function() {
        if (activeCaseId) {
            loadState();
            const interval = setInterval(loadState, 30000);
            return function() { clearInterval(interval); };
        }
    }, [activeCaseId]);

    const handleApplyCase = function() {
        if (!localCaseId.trim()) {
            setMessage('Enter a case ID.');
            return;
        }
        setCaseId(localCaseId.trim());
        setVisaType(localVisaType);
        setMessage('');
    };

    const handleSelectCase = function(selectedCase) {
        setCaseId(selectedCase.id);
        setLocalCaseId(selectedCase.id);
        setVisaType(selectedCase.visa_type);
        setLocalVisaType(selectedCase.visa_type);
        setMessage('');
    };

    const handleCreateCase = async function() {
        if (!newCaseRef.trim()) {
            setMessage('Enter a case reference.');
            return;
        }
        setLoading(true);
        setError('');
        try {
            const created = await window.V2ApiService.createCase({
                case_ref: newCaseRef.trim(),
                visa_type: localVisaType,
            });
            setCaseId(created.id);
            setLocalCaseId(created.id);
            setVisaType(created.visa_type);
            setMessage('Case created.');
        } catch (err) {
            setMessage('Create case failed: ' + err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleUploadDocument = async function() {
        if (!activeCaseId) {
            setMessage('Load or create a case before uploading.');
            return;
        }
        if (!selectedFile) {
            setMessage('Choose a document to upload.');
            return;
        }
        setUploading(true);
        setMessage('');
        try {
            const uploaded = await window.V2ApiService.uploadDocument(activeCaseId, selectedFile);
            setSelectedFile(null);
            setMessage('Uploaded ' + uploaded.original_name + '.');
            await loadState();
        } catch (err) {
            setMessage('Upload failed: ' + err.message);
        } finally {
            setUploading(false);
        }
    };

    const handleClassifyDocument = async function(documentId) {
        setClassifyingId(documentId);
        setMessage('');
        try {
            const versionsData = await window.V2ApiService.listDocumentVersions(activeCaseId, documentId);
            const versions = versionsData.versions || [];
            if (versions.length === 0) {
                setMessage('No document version found to classify.');
                return;
            }
            const latest = versions[versions.length - 1];
            const result = await window.V2ApiService.classifyVersion(activeCaseId, {
                document_id: documentId,
                version_id: latest.id,
                visa_type: localVisaType || visaType || 'EB2',
                force_reclassify: false,
            });
            setMessage('Classification completed: ' + result.classifications_created + ' classifications created.');
            await loadState();
        } catch (err) {
            setMessage('Classification failed: ' + err.message);
        } finally {
            setClassifyingId(null);
        }
    };

    const handleIngestKB = async function(kbDocumentId) {
        try {
            const result = await window.V2ApiService.ingestKBDocument(kbDocumentId);
            if (result && (result.status === 'queued' || result.job_id)) {
                setMessage('KB document queued for ingestion. Checking status...');
                var attempts = 0;
                var poll = setInterval(async function() {
                    attempts++;
                    try {
                        var docs = await window.V2ApiService.listKBDocuments();
                        var doc = (docs || []).find(function(d) {
                            return d.id === kbDocumentId ||
                                   d.kb_document_id === kbDocumentId;
                        });
                        if (doc && doc.lifecycle_state === 'indexed') {
                            clearInterval(poll);
                            setMessage('KB document indexed successfully.');
                            await loadState();
                        } else if (attempts >= 20) {
                            clearInterval(poll);
                            setMessage('Ingestion is taking longer than expected. Refresh to check status.');
                            await loadState();
                        }
                    } catch(e) {
                        clearInterval(poll);
                        await loadState();
                    }
                }, 3000);
            } else if (result && result.lifecycle_state === 'indexed') {
                setMessage('KB document indexed successfully.');
                await loadState();
            } else {
                setMessage('Ingest response: ' + JSON.stringify(result));
                await loadState();
            }
        } catch (err) {
            setMessage('KB ingest failed: ' + err.message);
        }
    };

    const handleUploadKB = async function() {
        if (!kbTitle.trim()) {
            setMessage('Enter a KB document title.');
            return;
        }
        if (!kbFile) {
            setMessage('Choose a KB document to upload.');
            return;
        }
        setKbUploading(true);
        setMessage('');
        try {
            const uploaded = await window.V2ApiService.uploadKBDocument(
                kbTitle.trim(),
                kbDocumentType,
                kbFile
            );
            setKbTitle('');
            setKbDocumentType('style_guide');
            setKbFile(null);
            setMessage('Uploaded KB document: ' + uploaded.title + '.');
            await loadState();
        } catch (err) {
            setMessage('KB upload failed: ' + err.message);
        } finally {
            setKbUploading(false);
        }
    };

    const handleGenerate = async function() {
        if (!documents || documents.length === 0) {
            setMessage('No documents available for generation.');
            return;
        }
        const indexed = documents.find(function(d) {
            return d.lifecycle_state === 'indexed';
        });
        if (!indexed) {
            setMessage('No indexed documents available. Index documents before generating.');
            return;
        }
        setGenerating(true);
        try {
            await window.V2ApiService.generateDraft(activeCaseId, {
                document_id: indexed.id,
                visa_type: localVisaType || visaType || 'EB2',
                force_generate: true,
            });
            setMessage('Draft generation started.');
            await loadState();
        } catch (err) {
            setMessage('Generation failed: ' + err.message);
        } finally {
            setGenerating(false);
        }
    };

    if (!activeCaseId) {
        const filteredCases = existingCases.filter(function(existingCase) {
            const needle = caseSearch.toLowerCase();
            return (
                existingCase.case_ref.toLowerCase().indexOf(needle) !== -1 ||
                existingCase.id.toLowerCase().indexOf(needle) !== -1 ||
                existingCase.visa_type.toLowerCase().indexOf(needle) !== -1
            );
        });

        return (
            <div className="max-w-5xl mx-auto p-6">
                <h1 className="text-2xl font-bold text-[#1a365d] mb-6">Case Dashboard</h1>
                <div className="bg-white rounded-lg shadow p-6 space-y-4">
                    <div className="border-b pb-4">
                        <div className="flex items-center justify-between gap-3 mb-3">
                            <h2 className="text-lg font-semibold text-[#1a365d]">Existing Cases</h2>
                            <button
                                onClick={loadCases}
                                className="bg-gray-200 px-3 py-1 rounded text-sm hover:bg-gray-300"
                            >
                                {casesLoading ? 'Loading...' : 'Refresh Cases'}
                            </button>
                        </div>
                        <input
                            type="text"
                            value={caseSearch}
                            onChange={function(e) { setCaseSearch(e.target.value); }}
                            className="w-full p-2 border rounded mb-3"
                            placeholder="Search by case reference, visa type, or case ID"
                        />
                        {filteredCases.length === 0 ? (
                            <p className="text-sm text-gray-500">
                                {casesLoading ? 'Loading cases...' : 'No existing cases found for this firm.'}
                            </p>
                        ) : (
                            <div className="max-h-72 overflow-auto border rounded">
                                {filteredCases.map(function(existingCase) {
                                    return (
                                        <button
                                            key={existingCase.id}
                                            onClick={function() { handleSelectCase(existingCase); }}
                                            className="w-full text-left p-3 border-b last:border-0 hover:bg-blue-50"
                                        >
                                            <span className="font-medium text-gray-900">{existingCase.case_ref}</span>
                                            <span className="ml-2 text-xs px-2 py-1 rounded bg-gray-100 text-gray-700">{existingCase.visa_type}</span>
                                            <span className="ml-2 text-xs px-2 py-1 rounded bg-green-50 text-green-700">{existingCase.status}</span>
                                            <span className="block text-xs text-gray-500 mt-1">{existingCase.id}</span>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Case ID</label>
                        <input
                            type="text"
                            value={localCaseId}
                            onChange={function(e) { setLocalCaseId(e.target.value); }}
                            className="w-full p-2 border rounded"
                            placeholder="129ecb0a-86d0-451c-a447-cc7bb5ab8269"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Visa Type</label>
                        <select
                            value={localVisaType}
                            onChange={function(e) { setLocalVisaType(e.target.value); }}
                            className="w-full p-2 border rounded"
                        >
                            <option value="EB2">EB2</option>
                            <option value="EB1">EB1</option>
                        </select>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <button
                            onClick={handleApplyCase}
                            className="bg-[#1a365d] text-white px-4 py-2 rounded"
                        >
                            Load Existing Case
                        </button>
                    </div>
                    <div className="border-t pt-4">
                        <label className="block text-sm font-medium text-gray-700 mb-1">New Case Reference</label>
                        <div className="flex flex-wrap gap-2">
                            <input
                                type="text"
                                value={newCaseRef}
                                onChange={function(e) { setNewCaseRef(e.target.value); }}
                                className="flex-1 min-w-[220px] p-2 border rounded"
                                placeholder="Client or matter reference"
                            />
                            <button
                                onClick={handleCreateCase}
                                className="bg-green-700 text-white px-4 py-2 rounded"
                            >
                                Create Case
                            </button>
                        </div>
                    </div>
                    {message && <p className="text-sm text-red-600">{message}</p>}
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-5xl mx-auto p-6">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-[#1a365d]">Case Dashboard</h1>
                    <p className="text-sm text-gray-600">Case: {activeCaseId} · Visa: {visaType || localVisaType || '—'}</p>
                </div>
                <div className="flex gap-2">
                    <button onClick={loadState} className="bg-gray-200 px-4 py-2 rounded hover:bg-gray-300">
                        Refresh
                    </button>
                </div>
            </div>

            <div className="mb-4 flex items-center gap-2">
                {invariantsOk === true && (
                    <span className="text-green-700 font-medium">✓ All invariants OK</span>
                )}
                {invariantsOk === false && (
                    <span className="text-red-700 font-medium">⚠ Invariant violation detected</span>
                )}
            </div>

            {message && <p className="mb-4 text-sm text-blue-700 bg-blue-50 p-2 rounded">{message}</p>}
            {error && <p className="mb-4 text-sm text-red-700 bg-red-50 p-2 rounded">{error}</p>}
            {loading && !workflow && <p className="text-gray-600">Loading...</p>}

            {workflow && (
                <div>
                    <div className="bg-white rounded-lg shadow p-6 mb-6">
                        <h2 className="text-lg font-semibold mb-4">Upload & Classify Evidence</h2>
                        <div className="flex flex-wrap gap-2 mb-4">
                            <input
                                type="file"
                                onChange={function(e) { setSelectedFile(e.target.files[0]); }}
                                className="flex-1 min-w-[220px] p-2 border rounded"
                            />
                            <button
                                onClick={handleUploadDocument}
                                disabled={uploading}
                                className="bg-[#1a365d] text-white px-4 py-2 rounded disabled:opacity-50"
                            >
                                {uploading ? 'Uploading...' : 'Upload Document'}
                            </button>
                        </div>
                        <p className="text-xs text-gray-500">
                            Upload creates the document version used for classification, coverage, and draft generation.
                        </p>
                    </div>

                    <div className="bg-white rounded-lg shadow p-6 mb-6">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-lg font-semibold">Documents</h2>
                            <button
                                onClick={handleGenerate}
                                disabled={generating}
                                className="bg-[#1a365d] text-white px-4 py-2 rounded disabled:opacity-50"
                            >
                                {generating ? 'Generating...' : 'Generate Draft'}
                            </button>
                        </div>
                        {documents.length === 0 ? (
                            <p className="text-gray-500 text-sm">No documents uploaded.</p>
                        ) : documents.map(function(doc) {
                            return (
                                <div key={doc.id} className="flex justify-between items-center gap-3 py-2 border-b last:border-0">
                                    <div className="flex flex-wrap items-center gap-y-1">
                                        <span className="text-sm">{doc.original_name}</span>
                                        <span className={'ml-1 text-xs px-2 py-1 rounded ' + lifecycleBadgeClass(doc.lifecycle_state)}>
                                            {doc.lifecycle_state}
                                        </span>
                                        <span className={'ml-1 text-xs px-2 py-1 rounded ' +
                                            participationBadgeClass(doc.participation_state)}>
                                            {participationLabel(doc.participation_state)}
                                        </span>
                                        <span className="ml-2 text-xs text-gray-400">
                                            {extractionMethodLabel(doc.extraction_method)}
                                        </span>
                                        <span className="ml-2 text-xs text-gray-400">
                                            {doc.evidence_excerpt_count || 0} Evidence Excerpts
                                        </span>
                                        <span className="ml-2 text-xs text-gray-500">{doc.version_count} version{doc.version_count === 1 ? '' : 's'}</span>
                                        <button
                                            onClick={function() { setProvenanceDoc(doc); }}
                                            className="ml-2 text-xs text-blue-600 hover:text-blue-800 underline">
                                            View Provenance
                                        </button>
                                    </div>
                                    <button
                                        onClick={function() { handleClassifyDocument(doc.id); }}
                                        disabled={classifyingId === doc.id}
                                        className="text-sm bg-blue-600 text-white px-3 py-1 rounded disabled:opacity-50 shrink-0"
                                    >
                                        {classifyingId === doc.id ? 'Classifying...' : 'Classify'}
                                    </button>
                                </div>
                            );
                        })}
                        {provenanceDoc && (
                            <DocumentProvenancePanel
                                caseId={activeCaseId}
                                document={provenanceDoc}
                                onClose={function() { setProvenanceDoc(null); }}
                                onReplace={function() {
                                    setProvenanceDoc(null);
                                    loadState();
                                }}
                            />
                        )}
                    </div>

                    <div className="bg-white rounded-lg shadow p-6 mb-6">
                        <h2 className="text-lg font-semibold mb-4">Coverage</h2>
                        {coverage && coverage.coverage ? (
                            <div>
                                <p className="text-sm mb-3">
                                    Overall status: <span className="font-medium">{coverage.overall_status}</span>
                                </p>
                                {coverage.coverage.map(function(item) {
                                    return (
                                        <div key={item.criteria_id} className="flex justify-between py-2 border-b last:border-0">
                                            <span className="text-sm">{item.criteria_code} — {item.criteria_label}</span>
                                            <span className="text-xs text-gray-600">{item.gap_status} · {item.chunk_count} chunks</span>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <p className="text-sm text-gray-500">Classify uploaded documents to populate coverage.</p>
                        )}
                    </div>

                    <div className="bg-white rounded-lg shadow p-6 mb-6">
                        <h2 className="text-lg font-semibold mb-4">KB Documents</h2>
                        <div className="border rounded p-4 mb-4 bg-gray-50">
                            <h3 className="text-sm font-semibold text-gray-800 mb-3">Upload KB Guidance</h3>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
                                <input
                                    type="text"
                                    value={kbTitle}
                                    onChange={function(e) { setKbTitle(e.target.value); }}
                                    className="p-2 border rounded text-sm"
                                    placeholder="Title, e.g. Firm style guide"
                                />
                                <select
                                    value={kbDocumentType}
                                    onChange={function(e) { setKbDocumentType(e.target.value); }}
                                    className="p-2 border rounded text-sm"
                                >
                                    <option value="style_guide">Style guide</option>
                                    <option value="firm_convention">Firm convention</option>
                                    <option value="precedent_letter">Precedent letter</option>
                                </select>
                                <input
                                    type="file"
                                    onChange={function(e) { setKbFile(e.target.files[0]); }}
                                    className="p-2 border rounded text-sm bg-white"
                                />
                            </div>
                            <button
                                onClick={handleUploadKB}
                                disabled={kbUploading}
                                className="bg-purple-700 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
                            >
                                {kbUploading ? 'Uploading KB...' : 'Upload KB Document'}
                            </button>
                            <p className="text-xs text-gray-500 mt-2">
                                KB documents feed firm style guidance. After upload, click Ingest to make them available.
                            </p>
                        </div>
                        {workflow.kb_documents.length === 0 ? (
                            <p className="text-gray-500 text-sm">No KB documents.</p>
                        ) : workflow.kb_documents.map(function(kb) {
                            return (
                                <div key={kb.kb_document_id} className="flex justify-between items-center py-2 border-b last:border-0">
                                    <div>
                                        <span className="text-sm font-medium">{kb.title}</span>
                                        <span className={'ml-2 text-xs px-2 py-1 rounded ' + lifecycleBadgeClass(kb.lifecycle_state)}>
                                            {kb.lifecycle_state}
                                        </span>
                                        <span className="ml-2 text-xs text-gray-500">{kb.chunk_count} chunks</span>
                                    </div>
                                    {kb.lifecycle_state !== 'indexed' && (
                                        <button
                                            onClick={function() { handleIngestKB(kb.kb_document_id); }}
                                            className="text-sm bg-[#1a365d] text-white px-3 py-1 rounded"
                                        >
                                            Ingest
                                        </button>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    <div className="bg-white rounded-lg shadow p-6">
                        <h2 className="text-lg font-semibold mb-4">Drafts</h2>
                        {workflow.drafts.length === 0 ? (
                            <p className="text-gray-500 text-sm">No drafts yet.</p>
                        ) : workflow.drafts.map(function(draft) {
                            return (
                                <div key={draft.draft_id} className="flex justify-between items-center py-3 border-b last:border-0">
                                    <div>
                                        <span className="text-sm font-medium">{draft.draft_id.slice(0, 8)}...</span>
                                        <span className="ml-2 text-xs text-gray-500">{draft.overall_status}</span>
                                        <span className="ml-2 text-xs text-gray-500">
                                            {draft.sections_approved}/{draft.section_count} approved
                                        </span>
                                    </div>
                                    <button
                                        onClick={function() {
                                            var sid = draft.draft_id || draft.id;
                                            var cid = activeCaseId;
                                            onReviewDraft(sid, cid, localVisaType || visaType || 'EB2');
                                        }}
                                        className="bg-[#1a365d] text-white px-3 py-1 rounded text-sm"
                                    >
                                        Review
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}

function JwtAuthBar() {
    const [token, setToken] = useState(window.V2ApiService.getToken() || '');
    const [firmId, setFirmId] = useState(
        (window.V2ApiService.getAuthState().lawFirmId) || '8f3e2a1b-4c5d-6e7f-8a9b-0c1d2e3f4a5b'
    );
    const [saved, setSaved] = useState(!!window.V2ApiService.getToken());

    const handleSave = function() {
        window.V2ApiService.setAuthState({ token: token.trim(), lawFirmId: firmId.trim() });
        setSaved(true);
    };

    if (saved && token) {
        return (
            <div className="bg-white border-b px-6 py-2 text-sm text-gray-600 flex justify-between items-center">
                <span>JWT configured · Firm: {firmId.slice(0, 8)}...</span>
                <button
                    onClick={function() {
                        window.V2ApiService.clearAuthState();
                        setToken('');
                        setSaved(false);
                    }}
                    className="text-red-600 underline"
                >
                    Clear token
                </button>
            </div>
        );
    }

    return (
        <div className="bg-yellow-50 border-b px-6 py-3">
            <p className="text-sm text-yellow-900 mb-2">Paste QA JWT token to authenticate API calls:</p>
            <div className="flex flex-wrap gap-2">
                <input
                    type="text"
                    value={token}
                    onChange={function(e) { setToken(e.target.value); setSaved(false); }}
                    className="flex-1 min-w-[200px] p-2 border rounded text-sm"
                    placeholder="Bearer token (without prefix)"
                />
                <input
                    type="text"
                    value={firmId}
                    onChange={function(e) { setFirmId(e.target.value); }}
                    className="w-72 p-2 border rounded text-sm"
                    placeholder="Firm ID"
                />
                <button onClick={handleSave} className="bg-[#1a365d] text-white px-4 py-2 rounded text-sm">
                    Save Token
                </button>
            </div>
        </div>
    );
}

function AttorneyWorkflowApp() {
    const [screen, setScreen] = useState('dashboard');
    const [caseId, setCaseId] = useState('');
    const [visaType, setVisaType] = useState('');
    const [reviewSession, setReviewSession] = useState(null);

    return (
        <div>
            <JwtAuthBar />
            <div className="bg-white border-b mb-4">
                <div className="max-w-5xl mx-auto px-6 py-3 flex gap-4">
                    <button
                        onClick={function() { setScreen('dashboard'); }}
                        className={screen === 'dashboard' ? 'font-bold text-[#1a365d]' : 'text-gray-600'}
                    >
                        Case Workflow
                    </button>
                </div>
            </div>

            {screen === 'dashboard' && (
                <CaseDashboard
                    caseId={caseId}
                    setCaseId={setCaseId}
                    visaType={visaType}
                    setVisaType={setVisaType}
                    onReviewDraft={function(draftIdToReview, reviewCaseId, reviewVisaType) {
                        console.log('Opening draft review:', reviewCaseId, draftIdToReview, reviewVisaType);
                        setReviewSession({
                            caseId: reviewCaseId,
                            draftId: draftIdToReview,
                            visaType: reviewVisaType || 'EB2',
                        });
                        setCaseId(reviewCaseId);
                        setVisaType(reviewVisaType || 'EB2');
                        setScreen('review');
                    }}
                />
            )}

            {screen === 'review' && reviewSession && (
                <DraftReviewScreen
                    caseId={reviewSession.caseId}
                    draftId={reviewSession.draftId}
                    visaType={reviewSession.visaType}
                    onBack={function() {
                        setReviewSession(null);
                        setScreen('dashboard');
                    }}
                />
            )}
        </div>
    );
}

window.AttorneyWorkflowApp = AttorneyWorkflowApp;
