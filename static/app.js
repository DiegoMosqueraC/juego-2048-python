/**
 * app.js - Controlador Frontend para 2048 en Python
 * ==================================================
 * Gestiona la sincronización con la API en Python, los efectos de sonido
 * generados mediante Web Audio API, el renderizado reactivo del tablero y los
 * controles de teclado, táctiles (swipes) y botones.
 */

// -----------------------------------------------------------------------------
// Módulo de Efectos de Sonido Sintetizados (Web Audio API)
// -----------------------------------------------------------------------------
class SoundEffects {
    constructor() {
        this.ctx = null;
        this.enabled = localStorage.getItem("2048_sound") !== "false";
    }

    _initContext() {
        if (!this.ctx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                this.ctx = new AudioContext();
            }
        }
        if (this.ctx && this.ctx.state === "suspended") {
            this.ctx.resume();
        }
    }

    toggle() {
        this.enabled = !this.enabled;
        localStorage.setItem("2048_sound", this.enabled);
        return this.enabled;
    }

    playMove() {
        if (!this.enabled) return;
        this._initContext();
        if (!this.ctx) return;

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(160, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(80, this.ctx.currentTime + 0.08);

        gain.gain.setValueAtTime(0.12, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.08);

        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start();
        osc.stop(this.ctx.currentTime + 0.08);
    }

    playMerge(value) {
        if (!this.enabled) return;
        this._initContext();
        if (!this.ctx) return;

        // Frecuencia dinámica: números más altos tienen notas más brillantes
        const baseFreq = 260 + Math.min(Math.log2(value || 4) * 55, 600);
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = "triangle";
        osc.frequency.setValueAtTime(baseFreq, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(baseFreq * 1.5, this.ctx.currentTime + 0.12);

        gain.gain.setValueAtTime(0.2, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.14);

        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start();
        osc.stop(this.ctx.currentTime + 0.14);
    }

    playWin() {
        if (!this.enabled) return;
        this._initContext();
        if (!this.ctx) return;

        // Arpegio de victoria
        const notes = [523.25, 659.25, 783.99, 1046.50]; // Do, Mi, Sol, Do alto
        notes.forEach((freq, idx) => {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            osc.type = "sine";
            osc.frequency.value = freq;
            const startTime = this.ctx.currentTime + idx * 0.1;
            gain.gain.setValueAtTime(0.25, startTime);
            gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.35);

            osc.connect(gain);
            gain.connect(this.ctx.destination);
            osc.start(startTime);
            osc.stop(startTime + 0.35);
        });
    }

    playGameOver() {
        if (!this.enabled) return;
        this._initContext();
        if (!this.ctx) return;

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(220, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(110, this.ctx.currentTime + 0.4);

        gain.gain.setValueAtTime(0.18, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.4);

        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start();
        osc.stop(this.ctx.currentTime + 0.4);
    }
}

// El servidor solo acepta comandos con cuerpo JSON (protección BUG-03).
const JSON_POST = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}"
};

// -----------------------------------------------------------------------------
// Cliente Principal del Juego 2048
// -----------------------------------------------------------------------------
class GameClient {
    constructor() {
        this.sound = new SoundEffects();
        this.boardElement = document.getElementById("game-board");
        this.tileContainer = document.getElementById("tile-container");
        this.currentScoreEl = document.getElementById("current-score");
        this.bestScoreEl = document.getElementById("best-score");
        this.scoreBubbleContainer = document.getElementById("score-bubble-container");

        this.modalWin = document.getElementById("modal-win");
        this.modalOver = document.getElementById("modal-over");
        this.finalScoreText = document.getElementById("final-score-text");

        this.btnUndo = document.getElementById("btn-undo");
        this.btnRestart = document.getElementById("btn-restart");
        this.btnSound = document.getElementById("btn-sound");
        this.btnTheme = document.getElementById("btn-theme");

        this.previousGrid = null;
        this.isProcessing = false;

        this.init();
    }

    async init() {
        this.setupEventListeners();
        this.setupTouchGestures();
        this.applySavedTheme();
        this.updateSoundIcon();

        // Cargar el estado inicial del servidor Python
        await this.fetchGameState();
    }

    // -------------------------------------------------------------------------
    // Comunicación con la API Python
    // -------------------------------------------------------------------------

