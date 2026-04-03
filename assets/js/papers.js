// ============================================
// Paper Tracker Page Scripts (v3 - No AI Analysis)
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    let allPapers = [];
    let currentDirection = 'medical';
    let currentDateFilter = 'all';
    let currentSourceFilter = 'all';
    let currentSearch = '';

    // Load papers data
    async function loadPapers() {
        try {
            const response = await fetch('papers/papers_data.json');
            if (!response.ok) throw new Error('No data');
            const data = await response.json();
            allPapers = data.papers || [];
            document.getElementById('lastUpdate').textContent = data.last_updated || 'Unknown';
            renderPapers();
        } catch (e) {
            document.getElementById('papersList').innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-rocket"></i>
                    <p>Paper tracker is initializing. Papers will appear after the first automated update.</p>
                    <p style="font-size:0.82rem; margin-top:8px; color:var(--text-light);">
                        The system fetches papers daily from arXiv, bioRxiv, and top venues via GitHub Actions.
                    </p>
                </div>
            `;
            document.getElementById('lastUpdate').textContent = 'Awaiting first update';
        }
    }

    // Filter papers
    function getFilteredPapers() {
        return allPapers.filter(p => {
            if (p.direction !== currentDirection) return false;

            if (currentSourceFilter !== 'all' && p.source !== currentSourceFilter) return false;

            if (currentDateFilter !== 'all') {
                const paperDate = new Date(p.date);
                const now = new Date();
                if (currentDateFilter === 'today') {
                    if (paperDate.toDateString() !== now.toDateString()) return false;
                } else if (currentDateFilter === 'week') {
                    const weekAgo = new Date(now - 7 * 24 * 60 * 60 * 1000);
                    if (paperDate < weekAgo) return false;
                } else if (currentDateFilter === 'month') {
                    const monthAgo = new Date(now - 30 * 24 * 60 * 60 * 1000);
                    if (paperDate < monthAgo) return false;
                }
            }

            if (currentSearch) {
                const q = currentSearch.toLowerCase();
                return (p.title && p.title.toLowerCase().includes(q)) ||
                       (p.authors && p.authors.toLowerCase().includes(q)) ||
                       (p.abstract && p.abstract.toLowerCase().includes(q));
            }

            return true;
        });
    }

    // Render papers
    function renderPapers() {
        const filtered = getFilteredPapers();
        const container = document.getElementById('papersList');

        if (filtered.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-search"></i>
                    <p>No papers found for the current filters.</p>
                </div>
            `;
            return;
        }

        // Group by date
        const grouped = {};
        filtered.forEach(p => {
            const date = p.date || 'Unknown';
            if (!grouped[date]) grouped[date] = [];
            grouped[date].push(p);
        });

        let html = '';
        const dates = Object.keys(grouped).sort((a, b) => new Date(b) - new Date(a));

        dates.forEach(date => {
            const displayDate = formatDate(date);
            html += `<div class="date-separator"><i class="fas fa-calendar-day"></i> ${displayDate}</div>`;
            grouped[date].forEach(paper => {
                html += renderPaperCard(paper);
            });
        });

        container.innerHTML = html;

        // Bind click to expand abstract
        container.querySelectorAll('.paper-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (e.target.closest('.paper-link-btn')) return;
                const id = card.dataset.id;
                const paper = allPapers.find(p => p.id === id);
                if (paper) showModal(paper);
            });
        });
    }

    function renderPaperCard(paper) {
        const sourceClass = paper.source || 'arxiv';
        const sourceLabel = {
            'arxiv': 'arXiv',
            'biorxiv': 'bioRxiv',
            'conference': 'Conference',
            'journal': 'Journal'
        }[sourceClass] || paper.source;

        // Truncate abstract for preview
        const abstractPreview = paper.abstract
            ? (paper.abstract.length > 200 ? paper.abstract.substring(0, 200) + '...' : paper.abstract)
            : '';

        return `
        <div class="paper-card" data-id="${paper.id}">
            <div class="paper-meta">
                <span class="paper-source ${sourceClass}">${sourceLabel}</span>
                <span class="paper-date">${paper.date}</span>
                ${paper.venue ? `<span class="paper-direction">${paper.venue}</span>` : ''}
            </div>
            <h3 class="paper-title-text">${paper.title}</h3>
            <p class="paper-authors-text">${paper.authors || ''}</p>
            <p class="paper-abstract-preview">${abstractPreview}</p>
            <div class="paper-footer">
                <div class="paper-links">
                    ${paper.url ? `<a href="${paper.url}" target="_blank" class="paper-link-btn" onclick="event.stopPropagation()"><i class="fas fa-external-link-alt"></i> Paper</a>` : ''}
                    ${paper.pdf_url ? `<a href="${paper.pdf_url}" target="_blank" class="paper-link-btn" onclick="event.stopPropagation()"><i class="fas fa-file-pdf"></i> PDF</a>` : ''}
                </div>
                <span class="paper-click-hint"><i class="fas fa-expand-alt"></i> Click to expand</span>
            </div>
        </div>
        `;
    }

    // Show modal with full abstract
    function showModal(paper) {
        const overlay = document.getElementById('modalOverlay');
        const content = document.getElementById('modalContent');

        const sourceLabel = {
            'arxiv': 'arXiv',
            'biorxiv': 'bioRxiv',
            'conference': 'Conference',
            'journal': 'Journal'
        }[paper.source] || paper.source;

        content.innerHTML = `
            <h2>${paper.title}</h2>
            <div class="modal-meta">
                <span class="modal-meta-item"><i class="fas fa-users"></i> ${paper.authors || 'Unknown'}</span>
                <span class="modal-meta-item"><i class="fas fa-calendar"></i> ${paper.date}</span>
                <span class="modal-meta-item"><i class="fas fa-database"></i> ${sourceLabel}</span>
                ${paper.venue ? `<span class="modal-meta-item"><i class="fas fa-bookmark"></i> ${paper.venue}</span>` : ''}
            </div>
            <div class="modal-links">
                ${paper.url ? `<a href="${paper.url}" target="_blank" class="paper-link-btn"><i class="fas fa-external-link-alt"></i> View Paper</a>` : ''}
                ${paper.pdf_url ? `<a href="${paper.pdf_url}" target="_blank" class="paper-link-btn"><i class="fas fa-file-pdf"></i> Download PDF</a>` : ''}
            </div>
            <h3>Abstract</h3>
            <p class="modal-abstract">${paper.abstract || 'No abstract available.'}</p>
        `;

        overlay.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function formatDate(dateStr) {
        try {
            const d = new Date(dateStr);
            const options = { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' };
            return d.toLocaleDateString('zh-CN', options);
        } catch {
            return dateStr;
        }
    }

    // Event listeners
    document.querySelectorAll('.dir-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.dir-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentDirection = tab.dataset.dir;
            renderPapers();
        });
    });

    document.getElementById('dateFilter').addEventListener('change', (e) => {
        currentDateFilter = e.target.value;
        renderPapers();
    });

    document.getElementById('sourceFilter').addEventListener('change', (e) => {
        currentSourceFilter = e.target.value;
        renderPapers();
    });

    document.getElementById('searchInput').addEventListener('input', (e) => {
        currentSearch = e.target.value;
        renderPapers();
    });

    // Modal close
    document.getElementById('modalClose').addEventListener('click', () => {
        document.getElementById('modalOverlay').classList.remove('open');
        document.body.style.overflow = '';
    });

    document.getElementById('modalOverlay').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
            e.currentTarget.classList.remove('open');
            document.body.style.overflow = '';
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.getElementById('modalOverlay').classList.remove('open');
            document.body.style.overflow = '';
        }
    });

    // Navbar
    const navbar = document.getElementById('navbar');
    window.addEventListener('scroll', () => {
        navbar.classList.toggle('scrolled', window.scrollY > 50);
    });

    const navToggle = document.getElementById('navToggle');
    const mobileMenu = document.getElementById('mobileMenu');
    if (navToggle) {
        navToggle.addEventListener('click', () => mobileMenu.classList.toggle('open'));
    }

    // Init
    loadPapers();
});
