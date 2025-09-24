const header = document.querySelector('.site-header');
const navToggle = document.querySelector('.nav-toggle');
const navLinks = document.querySelector('.nav-links');
const yearSpan = document.getElementById('year');

if (yearSpan) {
    yearSpan.textContent = new Date().getFullYear();
}

if (navToggle && navLinks && header) {
    navToggle.addEventListener('click', () => {
        const isOpen = header.classList.toggle('open');
        navLinks.classList.toggle('open');
        navToggle.setAttribute('aria-expanded', String(isOpen));
    });

    navLinks.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            header.classList.remove('open');
            navLinks.classList.remove('open');
            navToggle.setAttribute('aria-expanded', 'false');
        });
    });
}
