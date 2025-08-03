document.addEventListener('DOMContentLoaded', () => {
    // --- 1. DOM Element Selection ---
    const fileInputFiles = document.getElementById('fileInputFiles');
    const fileNameDisplay = document.getElementById('fileNameDisplay');
    const processButton = document.getElementById('processButton');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const messageArea = document.getElementById('messageArea');
    const downloadLinksContainer = document.getElementById('downloadLinksContainer');
    const downloadLinksList = document.getElementById('downloadLinksList');
    const canvas = document.getElementById('waveCanvas');
    const ctx = canvas.getContext('2d');

    // --- 2. State Management ---
    let selectedFile = null;

    // --- 3. Main Application Logic ---
    fileInputFiles.addEventListener('change', (event) => {
        if (event.target.files.length > 0) {
            selectedFile = event.target.files[0];
            fileNameDisplay.textContent = `Selected: ${selectedFile.name}`;
            messageArea.textContent = '';
            downloadLinksContainer.classList.add('hidden');
            processButton.disabled = false;
        } else {
            selectedFile = null;
            fileNameDisplay.textContent = 'No file selected.';
            processButton.disabled = true;
        }
    });

    processButton.addEventListener('click', async () => {
        if (!selectedFile) {
            messageArea.textContent = 'Please select a file first.';
            return;
        }
        processButton.disabled = true;
        loadingIndicator.classList.remove('hidden');
        messageArea.textContent = '';
        downloadLinksContainer.classList.add('hidden');
        const formData = new FormData();
        formData.append('file', selectedFile);
        try {
            // Change this line in your script.js
            const response = await fetch('https://cipher-bktt.onrender.com/api/process_hf', { /* ... */ });
            if (!response.ok) {
                const contentType = response.headers.get("content-type");
                let errorMessage;
                if (contentType && contentType.indexOf("application/json") !== -1) {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || 'An unknown server error occurred.';
                } else { errorMessage = await response.text(); }
                throw new Error(errorMessage);
            }
            const srtContent = await response.text();
            const blob = new Blob([srtContent], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const originalFileName = selectedFile.name.split('.').slice(0, -1).join('.');
            downloadLinksList.innerHTML = '';
            const link = document.createElement('a');
            link.href = url;
            link.download = `${originalFileName}.srt`;
            link.textContent = `Download Subtitles for ${originalFileName}`;
            link.className = "text-violet-400 hover:text-violet-300 underline block text-lg";
            downloadLinksContainer.appendChild(link);
            downloadLinksContainer.classList.remove('hidden');
        } catch (error) {
            console.error('An error occurred during processing:', error);
            messageArea.textContent = `Error: ${error.message}`;
        } finally {
            loadingIndicator.classList.add('hidden');
            processButton.disabled = false;
        }
    });

    // --- 4. NEW "CONSTELLATION" PARTICLE NETWORK ANIMATION ---

    // --- Configuration ---
    let particles = [];
    const numParticles = 100; // Adjust for more/less density
    const maxDistance = 120; // Max distance for lines to connect
    const particleSpeed = 0.5;

    // Mouse object to make the animation interactive
    const mouse = {
        x: undefined,
        y: undefined,
    };

    window.addEventListener('mousemove', (event) => {
        mouse.x = event.x;
        mouse.y = event.y;
    });

    // Particle class
    class Particle {
        constructor() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.vx = (Math.random() - 0.5) * particleSpeed; // x velocity
            this.vy = (Math.random() - 0.5) * particleSpeed; // y velocity
            this.radius = Math.random() * 1.5 + 1;
            // Use HSL for a nice color range between blue and purple
            this.hue = 220 + Math.random() * 80;
        }

        update() {
            this.x += this.vx;
            this.y += this.vy;

            // Wrap particles around the screen edges for continuous animation
            if (this.x < 0) this.x = canvas.width;
            if (this.x > canvas.width) this.x = 0;
            if (this.y < 0) this.y = canvas.height;
            if (this.y > canvas.height) this.y = 0;
        }

        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = `hsl(${this.hue}, 100%, 70%)`;
            ctx.fill();
        }
    }

    // --- Animation Setup and Loop ---
    function setupAnimation() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        particles = [];
        for (let i = 0; i < numParticles; i++) {
            particles.push(new Particle());
        }
    }

    function drawLines() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < maxDistance) {
                    // Draw a line with opacity based on distance
                    const opacity = 1 - distance / maxDistance;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(191, 128, 255, ${opacity})`; // Lavender color
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }
    }
    
    // Connect particles to the mouse
    function drawMouseLines() {
        if (mouse.x === undefined || mouse.y === undefined) return;

        for (let i = 0; i < particles.length; i++) {
            const dx = particles[i].x - mouse.x;
            const dy = particles[i].y - mouse.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < maxDistance * 1.5) { // Larger radius for mouse
                const opacity = 1 - distance / (maxDistance * 1.5);
                ctx.beginPath();
                ctx.moveTo(particles[i].x, particles[i].y);
                ctx.lineTo(mouse.x, mouse.y);
                ctx.strokeStyle = `rgba(160, 180, 255, ${opacity})`; // Lighter blue for mouse lines
                ctx.lineWidth = 0.7;
                ctx.stroke();
            }
        }
    }

    function animate() {
        // Draw a solid dark background each frame. THIS IS THE FIX.
        ctx.fillStyle = '#0b0b12';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Update and draw each particle
        particles.forEach(p => {
            p.update();
            p.draw();
        });

        // Draw the connecting lines
        drawLines();
        drawMouseLines();

        requestAnimationFrame(animate);
    }
    
    // Initialize and run
    window.addEventListener('resize', setupAnimation);
    setupAnimation();
    animate();
});
