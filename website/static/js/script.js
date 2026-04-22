// YG Engineering - Enhanced JavaScript functionality

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all functionality
    initScrollEffects();
    initFormEnhancements();
    initAnimations();
    initNavigation();
    
    // Initialize Lucide icons
    if (window.lucide) {
        lucide.createIcons();
    }
});

// Scroll effects and back to top
function initScrollEffects() {
    const backToTop = document.getElementById('backToTop');
    const header = document.querySelector('.header-fixed');
    const showAt = 300;
    
    function handleScroll() {
        const scrollY = window.scrollY;
        
        // Back to top button
        if (scrollY > showAt) {
            backToTop?.classList.add('show');
        } else {
            backToTop?.classList.remove('show');
        }
        
        // Header background opacity
        if (header) {
            const opacity = Math.min(scrollY / 100, 0.95);
            header.style.background = `rgba(17, 21, 28, ${opacity})`;
        }
    }
    
    // Throttled scroll handler
    let ticking = false;
    window.addEventListener('scroll', function() {
        if (!ticking) {
            requestAnimationFrame(function() {
                handleScroll();
                ticking = false;
            });
            ticking = true;
        }
    });
    
    // Back to top click handler
    backToTop?.addEventListener('click', function(e) {
        e.preventDefault();
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
    
    // Initial call
    handleScroll();
}

// Form enhancements
function initFormEnhancements() {
    // Add Bootstrap classes to form elements
    const formControls = document.querySelectorAll('input:not([type="hidden"]), textarea');
    const formSelects = document.querySelectorAll('select');
    
    formControls.forEach(control => {
        if (!control.classList.contains('form-control')) {
            control.classList.add('form-control');
        }
    });
    
    formSelects.forEach(select => {
        if (!select.classList.contains('form-select')) {
            select.classList.add('form-select');
        }
    });
    
    // Real-time form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea, select');
        
        inputs.forEach(input => {
            // Add validation on blur
            input.addEventListener('blur', function() {
                validateField(this);
            });
            
            // Clear validation on focus
            input.addEventListener('focus', function() {
                clearFieldValidation(this);
            });
        });
        
        // Enhanced form submission
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i data-lucide="loader-2" class="me-2 animate-spin"></i>Sending...';
                
                // Re-enable after 3 seconds (fallback)
                setTimeout(() => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i data-lucide="send" class="me-2"></i>Send Message';
                    if (window.lucide) lucide.createIcons();
                }, 3000);
            }
        });
    });
}

// Field validation
function validateField(field) {
    const value = field.value.trim();
    const fieldType = field.type;
    const isRequired = field.hasAttribute('required');
    
    // Clear previous validation
    clearFieldValidation(field);
    
    // Check if required field is empty
    if (isRequired && !value) {
        showFieldError(field, 'This field is required');
        return false;
    }
    
    // Email validation
    if (fieldType === 'email' && value) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            showFieldError(field, 'Please enter a valid email address');
            return false;
        }
    }
    
    // Phone validation (South African format)
    if (field.name === 'phone' && value) {
        const phoneRegex = /^(\+27|27|0)\s?\d{2}\s?\d{3}\s?\d{4}$/;
        if (!phoneRegex.test(value)) {
            showFieldError(field, 'Please enter a valid South African phone number');
            return false;
        }
    }
    
    // Name validation
    if ((field.name === 'first_name' || field.name === 'last_name' || field.name === 'full_name') && value) {
        const nameRegex = /^[A-Za-zÀ-ÖØ-öø-ÿ \'-]+$/;
        if (!nameRegex.test(value)) {
            showFieldError(field, 'Please enter a valid name');
            return false;
        }
    }
    
    // Show success for valid fields
    if (value) {
        showFieldSuccess(field);
    }
    
    return true;
}

