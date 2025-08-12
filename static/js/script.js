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
            fileNameDisplay.textContent = '';
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
        downloadLinksList.innerHTML = '';
        
        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const response = await fetch('/api/process_hf', { method: 'POST', body: formData });
            
            if (!response.ok) {
                const contentType = response.headers.get("content-type");
                let errorMessage;
                if (contentType && contentType.indexOf("application/json") !== -1) {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || 'An unknown server error occurred.';
                } else { 
                    errorMessage = await response.text(); 
                }
                throw new Error(errorMessage);
            }
            
            const srtContent = await response.text();
            const blob = new Blob([srtContent], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const originalFileName = selectedFile.name.split('.').slice(0, -1).join('.');
            
            const link = document.createElement('a');
            link.href = url;
            link.download = `${originalFileName}.srt`;
            link.textContent = `Download Subtitles (.srt)`;
            link.className = "text-violet-400 hover:text-violet-300 underline block text-lg";
            
            downloadLinksList.appendChild(link);
            downloadLinksContainer.classList.remove('hidden');

        } catch (error) {
            console.error('An error occurred during processing:', error);
            messageArea.textContent = `Error: ${error.message}`;
        } finally {
            loadingIndicator.classList.add('hidden');
            processButton.disabled = false;
        }
    });

    // --- 4. CONSTELLATION PARTICLE NETWORK ANIMATION ---
    let particles = [];
    const numParticles = 100;
    const maxDistance = 120;
    const particleSpeed = 0.5;
    const mouse = { x: undefined, y: undefined };

    window.addEventListener('mousemove', (event) => {
        mouse.x = event.x;
        mouse.y = event.y;
    });
    
    window.addEventListener('mouseout', () => {
        mouse.x = undefined;
        mouse.y = undefined;
    });

    class Particle {
        constructor() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.vx = (Math.random() - 0.5) * particleSpeed;
            this.vy = (Math.random() - 0.5) * particleSpeed;
            this.radius = Math.random() * 1.5 + 1;
            this.hue = 220 + Math.random() * 80;
        }

        update() {
            this.x += this.vx;
            this.y += this.vy;
            if (this.x < 0 || this.x > canvas.width) this.vx *= -1;
            if (this.y < 0 || this.y > canvas.height) this.vy *= -1;
        }

        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = `hsl(${this.hue}, 100%, 70%)`;
            ctx.fill();
        }
    }

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
                    const opacity = 1 - distance / maxDistance;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(191, 128, 255, ${opacity})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }
    }
    
    function drawMouseLines() {
        if (mouse.x === undefined) return;

        for (let i = 0; i < particles.length; i++) {
            const dx = particles[i].x - mouse.x;
            const dy = particles[i].y - mouse.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < maxDistance * 1.5) {
                const opacity = 1 - distance / (maxDistance * 1.5);
                ctx.beginPath();
                ctx.moveTo(particles[i].x, particles[i].y);
                ctx.lineTo(mouse.x, mouse.y);
                ctx.strokeStyle = `rgba(160, 180, 255, ${opacity})`;
                ctx.lineWidth = 0.7;
                ctx.stroke();
            }
        }
    }

    function animate() {
        ctx.fillStyle = '#0b0b12';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        particles.forEach(p => { p.update(); p.draw(); });
        drawLines();
        drawMouseLines();
        requestAnimationFrame(animate);
    }
    
    window.addEventListener('resize', setupAnimation);
    setupAnimation();
    animate();
});