    async fetchGameState() {
        try {
            const res = await fetch("/api/state");
            if (res.ok) {
                const data = await res.json();
                this.render(data);
            }
        } catch (err) {
            console.error("Error al obtener estado:", err);
        }
    }

    async sendMove(direction) {
        if (this.isProcessing) return;
        this.isProcessing = true;

        try {
            const res = await fetch("/api/move", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ direction })
            });

            if (res.ok) {
                const data = await res.json();
                if (data.moved) {
                    if (data.gained_points > 0) {
                        this.sound.playMerge(data.max_tile);
                        this.showScoreBubble(data.gained_points);
                    } else {
                        this.sound.playMove();
                    }
                    this.render(data);
                }
            }
        } catch (err) {
            console.error("Error al mover:", err);
        } finally {
            this.isProcessing = false;
        }
    }

    async undo() {
        if (this.isProcessing) return;
        this.isProcessing = true;
        try {
            const res = await fetch("/api/undo", JSON_POST);
            if (res.ok) {
                const data = await res.json();
                this.render(data);
                this.sound.playMove();
            }
        } catch (err) {
            console.error("Error al deshacer:", err);
        } finally {
            this.isProcessing = false;
        }
    }

    async reset() {
        try {
            const res = await fetch("/api/reset", JSON_POST);
            if (res.ok) {
                const data = await res.json();
                this.modalWin.classList.add("hidden");
                this.modalOver.classList.add("hidden");
                this.previousGrid = null;
                this.render(data);
                this.sound.playMove();
            }
        } catch (err) {
            console.error("Error al reiniciar:", err);
        }
    }

    async continuePlaying() {
        try {
            const res = await fetch("/api/continue", JSON_POST);
            if (res.ok) {
                const data = await res.json();
                this.modalWin.classList.add("hidden");
                this.render(data);
            }
        } catch (err) {
            console.error("Error al continuar:", err);
        }
    }

    // -------------------------------------------------------------------------
    // Renderizado del Tablero y Animaciones
    // -------------------------------------------------------------------------

    render(state) {
        const { grid, score, highscore, won, game_over, can_undo } = state;

        // Actualizar marcadores
        this.currentScoreEl.textContent = score.toLocaleString();
        this.bestScoreEl.textContent = highscore.toLocaleString();
        this.btnUndo.disabled = !can_undo;

        // Limpiar contenedor de fichas
        this.tileContainer.innerHTML = "";

        // Dibujar cada ficha en su posición de cuadrícula
        for (let r = 0; r < 4; r++) {
            for (let c = 0; c < 4; c++) {
                const val = grid[r][c];
                if (val > 0) {
                    const tileEl = document.createElement("div");
                    tileEl.textContent = val;

                    // Clases de estilo según el valor
                    let tileClass = val <= 2048 ? `tile-${val}` : "tile-super";
                    tileEl.className = `tile ${tileClass}`;

                    // Posicionamiento en el grid CSS
                    tileEl.style.gridRowStart = r + 1;
                    tileEl.style.gridColumnStart = c + 1;

                    // Detectar si es una ficha recién aparecida o fusionada para la animación
                    if (this.previousGrid) {
                        const prevVal = this.previousGrid[r][c];
                        if (prevVal === 0) {
                            tileEl.classList.add("tile-new");
                        } else if (prevVal < val) {
                            tileEl.classList.add("tile-merged");
                        }
                    }

                    this.tileContainer.appendChild(tileEl);
                }
            }
        }

        this.previousGrid = JSON.parse(JSON.stringify(grid));

        // Manejar ventanas modales de estado
        if (won) {
            this.modalWin.classList.remove("hidden");
            this.sound.playWin();
        } else {
            this.modalWin.classList.add("hidden");
        }

        if (game_over) {
            this.finalScoreText.textContent = score.toLocaleString();
            this.modalOver.classList.remove("hidden");
            this.sound.playGameOver();
        } else {
            this.modalOver.classList.add("hidden");
        }
    }

    showScoreBubble(points) {
        const bubble = document.createElement("span");
        bubble.className = "score-bubble";
        bubble.textContent = `+${points}`;
        this.scoreBubbleContainer.appendChild(bubble);

        setTimeout(() => {
            bubble.remove();
        }, 850);
    }

    // -------------------------------------------------------------------------
    // Eventos de Entrada (Teclado, Táctil, Botones)
    // -------------------------------------------------------------------------

    setupEventListeners() {
        // Atajos de teclado
        window.addEventListener("keydown", (e) => {
            // Evitar desplazamiento de página con teclas de flecha
            if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(e.code)) {
                e.preventDefault();
            }

            switch (e.key) {
                case "ArrowLeft":
                case "a":
                case "A":
                    this.sendMove("left");
                    break;
                case "ArrowRight":
                case "d":
                case "D":
                    this.sendMove("right");
                    break;
                case "ArrowUp":
                case "w":
                case "W":
                    this.sendMove("up");
                    break;
                case "ArrowDown":
                case "s":
                case "S":
                    this.sendMove("down");
                    break;
                case "u":
                case "U":
                    this.undo();
                    break;
                case "r":
                case "R":
                    this.reset();
                    break;
            }
        });

        // Botones de interfaz
        this.btnUndo.addEventListener("click", () => this.undo());
        this.btnRestart.addEventListener("click", () => this.reset());

        document.getElementById("btn-continue").addEventListener("click", () => this.continuePlaying());
        document.getElementById("btn-win-restart").addEventListener("click", () => this.reset());
        document.getElementById("btn-over-restart").addEventListener("click", () => this.reset());
        document.getElementById("btn-over-undo").addEventListener("click", () => {
            this.modalOver.classList.add("hidden");
            this.undo();
        });

        // Botones del D-Pad virtual en pantalla
        document.querySelectorAll(".dpad-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                const dir = btn.getAttribute("data-dir");
                if (dir) this.sendMove(dir);
            });
        });

        // Alternar sonido
        this.btnSound.addEventListener("click", () => {
            this.sound.toggle();
            this.updateSoundIcon();
        });

        // Alternar tema claro / oscuro
        this.btnTheme.addEventListener("click", () => {
            this.toggleTheme();
        });
    }

    setupTouchGestures() {
        let touchStartX = 0;
        let touchStartY = 0;
        let touchEndX = 0;
        let touchEndY = 0;

        const threshold = 35; // Distancia mínima en píxeles para reconocer un deslizamiento

        this.boardElement.addEventListener("touchstart", (e) => {
            const touch = e.changedTouches[0];
            touchStartX = touch.clientX;
            touchStartY = touch.clientY;
        }, { passive: true });

        this.boardElement.addEventListener("touchend", (e) => {
            const touch = e.changedTouches[0];
            touchEndX = touch.clientX;
            touchEndY = touch.clientY;

            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;

            if (Math.abs(deltaX) > Math.abs(deltaY)) {
                // Desplazamiento horizontal
                if (Math.abs(deltaX) > threshold) {
                    this.sendMove(deltaX > 0 ? "right" : "left");
                }
            } else {
                // Desplazamiento vertical
                if (Math.abs(deltaY) > threshold) {
                    this.sendMove(deltaY > 0 ? "down" : "up");
                }
            }
        }, { passive: true });
    }

    // -------------------------------------------------------------------------
    // Preferencias y Temas
    // -------------------------------------------------------------------------

    updateSoundIcon() {
        const iconOn = document.getElementById("icon-sound-on");
        const iconOff = document.getElementById("icon-sound-off");
        if (this.sound.enabled) {
            iconOn.classList.remove("hidden");
            iconOff.classList.add("hidden");
        } else {
            iconOn.classList.add("hidden");
            iconOff.classList.remove("hidden");
        }
    }

    applySavedTheme() {
        const savedTheme = localStorage.getItem("2048_theme") || "dark";
        document.documentElement.setAttribute("data-theme", savedTheme);
        this.updateThemeIcon(savedTheme);
    }

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
        const newTheme = currentTheme === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", newTheme);
        localStorage.setItem("2048_theme", newTheme);
        this.updateThemeIcon(newTheme);
    }

    updateThemeIcon(theme) {
        const iconMoon = document.getElementById("icon-moon");
        const iconSun = document.getElementById("icon-sun");
        if (theme === "dark") {
            iconMoon.classList.remove("hidden");
            iconSun.classList.add("hidden");
        } else {
            iconMoon.classList.add("hidden");
            iconSun.classList.remove("hidden");
        }
    }
}

// Iniciar aplicación cuando el DOM esté listo
document.addEventListener("DOMContentLoaded", () => {
    window.gameClient = new GameClient();
});
