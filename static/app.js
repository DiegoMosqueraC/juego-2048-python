/**
 * app.js - Cliente web del juego 2048
 * ===================================
 * Se comunica con la API de Python, dibuja el tablero con animaciones de
 * deslizamiento, reproduce sonidos sintetizados (Web Audio API) y atiende el
 * teclado, los gestos táctiles y los botones. Las decisiones puras (qué tecla
 * es qué acción, cuándo anunciar una victoria...) viven en game-utils.js.
 */
"use strict";

const {
    actionForKey,
    swipeDirection,
    tileClassName,
    digitClass,
    statusTransition,
    highestMergedValue
} = window.GameUtils;

// Debe coincidir con --slide-duration en style.css.
const SLIDE_DURATION_MS = 110;
const SWIPE_THRESHOLD_PX = 35;
const SCORE_BUBBLE_MS = 850;
const JSON_HEADERS = { "Content-Type": "application/json" };
const CONNECTION_ERROR = "Sin conexión con el servidor de Python. "
    + "Verifica que la terminal del juego siga abierta.";
const DIRECTION_PHRASES = {
    left: "a la izquierda",
    right: "a la derecha",
    up: "hacia arriba",
    down: "hacia abajo"
};

// -----------------------------------------------------------------------------
// Preferencias del usuario
// -----------------------------------------------------------------------------
// localStorage lanza excepciones en modo privado o con el almacenamiento
// bloqueado (BUG-16); en ese caso el juego funciona sin recordar preferencias.
const preferences = {
    get(key, fallback) {
        try {
            const value = window.localStorage.getItem(key);
            return value === null ? fallback : value;
        } catch (error) {
            return fallback;
        }
    },
    set(key, value) {
        try {
            window.localStorage.setItem(key, String(value));
        } catch (error) {
            // Sin almacenamiento disponible: la preferencia dura solo esta sesión.
        }
    }
};

function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// -----------------------------------------------------------------------------
// Efectos de sonido sintetizados (Web Audio API)
// -----------------------------------------------------------------------------
class SoundEffects {
    constructor() {
        this.context = null;
        this.enabled = preferences.get("2048_sound", "true") !== "false";
    }

    toggle() {
        this.enabled = !this.enabled;
        preferences.set("2048_sound", this.enabled);
        return this.enabled;
    }

    _audioContext() {
        if (!this.enabled) {
            return null;
        }
        if (!this.context) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (!AudioContextClass) {
                return null;
            }
            this.context = new AudioContextClass();
        }
        if (this.context.state === "suspended") {
            this.context.resume();
        }
        return this.context;
    }

    /** Reproduce un tono con caída exponencial de volumen. */
    _tone({ type, from, to = from, volume, duration, delay = 0 }) {
        const context = this._audioContext();
        if (!context) {
            return;
        }
        const start = context.currentTime + delay;
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.type = type;
        oscillator.frequency.setValueAtTime(from, start);
        if (to !== from) {
            oscillator.frequency.exponentialRampToValueAtTime(to, start + duration);
        }
        gain.gain.setValueAtTime(volume, start);
        gain.gain.exponentialRampToValueAtTime(0.001, start + duration);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start(start);
        oscillator.stop(start + duration);
    }

    playMove() {
        this._tone({ type: "sine", from: 160, to: 80, volume: 0.12, duration: 0.08 });
    }

    /** Las fusiones de fichas más altas suenan más agudas. */
    playMerge(value) {
        const base = 260 + Math.min(Math.log2(value || 4) * 55, 600);
        this._tone({ type: "triangle", from: base, to: base * 1.5, volume: 0.2, duration: 0.14 });
    }

    playWin() {
        // Arpegio Do - Mi - Sol - Do agudo.
        [523.25, 659.25, 783.99, 1046.5].forEach((frequency, index) => {
            this._tone({ type: "sine", from: frequency, volume: 0.25, duration: 0.35, delay: index * 0.1 });
        });
    }

    playGameOver() {
        this._tone({ type: "sawtooth", from: 220, to: 110, volume: 0.18, duration: 0.4 });
    }
}

