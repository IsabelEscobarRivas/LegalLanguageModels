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

const SECTION_ORDER = [
    'background',
    'experience',
    'expert_opinion',
    'achievements',
    'impact',
    'conclusion',
];

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

function reviewBadgeClass(action) {
    if (action === 'approved') return 'bg-green-100 text-green-800';
    if (action === 'edited') return 'bg-blue-100 text-blue-800';
    if (action === 'rejected') return 'bg-red-100 text-red-800';
    return 'bg-gray-100 text-gray-600';
}

function ProvenanceInspector({ section, traces, kbGuidanceApplied, kbTraceCount }) {
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
        try {
            const draftData = await window.V2ApiService.getDraft(caseId, draftId);
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

    const sectionsByCode = {};
    if (draft && draft.sections) {
        draft.sections.forEach(function(s) {
            sectionsByCode[s.section_code] = s;
        });
    }

    const orderedSections = SECTION_ORDER.map(function(code) {
        return sectionsByCode[code];
    }).filter(Boolean);

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

function CaseDashboard({ caseId, setCaseId, visaType, setVisaType, onReviewDraft, onBack }) {
    const [workflow, setWorkflow] = useState(null);
    const [invariantsOk, setInvariantsOk] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    const [generating, setGenerating] = useState(false);
    const [localCaseId, setLocalCaseId] = useState(caseId || '');
    const [localVisaType, setLocalVisaType] = useState(visaType || 'EB2');

    useEffect(function() {
        setLocalCaseId(caseId || '');
    }, [caseId]);

    useEffect(function() {
        setLocalVisaType(visaType || 'EB2');
    }, [visaType]);

    const activeCaseId = caseId || localCaseId;

    const loadState = async function() {
        if (!activeCaseId) return;
        setLoading(true);
        setError('');
        try {
            const wf = await window.V2ApiService.getWorkflowState(activeCaseId);
            setWorkflow(wf);
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

    const handleIngestKB = async function(kbDocumentId) {
        try {
            await window.V2ApiService.ingestKBDocument(kbDocumentId);
            setMessage('KB ingestion queued.');
            await loadState();
        } catch (err) {
            setMessage('KB ingest failed: ' + err.message);
        }
    };

    const handleGenerate = async function() {
        if (!workflow || !workflow.documents || workflow.documents.length === 0) {
            setMessage('No documents available for generation.');
            return;
        }
        const indexed = workflow.documents.find(function(d) {
            return d.lifecycle_state === 'indexed';
        });
        if (!indexed) {
            setMessage('No indexed documents available. Index documents before generating.');
            return;
        }
        setGenerating(true);
        try {
            await window.V2ApiService.generateDraft(activeCaseId, {
                document_id: indexed.document_id,
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
        return (
            <div className="max-w-5xl mx-auto p-6">
                <h1 className="text-2xl font-bold text-[#1a365d] mb-6">Case Dashboard</h1>
                <div className="bg-white rounded-lg shadow p-6 space-y-4">
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
                    <button
                        onClick={handleApplyCase}
                        className="bg-[#1a365d] text-white px-4 py-2 rounded"
                    >
                        Load Dashboard
                    </button>
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
                    <button onClick={onBack} className="bg-gray-200 px-4 py-2 rounded hover:bg-gray-300">
                        Back to Upload
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
                <>
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
                        {workflow.documents.length === 0 ? (
                            <p className="text-gray-500 text-sm">No documents uploaded.</p>
                        ) : workflow.documents.map(function(doc) {
                            return (
                                <div key={doc.document_id} className="flex justify-between items-center py-2 border-b last:border-0">
                                    <span className="text-sm">{doc.name}</span>
                                    <span className={'text-xs px-2 py-1 rounded ' + lifecycleBadgeClass(doc.lifecycle_state)}>
                                        {doc.lifecycle_state}
                                    </span>
                                </div>
                            );
                        })}
                    </div>

                    <div className="bg-white rounded-lg shadow p-6 mb-6">
                        <h2 className="text-lg font-semibold mb-4">KB Documents</h2>
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
                                        onClick={function() { onReviewDraft(draft.draft_id); }}
                                        className="bg-[#1a365d] text-white px-3 py-1 rounded text-sm"
                                    >
                                        Review
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                </>
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
    const [screen, setScreen] = useState('upload');
    const [caseId, setCaseId] = useState('');
    const [visaType, setVisaType] = useState('');
    const [draftId, setDraftId] = useState(null);

    return (
        <div>
            <JwtAuthBar />
            <div className="bg-white border-b mb-4">
                <div className="max-w-5xl mx-auto px-6 py-3 flex gap-4">
                    <button
                        onClick={function() { setScreen('upload'); }}
                        className={screen === 'upload' ? 'font-bold text-[#1a365d]' : 'text-gray-600'}
                    >
                        Document Upload
                    </button>
                    <button
                        onClick={function() { setScreen('dashboard'); }}
                        className={screen === 'dashboard' ? 'font-bold text-[#1a365d]' : 'text-gray-600'}
                    >
                        Case Dashboard
                    </button>
                </div>
            </div>

            {screen === 'upload' && (
                <DocumentIngestion
                    caseId={caseId}
                    setCaseId={setCaseId}
                    visaType={visaType}
                    setVisaType={setVisaType}
                />
            )}

            {screen === 'dashboard' && (
                <CaseDashboard
                    caseId={caseId}
                    setCaseId={setCaseId}
                    visaType={visaType}
                    setVisaType={setVisaType}
                    onReviewDraft={function(id) {
                        setDraftId(id);
                        setScreen('review');
                    }}
                    onBack={function() { setScreen('upload'); }}
                />
            )}

            {screen === 'review' && draftId && (
                <DraftReviewScreen
                    caseId={caseId}
                    draftId={draftId}
                    visaType={visaType || 'EB2'}
                    onBack={function() { setScreen('dashboard'); }}
                />
            )}
        </div>
    );
}

window.AttorneyWorkflowApp = AttorneyWorkflowApp;