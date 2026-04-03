// ============================================
// Paper Tracker Page Scripts
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
            // Direction filter
            if (p.direction !== currentDirection) return false;

            // Source filter
            if (currentSourceFilter !== 'all' && p.source !== currentSourceFilter) return false;

            // Date filter
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

            // Search filter
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

        // Bind click events
        container.querySelectorAll('.paper-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (e.target.closest('.paper-link-btn')) return;
                const id = card.dataset.id;
                const paper = allPapers.find(p => p.id === id);
                if (paper) showModal(paper);
            });
        });

        container.querySelectorAll('.paper-analysis-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.dataset.id;
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

        return `
        <div class="paper-card" data-id="${paper.id}">
            <div class="paper-meta">
                <span class="paper-source ${sourceClass}">${sourceLabel}</span>
                <span class="paper-date">${paper.date}</span>
                ${paper.venue ? `<span class="paper-direction">${paper.venue}</span>` : ''}
            </div>
            <h3 class="paper-title-text">${paper.title}</h3>
            <p class="paper-authors-text">${paper.authors || ''}</p>
            <p class="paper-abstract-preview">${paper.abstract || ''}</p>
            <div class="paper-footer">
                <div class="paper-links">
                    ${paper.url ? `<a href="${paper.url}" target="_blank" class="paper-link-btn" onclick="event.stopPropagation()"><i class="fas fa-external-link-alt"></i> Paper</a>` : ''}
                    ${paper.pdf_url ? `<a href="${paper.pdf_url}" target="_blank" class="paper-link-btn" onclick="event.stopPropagation()"><i class="fas fa-file-pdf"></i> PDF</a>` : ''}
                </div>
                ${paper.analysis ? `<button class="paper-analysis-btn" data-id="${paper.id}"><i class="fas fa-microscope"></i> AI Analysis</button>` : ''}
            </div>
        </div>
        `;
    }

    // Show modal with analysis
    function showModal(paper) {
        const overlay = document.getElementById('modalOverlay');
        const content = document.getElementById('modalContent');

        const sourceLabel = {
            'arxiv': 'arXiv',
            'biorxiv': 'bioRxiv',
            'conference': 'Conference',
            'journal': 'Journal'
        }[paper.source] || paper.source;

        let analysisHtml = '';
        if (paper.analysis) {
            analysisHtml = renderAnalysis(paper.analysis);
        }

        content.innerHTML = `
            <h2>${paper.title}</h2>
            <div class="modal-meta">
                <span class="modal-meta-item"><i class="fas fa-users"></i> ${paper.authors || 'Unknown'}</span>
                <span class="modal-meta-item"><i class="fas fa-calendar"></i> ${paper.date}</span>
                <span class="modal-meta-item"><i class="fas fa-database"></i> ${sourceLabel}</span>
                ${paper.venue ? `<span class="modal-meta-item"><i class="fas fa-bookmark"></i> ${paper.venue}</span>` : ''}
            </div>
            ${paper.url ? `<p><a href="${paper.url}" target="_blank"><i class="fas fa-external-link-alt"></i> View Original Paper</a></p>` : ''}
            <h3>Abstract</h3>
            <p>${paper.abstract || 'No abstract available.'}</p>
            ${analysisHtml}
        `;

        overlay.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function renderAnalysis(analysis) {
        if (typeof analysis === 'string') {
            // If analysis is raw markdown/text, render it
            return `<div class="analysis-section">${markdownToHtml(analysis)}</div>`;
        }

        // Structured analysis
        let html = '<h3>AI Deep Analysis</h3>';

        if (analysis.abstract_translation) {
            html += `<h4>0. 摘要翻译</h4><div class="analysis-section"><p>${analysis.abstract_translation}</p></div>`;
        }

        if (analysis.motivation) {
            html += `<h4>1. 方法动机</h4><div class="analysis-section">${markdownToHtml(analysis.motivation)}</div>`;
        }

        if (analysis.method_design) {
            html += `<h4>2. 方法设计</h4><div class="analysis-section">${markdownToHtml(analysis.method_design)}</div>`;
        }

        if (analysis.comparison) {
            html += `<h4>3. 与其他方法对比</h4><div class="analysis-section">${markdownToHtml(analysis.comparison)}</div>`;
        }

        if (analysis.experiments) {
            html += `<h4>4. 实验表现与优势</h4><div class="analysis-section">${markdownToHtml(analysis.experiments)}</div>`;
        }

        if (analysis.application) {
            html += `<h4>5. 学习与应用</h4><div class="analysis-section">${markdownToHtml(analysis.application)}</div>`;
        }

        if (analysis.summary) {
            html += `<h4>6. 总结</h4><div class="analysis-section">${markdownToHtml(analysis.summary)}</div>`;
        }

        if (analysis.pipeline_steps) {
            html += `<h4>速记版 Pipeline</h4><div class="pipeline-steps">`;
            analysis.pipeline_steps.forEach((step, i) => {
                if (i > 0) html += `<span class="pipeline-arrow"><i class="fas fa-arrow-right"></i></span>`;
                html += `<span class="pipeline-step"><span class="step-num">${i+1}</span>${step}</span>`;
            });
            html += `</div>`;
        }

        return html;
    }

    // Enhanced markdown to HTML with table support
    function markdownToHtml(text) {
        if (!text) return '';
        
        // Split into lines to detect tables
        const lines = text.split('\n');
        let html = '';
        let inTable = false;
        let tableHtml = '';
        let inParagraph = false;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            
            // Check if line is a table row
            if (line.startsWith('|') && line.endsWith('|')) {
                // Check if it's a separator row
                if (/^\|[\s-:|]+\|$/.test(line)) {
                    continue; // Skip separator rows
                }
                
                if (!inTable) {
                    if (inParagraph) { html += '</p>'; inParagraph = false; }
                    tableHtml = '<table>';
                    inTable = true;
                    // First row is header
                    const cells = line.split('|').filter(c => c.trim());
                    tableHtml += '<tr>' + cells.map(c => `<th>${inlineFormat(c.trim())}</th>`).join('') + '</tr>';
                } else {
                    const cells = line.split('|').filter(c => c.trim());
                    tableHtml += '<tr>' + cells.map(c => `<td>${inlineFormat(c.trim())}</td>`).join('') + '</tr>';
                }
            } else {
                if (inTable) {
                    html += tableHtml + '</table>';
                    inTable = false;
                    tableHtml = '';
                }
                
                if (line === '') {
                    if (inParagraph) { html += '</p>'; inParagraph = false; }
                } else {
                    if (!inParagraph) { html += '<p>'; inParagraph = true; }
                    else { html += '<br>'; }
                    html += inlineFormat(line);
                }
            }
        }
        
        if (inTable) html += tableHtml + '</table>';
        if (inParagraph) html += '</p>';
        
        return html;
    }
    
    function inlineFormat(text) {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>');
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