// -----------------------------------------------------------------------------
// Cliente del juego
// -----------------------------------------------------------------------------
class GameClient {
    constructor() {
        this.sound = new SoundEffects();
        this.el = {
            board: document.getElementById("game-board"),
            gridBackground: document.getElementById("grid-background"),
            tiles: document.getElementById("tile-container"),
            score: document.getElementById("current-score"),
            best: document.getElementById("best-score"),
            bubbles: document.getElementById("score-bubble-container"),
            goal: document.getElementById("goal-tile"),
            finalScore: document.getElementById("final-score-text"),
            toast: document.getElementById("toast"),
            announcer: document.getElementById("announcer"),
            undo: document.getElementById("btn-undo"),
            soundButton: document.getElementById("btn-sound"),
            themeButton: document.getElementById("btn-theme")
        };
        this.modals = {
            win: document.getElementById("modal-win"),
            over: document.getElementById("modal-over"),
            confirm: document.getElementById("modal-confirm")
        };
        this.state = null;
        this.size = 0;
        this.tileElements = new Map();
        this.busy = false;
        this.pendingDirection = null;
        this.focusBeforeModal = null;

        this.setupKeyboard();
        this.setupButtons();
        this.setupTouch();
        this.applyTheme(this.savedTheme());
        this.updateSoundButton();
        this.loadState();
    }

    // --- Comunicación con la API ----------------------------------------------