function showFieldError(field, message) {
    field.classList.add('is-invalid');
    field.classList.remove('is-valid');
    
    // Remove existing feedback
    const existingFeedback = field.parentNode.querySelector('.invalid-feedback');
    if (existingFeedback) {
        existingFeedback.remove();
    }
    
    // Add error message
    const feedback = document.createElement('div');
    feedback.className = 'invalid-feedback';
    feedback.textContent = message;
    field.parentNode.appendChild(feedback);
}

function showFieldSuccess(field) {
    field.classList.add('is-valid');
    field.classList.remove('is-invalid');
    
    // Remove error feedback
    const existingFeedback = field.parentNode.querySelector('.invalid-feedback');
    if (existingFeedback) {
        existingFeedback.remove();
    }
}

function clearFieldValidation(field) {
    field.classList.remove('is-valid', 'is-invalid');
    const feedback = field.parentNode.querySelector('.invalid-feedback');
    if (feedback) {
        feedback.remove();
    }
}

// Animation effects
function initAnimations() {
    // Intersection Observer for fade-in animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in-up');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observe elements for animation
    const animateElements = document.querySelectorAll('.capability-card, .service-card, .project-card, .mission-card');
    animateElements.forEach(el => {
        observer.observe(el);
    });
    
    // Parallax effect for hero patterns
    const patterns = document.querySelectorAll('.pattern');
    if (patterns.length > 0) {
        window.addEventListener('scroll', function() {
            const scrolled = window.pageYOffset;
            const rate = scrolled * -0.5;
            
            patterns.forEach((pattern, index) => {
                const speed = (index + 1) * 0.1;
                pattern.style.transform = `translateY(${rate * speed}px)`;
            });
        });
    }
}

// Navigation enhancements
function initNavigation() {
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            
            if (target) {
                const headerHeight = document.querySelector('.header-fixed')?.offsetHeight || 80;
                const targetPosition = target.offsetTop - headerHeight;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
    
    // Active navigation highlighting
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link[href^="#"]');
    const sections = document.querySelectorAll('section[id]');
    
    if (navLinks.length > 0 && sections.length > 0) {
        window.addEventListener('scroll', function() {
            const scrollPos = window.scrollY + 100;
            
            sections.forEach(section => {
                const sectionTop = section.offsetTop;
                const sectionHeight = section.offsetHeight;
                const sectionId = section.getAttribute('id');
                
                if (scrollPos >= sectionTop && scrollPos < sectionTop + sectionHeight) {
                    navLinks.forEach(link => {
                        link.classList.remove('active');
                        if (link.getAttribute('href') === `#${sectionId}`) {
                            link.classList.add('active');
                        }
                    });
                }
            });
        });
    }
    
    // Mobile menu auto-close
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    
    if (navbarToggler && navbarCollapse) {
        document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
            link.addEventListener('click', function() {
                if (navbarCollapse.classList.contains('show')) {
                    navbarToggler.click();
                }
            });
        });
    }
}

// Auto-hide messages
function initMessageHandling() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (alert && alert.parentNode) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    });
}

// Initialize message handling when DOM is ready
document.addEventListener('DOMContentLoaded', initMessageHandling);

// Utility functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Handle page load with hash
window.addEventListener('load', function() {
    if (location.hash) {
        setTimeout(() => {
            const target = document.querySelector(location.hash);
            if (target) {
                const headerHeight = document.querySelector('.header-fixed')?.offsetHeight || 80;
                const targetPosition = target.offsetTop - headerHeight;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        }, 100);
    }
});

// Service calculator (placeholder for future enhancement)
function initServiceCalculator() {
    // This could be expanded to include a pricing calculator
    // based on selected services and requirements
}

// Performance monitoring
function initPerformanceMonitoring() {
    // Monitor page load performance
    window.addEventListener('load', function() {
        if ('performance' in window) {
            const loadTime = performance.timing.loadEventEnd - performance.timing.navigationStart;
            console.log(`Page loaded in ${loadTime}ms`);
        }
    });
}

// Initialize performance monitoring
initPerformanceMonitoring();