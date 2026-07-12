import React, { useState, useEffect, useRef } from 'react';
import { 
  Image as ImageIcon, 
  Search, 
  Users, 
  Copy, 
  Settings as SettingsIcon, 
  Sparkles, 
  RefreshCw, 
  Upload, 
  Trash2, 
  X, 
  Calendar, 
  Folder, 
  MapPin, 
  Tag, 
  Check, 
  ExternalLink,
  ChevronRight,
  Info
} from 'lucide-react';

const API_URL = 'http://localhost:8000/api/v1';

export default function App() {
  const [activeTab, setActiveTab] = useState('gallery');
  const [photos, setPhotos] = useState([]);
  const [totalPhotos, setTotalPhotos] = useState(0);
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [photoDetail, setPhotoDetail] = useState(null);
  const [categories, setCategories] = useState([
    { id: 'all', name: 'All Photos' },
    { id: 'document', name: 'Documents' },
    { id: 'receipt', name: 'Receipts' },
    { id: 'prescription', name: 'Prescriptions' },
    { id: 'travel', name: 'Travel' },
    { id: 'pets', name: 'Pets' },
    { id: 'people', name: 'People' },
    { id: 'other', name: 'Others' }
  ]);
  const [selectedCategory, setSelectedCategory] = useState('all');
  
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searchPlan, setSearchPlan] = useState(null);
  const [isSearching, setIsSearching] = useState(false);

  // People state
  const [people, setPeople] = useState([]);
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [personPhotos, setPersonPhotos] = useState([]);
  const [editingPersonId, setEditingPersonId] = useState(null);
  const [editingName, setEditingName] = useState('');
  const [isClustering, setIsClustering] = useState(false);

  // Duplicates state
  const [exactDuplicates, setExactDuplicates] = useState([]);
  const [nearDuplicates, setNearDuplicates] = useState([]);
  const [nearThreshold, setNearThreshold] = useState(6);
  const [isScanningDuplicates, setIsScanningDuplicates] = useState(false);

  // Settings / Sync State
  const [isGoogleConnected, setIsGoogleConnected] = useState(false);
  const [syncStatus, setSyncStatus] = useState({ local: 'idle', google: 'idle' });
  const fileInputRef = useRef(null);

  // Extract Google Photos tokens from callback URL redirect
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const refreshToken = params.get('refresh_token');
    
    if (token) {
      localStorage.setItem('google_access_token', token);
      if (refreshToken) {
        localStorage.setItem('google_refresh_token', refreshToken);
      }
      setIsGoogleConnected(true);
      
      // Clean query params from address bar for security
      window.history.replaceState({}, document.title, window.location.pathname);
      alert("Successfully connected Google Photos!");
    }
  }, []);

  // Load photos on mount and category change
  useEffect(() => {
    loadPhotos();
  }, [selectedCategory]);

  useEffect(() => {
    if (activeTab === 'people') {
      loadPeople();
    } else if (activeTab === 'duplicates') {
      loadDuplicates();
    } else if (activeTab === 'settings') {
      checkGoogleStatus();
    }
  }, [activeTab]);

  // Poll sync status from the backend only while a sync is active
  useEffect(() => {
    if (syncStatus.local !== 'syncing' && syncStatus.google !== 'syncing') {
      return;
    }

    const checkStatus = async () => {
      try {
        const response = await fetch(`${API_URL}/photos/sync/status`);
        const data = await response.json();
        setSyncStatus(data);

        // Reload photos list in real-time to show new images populating
        loadPhotos();
      } catch (err) {
        console.error("Error polling sync status:", err);
      }
    };

    const intervalId = setInterval(checkStatus, 3000);

    return () => {
      clearInterval(intervalId);
    };
  }, [syncStatus.local, syncStatus.google]);

  const loadPhotos = async () => {
    try {
      const catFilter = selectedCategory === 'all' ? '' : `category=${selectedCategory}`;
      const response = await fetch(`${API_URL}/photos/?${catFilter}&limit=100`);
      const data = await response.json();
      setPhotos(data.photos);
      setTotalPhotos(data.total);
    } catch (err) {
      console.error("Error loading photos:", err);
    }
  };

  const loadPeople = async () => {
    try {
      const response = await fetch(`${API_URL}/people/`);
      const data = await response.json();
      setPeople(data);
    } catch (err) {
      console.error("Error loading people:", err);
    }
  };

  const loadDuplicates = async () => {
    setIsScanningDuplicates(true);
    try {
      const resExact = await fetch(`${API_URL}/duplicates/exact`);
      const dataExact = await resExact.json();
      setExactDuplicates(dataExact.groups);

      const resNear = await fetch(`${API_URL}/duplicates/near?threshold=${nearThreshold}`);
      const dataNear = await resNear.json();
      setNearDuplicates(dataNear.pairs);
    } catch (err) {
      console.error("Error loading duplicates:", err);
    } finally {
      setIsScanningDuplicates(false);
    }
  };

  const checkGoogleStatus = async () => {
    // Check connection offline via local storage presence
    const token = localStorage.getItem('google_access_token');
    setIsGoogleConnected(!!token);
  };

  // Photo actions
  const handlePhotoClick = async (photo) => {
    setSelectedPhoto(photo);
    setPhotoDetail(null);
    try {
      const response = await fetch(`${API_URL}/photos/${photo.id}`);
      const data = await response.json();
      setPhotoDetail(data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setSyncStatus(prev => ({ ...prev, local: 'uploading' }));
    try {
      const res = await fetch(`${API_URL}/photos/upload`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      alert("Photo uploaded successfully! Processing in background...");
      loadPhotos();
    } catch (err) {
      alert("Upload failed");
    } finally {
      setSyncStatus(prev => ({ ...prev, local: 'idle' }));
    }
  };

  const handleDeletePhoto = async (photoId) => {
    if (!confirm("Are you sure you want to delete this photo?")) return;
    try {
      await fetch(`${API_URL}/photos/${photoId}`, { method: 'DELETE' });
      setSelectedPhoto(null);
      loadPhotos();
      if (activeTab === 'duplicates') loadDuplicates();
    } catch (err) {
      alert("Failed to delete photo");
    }
  };

  // Search action
  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      const response = await fetch(`${API_URL}/search/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery })
      });
      const data = await response.json();
      setSearchResults(data.photos);
      setSearchPlan(data.search_plan);
    } catch (err) {
      console.error(err);
      alert("Search failed");
    } finally {
      setIsSearching(false);
    }
  };

  // People cluster action
  const handlePersonClick = async (person) => {
    setSelectedPerson(person);
    try {
      const response = await fetch(`${API_URL}/people/${person.id}`);
      const data = await response.json();
      setPersonPhotos(data.photos);
    } catch (err) {
      console.error(err);
    }
  };

  const handleRenamePerson = async (clusterId) => {
    if (!editingName.trim()) return;
    try {
      const response = await fetch(`${API_URL}/people/${clusterId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editingName })
      });
      setEditingPersonId(null);
      setEditingName('');
      loadPeople();
      if (selectedPerson && selectedPerson.id === clusterId) {
        setSelectedPerson(prev => ({ ...prev, name: editingName }));
      }
    } catch (err) {
      alert("Failed to rename person");
    }
  };

  const handleReclusterFaces = async () => {
    setIsClustering(true);
    try {
      await fetch(`${API_URL}/people/recluster`, { method: 'POST' });
      alert("Face clustering triggered in background!");
      setTimeout(() => {
        loadPeople();
        setIsClustering(false);
      }, 3000);
    } catch (err) {
      alert("Reclustering failed");
      setIsClustering(false);
    }
  };

  // Sync actions
  const handleLocalSync = async () => {
    setSyncStatus(prev => ({ ...prev, local: 'syncing' }));
    try {
      await fetch(`${API_URL}/photos/sync/local`, { method: 'POST' });
    } catch (err) {
      alert("Sync failed");
      setSyncStatus(prev => ({ ...prev, local: 'idle' }));
    }
  };

  const handleGoogleConnect = async () => {
    try {
      const res = await fetch(`${API_URL}/auth/google/url`);
      const data = await res.json();
      window.location.href = data.url;
    } catch (err) {
      alert("Could not load authorization URL");
    }
  };

  const handleGoogleSync = async () => {
    const token = localStorage.getItem('google_access_token');
    const refreshToken = localStorage.getItem('google_refresh_token');
    if (!token) {
      alert("Google Photos is not authenticated. Please connect your account first.");
      return;
    }
    setSyncStatus(prev => ({ ...prev, google: 'syncing' }));
    try {
      await fetch(`${API_URL}/photos/sync/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_token: token, refresh_token: refreshToken })
      });
    } catch (err) {
      alert("Sync failed");
      setSyncStatus(prev => ({ ...prev, google: 'idle' }));
    }
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <aside className="glass" style={{
        width: '280px',
        padding: '30px 20px',
        margin: '20px 0 20px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '30px',
        height: 'calc(100vh - 40px)',
        position: 'sticky',
        top: '20px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            background: 'var(--accent-gradient)',
            padding: '10px',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Sparkles size={24} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontFamily: 'var(--font-accent)', fontSize: '1.3rem', fontWeight: 700, letterSpacing: '0.5px' }}>AURA</h1>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>AI PHOTO ORGANISER</p>
          </div>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
          <button 
            className={`btn ${activeTab === 'gallery' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => { setActiveTab('gallery'); setSelectedPerson(null); }}
            style={{ justifyContent: 'flex-start', width: '100%' }}
          >
            <ImageIcon size={18} />
            <span>All Photos</span>
          </button>

          <button 
            className={`btn ${activeTab === 'search' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => { setActiveTab('search'); setSelectedPerson(null); }}
            style={{ justifyContent: 'flex-start', width: '100%' }}
          >
            <Search size={18} />
            <span>Search Planner</span>
          </button>

          <button 
            className={`btn ${activeTab === 'people' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => { setActiveTab('people'); setSelectedPerson(null); }}
            style={{ justifyContent: 'flex-start', width: '100%' }}
          >
            <Users size={18} />
            <span>Group People</span>
          </button>

          <button 
            className={`btn ${activeTab === 'duplicates' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => { setActiveTab('duplicates'); setSelectedPerson(null); }}
            style={{ justifyContent: 'flex-start', width: '100%' }}
          >
            <Copy size={18} />
            <span>Duplicates</span>
          </button>

          <button 
            className={`btn ${activeTab === 'settings' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => { setActiveTab('settings'); setSelectedPerson(null); }}
            style={{ justifyContent: 'flex-start', width: '100%' }}
          >
            <SettingsIcon size={18} />
            <span>Settings & Sync</span>
          </button>
        </nav>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <button className="btn btn-secondary" onClick={() => fileInputRef.current.click()} style={{ width: '100%' }}>
            <Upload size={16} />
            <span>Upload Photo</span>
          </button>
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleUpload} 
            accept="image/*" 
            style={{ display: 'none' }} 
          />
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textAlign: 'center' }}>
            Total photos Indexed: <strong>{totalPhotos}</strong>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main style={{ flex: 1, padding: '40px', overflowY: 'auto', height: '100vh' }}>
        
        {/* Tab 1: Gallery */}
        {activeTab === 'gallery' && !selectedPerson && (
          <div className="animate-fade">
            <header style={{ marginBottom: '35px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ fontSize: '2rem', fontWeight: 700, fontFamily: 'var(--font-accent)' }}>Library</h2>
                <p style={{ color: 'var(--text-secondary)' }}>Browse your automatically structured photo collection</p>
              </div>
              <div style={{ display: 'flex', gap: '12px' }}>
                <button className="btn btn-secondary" onClick={handleLocalSync} disabled={syncStatus.local !== 'idle'}>
                  <RefreshCw size={16} className={syncStatus.local !== 'idle' ? 'spin' : ''} />
                  <span>Scan Folder</span>
                </button>
              </div>
            </header>

            {/* Category Pills */}
            <div style={{ display: 'flex', gap: '10px', overflowX: 'auto', paddingBottom: '15px', marginBottom: '25px' }}>
              {categories.map(cat => (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  style={{
                    padding: '8px 20px',
                    borderRadius: '50px',
                    border: '1px solid',
                    borderColor: selectedCategory === cat.id ? 'var(--accent-color)' : 'var(--border-glass)',
                    background: selectedCategory === cat.id ? 'var(--accent-gradient)' : 'rgba(255,255,255,0.02)',
                    color: '#fff',
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: '0.85rem',
                    transition: 'var(--transition-smooth)'
                  }}
                >
                  {cat.name}
                </button>
              ))}
            </div>

            {/* Photo Grid */}
            {photos.length === 0 ? (
              <div className="glass" style={{ padding: '80px 20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <ImageIcon size={48} style={{ marginBottom: '15px', opacity: 0.5 }} />
                <p style={{ fontSize: '1.1rem' }}>No photos found in this category.</p>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '5px' }}>Use "Scan Folder" or upload an image to start.</p>
              </div>
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                gap: '20px'
              }}>
                {photos.map(photo => (
                  <div 
                    key={photo.id}
                    className="glass"
                    onClick={() => handlePhotoClick(photo)}
                    style={{
                      overflow: 'hidden',
                      cursor: 'pointer',
                      borderRadius: '12px',
                      aspectRatio: '1',
                      position: 'relative',
                      transition: 'var(--transition-smooth)'
                    }}
                  >
                    <img 
                      src={`${API_URL}/photos/${photo.id}/file`} 
                      alt={photo.caption} 
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      onError={(e) => {
                        e.target.src = "https://images.unsplash.com/photo-1542038784456-1ea8e935640e?q=80&w=300&auto=format&fit=crop";
                      }}
                    />
                    <div style={{
                      position: 'absolute',
                      bottom: 0,
                      left: 0,
                      right: 0,
                      background: 'linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 100%)',
                      padding: '15px 10px 10px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-end',
                      opacity: 0,
                      transition: 'opacity 0.2s ease'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.opacity = 1}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = 0}
                    >
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#fff', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', maxWidth: '80%' }}>
                        {photo.caption || 'Photo'}
                      </span>
                      <span style={{
                        background: 'rgba(255,255,255,0.2)',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontSize: '0.65rem',
                        textTransform: 'uppercase'
                      }}>
                        {photo.category}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Search Planner */}
        {activeTab === 'search' && (
          <div className="animate-fade">
            <header style={{ marginBottom: '35px' }}>
              <h2 style={{ fontSize: '2rem', fontWeight: 700, fontFamily: 'var(--font-accent)' }}>AI Search Console</h2>
              <p style={{ color: 'var(--text-secondary)' }}>Search your photos using natural language query planning</p>
            </header>

            <form onSubmit={handleSearch} style={{ display: 'flex', gap: '12px', marginBottom: '30px' }}>
              <div style={{ position: 'relative', flex: 1 }}>
                <Search style={{ position: 'absolute', left: '15px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} size={20} />
                <input 
                  type="text" 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="e.g., 'show me the receipts from my Goa trip with Rahul'" 
                  style={{ paddingLeft: '45px', fontSize: '1.05rem', borderRadius: '12px' }}
                />
              </div>
              <button type="submit" className="btn btn-primary" style={{ borderRadius: '12px', padding: '0 30px' }} disabled={isSearching}>
                {isSearching ? 'Planning...' : 'Ask AI'}
              </button>
            </form>

            {/* Display Search Plan (Structured Output) */}
            {searchPlan && (
              <div className="glass" style={{ padding: '20px', marginBottom: '30px', borderLeft: '4px solid var(--accent-color)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '15px' }}>
                  <Sparkles size={16} color="var(--accent-color)" />
                  <h4 style={{ fontWeight: 700, fontSize: '0.95rem' }}>AI Query Execution Plan</h4>
                </div>
                
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Semantic Query</span>
                    <p style={{ fontSize: '0.9rem', fontWeight: 600 }}>{searchPlan.semantic_query || 'None'}</p>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Categories Filter</span>
                    <div style={{ display: 'flex', gap: '5px', marginTop: '3px' }}>
                      {searchPlan.categories ? searchPlan.categories.map(c => (
                        <span key={c} className="glass" style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', background: 'rgba(139, 92, 246, 0.1)' }}>{c}</span>
                      )) : <p style={{ fontSize: '0.9rem', fontWeight: 600 }}>All</p>}
                    </div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>OCR Search Keyword</span>
                    <p style={{ fontSize: '0.9rem', fontWeight: 600 }}>{searchPlan.ocr_query || 'None'}</p>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Location Metadata</span>
                    <p style={{ fontSize: '0.9rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <MapPin size={14} /> {searchPlan.location || 'None'}
                    </p>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>People Cluster Names</span>
                    <p style={{ fontSize: '0.9rem', fontWeight: 600 }}>{searchPlan.person_names ? searchPlan.person_names.join(', ') : 'None'}</p>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Date range</span>
                    <p style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                      {searchPlan.date_start ? `${new Date(searchPlan.date_start).toLocaleDateString()} - ${new Date(searchPlan.date_end).toLocaleDateString()}` : 'Anytime'}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Search Results */}
            {searchResults !== null && (
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: '15px' }}>Results ({searchResults.length})</h3>
                {searchResults.length === 0 ? (
                  <div className="glass" style={{ padding: '50px 20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                    No photos matched your query parameters. Try a different search!
                  </div>
                ) : (
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                    gap: '20px'
                  }}>
                    {searchResults.map(photo => (
                      <div 
                        key={photo.id}
                        className="glass"
                        onClick={() => handlePhotoClick(photo)}
                        style={{
                          overflow: 'hidden',
                          cursor: 'pointer',
                          borderRadius: '12px',
                          aspectRatio: '1',
                          transition: 'var(--transition-smooth)'
                        }}
                      >
                        <img 
                          src={`${API_URL}/photos/${photo.id}/file`} 
                          alt={photo.caption} 
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Group People */}
        {activeTab === 'people' && !selectedPerson && (
          <div className="animate-fade">
            <header style={{ marginBottom: '35px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ fontSize: '2rem', fontWeight: 700, fontFamily: 'var(--font-accent)' }}>Grouped People</h2>
                <p style={{ color: 'var(--text-secondary)' }}>Identify and label family and friends grouped by facial recognition</p>
              </div>
              <button className="btn btn-secondary" onClick={handleReclusterFaces} disabled={isClustering}>
                <RefreshCw size={16} className={isClustering ? 'spin' : ''} />
                <span>Sync Face Clusters</span>
              </button>
            </header>

            {people.length === 0 ? (
              <div className="glass" style={{ padding: '80px 20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <Users size={48} style={{ marginBottom: '15px', opacity: 0.5 }} />
                <p style={{ fontSize: '1.1rem' }}>No face clusters identified yet.</p>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '5px' }}>Upload photos with clear human faces, then click "Sync Face Clusters".</p>
              </div>
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                gap: '20px'
              }}>
                {people.map(person => (
                  <div 
                    key={person.id}
                    className="glass"
                    style={{
                      overflow: 'hidden',
                      borderRadius: '16px',
                      cursor: 'pointer',
                      textAlign: 'center',
                      padding: '20px',
                      transition: 'var(--transition-smooth)',
                      position: 'relative'
                    }}
                    onClick={() => handlePersonClick(person)}
                  >
                    {/* Circle Face Crop */}
                    <div style={{
                      width: '100px',
                      height: '100px',
                      borderRadius: '50%',
                      overflow: 'hidden',
                      margin: '0 auto 15px',
                      border: '3px solid rgba(255,255,255,0.1)',
                      boxShadow: 'var(--shadow-glass)'
                    }}>
                      <img 
                        src={person.cover_photo_path ? `${API_URL}/photos/${person.cover_photo_id}/file` : "https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=150&auto=format&fit=crop"} 
                        alt={person.name} 
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        onError={(e) => {
                          e.target.src = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=150&auto=format&fit=crop";
                        }}
                      />
                    </div>
                    
                    {editingPersonId === person.id ? (
                      <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', gap: '5px', marginTop: '10px' }}>
                        <input 
                          type="text" 
                          value={editingName} 
                          onChange={(e) => setEditingName(e.target.value)} 
                          style={{ padding: '6px 10px', fontSize: '0.85rem' }}
                          placeholder="Name..."
                          autoFocus
                        />
                        <button className="btn btn-primary" onClick={() => handleRenamePerson(person.id)} style={{ padding: '0 10px' }}>
                          <Check size={14} />
                        </button>
                      </div>
                    ) : (
                      <div>
                        <h4 style={{ fontWeight: 600, fontSize: '1.05rem', color: '#fff' }}>{person.name}</h4>
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>{person.face_count} Photos</p>
                        <button 
                          className="btn btn-secondary" 
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingPersonId(person.id);
                            setEditingName(person.name);
                          }}
                          style={{
                            padding: '4px 10px',
                            fontSize: '0.75rem',
                            marginTop: '10px',
                            width: '100%',
                            borderRadius: '6px'
                          }}
                        >
                          Rename
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 3b: Person Photos Detail View */}
        {selectedPerson && (
          <div className="animate-fade">
            <header style={{ marginBottom: '35px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span 
                  onClick={() => setSelectedPerson(null)} 
                  style={{ color: 'var(--accent-color)', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '8px' }}
                >
                  &larr; Back to People
                </span>
                <h2 style={{ fontSize: '2rem', fontWeight: 700, fontFamily: 'var(--font-accent)' }}>Photos of {selectedPerson.name}</h2>
              </div>
            </header>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: '20px'
            }}>
              {personPhotos.map(photo => (
                <div 
                  key={photo.id}
                  className="glass"
                  onClick={() => handlePhotoClick(photo)}
                  style={{
                    overflow: 'hidden',
                    cursor: 'pointer',
                    borderRadius: '12px',
                    aspectRatio: '1',
                    transition: 'var(--transition-smooth)'
                  }}
                >
                  <img 
                    src={`${API_URL}/photos/${photo.id}/file`} 
                    alt={photo.caption} 
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 4: Duplicates */}
        {activeTab === 'duplicates' && (
          <div className="animate-fade">
            <header style={{ marginBottom: '35px' }}>
              <h2 style={{ fontSize: '2rem', fontWeight: 700, fontFamily: 'var(--font-accent)' }}>Duplicates Manager</h2>
              <p style={{ color: 'var(--text-secondary)' }}>Locate exact binary copies and visually similar near-duplicate photos</p>
            </header>

            {/* Threshold adjust for near duplicates */}
            <div className="glass" style={{ padding: '20px', marginBottom: '30px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Near-Duplicate Sensitivity:</span>
                <input 
                  type="range" 
                  min="2" 
                  max="12" 
                  value={nearThreshold} 
                  onChange={(e) => setNearThreshold(parseInt(e.target.value))}
                  style={{ width: '150px' }}
                />
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Distance &le; {nearThreshold}</span>
              </div>
              <button className="btn btn-primary" onClick={loadDuplicates} disabled={isScanningDuplicates}>
                {isScanningDuplicates ? 'Scanning...' : 'Re-scan Duplicates'}
              </button>
            </div>

            {/* Sections */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
              
              {/* Exact Duplicates */}
              <section>
                <h3 style={{ fontSize: '1.4rem', fontWeight: 600, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span>Exact Duplicates</span>
                  <span style={{ background: 'rgba(239, 68, 68, 0.15)', color: 'var(--error)', padding: '2px 10px', borderRadius: '50px', fontSize: '0.8rem' }}>{exactDuplicates.length} Groups</span>
                </h3>

                {exactDuplicates.length === 0 ? (
                  <div className="glass" style={{ padding: '30px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                    No exact duplicates found.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    {exactDuplicates.map((group, gIdx) => (
                      <div key={gIdx} className="glass" style={{ padding: '20px' }}>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '10px' }}>SHA256: {group.sha256}</div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '20px' }}>
                          {group.photos.map(p => (
                            <div key={p.id} style={{ position: 'relative' }}>
                              <img 
                                src={`${API_URL}/photos/${p.id}/file`} 
                                style={{ width: '100%', aspectRatio: '1', objectFit: 'cover', borderRadius: '8px' }}
                              />
                              <button 
                                className="btn btn-danger" 
                                onClick={() => handleDeletePhoto(p.id)}
                                style={{
                                  position: 'absolute',
                                  top: '10px',
                                  right: '10px',
                                  padding: '8px',
                                  borderRadius: '50%'
                                }}
                              >
                                <Trash2 size={14} />
                              </button>
                              <div style={{ fontSize: '0.75rem', marginTop: '5px', color: 'var(--text-secondary)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                                {p.storage_type === 'local' ? p.file_path.split('\\').pop() : 'Google Photos'}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Near Duplicates */}
              <section>
                <h3 style={{ fontSize: '1.4rem', fontWeight: 600, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span>Near Duplicates (Resized, compressed, or brightness modifications)</span>
                  <span style={{ background: 'rgba(245, 158, 11, 0.15)', color: 'var(--warning)', padding: '2px 10px', borderRadius: '50px', fontSize: '0.8rem' }}>{nearDuplicates.length} Pairs</span>
                </h3>

                {nearDuplicates.length === 0 ? (
                  <div className="glass" style={{ padding: '30px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                    No near duplicates found.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    {nearDuplicates.map((pair, pIdx) => (
                      <div key={pIdx} className="glass" style={{ padding: '20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '15px' }}>
                          <span>pHash Distance: {pair.distance} (Very High Similarity)</span>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                          
                          {/* Image 1 */}
                          <div style={{ position: 'relative' }}>
                            <img 
                              src={`${API_URL}/photos/${pair.photo1.id}/file`} 
                              style={{ width: '100%', height: '220px', objectFit: 'cover', borderRadius: '8px' }}
                            />
                            <button 
                              className="btn btn-danger" 
                              onClick={() => handleDeletePhoto(pair.photo1.id)}
                              style={{ position: 'absolute', top: '10px', right: '10px', padding: '8px', borderRadius: '50%' }}
                            >
                              <Trash2 size={14} />
                            </button>
                            <div style={{ fontSize: '0.75rem', marginTop: '5px', color: 'var(--text-secondary)' }}>
                              Path: {pair.photo1.file_path.split('\\').pop()}
                            </div>
                          </div>

                          {/* Image 2 */}
                          <div style={{ position: 'relative' }}>
                            <img 
                              src={`${API_URL}/photos/${pair.photo2.id}/file`} 
                              style={{ width: '100%', height: '220px', objectFit: 'cover', borderRadius: '8px' }}
                            />
                            <button 
                              className="btn btn-danger" 
                              onClick={() => handleDeletePhoto(pair.photo2.id)}
                              style={{ position: 'absolute', top: '10px', right: '10px', padding: '8px', borderRadius: '50%' }}
                            >
                              <Trash2 size={14} />
                            </button>
                            <div style={{ fontSize: '0.75rem', marginTop: '5px', color: 'var(--text-secondary)' }}>
                              Path: {pair.photo2.file_path.split('\\').pop()}
                            </div>
                          </div>

                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </div>
        )}

        {/* Tab 5: Settings & Sync */}
        {activeTab === 'settings' && (
          <div className="animate-fade">
            <header style={{ marginBottom: '35px' }}>
              <h2 style={{ fontSize: '2rem', fontWeight: 700, fontFamily: 'var(--font-accent)' }}>Settings & Data Sync</h2>
              <p style={{ color: 'var(--text-secondary)' }}>Manage your image storage directories and integrations</p>
            </header>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
              {/* Local File System Sync */}
              <div className="glass" style={{ padding: '30px' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '10px' }}>Local Storage Scan</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '20px' }}>
                  AURA scans the directory mounted as <strong>/photos_data</strong> in your container recursively for photos. Any new images found will automatically undergo duplicate checking, CLIP indexing, and face recognition.
                </p>
                <button className="btn btn-primary" onClick={handleLocalSync} disabled={syncStatus.local !== 'idle'}>
                  <RefreshCw size={16} className={syncStatus.local !== 'idle' ? 'spin' : ''} />
                  <span>Start Scanning Local Folder</span>
                </button>
              </div>

              {/* Google Photos Integration */}
              <div className="glass" style={{ padding: '30px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Google Photos Connection</h3>
                  <span style={{
                    padding: '4px 12px',
                    borderRadius: '50px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    background: isGoogleConnected ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                    color: isGoogleConnected ? 'var(--success)' : 'var(--error)'
                  }}>
                    {isGoogleConnected ? 'CONNECTED' : 'DISCONNECTED'}
                  </span>
                </div>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '20px' }}>
                  Link AURA to your Google Photos library to automatically import photos, download copies into the backend workspace, and scan them using local face recognition and vector models.
                </p>

                <div style={{ display: 'flex', gap: '15px' }}>
                  {!isGoogleConnected ? (
                    <button className="btn btn-primary" onClick={handleGoogleConnect}>
                      <ExternalLink size={16} />
                      <span>Authenticate Google Account</span>
                    </button>
                  ) : (
                    <>
                      <button className="btn btn-primary" onClick={handleGoogleSync} disabled={syncStatus.google !== 'idle'}>
                        <RefreshCw size={16} className={syncStatus.google !== 'idle' ? 'spin' : ''} />
                        <span>Sync Google Photos</span>
                      </button>
                      <button className="btn btn-secondary" onClick={() => {
                        localStorage.removeItem('google_access_token');
                        localStorage.removeItem('google_refresh_token');
                        setIsGoogleConnected(false);
                        alert("Disconnected Google Photos connection. Client-side credentials cleared.");
                      }}>
                        <span>Disconnect</span>
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Photo Detail Modal */}
      {selectedPhoto && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'var(--bg-modal)',
          backdropFilter: 'blur(20px)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '40px'
        }}
        onClick={() => setSelectedPhoto(null)}
        >
          <div 
            className="glass"
            style={{
              width: '100%',
              maxWidth: '1100px',
              height: 'calc(100vh - 80px)',
              display: 'flex',
              overflow: 'hidden',
              cursor: 'default'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Left Image View */}
            <div style={{
              flex: 1,
              backgroundColor: 'rgba(0,0,0,0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              padding: '20px'
            }}>
              <img 
                src={`${API_URL}/photos/${selectedPhoto.id}/file`} 
                alt={selectedPhoto.caption} 
                style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', borderRadius: '4px' }}
              />
              
              <button 
                onClick={() => setSelectedPhoto(null)}
                style={{
                  position: 'absolute',
                  top: '20px',
                  left: '20px',
                  background: 'rgba(0,0,0,0.5)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '50%',
                  padding: '10px',
                  color: '#fff',
                  cursor: 'pointer'
                }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Right Meta View */}
            <div style={{
              width: '380px',
              borderLeft: '1px solid var(--border-glass)',
              display: 'flex',
              flexDirection: 'column',
              padding: '30px',
              overflowY: 'auto'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                <span style={{
                  background: 'var(--accent-gradient)',
                  padding: '4px 12px',
                  borderRadius: '50px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  textTransform: 'uppercase'
                }}>
                  {photoDetail?.category || selectedPhoto.category}
                </span>
                <button className="btn btn-danger" onClick={() => handleDeletePhoto(selectedPhoto.id)} style={{ padding: '6px 10px', borderRadius: '6px' }}>
                  <Trash2 size={14} />
                </button>
              </div>

              <h3 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '10px' }}>{photoDetail?.caption || selectedPhoto.caption || "Image Detail"}</h3>
              
              {photoDetail?.taken_at && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '25px' }}>
                  <Calendar size={14} />
                  <span>Taken: {new Date(photoDetail.taken_at).toLocaleString()}</span>
                </div>
              )}

              {/* Extracted Faces */}
              {photoDetail?.faces && photoDetail.faces.length > 0 && (
                <div style={{ marginBottom: '25px' }}>
                  <h4 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '10px' }}>Detected People</h4>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                    {photoDetail.faces.map(f => (
                      <span 
                        key={f.id} 
                        className="glass" 
                        style={{ 
                          padding: '6px 12px', 
                          borderRadius: '8px', 
                          fontSize: '0.8rem',
                          background: 'rgba(255,255,255,0.03)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px'
                        }}
                      >
                        <Users size={12} color="var(--accent-color)" />
                        <strong>{f.person_name}</strong>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* OCR Text */}
              {photoDetail?.ocr_text && (
                <div style={{ marginBottom: '25px' }}>
                  <h4 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '10px' }}>Extracted Document Text (OCR)</h4>
                  <div style={{
                    background: 'rgba(0,0,0,0.3)',
                    border: '1px solid var(--border-glass)',
                    padding: '12px',
                    borderRadius: '8px',
                    fontSize: '0.85rem',
                    fontFamily: 'monospace',
                    maxHeight: '180px',
                    overflowY: 'auto',
                    whiteSpace: 'pre-wrap',
                    color: 'var(--text-secondary)'
                  }}>
                    {photoDetail.ocr_text}
                  </div>
                </div>
              )}

              {/* Meta properties */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: 'auto', borderTop: '1px solid var(--border-glass)', paddingTop: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Storage Type:</span>
                  <span style={{ fontWeight: 600 }}>{selectedPhoto.storage_type.toUpperCase()}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>File Path:</span>
                  <span 
                    style={{ fontWeight: 600, wordBreak: 'break-all', textAlign: 'right', maxWidth: '70%' }}
                    title={selectedPhoto.file_path}
                  >
                    {selectedPhoto.file_path.split('/').pop().split('\\').pop()}
                  </span>
                </div>
                {photoDetail?.metadata_json && Object.keys(photoDetail.metadata_json).length > 0 && (
                  <>
                    {photoDetail.metadata_json.location && (
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                        <span style={{ color: 'var(--text-muted)' }}>Location:</span>
                        <span style={{ fontWeight: 600 }}>{photoDetail.metadata_json.location}</span>
                      </div>
                    )}
                    {photoDetail.metadata_json.objects && photoDetail.metadata_json.objects.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', fontSize: '0.8rem' }}>
                        <span style={{ color: 'var(--text-muted)' }}>Detected Objects:</span>
                        <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
                          {photoDetail.metadata_json.objects.join(', ')}
                        </span>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>

          </div>
        </div>
      )}

      {/* Spinner and utility CSS */}
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        .spin {
          animation: spin 1s linear infinite;
        }
      `}</style>
    </div>
  );
}