    /**
     * GET si no hay cuerpo; POST con JSON si lo hay.
     * @returns {Promise<{ok: boolean, status: number, data: object} | null>}
     *          null si el servidor no respondió.
     */
    async request(path, body) {
        const options = body === undefined
            ? { cache: "no-store" }
            : { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body) };
        let response;
        try {
            response = await fetch(path, options);
        } catch (error) {
            this.showToast(CONNECTION_ERROR);
            return null;
        }
        this.hideToast();
        let data = {};
        try {
            data = await response.json();
        } catch (error) {
            // Respuesta sin JSON: se informa con el código de estado.
        }
        return { ok: response.ok, status: response.status, data };
    }

    async loadState() {
        const result = await this.request("/api/state");
        if (result && result.ok) {
            this.applyState(result.data, { appear: true });
        }
    }

    async move(direction) {
        if (this.openModalName()) {
            return;
        }
        if (this.busy) {
            // Se recuerda la última dirección pedida para no perder pulsaciones rápidas.
            this.pendingDirection = direction;
            return;
        }
        this.busy = true;
        try {
            const result = await this.request("/api/move", { direction });
            if (result && result.ok && result.data.moved) {
                await this.animateSlide(result.data.tile_moves);
                this.playMoveSound(result.data);
                this.applyState(result.data, { move: result.data });
                this.announceMove(direction, result.data);
            }
        } finally {
            this.busy = false;
            const next = this.pendingDirection;
            this.pendingDirection = null;
            if (next) {
                this.move(next);
            }
        }
    }

    async undo() {
        if (this.busy) {
            return;
        }
        this.busy = true;
        try {
            const result = await this.request("/api/undo", {});
            if (result && result.ok && result.data.undone) {
                this.applyState(result.data, {});
                this.sound.playMove();
                this.announce(`Jugada deshecha. Puntuación: ${result.data.score}.`);
            }
        } finally {
            this.busy = false;
        }
    }

    /** Pide confirmación si hay una partida en curso con puntos (BUG-13). */
    requestReset() {
        const inProgress = this.state && this.state.status === "playing" && this.state.score > 0;
        if (inProgress) {
            this.toggleModal("confirm", true);
        } else {
            this.reset();
        }
    }

    async reset() {
        this.toggleModal("confirm", false);
        const result = await this.request("/api/reset", {});
        if (result && result.ok) {
            this.applyState(result.data, { appear: true });
            this.sound.playMove();
            this.announce("Nueva partida iniciada.");
        }
    }

    async continuePlaying() {
        const result = await this.request("/api/continue", {});
        if (result && (result.ok || result.status === 409)) {
            await this.loadState();
        }
    }

    // --- Dibujo del tablero ------------------------------------------------------

    /**
     * Actualiza toda la interfaz con un estado del servidor.
     * @param {object} options move: datos de la jugada (animaciones de fusión y
     *        ficha nueva); appear: anima la aparición de todas las fichas.
     */
    applyState(state, options) {
        const firstLoad = this.state === null;
        const previousStatus = firstLoad ? state.status : this.state.status;
        if (state.size !== this.size) {
            this.buildGrid(state.size);
        }
        this.state = state;
        this.updateScores(state, options.move);
        this.renderTiles(state, options);
        this.updateDialogs(previousStatus, state, firstLoad);
        this.el.undo.disabled = !state.can_undo;
        this.el.goal.textContent = state.winning_tile;
    }

    /** Genera las celdas de fondo para un tablero de size x size. */
    buildGrid(size) {
        this.size = size;
        this.el.board.style.setProperty("--size", size);
        const cells = Array.from({ length: size * size }, () => {
            const cell = document.createElement("div");
            cell.className = "grid-cell";
            return cell;
        });
        this.el.gridBackground.replaceChildren(...cells);
    }

    createTile(value, row, col) {
        const tile = document.createElement("div");
        tile.className = `tile ${tileClassName(value, this.state.winning_tile)} ${digitClass(value)}`;
        tile.style.setProperty("--row", row);
        tile.style.setProperty("--col", col);
        const inner = document.createElement("div");
        inner.className = "tile-inner";
        inner.textContent = value;
        tile.appendChild(inner);
        return tile;
    }

    renderTiles(state, { move, appear }) {
        const merged = new Set((move ? move.merged_cells : []).map(([r, c]) => `${r},${c}`));
        const newTile = move && move.new_tile ? `${move.new_tile.row},${move.new_tile.col}` : null;
        const tiles = [];
        this.tileElements.clear();
        state.grid.forEach((rowValues, row) => {
            rowValues.forEach((value, col) => {
                if (!value) {
                    return;
                }
                const key = `${row},${col}`;
                const tile = this.createTile(value, row, col);
                if (appear || key === newTile) {
                    tile.classList.add("tile-new");
                } else if (merged.has(key)) {
                    tile.classList.add("tile-merged");
                }
                this.tileElements.set(key, tile);
                tiles.push(tile);
            });
        });
        this.el.tiles.replaceChildren(...tiles);
    }

    /**
     * Desliza cada ficha desde su celda de origen hasta su destino (BUG-12: antes
     * no había deslizamiento y toda ficha movida "aparecía" como si fuera nueva).
     */
    animateSlide(tileMoves) {
        if (!tileMoves || tileMoves.length === 0 || prefersReducedMotion()) {
            return Promise.resolve();
        }
        tileMoves.forEach(({ from, to }) => {
            const tile = this.tileElements.get(`${from[0]},${from[1]}`);
            if (tile) {
                tile.style.setProperty("--row", to[0]);
                tile.style.setProperty("--col", to[1]);
            }
        });
        return new Promise((resolve) => setTimeout(resolve, SLIDE_DURATION_MS));
    }

    updateScores(state, move) {
        this.el.score.textContent = state.score.toLocaleString("es-CO");
        this.el.best.textContent = state.highscore.toLocaleString("es-CO");
        if (move && move.points > 0) {
            this.showScoreBubble(move.points);
        }
    }

    showScoreBubble(points) {
        const bubble = document.createElement("span");
        bubble.className = "score-bubble";
        bubble.textContent = `+${points}`;
        this.el.bubbles.appendChild(bubble);
        setTimeout(() => bubble.remove(), SCORE_BUBBLE_MS);
    }

    playMoveSound(data) {
        const mergedValue = highestMergedValue(data.grid, data.merged_cells);
        if (mergedValue > 0) {
            this.sound.playMerge(mergedValue);
        } else {
            this.sound.playMove();
        }
    }

    // --- Diálogos y anuncios -------------------------------------------------------

    /** Muestra u oculta los diálogos de victoria y fin, y anuncia los cambios. */
    updateDialogs(previousStatus, state, firstLoad) {
        this.el.finalScore.textContent = state.score.toLocaleString("es-CO");
        // Sin historial (p. ej., tras recargar la página) no hay jugada que deshacer.
        document.getElementById("btn-over-undo").disabled = !state.can_undo;
        this.toggleModal("win", state.status === "won");
        this.toggleModal("over", state.status === "game_over");
        // BUG-14: sonido y anuncio solo al ENTRAR en el estado, nunca al recargar.
        const transition = firstLoad ? null : statusTransition(previousStatus, state.status);
        if (transition === "won") {
            this.sound.playWin();
            this.announce("¡Felicitaciones! Alcanzaste la ficha 2048.");
        } else if (transition === "game_over") {
            this.sound.playGameOver();
            this.announce(`Fin de la partida. Puntuación final: ${state.score}.`);
        }
    }

    openModalName() {
        return Object.keys(this.modals).find((name) => !this.modals[name].classList.contains("hidden"));
    }

    toggleModal(name, open) {
        const modal = this.modals[name];
        const isOpen = !modal.classList.contains("hidden");
        if (open === isOpen) {
            return;
        }
        if (open) {
            this.focusBeforeModal = document.activeElement;
            modal.classList.remove("hidden");
            modal.querySelector("button").focus();
        } else {
            modal.classList.add("hidden");
            if (this.focusBeforeModal && document.contains(this.focusBeforeModal)) {
                this.focusBeforeModal.focus();
            }
        }
    }

    /** Escape cierra la confirmación y Tab no sale del diálogo abierto. */
    handleModalKey(event, name) {
        if (event.key === "Escape" && name === "confirm") {
            this.toggleModal("confirm", false);
            return;
        }
        if (event.key !== "Tab") {
            return;
        }
        const buttons = Array.from(this.modals[name].querySelectorAll("button"));
        const index = buttons.indexOf(document.activeElement);
        const step = event.shiftKey ? -1 : 1;
        event.preventDefault();
        buttons[(index + step + buttons.length) % buttons.length].focus();
    }

    announce(message) {
        this.el.announcer.textContent = message;
    }

    announceMove(direction, data) {
        const points = data.points > 0 ? ` Ganaste ${data.points} puntos.` : "";
        this.announce(`Movimiento ${DIRECTION_PHRASES[direction]}.${points} `
            + `Puntuación: ${data.score}. Ficha mayor: ${data.max_tile}.`);
    }

    showToast(message) {
        this.el.toast.textContent = message;
        this.el.toast.classList.remove("hidden");
    }

    hideToast() {
        this.el.toast.classList.add("hidden");
    }

    // --- Entradas: teclado, botones y gestos ------------------------------------

    setupKeyboard() {
        window.addEventListener("keydown", (event) => {
            const modalName = this.openModalName();
            if (modalName) {
                this.handleModalKey(event, modalName);
                return;
            }
            const action = actionForKey(event);
            if (!action) {
                return;
            }
            event.preventDefault(); // Las flechas no deben desplazar la página.
            if (action.type === "move") {
                this.move(action.direction);
            } else if (action.type === "undo") {
                this.undo();
            } else if (action.type === "reset") {
                this.requestReset();
            }
        });
    }

    setupButtons() {
        const onClick = (id, handler) => document.getElementById(id).addEventListener("click", handler);
        onClick("btn-undo", () => this.undo());
        onClick("btn-restart", () => this.requestReset());
        onClick("btn-continue", () => this.continuePlaying());
        onClick("btn-win-restart", () => this.reset());
        onClick("btn-over-restart", () => this.reset());
        onClick("btn-over-undo", () => this.undo());
        onClick("btn-confirm-restart", () => this.reset());
        onClick("btn-cancel-restart", () => this.toggleModal("confirm", false));
        onClick("btn-sound", () => {
            this.sound.toggle();
            this.updateSoundButton();
        });
        onClick("btn-theme", () => {
            const current = document.documentElement.getAttribute("data-theme");
            const next = current === "dark" ? "light" : "dark";
            preferences.set("2048_theme", next);
            this.applyTheme(next);
        });
        document.querySelectorAll(".dpad-btn").forEach((button) => {
            button.addEventListener("click", () => this.move(button.dataset.dir));
        });
    }

    setupTouch() {
        let startX = 0;
        let startY = 0;
        this.el.board.addEventListener("touchstart", (event) => {
            startX = event.changedTouches[0].clientX;
            startY = event.changedTouches[0].clientY;
        }, { passive: true });
        this.el.board.addEventListener("touchend", (event) => {
            const touch = event.changedTouches[0];
            const direction = swipeDirection(touch.clientX - startX, touch.clientY - startY,
                SWIPE_THRESHOLD_PX);
            if (direction) {
                this.move(direction);
            }
        }, { passive: true });
    }

    // --- Preferencias visuales ------------------------------------------------------

    savedTheme() {
        const systemTheme = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
        return preferences.get("2048_theme", systemTheme);
    }

    applyTheme(theme) {
        const dark = theme === "dark";
        document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
        this.el.themeButton.setAttribute("aria-pressed", String(dark));
        document.getElementById("icon-moon").classList.toggle("hidden", !dark);
        document.getElementById("icon-sun").classList.toggle("hidden", dark);
    }

    updateSoundButton() {
        const enabled = this.sound.enabled;
        this.el.soundButton.setAttribute("aria-pressed", String(enabled));
        document.getElementById("icon-sound-on").classList.toggle("hidden", !enabled);
        document.getElementById("icon-sound-off").classList.toggle("hidden", enabled);
    }
}

// Los scripts usan "defer": el DOM ya está listo cuando se ejecuta esta línea.
window.gameClient = new GameClient();
