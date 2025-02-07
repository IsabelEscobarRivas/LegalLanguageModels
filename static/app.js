const { useState, useRef, useEffect } = React;

const DocumentIngestion = () => {
    const [caseId, setCaseId] = useState('');
    const [visaType, setVisaType] = useState('');
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
        if (!selectedFile || !caseId || !visaType || !category) {
            setUploadStatus('Please fill in all fields and select a file');
            return;
        }

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('case_id', caseId);
        formData.append('visa_type', visaType);
        formData.append('category', category);

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

                {/* File Upload Section LAST */}
                {category && (
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

ReactDOM.render(<DocumentIngestion />, document.getElementById("root"));