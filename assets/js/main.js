// ============================================
// Xiaoquan Zhi - Personal Homepage Scripts
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Typing animation
    const titles = [
        'Undergraduate Researcher @ Tianjin University',
        'Natural Language Processing & AI for Health',
        'Medical Dialogue Systems & Virtual Cell',
        'National Scholarship Winner (x2)'
    ];
    let titleIndex = 0;
    let charIndex = 0;
    let isDeleting = false;
    const typingEl = document.getElementById('typingText');

    function typeText() {
        if (!typingEl) return;
        const current = titles[titleIndex];
        if (isDeleting) {
            typingEl.textContent = current.substring(0, charIndex - 1);
            charIndex--;
        } else {
            typingEl.textContent = current.substring(0, charIndex + 1);
            charIndex++;
        }

        let speed = isDeleting ? 30 : 60;

        if (!isDeleting && charIndex === current.length) {
            speed = 2000;
            isDeleting = true;
        } else if (isDeleting && charIndex === 0) {
            isDeleting = false;
            titleIndex = (titleIndex + 1) % titles.length;
            speed = 500;
        }

        setTimeout(typeText, speed);
    }
    typeText();

    // Navbar scroll effect
    const navbar = document.getElementById('navbar');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // Active nav link on scroll
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link[href^="#"]');

    window.addEventListener('scroll', () => {
        let current = '';
        sections.forEach(section => {
            const sectionTop = section.offsetTop - 100;
            if (scrollY >= sectionTop) {
                current = section.getAttribute('id');
            }
        });
        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === '#' + current) {
                link.classList.add('active');
            }
        });
    });

    // Mobile menu toggle
    const navToggle = document.getElementById('navToggle');
    const mobileMenu = document.getElementById('mobileMenu');

    if (navToggle) {
        navToggle.addEventListener('click', () => {
            mobileMenu.classList.toggle('open');
        });
    }

    // Close mobile menu on link click
    document.querySelectorAll('.mobile-link').forEach(link => {
        link.addEventListener('click', () => {
            mobileMenu.classList.remove('open');
        });
    });

    // Intersection Observer for animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    document.querySelectorAll('.pub-card, .research-card, .timeline-item, .skill-category').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });

    // Add visible class styles
    const style = document.createElement('style');
    style.textContent = '.visible { opacity: 1 !important; transform: translateY(0) !important; }';
    document.head.appendChild(style);

    // Particles background
    const particlesContainer = document.getElementById('particles');
    if (particlesContainer) {
        for (let i = 0; i < 30; i++) {
            const particle = document.createElement('div');
            particle.style.cssText = `
                position: absolute;
                width: ${Math.random() * 4 + 2}px;
                height: ${Math.random() * 4 + 2}px;
                background: ${Math.random() > 0.5 ? 'rgba(37,99,235,0.15)' : 'rgba(6,182,212,0.15)'};
                border-radius: 50%;
                left: ${Math.random() * 100}%;
                top: ${Math.random() * 100}%;
                animation: float ${Math.random() * 10 + 10}s linear infinite;
                animation-delay: ${Math.random() * 5}s;
            `;
            particlesContainer.appendChild(particle);
        }

        const floatStyle = document.createElement('style');
        floatStyle.textContent = `
            @keyframes float {
                0% { transform: translateY(0) translateX(0); opacity: 0; }
                10% { opacity: 1; }
                90% { opacity: 1; }
                100% { transform: translateY(-100vh) translateX(${Math.random() * 200 - 100}px); opacity: 0; }
            }
        `;
        document.head.appendChild(floatStyle);
    }
});
