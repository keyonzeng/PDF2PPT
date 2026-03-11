// Smooth scroll for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Navbar scroll effect
let lastScroll = 0;
const navbar = document.querySelector('.navbar');

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;
    
    if (currentScroll > 100) {
        navbar.style.top = currentScroll > lastScroll ? '-100px' : '1rem';
    } else {
        navbar.style.top = '1rem';
    }
    
    lastScroll = currentScroll;
});

// Intersection Observer for animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Observe all feature cards, pricing cards, and testimonial cards
document.querySelectorAll('.feature-card, .pricing-card, .testimonial-card').forEach(card => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(30px)';
    card.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
    observer.observe(card);
});

// Add cursor pointer to all cards
document.querySelectorAll('.feature-card, .pricing-card, .testimonial-card').forEach(card => {
    card.style.cursor = 'pointer';
});

// Parallax effect for hero section
window.addEventListener('scroll', () => {
    const scrolled = window.pageYOffset;
    const heroVisual = document.querySelector('.hero-visual');
    
    if (heroVisual && scrolled < window.innerHeight) {
        heroVisual.style.transform = `translateY(${scrolled * 0.3}px)`;
    }
});

// Animate stats on scroll
const animateStats = (entries, observer) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const stats = entry.target.querySelectorAll('.stat-number');
            stats.forEach(stat => {
                const target = stat.textContent;
                const isNumber = target.match(/[\d.]+/);
                
                if (isNumber) {
                    const value = parseFloat(isNumber[0]);
                    const suffix = target.replace(isNumber[0], '');
                    let current = 0;
                    const increment = value / 50;
                    
                    const counter = setInterval(() => {
                        current += increment;
                        if (current >= value) {
                            stat.textContent = target;
                            clearInterval(counter);
                        } else {
                            if (suffix.includes('.')) {
                                stat.textContent = current.toFixed(1) + suffix;
                            } else if (suffix === 'K+' || suffix === 'M+') {
                                stat.textContent = Math.floor(current) + suffix;
                            } else {
                                stat.textContent = Math.floor(current) + suffix;
                            }
                        }
                    }, 30);
                }
            });
            observer.unobserve(entry.target);
        }
    };
};

const statsObserver = new IntersectionObserver(animateStats, {
    threshold: 0.5
});

const heroStats = document.querySelector('.hero-stats');
if (heroStats) {
    statsObserver.observe(heroStats);
}

// Add hover effect to buttons
document.querySelectorAll('.btn-primary, .btn-cta').forEach(button => {
    button.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-2px)';
    });
    
    button.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
    });
});

// Prefers reduced motion
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

if (prefersReducedMotion.matches) {
    // Disable animations for users who prefer reduced motion
    document.querySelectorAll('*').forEach(el => {
        el.style.animation = 'none';
        el.style.transition = 'none';
    });
}

console.log('✨ PDF2PPT Landing Page Loaded Successfully!');
